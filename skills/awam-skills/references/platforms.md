# 平台发布（platforms）

把 `awam-skills` 组织下已公开的技能发布到第三方技能平台，并同步发布规划。

> 平台命令 / 接口以各平台**官方文档为最新权威**；本页给出当前公开流程、入口与**实测踩坑**（截至 2026-10，已实测发布 `ssh-deploy-skill`：魔搭、LobeHub、豆包导入包）。账号注册、登录与付费由用户完成，本 Skill 不代为处理。

## 通用前置

- 技能仓已在 GitHub `awam-skills` 公开且含 `SKILL.md`（嵌套则 `skills/<name>/SKILL.md`）。
- 文件统一 **UTF-8（无 BOM）**；`SKILL.md` 建议 **LF 行尾**（Windows 复制常残留 CRLF，会触发魔搭解析错误，见下方踩坑）。
- `SKILL.md` frontmatter 齐备：`name` / `version`（创建模板默认 `0.0.1`）/ `description`；发魔搭 / LobeHub 前按 semver 提升 `version`（初始值可取自技能 `_meta.json`）。
- 用户已在该平台注册 / 登录 / 开通（涉及付费需用户确认）。

## 平台清单

| 平台 | 区域 | 发布通道 | 前置 | 适合技能 |
|------|------|----------|------|----------|
| **LobeHub** | 国际 | SKILL.md bundle + CLI `npx -y @lobehub/market-cli` | 账号 + 网页提交仓库 | 跨 agent 通用型（ssh-deploy、awam-git、github-organize） |
| **魔搭 ModelScope** | 国内 | Skills Central + `modelscope-skill-upload`（OpenAPI） | 账号 | 通用与运维技能均合适 |
| **豆包技能中心** | 国内 | 豆包电脑版侧边栏「技能」→ 技能中心导入 | 豆包客户端 | 个人工作流与通用技能；成本最低 |
| **ClawHub** | 国际 | `clawhub skill publish ./<dir>` | OpenClaw / clawhub CLI | OpenClaw 生态技能（quicker-connector） |
| **AgentPowers** | 国际 | MCP 标准提交（8 层安全扫描） | 账号 / 后台 | 高品质 / 付费向（windows-autostart、letsencrypt 等） |

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

优先用魔搭上的 **`modelscope-skill-upload`** 技能流程：打包 zip → 上传拿 file_id → 创建 Skill → 验证。

1. 打包：zip **根目录必须恰好 1 个 `SKILL.md`**，frontmatter 含 `name` / `version` / `description`，zip ≤5MB。
2. 上传：`POST https://modelscope.cn/openapi/v1/files/upload`（multipart 字段 `file`）→ 取 `data.id` 作 file_id。
3. 创建：`POST /skills`（body 含 file_id、display_name、license、category 等）；重复创建报 **409 DuplicateEntity**。
4. 验证：`GET /skills?filter.owner=<owner>&page_size=50`（**列表接口可靠**；详情接口 `/skills/@owner/name` 可能 404，以列表为准）。

**踩坑：** SKILL.md 为 **CRLF 行尾**时上传报 `UploadedFileInvalid: must contain 'name' field`（实际是行尾问题）——必须转 LF，Windows 下用 `write_bytes` / 二进制写回，防止 `\r\n` 被重新引入。
- 鉴权：`Authorization: Bearer <token>`；token 仅走环境变量，不入仓库 / 日志。

### 豆包技能中心（已实测导入包）

- 导入格式：**文件夹或 zip 内含 `SKILL.md` 即可**，名称须与技能同名；打包 zip 时**顶层为技能同名文件夹**。
- 入口：豆包电脑版侧边栏「技能·连接器·伙伴」→ 我的技能 → 新建 → 上传技能（拖入文件夹 / zip）。
- 个人工作流与通用技能，接入成本最低。

### ClawHub（OpenClaw，未实测）

- 先预览：`clawhub skill publish ./my-skill --dry-run`（检查元数据完整、文件合规）。
- 正式发布：`clawhub skill publish ./my-skill --slug <slug> --name <name> --version <v> --changelog <msg>`。
- 适合 OpenClaw 生态技能；`quicker-connector` 首选此平台。
- 社区含少量恶意样本（有第三方审计称约 7%），发布端无碍；若安装他人技能留意来源。

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
