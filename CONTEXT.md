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

## 同步

用 `scripts/sync_skills.py` 或 GitHub Actions「Sync Skills Catalog」根据组织仓、topic 与 overrides 重写索引仓 `README.md`。发布流程**不**在本地跑同步，避免与 Actions 争写。

_Avoid_: 发布（发布会间接触发同步，但同步本身不是发布的全部）

## overrides

`skills.overrides.json`：人工指定技能分类与中文简介的权威覆盖；同步时优先于仓库自带 description。

## 脚手架布局

创建时可选的两种仓库结构：

- **扁平布局**：根目录 `SKILL.md`（如 `github-organize`）——**默认**
- **嵌套布局**：`skills/<name>/SKILL.md`，根目录可放 CLI / 测试 / 领域文档（如 `windows-autostart-skill`）——仅当有根目录 CLI、多技能或需要 CONTEXT 时选用

## 创建/发布 Skill

本索引仓内叠加的可安装 Skill，路径 `skills/awam-skills/SKILL.md`，name 为 `awam-skills`。负责 Awam 个人的创建与发布流程，不负责通用 Skill 优化。

## 仓库命名

新建技能仓在组织 `awam-skills` 下的默认名：若 skill `name` 已以 `-skill` 结尾则为 `name` 本身，否则为 **`<name>-skill`**（kebab-case）。既有仓不强制回溯改名。

_Avoid_: 与 skill `name` 裸名一律等同（旧习惯）；`foo-skill-skill` 双后缀

## README 单写者

索引仓 `README.md` 的权威写入方是 **GitHub Actions「Sync Skills Catalog」**。发布流程只更新 `skills.overrides.json`（及远程 Topics/description），**本地不跑** `sync_skills.py`，以免与线上同步争写。

## Non-goals（本 Skill 明确不做）

- 通用 Skill 质量/结构优化（progressive disclosure、跨 harness、skill-creator-advanced 等）
- ClawHub / OpenClaw 市场包装与发布清单
- 对他人技能仓做 review / 重构建议
- 仅为「公共能力」去改同步脚本；仅当个人发布/收录流程会踩坑时才允许最小改动
