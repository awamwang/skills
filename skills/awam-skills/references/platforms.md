# 平台发布（platforms）

把 `awam-skills` 组织下已公开的技能发布到第三方技能平台，并同步发布规划。

> 平台命令 / 接口以各平台**官方文档为最新权威**；本页给出当前公开流程、入口与**实测踩坑**（截至 2026-10，已实测发布 `ssh-deploy-skill`：魔搭、LobeHub、豆包导入包；`quicker-connector`：魔搭 **SDK 通道** + ClawHub + 豆包导入包）。账号注册、登录与付费由用户完成，本 Skill 不代为处理。

## 通用前置

- 技能仓已在 GitHub `awam-skills` 公开且含 `SKILL.md`（嵌套则 `skills/<name>/SKILL.md`）。
- 文件统一 **UTF-8（无 BOM）**；`SKILL.md` 建议 **LF 行尾**（Windows 复制常残留 CRLF，会触发魔搭解析错误，见下方踩坑）。
- `SKILL.md` frontmatter 齐备：`name` / `version`（创建模板默认 `0.0.1`）/ `description`；发魔搭 / LobeHub 前按 semver 提升 `version`（初始值可取自技能 `_meta.json`）。
- 用户已在该平台注册 / 登录 / 开通（涉及付费需用户确认）。

## 平台清单

| 平台 | 区域 | 发布通道 | 前置 | 适合技能 |
|------|------|----------|------|----------|
| **LobeHub** | 国际 | SKILL.md bundle + CLI `npx -y @lobehub/market-cli` | 账号 + 网页提交仓库 | 跨 agent 通用型（ssh-deploy、awam-git、github-organize） |
| **魔搭 ModelScope** | 国内 | [publish_modelscope.py](../scripts/publish_modelscope.py)（zip→file_id→创建） | 账号 + `MODELSCOPE_API_TOKEN` | 通用与运维技能均合适 |
| **豆包技能中心** | 国内 | [publish_doubao.py](../scripts/publish_doubao.py) 打包 + 客户端导入 | 豆包客户端 | 个人工作流与通用技能；成本最低 |
| **ClawHub** | 国际 | [publish_clawhub.py](../scripts/publish_clawhub.py)（封装 `clawhub` CLI） | npm 包 `clawhub` + 设备流登录 | OpenClaw 生态技能（quicker-connector） |
| **AgentPowers** | 国际 | MCP 标准提交（8 层安全扫描） | 账号 / 后台 | 高品质 / 付费向（windows-autostart、letsencrypt 等） |

## 凭据管理（通用）

发布脚本**不要求每次手填 token**——由 [scripts/credentials.py](../scripts/credentials.py) 统一查找，
查找顺序固定为：**命令行 > 环境变量 > 用户级配置 > 仓内 `.local` 配置**：

| 顺序 | 来源 | 示例 |
|---|---|---|
| 1 | 命令行参数 | `--token` / `--owner` |
| 2 | 环境变量 | `MODELSCOPE_API_TOKEN` / `MODELSCOPE_OWNER` |
| 3 | `<PLATFORM>_CREDENTIALS` 指向的文件 | `MODELSCOPE_CREDENTIALS=/path/cred.json` |
| 4 | **用户级配置（推荐落点）** | `~/.workbuddy/secrets/modelscope.json` |
| 5 | 用户级统一配置 | `~/.config/awam-skills/credentials.json`（`platforms.<platform>` 段） |
| 6 | 仓内本地配置 | 索引仓 `.credentials.local.json`（已 gitignore） |

- **推荐落点是 `~/.workbuddy/secrets/<platform>.json`**：该目录不在任何 git 仓库内，天然不会被提交。
- 配置格式（平台专属文件）：`{"owner": "<用户名>", "api_key": "...", "sdk_token": "..."}`；
  token 字段按 `token > api_key > sdk_token > access_token` 取第一个非空值。
  统一文件则写在 `platforms.<platform>` 段下。
- 排查：`python scripts/publish_modelscope.py --dir <技能仓> --show-credentials`
  只打印**来源路径与脱敏 token**（前 8 位 + 长度），不打印明文。
- 铁律：token 不入库、不进日志；脚本日志只输出来源路径。

## 各平台发布步骤

### LobeHub（已实测）

**identifier 必须是 `owner-repo` 格式**（GitHub `owner/repo` 把 `/` 换成 `-`，如 `awam-skills-ssh-deploy-skill`），**不是**裸 repo 名——裸名和错误 owner 都会导致 claim "Skill not found"。

1. **前置：网页提交仓库（必须，CLI 无法代做）。** 技能仓库公开后，用户打开 LobeHub 创作者主页（官方指引 `lobehub.com/zh/docs/usage/community/become-a-creator`）→「技能」区域 →「提交仓库」→ 选择该 GitHub 仓库。提交后技能进入 marketplace，CLI 才能认领。
2. 连接 GitHub：`npx -y @lobehub/market-cli github connect`；`github status` 应显示 `✓ GitHub connected`。
3. 认领：`npx -y @lobehub/market-cli skill claim <owner-repo>`。已拥有时返回 "You already own this skill"（正常，跳过即可）。
4. 发布：`npx -y @lobehub/market-cli skill publish --dir <技能目录> --identifier <owner-repo>`。

**踩坑（market-cli 0.0.41）：** `skill publish` 会复用 `skill list` 的共享请求头，把 `Content-Type` 设成 `application/json`（而非 `multipart/form-data`），服务端报 `Failed to parse form data`。**绕过方式**——用 curl 手动发送 multipart：

```bash
curl -X POST "https://market.lobehub.com/api/v1/user/skills/<identifier>/versions" \
  -H "Authorization: Bearer <token>" \
  -F "file=@<技能目录>.zip;type=application/zip;filename=<identifier>.zip"
```

- zip 打包规则与 CLI 一致：`SKILL.md` 在 zip 根，跳过 `.` / `node_modules` / `__pycache__`；frontmatter `name` / `version` / `description` 即可，`name` 小写 kebab 且与目录名一致。
- 鉴权 token 取 CLI 本地已存的 user token（调试日志可见 `Authorization: Bearer ...`）；仅走环境变量，用完即清。
- 验证：`lhm skill list`（status 应为 `published`）；marketplace 页 `market.lobehub.com/s/<identifier>`。

### 魔搭 ModelScope（已实测）

**优先走官方 SDK**（与魔搭上的 `modelscope-skill-upload` 技能同一套流程）：
打包 zip → 上传拿 file_id → 创建 Skill → 验证。

#### 前置：装 SDK（一次性）

```bash
python skills/awam-skills/scripts/setup_env.py            # 幂等；已装则跳过
python skills/awam-skills/scripts/setup_env.py --check    # 只检测
```

装的是 `modelscope` + **`modelscope_hub`**（1.40 起 hub 客户端已拆成独立包，
skill 上传能力在后者）。两者都用 `--no-deps` 装，避免被拖入 torch；
再显式补齐真正需要的 `requests`/`idna`/`charset-normalizer`/`certifi`/
`urllib3`/`packaging`/`tqdm`/`addict`/`filelock`/`setuptools`/`cryptography`。

#### 发布

```bash
python skills/awam-skills/scripts/publish_modelscope.py --dir <技能仓>            # 凭据自动查找
python skills/awam-skills/scripts/publish_modelscope.py --dir <技能仓> --dry-run  # 打包校验 + 通道自检
```

`--via auto|sdk|openapi`（默认 auto，优先 SDK）：

| 通道 | 实现 | 依赖 |
|---|---|---|
| `sdk` | `modelscope_hub`：`upload_file_to_openapi()` → `create_repo(repo_type="skill")`（内部 `POST /skills`，payload 用 `skill_file`） | 需 setup_env |
| `openapi` | 裸 HTTP：`POST /files/upload` → `POST /skills` | 仅标准库 |

**两条通道用的是同一个 AccessToken**；SDK 只是把 token 同时放进
`Authorization: Bearer` 与 cookie（`m_session_id` / `modelscope_session`）。

1. 打包：zip **根目录必须恰好 1 个 `SKILL.md`**，frontmatter 含 `name` / `version` / `description`，zip ≤5MB。
2. 上传：`POST https://modelscope.cn/openapi/v1/files/upload`（multipart 字段 `file`）→ 取 `data.id` 作 file_id。
3. 创建：`POST /skills`（body 含 file_id、display_name、license、category 等）；重复创建报 **409 DuplicateEntity**。
4. 验证：`GET /openapi/v1/skills/<owner>/<name>`（**详情接口最可靠**，带 `Authorization: Bearer <token>` 返回 `{"success": true, "data": {...}}`，含 `license` / `category` / `tags` / `last_modified` / `install_command`）。
   ⚠ 实测（2026-10-07，quicker-connector 经 SDK 通道发布成功）：`GET /openapi/v1/skills?filter.owner=<owner>` **返回 total 0**，发布成功也一样 —— 列表接口不可用，**别用列表判定成功与否**；另外列表不带 token 也返回 200，更不能当鉴权判据。SDK 通道以 `create_repo` 返回的 `id` 为准，再用上面的详情接口复核。

**踩坑：** SKILL.md 为 **CRLF 行尾**时上传报 `UploadedFileInvalid: must contain 'name' field`（实际是行尾问题）——必须转 LF，Windows 下用 `write_bytes` / 二进制写回，防止 `\r\n` 被重新引入。
- 鉴权：`Authorization: Bearer <token>`（SDK 通道同时带 cookie）。
- **token 获取：<https://modelscope.cn/my/myaccesstoken>**（用户中心 → AccessToken）。
  凭据文件里填 `api_key`（或 `sdk_token`，两者都会被采用）。
- **坑：token 失效的报错长什么样。** 服务端会明确回
  `[400] 登录失败，AccessToken错误，请从用户中心获取AccessToken或刷新`（`code=10010103009`，SDK `login()` 的判断最权威）；
  或裸 HTTP 下报 `401 InvalidAuthentication: user not authenticated`。
  注意**列表接口不带 token 也返回 200**，别把「列表能通」当成「token 有效」。
  出现上述报错时不要去改代码，直接去用户中心刷新 token。
- 请求**必须强制直连**：本机 `HTTPS_PROXY` 对魔搭（国内站）的 HTTPS 隧道会返回 502，脚本已用
  `ProxyHandler({})` 绕过；自己写请求时同理。

### 豆包技能中心（已实测导入包）

- 导入格式：**文件夹或 zip 内含 `SKILL.md` 即可**，名称须与技能同名；打包 zip 时**顶层为技能同名文件夹**。
- 入口：豆包电脑版侧边栏「技能·连接器·伙伴」→ 我的技能 → 新建 → 上传技能（拖入文件夹 / zip）。
- 个人工作流与通用技能，接入成本最低。
- **无公开上传 API**，只能客户端导入。用 [scripts/publish_doubao.py](../scripts/publish_doubao.py) 打包并打印步骤，导入成功后加 `--mark-done` 更新规划：

```bash
python skills/awam-skills/scripts/publish_doubao.py --dir <技能仓> [--out <zip>]
python skills/awam-skills/scripts/publish_doubao.py --dir <技能仓> --mark-done   # 导入成功后
```

### ClawHub（OpenClaw，已实测 2026-10-06：quicker-connector 1.2.0 → 1.5.0）

**一键脚本（推荐）**：[scripts/publish_clawhub.py](../scripts/publish_clawhub.py) 已封装下列全部踩坑（干净目录、去代理、`--no-input`、发后刷新规划）：

```bash
export CLAWHUB_BIN=<clawhub.cmd 或 dist/cli.js 路径>   # 不在 PATH 时必填
python skills/awam-skills/scripts/publish_clawhub.py --dir <技能仓> --dry-run   # 预览
python skills/awam-skills/scripts/publish_clawhub.py --dir <技能仓>             # 发布 + 刷新规划
```

手敲命令时的要点：

1. **CLI 是 npm 无作用域包 `clawhub`**（v0.23.3，作者 steipete）。`@clawhub/cli` 只有 0.0.2，是占位包，**不要用**。
2. **必须带 `--no-input`**。缺了它，遇到「同 slug 已存在，是否更新」的交互确认会**静默挂死**——无输出、只能靠超时杀掉（`EXIT=124`），极易误判为网络问题。
3. **代理会让发布 502**：本机 `HTTPS_PROXY` 对 registry 的 HTTPS 隧道返回 `Proxy response (502) !== 200 when HTTP Tunneling`，而直连正常。发布时剥离代理：
   `env -u HTTPS_PROXY -u https_proxy -u HTTP_PROXY -u http_proxy NO_PROXY='*' clawhub ...`（脚本已内置）。
4. **登录走设备流**：`clawhub login --device --no-browser`。后台进程不会自动开浏览器，需人工打开 CLI 打印的 `https://clawhub.ai/cli/device?user_code=XXXX` 并确认；code 15 分钟有效。轮询报 `Device flow error: true` 时重开一个即可（旧的会作废）。dry-run **免登录**。
5. **已存在的 slug 就是版本更新**，不用 rename/merge：`inspect <slug>` 看当前线上版本，publish 时给新 `--version` 即可。
6. **publication 是异步的**：publish 返回 `ok: true` + `status: pending-publication`，此时 `inspect` 可能仍显示旧 `latestVersion`。用 `clawhub skill verify <slug>` 跟进扫描/上线，不要因为 inspect 没变就重复发布。
7. **上传慢**：35 文件 / 约 1.6MB 实测约 3.5 分钟才有返回，超时给足（脚本 600s）。
8. 适合 OpenClaw 生态技能；`quicker-connector` 首选此平台。社区含少量恶意样本（有第三方审计称约 7%），发布端无碍；若安装他人技能留意来源。

### AgentPowers（未实测）

- 按 MCP 标准提交，经 8 层自动化安全扫描后上线。
- Web 后台管理 listing。
- 偏海外付费市场，适合有付费潜力的 Windows 运维技能。

## 发布后同步规划

每完成一个平台的发布：

1. 在 `docs/publishing-plan.json` 将该技能对应平台的 `status` 改为 `done`。
2. 运行 `python skills/awam-skills/scripts/plan_skills.py` 刷新 `docs/publishing-plan.md` 视图。

## 禁止

- 替用户在平台注册、登录、付费或接受付费协议。
- 在平台之外另造市场 / 清单文件（`skill.json`、ClawHub 包等）作为发布依据——统一走本页流程。
- 发布前未确认技能可公开（涉及私密配置 / 凭据 / 内部路径的，先泛化再发）。
- 把平台鉴权 token 写入仓库 / 日志 / 长期留存的调试文件；仅走环境变量，用完即清。
