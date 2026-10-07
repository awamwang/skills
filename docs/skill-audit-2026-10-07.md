# awam-skills Skill 安全 / 质量审查与优化清单

- **审查日期**：2026-10-07
- **审查范围**：`skills/awam-skills/`（SKILL.md + references/ + scripts/ + templates/）
- **审查者**：AI Engineer Expert
- **审查方法**：静态阅读全部 1+4+9+2 = 16 个文件，未运行任何脚本
- **整体结论**：无 RCE / 提权级硬伤；凭据不入库、`--no-input`、代理剥离、`json.loads` 自校验等基础防护已到位。仍有若干脱敏 / 超时 / 路径校验 / 文档示范的安全收口点。

---

## 风险等级图例

| 级别 | 含义 | 处置建议 |
|------|------|----------|
| 🔴 P1 | 高优先级，可能直接或间接泄露凭据 / 触发任意执行 | 必修 |
| 🟡 P2 | 中优先级，质量或边界 case 风险 | 建议修 |
| 🟢 P3 | 细节优化 | 视情况 |
| 🧠 结构性 | 体验 / 重构，非安全 | 单独评估 |

---

## 🔴 P1 — 高优先级（6 项）

### 1. 错误响应体直接入日志
- **位置**：`scripts/publish_modelscope.py`（`http_json` / 新增 `sanitize_body`）
- **问题**：`raise SystemExit(f"HTTP {e.code} {url}\n{raw[:800]}")` 将服务端响应体最多 800 字节打到日志。响应体在某些 4xx / 5xx 路径下可能含服务端回显的请求头（`Authorization`、`Cookie`、上传时的 boundary 等），间接泄露凭据。
- **修复**：新增 `sanitize_body()`，按「Authorization 键 → 其它凭据键 → 前缀字面量 → Bearer/Basic → URL query」五级顺序脱敏后再截断；三处 `raw[:N]` 全部改走它。用户中心那条「AccessToken 错误」的官方报错文案经实测**不受影响**（不含凭据值）。
- **状态**：✅ done（2026-10-07）

### 2. `mask()` 脱敏不足
- **位置**：`scripts/credentials.py`（`mask`）
- **问题**：原实现 `f"{token[:8]}…({len(token)} 位)"`，前 8 位对 `ms_`/`ghp_`/`sk-` 这类可预测前缀几乎等同明文。
- **修复**：改为「首尾各 4 位」`f"{token[:4]}…{token[-4:]}({n} 位)"`；长度 < 12 只留长度（`…(N 位，已隐去)`）。实测 `ms-b…f697(39 位)`。
- **状态**：✅ done（2026-10-07）

### 3. `CLAWHUB_BIN` 路径未校验
- **位置**：`scripts/publish_clawhub.py`（新增 `_looks_like_clawhub`，`find_clawhub` 调用）
- **问题**：环境变量指向任意路径都被无校验执行，被污染时可执行任意二进制。
- **修复**：新增 `_looks_like_clawhub()` 三重确认（文件名以 `clawhub` 开头 / 路径含 `clawhub` 目录段 / `.js` 入口）。实测 11 例全部符合预期：放行 `clawhub.cmd`、`bin/clawdhub.js` 等，拒绝 `mimikatz.exe`、`calc.exe`、`bash`、`random.js`；本机真实安装的 `clawhub.cmd` 仍正常解析。另对 POSIX 非 `.js` 目标补了可执行位检查。
- **状态**：✅ done（2026-10-07）

### 4. GitHub API 请求无超时
- **位置**：`scripts/query_skills.py`（新增 `HTTP_TIMEOUT = 30`，`gh_request` / `gh_paginate`）
- **问题**：`urllib.request.urlopen(req)` 未传 `timeout`，网络挂死时调用方一直等。
- **修复**：两个函数加 `timeout: int = HTTP_TIMEOUT` 形参并传入 `urlopen`；分页场景每页独立计超时；`gh_request` 补 `URLError` 分支把超时转成可读报错。
- **状态**：✅ done（2026-10-07）

### 5. 文档示例直接把 token 写进 curl header
- **位置**：`references/platforms.md`（LobeHub 踩坑段）
- **问题**：`curl -H "Authorization: Bearer <token>"` 易被复制粘贴，token 落 shell history / 终端日志。
- **修复**：示例改为 `read -rs LOBEHUB_TOKEN` 交互读取 → `-H "Authorization: Bearer $LOBEHUB_TOKEN"` → `unset`；并明确标注「只有 `<identifier>` / `<技能目录>` 是需替换的占位符，切勿粘贴明文 token」。同页鉴权说明同步改为「只经环境变量传递，用完即 unset」。
- **状态**：✅ done（2026-10-07）

### 6. 凭据文件兜底路径仅靠 gitignore 防护
- **位置**：`scripts/credentials.py`（新增 `_repo_local_allowed`，`candidate_paths` 调用）
- **问题**：候选路径含索引仓内 `.credentials.local.json`，若 gitignore 被删 / fork 仓不带 gitignore，凭据会静默入库。
- **修复**：新增 `_repo_local_allowed()` —— 仅当索引仓 `.gitignore` 存在且确实覆盖 `.credentials.local.json`（或 `*.credentials.json`）时才把该路径加入候选；否则**剔除并告警**（去重，只报一次）。实测四种情形（未覆盖 / 精确名 / 通配 / 缺 gitignore）全部符合预期。附带 P3#16 的 POSIX 权限检查（`_check_file_perms`）已一并落地。
- **状态**：✅ done（2026-10-07）

---

## 🟡 P2 — 中优先级（6 项）

### 7. 打包用黑名单而非白名单
- **位置**：`scripts/public_files.py`（新增 `whitelist_dirs` / `whitelist_blocks`）
- **问题**：原黑名单模型下，新增意外目录（`.secrets/`、`.credentials/`、`.local/`）会被打进发布包。
- **修复**：新增**可选**顶层目录白名单——设置 `AWAM_PACK_WHITELIST_DIRS=references,scripts,templates,...` 后，只有这些顶层目录（+ 打包根直属文件如 SKILL.md）进入发布集。**默认关闭**，理由：技能仓可自带任意目录（`assets/`、`evals/`），一上来就白名单会误伤合法内容；这是给「敏感技能」的加固开关。值 `*`/`all` 等同关闭。实测：白名单模式正确剔除 `docs`、`.workbuddy`。
- **状态**：✅ done（2026-10-07，opt-in 版）

### 8. 发布前未做敏感串扫描
- **位置**：新增 `scripts/preflight_secrets.py`；三发布脚本在打包前调用
- **问题**：误把含 `sk-` / `ghp_` / `AKIA` / 私钥块 的内容传上公开平台是**不可逆**事故。
- **修复**：新增 `preflight_secrets.py`，三层规则——① 文件名（`.env*`/`*.pem`/`*.key`/`*credential*`/`*secret*` 等）；② 内容正则（私钥块、`ghp_`/`gho_`/`ghs_`/`github_pat_`/`sk-`/`AKIA`/`ms-`/Stripe/Slack/Google/JWT/数据库连接串/凭据赋值）；③ 豁免标记 `# awam-allow-secret`。
  - 集成：`publish_modelscope`/`publish_doubao` 在 `build_zip` 内扫；`publish_clawhub` 在导出 staging 后扫（新增 `scan_staging`）。三脚本均加 `--skip-secret-scan` 逃生阀。
  - 也可独立跑：`python scripts/preflight_secrets.py --dir <技能仓>`（命中 exit 1）。
  - **踩坑**：初版文件名规则把 `credentials.py`（凭据**处理**模块本身）误拦了——加 `EXEMPT_NAMES` 豁免源码文件名，内容扫描仍生效。
  - 实测：真技能扫描通过；埋 `ghp_` 的 fixture 被拦（exit 1）；加豁免标记后放行；`notes.md` 内嵌凭据也能按内容拦下。
- **状态**：✅ done（2026-10-07）

### 9. `plan_store.py` 用正则做 JSON 篡改
- **位置**：`scripts/plan_store.py`
- **问题**：原文用「定位扫描器 + 一处正则替换值 + 字符串拼接插键」，仍属文本级操作；写盘非原子。
- **修复**：重构为**对象级 + 块级重写**——① `json.loads` 后直接在 dict 上改 `status.<platform>`（值正确性由对象操作保证，彻底去掉正则替换与手写拼接）；② 复用括号配对扫描器定位技能块，只重生成块内 `status` 那一行（统一紧凑格式 `{ "k": "v", ... }`，每平台一行）；③ 其余所有行原样保留；④ 写盘改**原子写**（temp + `os.replace`），消除中途崩溃截断风险。**逐字节保排版已放弃**（用户确认展示清晰即可，风格可统一）。
- **实测**：真文件改动恰好 1 行、行数守恒、幂等；缺键新增 / 多行 status 压缩回单行 / 不存在技能 / 非法 JSON / 全技能连续改 共 6 用例通过；三发布脚本 `update_plan` 集成（doubao/clawhub/modelscope）端到端跑通，3 次调用仅 2 行变化（1 次为幂等 no-op）。
- **状态**：✅ done（2026-10-07）

### 10. `setup_env.py --mirror` 不校验 URL scheme
- **位置**：`scripts/setup_env.py`（新增 `validate_mirror` / `TRUSTED_MIRROR_HOSTS`）
- **问题**：`--mirror` 原样进 `pip install -i <url>`，http / 投毒镜像可污染环境。
- **修复**：新增 `validate_mirror()` —— 必须 `https`，且主机在可信白名单（pypi.org / 清华 / 阿里 / 腾讯 / 中科大 / 华为）。实测 6 例全符合预期，含「前缀伪装域」`evil-pypi.tuna.tsinghua.edu.cn.attacker.com` 被正确拒绝。
- **状态**：✅ done（2026-10-07）

### 11. `publish_doubao.py` 刷新视图失败静默
- **位置**：`scripts/publish_doubao.py`（新增 `refresh_view`）
- **问题**：原 `subprocess.run(...)` 不看 returncode，刷新失败时用户以为成功。
- **修复**：抽出 `refresh_view()`，捕获 `OSError`/`SubprocessError` 与 returncode != 0 并打印 `exit=` 与 stderr；与 `publish_modelscope` 实现对齐。
- **状态**：✅ done（2026-10-07）

### 12. 仓库根缺 `.gitignore`
- **位置**：新增 `skills/awam-skills/.gitignore`
- **问题**：`scripts/__pycache__/` 已在工作树中被看到；未来 `.cache/`、`*.log`、发布 zip 也可能进仓。
- **修复**：新增该 Skill 自己的 `.gitignore`，覆盖 `__pycache__/`、`*.py[cod]`、`.cache/`、`.workbuddy/`、`*-doubao.zip`、凭据文件双保险等。（注意与 `templates/gitignore` 区分——后者是给「被创建的技能仓」用的。）
- **状态**：✅ done（2026-10-07）

---

## 🟢 P3 — 细节优化（6 项）

### 13. `--dir` 不校验来源
- **位置**：所有 publish 脚本（新增 `credentials.source_guard`）
- **问题**：未校验传入目录是否 git 仓 / origin 是否指向 `awam-skills` 组织。误传个人仓会发到组织平台。
- **修复**：`credentials.py` 新增 `source_guard()` + `git_remote_repo()`（后者从 `publish_clawhub` 抽上来复用）。受信来源为 `awam-skills/` **与** `awamwang/`（实测 `wiz-migration`、索引仓自身走个人仓 `awamwang`，只认组织会误伤合法发布）。三发布脚本在打包前调用，命中即中止并提示 `--allow-foreign-repo` 逃生阀。实测：`awam-skills/*` 与 `awamwang/*` 全部放行，陌生仓 `evil/foo` 与非 git 目录被拦。
- **状态**：✅ done（2026-10-07）

### 14. JSON 输出间接泄露主机目录结构
- **位置**：`scripts/query_skills.py`（新增 `_mask_host_path` / `mask_json_payload`）
- **问题**：JSON 输出含本机 junction target 路径（`\\?\G:\Projects\...`），间接泄露主机目录结构。
- **修复**：仅 JSON 模式脱敏（markdown 保留以便调试）——① 去 `\\?\` 长路径前缀；② home 内 → `~/...`；③ 其它盘符绝对路径 → `G:/…/<末段>`（隐藏中间层级）。覆盖 `meta.index_root/local_dir`、`local[].path_or_url`、`local[].extra.target`、`compare[].local_path`。实测 `\\?\G:\Projects\19AI\skills\awam` → `G:/…/awam`。
- **状态**：✅ done（2026-10-07）

### 15. `--show-credentials` 入口分散
- **位置**：`credentials.py` 新增 `show()` + `__main__`；三发布脚本统一
- **问题**：凭据排查入口不一致（只有 modelscope 有）。
- **修复**：`credentials.py` 提供 `show(platform)` 与 `python -m credentials <platform> [--paths]` 统一入口；clawhub / doubao 补齐 `--show-credentials` 并委托给 `creds.show`。三脚本 `--dir` 改为非必填（`--show-credentials` 不再强制要 `--dir`）。
- **状态**：✅ done（2026-10-07）

### 16. 凭据文件权限未校验
- **位置**：`scripts/credentials.py`（`_check_file_perms`，P1 阶段随 #6 一并落地）
- **问题**：POSIX 下凭据文件 mode 若非 0600 不会 warn，组 / 其它用户可读。
- **修复**：`_check_file_perms()` —— 仅 POSIX（Windows 跳过），`stat.S_IMODE` 有 0o077 位即告警建议 `chmod 600`；在 `load()` 的显式文件与候选路径两处调用，`_warn_once` 去重。
- **状态**：✅ done（2026-10-07，随 P1 落地）

### 17. `npx -y @lobehub/market-cli` 未锁版本
- **位置**：`references/platforms.md`
- **问题**：每次拉 latest，npm 投毒（包被劫持）时直接执行恶意代码。
- **修复**：全部 5 处 `@lobehub/market-cli` 固定为 `@0.0.41`（与文内「踩坑 0.0.41」一致），并加版本锁定说明（升级前先 `npm view ... version` 核对 integrity）。
- **状态**：✅ done（2026-10-07）

### 18. `plan_skills.py` 的 `updated` 字段无格式校验
- **位置**：`scripts/plan_skills.py`（新增 `_normalize_updated`）
- **问题**：`updated` 直接拼到 markdown，脏值会原样渲染（如「更新：今天」）。
- **修复**：新增 `_normalize_updated()` —— 合法 ISO 日期/时间规范显示（带时区转 UTC），否则回退文件 mtime 并标注「（取自文件修改时间）」。`render()` 增加 `plan_path` 形参。实测 6 例：`2026-10-07T17:00:00`→`2026-10-07 17:00`、`今天`/空串→mtime 兜底、`Z` 后缀→`… UTC`。
- **状态**：✅ done（2026-10-07）

---

## 🧠 结构性优化（非安全，4 项）

### A. 集中超时常量
- 各脚本 `subprocess.run` 的 timeout 散落（60/120/300/600 不等），建议抽到 `scripts/constants.py`。
- **状态**：☐ pending

### B. dry-run 通道自检统一
- `publish_modelscope.py:155-169` 已实现 `check_channel()`，`publish_clawhub.py` 可加同款（自动检测 CLI 是否在 PATH / 是否登录态）。
- **状态**：☐ pending

### C. preflight check
- 发布前自动跑 `query_skills.py`，确认技能已进 `awam-skills` 组织 + 已在 `skills.overrides.json`，否则中止发布。
- **状态**：☐ pending

### D. setup_env.py 默认强 venv 隔离
- 当前直接 `pip install`，污染用户 PYTHONPATH（虽 SKILL 说幂等）。建议默认建 `.venv` 在索引仓 `tools/` 下，`--check` 不创建。
- **状态**：☐ pending

### E. 凭据加载时打印文件 mode / owner 警告
- 与 #16 互补，POSIX 下打印 owner uid 与 mode 帮助快速定位配置失误。
- **状态**：☐ pending

---

## 推荐处置路径

1. **第一批（建议立即修）**：P1 全部 6 项——凭据脱敏 + 超时 + 路径校验 + 文档修正 + gitignore 兜底。改动小、风险高、收益最大。
2. **第二批（下一次发布窗口）**：P2 的 #7（白名单打包）、#8（敏感串扫描）、#11（错误处理补齐）、#12（仓库根 gitignore）、#9（plan_store 对象级重构）。
3. **第三批（质量收口）**：P3 6 项 + 结构性 A/B/C/D/E 按需排期。

---

## 变更追溯

| 日期 | 操作 | 改动项 | 备注 |
|------|------|--------|------|
| 2026-10-07 | 创建 | 全文 | 初次审查记录 |
| 2026-10-07 | 修复 | P1 #1–#6 | 6 项全部落地；顺带完成 P3 #16 的 POSIX 权限告警。改动文件：`scripts/credentials.py`、`scripts/publish_modelscope.py`、`scripts/publish_clawhub.py`、`scripts/query_skills.py`、`references/platforms.md`。已验证：4 脚本 `py_compile` 通过；mask / 脱敏 / CLAWHUB_BIN 校验 / gitignore 守卫 均单测通过；`--show-credentials`、`query_skills.py`、两个 `--dry-run`、`preflight.py` 端到端跑通 |
| 2026-10-07 | 提交 | P1 全部 | 拆两个 commit：`fix(skills): 收紧发布脚本的凭据脱敏与外部命令校验`、`docs(skills): 修正平台凭据示例并补充脱敏与守卫说明`（均未 push） |
| 2026-10-07 | 修复 | P2 #7 #8 #10 #11 #12 + P3 #18 | 5 项 P2 落地 + 顺带完成 P3 #18。新增 `scripts/preflight_secrets.py`、`skills/awam-skills/.gitignore`；改 `public_files.py`（白名单 opt-in）、`setup_env.py`（mirror 校验）、`publish_doubao.py`（refresh_view）、三发布脚本（接入敏感串扫描 + `--skip-secret-scan`）、`plan_skills.py`（updated 校验）。已验证：10 脚本 `py_compile` 通过；mirror 校验 6 例、updated 6 例、扫描器拦截/豁免、白名单开关 全部单测通过；三个发布脚本 `--dry-run` + `preflight_secrets.py` 端到端跑通。**#9（plan_store 重构）本轮未动**，单独评估 |
| 2026-10-07 | 重构 | P2 #9 | `plan_store.py` 改为对象级 + 块级重写：dict 层改值（去正则）、只重写 `status` 一行、原子写。逐字节保排版约束经用户确认放弃（展示清晰即可、风格可统一）。已验证：6 边界用例 + 三发布脚本 `update_plan` 集成全通过，真文件改动 1 行、行数守恒、幂等 |
| 2026-10-07 | 修复 | P3 #13 #14 #15 #17 | 4 项 P3 收口。① #13 `credentials.source_guard` + `git_remote_repo`，受信来源 `awam-skills/`+`awamwang/`（实测 wiz-migration 走个人仓，只认组织会误伤），三脚本打包前校验 + `--allow-foreign-repo` 逃生阀；② #14 `query_skills` JSON 脱敏（去 `\\?\`、home→`~/`、盘符绝对路径→`G:/…/末段`），markdown 保留；③ #15 `credentials.show` + `python -m credentials`，clawhub/doubao 补齐 `--show-credentials`，三脚本 `--dir` 改非必填；④ #17 文档 5 处 market-cli 锁 `@0.0.41`。已验证：11 脚本 py_compile；source_guard 真实来源/陌生仓/非 git 三态、mask 多态、三脚本 show-credentials、doubao 打包 + clawhub dry-run、query_skills JSON 端到端全通过 |