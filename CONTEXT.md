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

## 查询

用 `skills/awam-skills/scripts/query_skills.py` **只读**列出并对比三处技能：组织 `awam-skills` 仓库、索引仓远程 README（及仓内流程 Skill）、本机 `~/.agents/skills/awam/`。由脚本出表，不靠 AI 逐步手查。

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

## 创建/发布/查询 Skill

本索引仓内叠加的可安装 Skill，路径 `skills/awam-skills/SKILL.md`，name 为 `awam-skills`。负责 Awam 个人的创建、发布与三方查询对比，不负责通用 Skill 优化。

## 本机 awam 目录

`~/.agents/skills/awam/`（Windows: `%USERPROFILE%\.agents\skills\awam\`）：本机按「awam」命名空间放置的技能子目录，查询流程与组织仓、索引仓对照用。与 skills 根目录下其它第三方技能无关。

## 仓库命名

新建技能仓在组织 `awam-skills` 下的默认名：若 skill `name` 已以 `-skill` 结尾则为 `name` 本身，否则为 **`<name>-skill`**（kebab-case）。既有仓不强制回溯改名。

_Avoid_: 与 skill `name` 裸名一律等同（旧习惯）；`foo-skill-skill` 双后缀

## README 单写者

索引仓 `README.md` 的权威写入方是 **GitHub Actions「Sync Skills Catalog」**。发布流程只更新 `skills.overrides.json`（及远程 Topics/description），**本地不跑** `sync_skills.py`，以免与线上同步争写。

## 发布规划

`docs/publishing-plan.json`：按「技能 × 平台」记录每个技能的发布规划（`plan`）与实际情况（`status`）的权威数据；人读视图 `docs/publishing-plan.md` 由 `scripts/plan_skills.py` 生成。**新建技能必须配套登记发布规划**；每完成一个平台发布即更新对应 `status` 并刷新视图。

_Avoid_: 手改 `publishing-plan.md` 视图（由脚本生成）；漏登记新技能

## 平台发布

把 `awam-skills` 组织下已公开的技能发布到第三方技能平台（LobeHub、魔搭 ModelScope、豆包技能中心、ClawHub、AgentPowers）。流程见 `references/platforms.md`；发布后同步 `publishing-plan.json`。不含替用户注册、登录或付费。

_Avoid_: 在平台之外另造市场 / 清单文件作为发布依据

## Non-goals（本 Skill 明确不做）

- 通用 Skill 质量/结构优化（progressive disclosure、跨 harness、skill-creator-advanced 等）
- 对他人技能仓做 review / 重构建议
- 仅为「公共能力」去改同步脚本；仅当个人发布/收录流程会踩坑时才允许最小改动
- 第三方平台的账号注册、登录、付费开通（需要用户完成）
