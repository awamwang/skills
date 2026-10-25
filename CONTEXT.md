# Domain Glossary

## 技能索引仓

本仓库（`awamwang/skills` / 本地 `awam-skills`）：罗列 Awam 个人技能的目录仓。职责是分类索引与自动同步，不是单个技能的实现代码。

_Avoid_: 技能仓、实现仓、catalog 若未特指本仓

## 技能仓

承载某一个 Skill 实现的 GitHub 仓库，默认归属组织 `awam-skills`。可被索引仓收录。

_Avoid_: 把索引仓本身称作技能仓（除非在讨论其叠加的「创建/发布」Skill）

## 创建

按 Awam 个人基础模式**初始化**一个技能仓：本地脚手架 + 在 `awam-skills` 组织下建立空仓并配置 remote。不包含把内容推上去，也不算发布完成。

_Avoid_: 脚手架、init、scaffold（口语可说，文档与 Skill 正文用「创建」）

## 发布

将已有技能仓公开到 GitHub 并完成收录所需收尾：必要时 push 技能仓内容、设 Topics（`skill` / `skills` 与可选 `cat-*`）、对齐 repo description、更新索引仓 `skills.overrides.json`。README 刷新交给线上同步（见「README 单写者」）。不含 ClawHub / 市场包装。

_Avoid_: 上架、publish to marketplace

## 升级

对**发布规划内**已管理技能做发版升号：用 `skills/awam-skills/scripts/upgrade_skill.py` 提升技能仓 `SKILL.md` frontmatter `version`，并回写本机 `docs/repos.json` 对应条目的版本字段。权威 version 仍在技能仓；repos 上的 version 字段是本机管理快照（gitignore）。脚本**不**自动 commit / push；升号后由用户提交，再按需走平台发布（`release.py`）。可用 `--refresh` 从本机克隆重刷版本字段，`--list` 只读列出。

_Avoid_: 本机 `git pull` / Agent 安装路径同步；把手改 version 行当作升级；把 repos 版本字段当成权威源

## 查询

用 `skills/awam-skills/scripts/query_skills.py` **只读**列出并对比三处技能：组织 `awam-skills` 仓库、索引仓远程 README（及仓内流程 Skill）、本机技能扫描根（默认 `G:\Projects\19AI\skills`，由仓库根 `.env` 的 `AWAM_SKILLS_LOCAL_DIR` 配置；支持子目录嵌套的 `SKILL.md`，可用 `AWAM_SKILLS_LOCAL_EXCLUDE` 按目录名排除）。由脚本出表，不靠 AI 逐步手查。

_Avoid_: 同步（会写 README）；发布

## 同步

用 `scripts/sync_skills.py` 或 GitHub Actions「Sync Skills Catalog」根据组织仓、topic 与 overrides 重写索引仓 `README.md`。发布流程**不**在本地跑同步，避免与 Actions 争写。

_Avoid_: 发布（发布会间接触发同步，但同步本身不是发布的全部）

## overrides

`skills.overrides.json`：人工指定技能分类与中文简介的权威覆盖；同步时优先于仓库自带 description。

## 脚手架布局

创建时可选的两种仓库结构：

- **扁平布局**：根目录 `SKILL.md`（如 `github-organize`）——**默认**
- **嵌套布局**：`skills/<name>/SKILL.md`，根目录可放 CLI / 测试 / 领域文档（如 `windows-autostart-skill`）——仅当有根目录 CLI、多技能或需要 CONTEXT 时选用

## 创建/发布/查询/升级 Skill

本索引仓内叠加的可安装 Skill，路径 `skills/awam-skills/SKILL.md`，name 为 `awam-skills`。负责 Awam 个人的创建、发布、三方查询对比与发版升级，不负责通用 Skill 优化。

## 本机 repos 与版本字段

`docs/repos.json`（gitignore；模板 `docs/repos.example.json`）：技能 key → 本机 `path`，以及版本管理字段：

| 字段 | 含义 |
|------|------|
| `path` | 本地克隆路径（`null` = 未找到） |
| `version` | frontmatter version 快照 |
| `name` | frontmatter name |
| `repo` | GitHub `owner/repo` |
| `version_updated` | 版本字段最近刷新日 |
| `version_reason` | `version` 为 null 时的原因 |

由 `upgrade_skill.py --refresh` / 升版回写；无本机路径时 `version` 为 null 并带 `version_reason`，不编造。

_Avoid_: 手改版本字段代替跑脚本；把 `publishing-state.json`（各平台已发布 commit/version）与 repos 版本字段混为一谈；提交 `repos.json`

## 本机技能扫描根

查询脚本扫描的本机技能根目录。默认 `G:\Projects\19AI\skills`；权威配置在索引仓根 `.env`（模板 `.env.example`）：

- `AWAM_SKILLS_LOCAL_DIR`：扫描根路径
- `AWAM_SKILLS_LOCAL_EXCLUDE`：按目录名排除（逗号分隔），命中技能目录名或其祖先目录名则不纳入管理对比

支持根下任意深度嵌套的 `SKILL.md`（扁平仓与 `skills/<name>/SKILL.md` 嵌套布局均可）。CLI 可用 `--local-dir` / `--exclude` 临时覆盖。

## 仓库命名

新建技能仓在组织 `awam-skills` 下的默认名：若 skill `name` 已以 `-skill` 结尾则为 `name` 本身，否则为 **`<name>-skill`**（kebab-case）。既有仓不强制回溯改名。

_Avoid_: 与 skill `name` 裸名一律等同（旧习惯）；`foo-skill-skill` 双后缀

## README 单写者

索引仓 `README.md` 的权威写入方是 **GitHub Actions「Sync Skills Catalog」**。发布流程只更新 `skills.overrides.json`（及远程 Topics/description），**本地不跑** `sync_skills.py`，以免与线上同步争写。

## 发布规划

`docs/publishing-plan.json`：按「技能 × 平台」记录每个技能的发布规划（`plan`）与实际情况（`status`）的权威数据；人读视图 `docs/publishing-plan.md` 由 `scripts/plan_skills.py` 生成。**新建技能必须配套登记发布规划**；每完成一个平台发布即更新对应 `status` 并刷新视图。

_Avoid_: 手改 `publishing-plan.md` 视图（由脚本生成）；漏登记新技能

## 平台发布

把 `awam-skills` 组织下已公开的技能发布到第三方技能平台（LobeHub、魔搭 ModelScope、豆包技能中心、ClawHub、skills.sh、AgentPowers）。流程见 `references/platforms.md`；发布后同步 `publishing-plan.json`。不含替用户注册、登录或付费。

_Avoid_: 在平台之外另造市场 / 清单文件作为发布依据

## Non-goals（本 Skill 明确不做）

- 通用 Skill 质量/结构优化（progressive disclosure、跨 harness、skill-creator-advanced 等）
- 对他人技能仓做 review / 重构建议
- 仅为「公共能力」去改同步脚本；仅当个人发布/收录流程会踩坑时才允许最小改动
- 第三方平台的账号注册、登录、付费开通（需要用户完成）
