---
name: awam-skills
version: 0.2.4
description: >-
  按 Awam 个人约定创建、发布、升级、移出管理或查询 AI 技能：初始化 awam-skills 组织下的技能仓库脚手架，
  发布到 GitHub 后更新 Topics、description 与索引仓 overrides，用脚本对比组织仓 /
  索引仓远程 / 本机技能扫描根（默认 G:\Projects\19AI\skills，可由 .env 配置）的技能列表
  与存在性，对管理中的技能做发版升号并回写 docs/repos.json 版本字段，把技能移出发布规划与本机管理映射，
  以及把技能发布到第三方平台（LobeHub / 魔搭 ModelScope / 豆包 / ClawHub / skills.sh / AgentPowers）
  并维护发布规划（docs/publishing-plan.json）。发布前先用 preflight.py 查一遍本机就绪度。
  在用户提到创建技能、初始化技能仓、发布技能、升级技能版本、移出管理、不再管理某技能、版本管理、
  收录到 awam-skills 索引、发布到平台 / 市场、发布规划、查询技能列表、对比本机与线上技能，
  或显式调用 /awam-skills 时使用。不处理通用 Skill 质量优化或对他人仓的 review。
disable-model-invocation: true
---

# awam-skills（创建 / 发布 / 升级 / 移出管理 / 查询 / 平台发布）

Awam 个人技能仓的**创建**、**发布**、**升级**、**移出管理**、**查询**与**第三方平台发布**流程。领域词见仓库根目录 [CONTEXT.md](../../CONTEXT.md)。

## 何时用

| 用户意图 | 走哪条 |
|----------|--------|
| 新建 / 初始化技能仓 | [创建](references/create.md) |
| **升级技能版本 / 版本管理**（工作区须干净 → 升 version → 回写 repos → 自动 commit；不 push） | [升级](references/upgrade.md)；固定入口 [scripts/upgrade_skill.py](scripts/upgrade_skill.py)（**禁止手改 version 代替**） |
| **移出管理**（从 plan / repos / state 拿掉，不再升级与漂移检测） | [移出管理](references/unmanage.md)；固定入口 [scripts/unmanage_skill.py](scripts/unmanage_skill.py)（**禁止手删 JSON 代替**） |
| **发布前的本机就绪检查**（git 状态、与远程是否同步、frontmatter、打包根、私密夹带、本机绝对路径） | [scripts/preflight.py](scripts/preflight.py)（**任何发布动作之前先跑**） |
| **发布包敏感串扫描**（凭据 / 私钥 / token 会不会被打进包） | [scripts/preflight_secrets.py](scripts/preflight_secrets.py)；魔搭 / 豆包 / ClawHub / LobeHub 上传型脚本已内置，命中即中止；skills.sh 无上传环节，不适用 |
| 仅改 frontmatter version、不回写台账 | [scripts/bump_version.py](scripts/bump_version.py)（管理流程优先 `upgrade_skill.py`） |
| 推到 GitHub 并进索引 | [发布](references/publish.md)；Topics/description/state 用 [scripts/publish_github.py](scripts/publish_github.py) |
| 发布到第三方平台 / 更新发布规划 | [平台发布](references/platforms.md)；一键编排 [scripts/release.py](scripts/release.py)（魔搭/ClawHub/skills.sh 默认可并行） |
| **发布后线上复核** | [scripts/verify_publish.py](scripts/verify_publish.py) |
| **索引仓 state/视图提交助手**（白名单 stage；需 `--yes` 才 commit） | [scripts/commit_publish_state.py](scripts/commit_publish_state.py) |
| **发布提醒 / 漂移检测**（哪些技能本地改了但平台没跟上） | [scripts/check_publish_drift.py](scripts/check_publish_drift.py)：对技能仓做了提交、或用户问「接下来发什么」时跑；有漂移逐个问是否现在发布（见下方「发布提醒」节） |
| 平台凭据（token）从哪来 | [凭据管理](references/platforms.md#凭据管理通用)：由 [scripts/credentials.py](scripts/credentials.py) 自动查找，**不要向用户索要**——先跑 `--show-credentials` |
| 依赖没装 / 报缺模块 | 跑 [scripts/setup_env.py](scripts/setup_env.py)（幂等，含魔搭 SDK `modelscope_hub`） |
| 列组织 / 索引远程 / 本机技能并对比 | [查询](references/query.md) |
| **本机管理控制台**（勾选改规划、多选升级 / 移出管理 / 批量发布；规划与发版分开） | [scripts/manage_console.py](scripts/manage_console.py)（`python skills/awam-skills/scripts/manage_console.py [--open]`） |
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
| 本机路径与版本字段 | `docs/repos.json`（gitignore）：`path` + `version`/`name`/`repo`/`version_updated`/`version_reason`；由 [upgrade_skill.py](scripts/upgrade_skill.py) 刷新/回写。`repos.example.json` 仅字段示例，非全量空清单 |

## 仓库命名

```
repo_name = name if name.endswith("-skill") else f"{name}-skill"
```

全小写 kebab-case。既有仓不改名。

## 布局选择（创建）

- **默认扁平**：根目录 `SKILL.md`
- **嵌套**：仅当用户明确需要根目录 CLI、一仓多技能、或 `CONTEXT.md` 时 → `skills/<name>/SKILL.md`

## 总流程

1. 判定意图：创建 / 升级 / 移出管理 / 发布 / 平台发布 / 查询 / 创建后发布（先创建再实现，发布另开或用户明确要求时再发）。
2. 读 [CONTEXT.md](../../CONTEXT.md) 与相关 ADR（`docs/adr/`）。
3. 按对应 reference 逐步执行；缺分类、发布目标平台等决策时**问用户**，不替用户拍板索引语义。
4. **升级**必须跑 [scripts/upgrade_skill.py](scripts/upgrade_skill.py)（见 [升级](references/upgrade.md)）：
   工作区须干净（否则中止报错）→ 升号并回写 `docs/repos.json` 版本字段 → **默认自动 commit**
   （不 push）；**禁止**手改 version / 只改 repos 字段。告知用户再按需 push / 发平台。
4b. **移出管理**必须跑 [scripts/unmanage_skill.py](scripts/unmanage_skill.py)（见 [移出管理](references/unmanage.md)）：
   从 plan / repos / state 去掉；**禁止**手删 JSON。不删本机目录；索引仓入库文件需用户确认后再 commit。
5. **任何发布动作之前，先跑 [scripts/preflight.py](scripts/preflight.py)**：
   `python skills/awam-skills/scripts/preflight.py --dir <技能仓>`。
   它一次查完「发出去就收不回」的本机问题：不是 git 仓 / 工作区有未提交改动 / 本地领先远程
   （发的内容与 GitHub 对不上）/ frontmatter 缺 `version`（魔搭硬要求）/ 打包根定不下来
   / 私密文件已被 git 跟踪 / 疑似本机绝对路径 / 索引仓副本与安装副本内容不一致。
   结果 `FAIL` 时**不要发布**，先处理。
6. 升号（已由脚本 commit）后按需 push 技能仓，再发平台（管理流程用 `upgrade_skill.py`；仅改文件可用
   [bump_version.py](scripts/bump_version.py)，但不回写台账、不 commit）。
7. **查询**必须跑 [scripts/query_skills.py](scripts/query_skills.py)，禁止用手搓 `gh`/扫目录代替。
8. **平台发布 / 规划更新**优先走 [scripts/release.py](scripts/release.py) 编排
   （内部调 preflight + 各 `publish_*.py` + `verify_publish.py`）；
   单平台仍可直接跑对应脚本，细节见 [references/platforms.md](references/platforms.md)。
   每完成一个平台发布，脚本会更新 `docs/publishing-plan.json` 的 `status` 并刷新视图。
   **凭据不要问用户**：由 [scripts/credentials.py](scripts/credentials.py) 按固定顺序自动查找（首选 `~/.workbuddy/secrets/<platform>.json`）；缺凭据时才提示用户去补哪个文件。排查用 `--show-credentials`（脱敏）。
   **依赖缺失先跑** [scripts/setup_env.py](scripts/setup_env.py)：魔搭发布走官方 SDK（`modelscope_hub`），首次使用需装依赖；脚本幂等，`--check` 只检测。
   **发布源必须是索引仓里的技能目录**，不要用 `~/.workbuddy/skills/` 下的安装副本 —— 那里混着宿主注入的元数据，且脱离 git 后安全兜底只剩黑名单。
9. 不主动 `git commit` / `git push` 索引仓，除非用户明确要求；技能仓的首次 push 仅在**发布**流程且检测到远程无提交时执行。

## 本机发现（可选）

本 Skill 只活在索引仓，不单独发组织仓。若要在其它工作区调用，把本目录链到 Agent skills 路径。

**推荐用 junction（一份真相，不会过期）**：

```powershell
New-Item -ItemType Junction -Force -Path "$env:USERPROFILE\.agents\skills\awam-skills" -Target "<本仓绝对路径>\skills\awam-skills"
```

**复制副本会过期**（2026-10-07 实际踩到：改了索引仓的 `platforms.md`，执行时用的是
`~/.workbuddy/skills/awam-skills` 下的旧副本，于是照着过时说明操作，白走一段路）。
如果确实用了复制，**改完索引仓后立刻同步**：

```bash
SRC="<索引仓>/skills/awam-skills"; DST="$HOME/.workbuddy/skills/awam-skills"
for item in SKILL.md references scripts templates; do cp -r "$SRC/$item" "$DST/"; done
rm -rf "$DST/scripts/__pycache__"
```

两类副本是否已对齐，`scripts/preflight.py` 会逐目录比对**内容哈希**报出来（它同时看
`~/.workbuddy/skills/` 与 `~/.agents/skills/` 两处），不用手工 diff。

## 发布提醒（漂移检测）

会话里对技能仓做了提交，或用户问「接下来发什么 / 哪些还没发」时，跑：

```bash
python skills/awam-skills/scripts/check_publish_drift.py
```

它对比三份数据——`docs/publishing-plan.json`（哪些平台 status=done）、本机私有的
`docs/repos.json`（克隆路径映射，已 gitignore；缺则从 `docs/repos.example.json` 复制）、
`docs/publishing-state.json`（各平台最近发布的 commit / version）——
列出**本地已前进但平台没跟上**的条目。检测到漂移时用 question **逐个问用户**是否现在发布；
确认后照常 preflight + 平台发布流程，不要默默替用户发。退出码 0=无漂移 / 1=有待发布。

- **ClawHub / 魔搭 / 豆包 / LobeHub / skills.sh / GitHub 收口**：对应 publish 脚本成功后自动写 state；
- **仍须网页手动的步骤**（LobeHub 首次「提交仓库」claim、豆包客户端导入）：完成后跑
  `check_publish_drift.py --record <技能 key> <platform>` 或豆包脚本 `--mark-done`；
- **新标 done 的平台**没有历史记录：`--record-baseline` 以当前 HEAD 批量回填基线
  （基线之后的新提交才算待发布）；
- 技能仓挪目录 / 换机器：只改本机 `docs/repos.json`，**不要提交**该文件。

## 快速对照

| 步骤 | 创建 | 升级 | 移出管理 | 发布 | 查询 | 平台发布 |
|------|------|------|----------|------|------|----------|
| 跑 `upgrade_skill.py` | — | ✅ **必跑** | — | — | — | 升号时优先 |
| 跑 `unmanage_skill.py` | — | — | ✅ **必跑** | — | — | — |
| 跑 `preflight.py` | — | — | — | ✅ **发布前必跑** | — | ✅ **发布前必跑** |
| `bump_version.py`（不回写台账） | — | 可选底层 | — | ✅ 升版本时 | — | ✅ 发魔搭/LobeHub/ClawHub 前 |
| 本地脚手架 | ✅ | — | — | — | — | — |
| `gh repo create awam-skills/<repo>` | ✅ 空仓 + remote | — | — | — | — | — |
| push 技能仓内容 | ❌ | ❌（用户确认后） | — | ✅ 仅当远程无提交 | — | — |
| Topics / description（`publish_github.py`） | ❌（可留到发布） | — | — | ✅ | — | ✅（编排内会跑） |
| 改 `skills.overrides.json` | ❌ | — | 仅 `--also-overrides` | ✅ | ❌ | — |
| 本地 `sync_skills.py` | ❌ | ❌ | ❌ | ❌（交给 Actions） | ❌ | — |
| 跑 `query_skills.py` | — | — | — | — | ✅ 必跑 | — |
| 发布到第三方平台 | — | 升号后可选 | — | — | — | ✅ `release.py` 或各 `publish_*.py` |
| `verify_publish.py` | — | — | — | — | — | ✅ 发布后复核 |
| 更新 `publishing-plan.json` + 跑 `plan_skills.py` | — | — | ✅ 脚本自动 | ✅ 建议 | — | ✅ 脚本自动刷新 |
| 回写 / 清理 `repos.json` | — | ✅ 版本字段（勿提交） | ✅ 删条目（勿提交） | — | — | — |
