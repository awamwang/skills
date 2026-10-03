# 平台发布（platforms）

把 `awam-skills` 组织下已公开的技能发布到第三方技能平台，并同步发布规划。

> 平台命令 / 接口以各平台**官方文档为最新权威**；本页给出当前公开流程与入口，不代替官方文档。账号注册、登录与付费由用户完成，本 Skill 不代为处理。

## 通用前置

- 技能仓已在 GitHub `awam-skills` 公开且含 `SKILL.md`（嵌套则 `skills/<name>/SKILL.md`）。
- 文件统一 **UTF-8（无 BOM）**。
- `SKILL.md` frontmatter 齐备（`name` / `description`）。
- 用户已在该平台注册 / 登录 / 开通（涉及付费需用户确认）。

## 平台清单

| 平台 | 区域 | 发布通道 | 前置 | 适合技能 |
|------|------|----------|------|----------|
| **LobeHub** | 国际 | SKILL.md bundle + CLI `npx -y @lobehub/market-cli` | 账号 | 跨 agent 通用型（ssh-deploy、awam-git、github-organize） |
| **魔搭 ModelScope** | 国内 | Skills Central + `modelscope-skill-upload`（OpenAPI） | 账号 | 通用与运维技能均合适 |
| **豆包技能中心** | 国内 | 豆包电脑版侧边栏「技能」→ 技能中心导入 | 豆包客户端 | 个人工作流与通用技能；成本最低 |
| **ClawHub** | 国际 | `clawhub skill publish ./<dir>` | OpenClaw / clawhub CLI | OpenClaw 生态技能（quicker-connector） |
| **AgentPowers** | 国际 | MCP 标准提交（8 层安全扫描） | 账号 / 后台 | 高品质 / 付费向（windows-autostart、letsencrypt 等） |

## 各平台发布步骤

### LobeHub

- 打包 `SKILL.md`（及所需资源）为 bundle。
- 用官方 CLI：`npx -y @lobehub/market-cli`（安装/发布/版本管理；发布子命令以 `--help` 与官方文档为准）。
- 跨 Claude、Cursor、Codex 等，分发量最大；适合优先铺开。

### 魔搭 ModelScope

- 优先用魔搭上的 **`modelscope-skill-upload`** 技能自动完成：打包 zip → 上传拿 `file_id` → 创建 Skill → 验证发布。
- 也支持后续更新技能设置。
- 中文生态最大，通用与运维技能都合适。

### 豆包技能中心

- 豆包电脑版侧边栏「技能」入口 → 技能中心 → 添加 / 导入自定义技能。
- 使用自定义技能前确认来源、权限、依赖与适用端。
- 个人工作流与通用技能，接入成本最低。

### ClawHub（OpenClaw）

- 先预览：`clawhub skill publish ./my-skill --dry-run`（检查元数据完整、文件合规）。
- 正式发布：`clawhub skill publish ./my-skill --slug <slug> --name <name> --version <v> --changelog <msg>`。
- 适合 OpenClaw 生态技能；`quicker-connector` 首选此平台。
- 社区含少量恶意样本（有第三方审计称约 7%），发布端无碍；若安装他人技能留意来源。

### AgentPowers

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
