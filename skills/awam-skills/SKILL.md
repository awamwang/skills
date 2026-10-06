---
name: awam-skills
description: >-
  按 Awam 个人约定创建、发布或查询 AI 技能：初始化 awam-skills 组织下的技能仓库脚手架，
  发布到 GitHub 后更新 Topics、description 与索引仓 overrides，用脚本对比组织仓 /
  索引仓远程 / 本机 ~/.agents/skills/awam 的技能列表与存在性，以及把技能发布到第三方
  平台（LobeHub / 魔搭 ModelScope / 豆包 / ClawHub / AgentPowers）并维护发布规划
  （docs/publishing-plan.json）。在用户提到创建技能、初始化技能仓、发布技能、收录到
  awam-skills 索引、发布到平台 / 市场、发布规划、查询技能列表、对比本机与线上技能，
  或显式调用 /awam-skills 时使用。不处理通用 Skill 质量优化或对他人仓的 review。
disable-model-invocation: true
---

# awam-skills（创建 / 发布 / 查询 / 平台发布）

Awam 个人技能仓的**创建**、**发布**、**查询**与**第三方平台发布**流程。领域词见仓库根目录 [CONTEXT.md](../../CONTEXT.md)。

## 何时用

| 用户意图 | 走哪条 |
|----------|--------|
| 新建 / 初始化技能仓 | [创建](references/create.md) |
| 推到 GitHub 并进索引 | [发布](references/publish.md) |
| 发布到第三方平台 / 更新发布规划 | [平台发布](references/platforms.md)（ClawHub / 魔搭 / 豆包各有 [scripts/](scripts/) 下对应脚本） |
| 平台凭据（token）从哪来 | [凭据管理](references/platforms.md#凭据管理通用)：由 [scripts/credentials.py](scripts/credentials.py) 自动查找，**不要向用户索要**——先跑 `--show-credentials` |
| 列组织 / 索引远程 / 本机 awam 技能并对比 | [查询](references/query.md) |
| 改 skill 结构、写更好的 prompt、通用质量优化 | **拒绝**（Non-goals） |

## Non-goals

- 通用 Skill 质量/结构优化（progressive disclosure、跨 harness、skill-creator-advanced 等）
- 对他人技能仓做 review / 重构建议
- 仅为「公共能力」改同步脚本（个人发布踩坑时才允许最小改动）
- 第三方平台的账号注册、登录、付费开通（需要用户完成）

## 常量

| 项 | 值 |
|----|-----|
| 组织 | `awam-skills` |
| 索引仓（本仓） | 含 `skills.overrides.json` 与本 Skill 的 git 根 |
| Topics（必打） | `skill`、`skills` |
| 分类 Topics（可选） | `skills.overrides.json` 里各类的 `topics`（如 `cat-ops`） |
| README 写入方 | **仅** GitHub Actions「Sync Skills Catalog」——发布时**禁止**本地跑 `scripts/sync_skills.py` |
| 发布规划权威 | `docs/publishing-plan.json`（每个技能 × 平台的 `plan`/`status`）；人读视图 `docs/publishing-plan.md` 由 [scripts/plan_skills.py](scripts/plan_skills.py) 生成，**勿手改视图** |

## 仓库命名

```
repo_name = name if name.endswith("-skill") else f"{name}-skill"
```

全小写 kebab-case。既有仓不改名。

## 布局选择（创建）

- **默认扁平**：根目录 `SKILL.md`
- **嵌套**：仅当用户明确需要根目录 CLI、一仓多技能、或 `CONTEXT.md` 时 → `skills/<name>/SKILL.md`

## 总流程

1. 判定意图：创建 / 发布 / 平台发布 / 查询 / 创建后发布（先创建再实现，发布另开或用户明确要求时再发）。
2. 读 [CONTEXT.md](../../CONTEXT.md) 与相关 ADR（`docs/adr/`）。
3. 按对应 reference 逐步执行；缺分类、发布目标平台等决策时**问用户**，不替用户拍板索引语义。
4. **查询**必须跑 [scripts/query_skills.py](scripts/query_skills.py)，禁止用手搓 `gh`/扫目录代替。
5. **平台发布 / 规划更新**走 [references/platforms.md](references/platforms.md)；每完成一个平台发布，更新 `docs/publishing-plan.json` 的 `status` 并跑 [scripts/plan_skills.py](scripts/plan_skills.py) 刷新视图。ClawHub 用 [scripts/publish_clawhub.py](scripts/publish_clawhub.py) 一键完成「干净目录 → 发布 → 刷新规划」。
   **凭据不要问用户**：由 [scripts/credentials.py](scripts/credentials.py) 按固定顺序自动查找（首选 `~/.workbuddy/secrets/<platform>.json`）；缺凭据时才提示用户去补哪个文件。排查用 `--show-credentials`（脱敏）。
6. 不主动 `git commit` / `git push` 索引仓，除非用户明确要求；技能仓的首次 push 仅在**发布**流程且检测到远程无提交时执行。

## 本机发现（可选）

本 Skill 只活在索引仓，不单独发组织仓。若要在其它工作区调用，把本目录链到 Agent skills 路径，例如：

```powershell
New-Item -ItemType Junction -Force -Path "$env:USERPROFILE\.agents\skills\awam-skills" -Target "<本仓绝对路径>\skills\awam-skills"
```

## 快速对照

| 步骤 | 创建 | 发布 | 查询 | 平台发布 |
|------|------|------|------|----------|
| 本地脚手架 | ✅ | — | — | — |
| `gh repo create awam-skills/<repo>` | ✅ 空仓 + remote | — | — | — |
| push 技能仓内容 | ❌ | ✅ 仅当远程无提交 | — | — |
| Topics / description | ❌（可留到发布） | ✅ | — | — |
| 改 `skills.overrides.json` | ❌ | ✅ | ❌ | — |
| 本地 `sync_skills.py` | ❌ | ❌（交给 Actions） | ❌ | — |
| 跑 `query_skills.py` | — | — | ✅ 必跑 | — |
| 发布到第三方平台 | — | — | — | ✅ platforms.md（ClawHub 走 [publish_clawhub.py](scripts/publish_clawhub.py)） |
| 更新 `publishing-plan.json` + 跑 `plan_skills.py` | — | ✅ 建议 | — | ✅ 必跑 |
