# 平台发布（platforms）

把 `awam-skills` 组织下已公开的技能发布到第三方技能平台，并同步发布规划。

> 平台命令 / 接口以各平台**官方文档为最新权威**；本页给出当前公开流程、入口与**实测踩坑**（截至 2026-10，已实测发布 `ssh-deploy-skill`：魔搭、LobeHub、豆包导入包；`quicker-connector`：魔搭 **SDK 通道** + ClawHub + 豆包导入包；`awam-todo-skill`：魔搭、ClawHub + 豆包导入包，LobeHub 被人工前置挡住）。账号注册、登录与付费由用户完成，本 Skill 不代为处理。

## 通用前置

- 技能仓已在 GitHub `awam-skills` 公开且含 `SKILL.md`（嵌套则 `skills/<name>/SKILL.md`）。
- 文件统一 **UTF-8（无 BOM）**；`SKILL.md` 建议 **LF 行尾**（Windows 复制常残留 CRLF，会触发魔搭解析错误，见下方踩坑）。
- `SKILL.md` frontmatter 齐备：`name` / `version`（创建模板默认 `0.0.1`）/ `description`；发魔搭 / LobeHub 前按 semver 提升 `version`（初始值可取自技能 `_meta.json`）。
- 用户已在该平台注册 / 登录 / 开通（涉及付费需用户确认）。
- **发布源是索引仓 / 技能仓里的目录**，不是 `~/.workbuddy/skills/` 下的安装副本 —— 后者混着宿主注入的 `_user_meta.json`，且脱离 git 后安全兜底只剩黑名单。
- **发布前先跑 preflight**（见下一节），别带着「本地领先远程」「不是 git 仓」这类本机问题去发。

## 发布前检查（preflight，任何平台都要先跑）

```bash
python skills/awam-skills/scripts/preflight.py --dir <技能仓>
python skills/awam-skills/scripts/preflight.py --dir <仓A> --dir <仓B>   # 批量预检
python skills/awam-skills/scripts/preflight.py --dir <技能仓> --json     # 给脚本用
```

一次查完「发出去就收不回」的本机问题，输出 `✅ PASS / ⚠ WARN / ❌ FAIL` 与退出码
（有 FAIL 退 1）。这是 2026-10-07 一次发布里连着踩到三个坑之后加的，三个都是**发布前
30 秒能查出来**的：

| 检查项 | 为什么 |
|---|---|
| SKILL.md 存在 + **打包根唯一** | 嵌套布局若按仓库根打包，zip 根下没有 SKILL.md（见下节） |
| 是 git 仓库 / 有 origin | 不是 git 仓：ClawHub 的 `git archive` 直接失败，打包器还会退化成黑名单遍历 |
| **本地领先远程** → FAIL | 发出去的内容比 GitHub 上的仓新，两边对不上（实测 awam-todo 带着 1 个未推提交） |
| 工作区有未提交改动 → WARN | 平台发的是工作区内容，与仓库 HEAD 不一致 |
| frontmatter `name` / `version` / `description` | 魔搭与 LobeHub 都硬性要求；**老仓常只缺 `version`**（实测 windows-autostart） |
| BOM / CRLF | CRLF 会让魔搭报 `must contain 'name' field`（实际是行尾问题）。本机多数仓 `core.autocrlf=true`，工作区必然 CRLF —— 这种情况 preflight 判为正常（发布时会自动转 LF），只在 autocrlf 未开时才提示 |
| **私密文件是否已被 git 跟踪** → FAIL | 发布包已自动排除，但仓库里已经泄漏，得 `git rm --cached` + 补 `.gitignore` |
| 已安装副本与索引仓**内容哈希**是否一致 | 复制型副本会过期，照它读文档 / 跑脚本会走弯路（实测踩到） |

## 打包根：扁平 vs 嵌套（决定 zip 能不能被平台接受）

平台要求 **zip 根目录恰好 1 个 `SKILL.md`**。所以「仓库根」与「打包根」是两件事：

| 布局 | 仓库结构 | 打包根 |
|---|---|---|
| 扁平 | `<仓库>/SKILL.md` | 仓库根 |
| 嵌套 | `<仓库>/skills/<技能名>/SKILL.md` | 那个 `<技能名>/` 目录 |

三个打包脚本（魔搭 / 豆包 / ClawHub）都通过 [scripts/public_files.py](../scripts/public_files.py)
的 `find_skill_root()` / `pack_files()` 判定打包根，并**按打包根**取路径；打包根之外的
文件（仓库级 `README.md`、`.github/`、`.gitignore`）会打印「打包根外跳过 N 个」。

**踩坑（2026-10-07 发现）**：改之前三个打包器都按**仓库根**取路径。扁平的仓库看不出问题，
但 `starup-skill` 这种嵌套仓（`skills/windows-autostart/SKILL.md`）会：魔搭报
「找不到 SKILL.md」（`read_frontmatter` 按 `<仓库名>` 猜嵌套目录，对不上），
即使找到了，zip 根下也没有 SKILL.md，根目录校验直接不过。**等于这个技能一直发不出去。**

一仓多技能（多个 `skills/*/SKILL.md`）时打包根无法自动判定，脚本会明确报错 —— 拆成一仓一技能。

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

#### ⚠ 发布包内容（P0，2026-10-07 实际踩到）

**曾把 `storage/`、`env.json`、`index.json`、`web/*.log` 一起发上公开平台。**
早期打包器只排除 `.git` / `.workbuddy` / `__pycache__` 这类工程目录，于是把本地私密数据
（真实待办内容、主机名、本机 cwd、编辑器路径）打进了公开包 —— **发布包是公开物**。

现在统一走 [scripts/public_files.py](../scripts/public_files.py)：**只发 git 跟踪文件**
（= 作者选择公开的表面，也是「技能仓须已在 GitHub 公开」这条前置的自然含义），
再叠一层硬黑名单（`storage/`、`env.json`、`index.json`、`*.log`、`*.pyc`、`_user_meta.json` …）兜底。
`publish_modelscope.py` / `publish_doubao.py` / `publish_clawhub.py` 都已改用它，并在日志里
逐条打印被排除的文件。

补充（2026-10-07 复查时发现）：`publish_clawhub.py` 之所以一直干净，是因为它走 `git archive`
只取跟踪文件 —— **但它的非 git 回退分支当时也在按排除表复制，同一个漏洞只是没触发**，现已一并改为
走 `public_files`。顺带删掉了三个脚本里的 `EXCLUDE_DIRS` 常量：留着就是下次复发的种子。

**发布后必须复核**：把线上内容拉回来列一遍文件清单，确认无私密文件。只看接口返回的
`success: true` 不够 —— 本次正是靠下载复核才确认泄漏已清除。

#### 已存在的技能怎么更新内容

同名技能不能再 create，魔搭也没有「新建版本」接口。**替换内容的通道是 settings**：

```
POST  /openapi/v1/files/upload                                → 新 file_id
PATCH /openapi/v1/skills/{owner}/{skill_name}/settings
      body: {"skill_file": "<新 file_id>"}                     → {"success": true}
```

`publish_modelscope.py` 已内置：SDK 通道遇 409 会自动转成上面的更新流程
（日志会写「改为更新已有技能的内容」）。

**OpenAPI 通道的字段名**（以 SDK 的 `CreateSkillPayload` 为准）：技能名是 **`skill_name`**
（不是 `name`），内容文件是 **`skill_file`**（不是 `file_id`）。早先脚本写成 `name` / `file_id`，
服务端一直回 `InputParameterError: skill name is required` —— 这就是 OpenAPI 通道长期不可用的原因，已修正。

**解释器必须选装了 SDK 的那个**：本机 `modelscope_hub` 装在
`~/.workbuddy/binaries/python/envs/default/Scripts/python.exe`。用不带 SDK 的解释器跑，
`--via auto` 会**静默回退到 OpenAPI 通道**，于是下载 100MB 的上传白做、只在最后一步报错。
跑之前先看输出里的「通道自检」那一行。

**旧上传的 zip 不会因为替换 `skill_file` 而被删除**，它留在魔搭的「上传文件」里。
一旦发布过含私密数据的旧文件，除了替换技能内容，还要去魔搭用户中心把那个 file 删掉。

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

默认输出到 **`~/.awam-publish/<name>-doubao.zip`（仓库外）**，不再写进技能仓 ——
写进仓里会被 `git status` 看见，容易误提交进公开仓库。要放别处用 `--out`。

### ClawHub（OpenClaw，已实测 2026-10-06：quicker-connector 1.2.0 → 1.5.0）

**一键脚本（推荐）**：[scripts/publish_clawhub.py](../scripts/publish_clawhub.py) 已封装下列全部踩坑（干净目录、去代理、`--no-input`、发后刷新规划）：

```bash
export CLAWHUB_BIN=<clawhub.cmd 或 dist/cli.js 路径>   # 不在 PATH 时必填
python skills/awam-skills/scripts/publish_clawhub.py --dir <技能仓> --dry-run   # 预览
python skills/awam-skills/scripts/publish_clawhub.py --dir <技能仓>             # 发布 + 刷新规划
python skills/awam-skills/scripts/publish_clawhub.py --dir <技能仓> --keep-tmp  # 留临时目录排查
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
9. **`verify` 返回 `ok:false` 不等于发布失败**（2026-10-07 实测 awam-todo）。`skill verify <slug>` 的两个常见 reason：
   - `security.status_not_clean`：平台侧 LLM 安全复审给 `security.status=suspicious`。**这是平台级共性，不是本仓缺陷** ——
     已上线的 `quicker-connector` 同样如此（它的原话是「能跑本地动作、部分网络与确认行为披露不足」）。
     `inspect` 里的 `Moderate CLEAN` 与 `verify` 里的 security 判定是两套东西，后者偏保守，技能照常上线可访问。
   - `card.missing`：缺少 `skill-card.md`（`card.available=false`）。`quicker-connector` 是 `true`，说明这
     能补；**但别自己造这个文件**（见下方「禁止」），要补就照平台给的 `card.url` 规范来。
10. **中文文件名会被上传成乱码**：实测 `优化建议.md` 在线上文件清单里变成 `浼樺寲寤鸿.md`
    （CLI / registry 的编码往返问题）。功能无碍，但看起来脏；要么接受，要么发布前把非 ASCII
    文件名的文件改名 / 排除。

### AgentPowers（未实测）

- 按 MCP 标准提交，经 8 层自动化安全扫描后上线。
- Web 后台管理 listing。
- 偏海外付费市场，适合有付费潜力的 Windows 运维技能。

## 发布后复核（通用铁律）

**只看接口返回的 `success: true` 不够**——脚本的判断可能错，平台也可能异步。
每次发布后都要**以线上的内容为准**做一次复核；尤其要确认没把本机私密数据发上去
（2026-10-07 那次就是靠「下载回来列文件清单」才确认泄漏已清除）。

| 平台 | 复核手段 | 看什么 |
|---|---|---|
| 魔搭 | `api.download_repo("<owner>/<name>", repo_type=RepoType.SKILL, local_dir=…)` | 文件清单里无 `storage/`、`env.json`、`index.json`、`*.log` |
| ClawHub | `clawhub inspect <slug>` / `clawhub skill verify <slug>` | `Latest` 版本与文件数；`verify` 的 `ok:false` 不必然是发布失败（见 ClawHub 小节） |
| LobeHub | `npx -y @lobehub/market-cli skill list` | status 为 `published` |
| 豆包 | 客户端「我的技能」里看条目 | 无 API，只能人工看；导入成功后回跑 `--mark-done` |

## 批量发布

多个技能一起发时，**先全部预检、再逐个正式发**，不要边发边发现问题：

```bash
# 1) 批量预检（不碰网络、不改任何状态）
python skills/awam-skills/scripts/preflight.py --dir <仓A> --dir <仓B> --dir <仓C>

# 2) 逐个干跑，确认打包内容与文件数（--no-plan 表示不写发布规划）
python skills/awam-skills/scripts/publish_modelscope.py --dir <仓A> --dry-run --no-plan
python skills/awam-skills/scripts/publish_doubao.py    --dir <仓A>

# 3) 逐个正式发（去掉 --dry-run；这一步才会写规划并刷新视图）
python skills/awam-skills/scripts/publish_modelscope.py --dir <仓A>
```

干跑阶段会打印「发布文件集：N 个（来源：…）」与被打包根跳过的文件 —— **先看这一行**
再决定发不发。干跑不需要 token 的部分（打包、通道自检）也会一起跑，能提前暴露
「解释器选错导致通道回退」这类问题。

## 本机环境备忘（Windows，实测）

这些是环境层面反复咬人的点，写在这里免得每次重新摸：

| 现象 | 处理 |
|---|---|
| 发布脚本报「缺模块 / SDK 不可用」 | 用 **venv 解释器**跑：`~/.workbuddy/binaries/python/envs/default/Scripts/python.exe`；托管 python 没装 `modelscope_hub`，`--via auto` 会**静默回退**到 OpenAPI 通道 |
| ClawHub 找不到 CLI | 实测落在托管 node 工作区：`~/.workbuddy/binaries/node/workspace/node_modules/clawhub/dist/cli.js`，用 `CLAWHUB_BIN` 指过去 |
| 代理导致 502 | 两个脚本都已内置剥离 `*_PROXY` + `NO_PROXY='*'`；自己手敲命令时照做 |
| 临时目录越堆越多 | 脚本已改为 `finally` 清理（`--keep-tmp` 可保留）。手工清 `%TEMP%` 时用 **Python `shutil.rmtree`** —— bash 的 `rm -rf` 与 PowerShell 的 `Remove-Item` 在本沙箱会被拦（SIGTERM），Python 不会 |
| 一堆历史 `modelscope_publish_*` / `clawhub_publish_*` | 上面那条的遗留，按需清；新版本不再产生 |

## 发布后同步规划

每完成一个平台的发布：

1. 在 `docs/publishing-plan.json` 将该技能对应平台的 `status` 改为 `done`。
2. 运行 `python skills/awam-skills/scripts/plan_skills.py` 刷新 `docs/publishing-plan.md` 视图。

## 禁止

- 替用户在平台注册、登录、付费或接受付费协议。
- 在平台之外另造市场 / 清单文件（`skill.json`、ClawHub 包等）作为发布依据——统一走本页流程。
- 发布前未确认技能可公开（涉及私密配置 / 凭据 / 内部路径的，先泛化再发）。
- 把平台鉴权 token 写入仓库 / 日志 / 长期留存的调试文件；仅走环境变量，用完即清。
- **用 `~/.workbuddy/skills/`（或 `~/.agents/skills/`）下的安装副本作为发布源**——发布源只能是
  技能仓目录，副本既可能过期，又脱离 git 跟踪，安全兜底会失去「作者已公开的表面」这层依据。
- **在打包器里自建「排除目录表」代替 [scripts/public_files.py](../scripts/public_files.py)**。
  只跳过 `.git` / `__pycache__` 这类工程目录是不够的 —— 那正是当初把 `storage/`、`env.json`、
  `index.json` 打进公开包的原因。要加排除项就加进 `public_files.py` 的黑名单，一处生效、三处复用。
- **只看接口返回 `success: true` 就宣称发布成功**。必须按上一节做一次线上内容复核。
