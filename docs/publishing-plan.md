# 技能发布规划

> 权威数据：[publishing-plan.json](publishing-plan.json) · 视图由 `skills/awam-skills/scripts/plan_skills.py` 生成，请勿手改本文件 · 更新：2026-10-06

## 平台

| 平台 | 区域 | 通道 | 优先级 | 说明 |
|------|------|------|:------:|------|
| **GitHub（基础层）** | — | 组织仓 + 索引 | 基础 | 现有分发与索引基础；第三方平台发布以已公开的 GitHub 仓为前提 |
| **LobeHub** | 国际 | SKILL.md bundle / CLI | 主推 | 330k+ 技能、跨 Claude/Cursor 等，官方 CLI @lobehub/market-cli，分发量最大 |
| **魔搭 ModelScope** | 国内 | Skills Central / modelscope-skill-upload | 主推 | 中文开源生态最大，有现成上传 Skill 走 OpenAPI（zip→file_id→创建） |
| **豆包技能中心** | 国内 | 技能中心导入 | 主推 | 豆包电脑版侧边栏技能入口，可挂自定义技能，成本最低 |
| **ClawHub** | 国际 | clawhub CLI | 定向 | OpenClaw 官方 registry；quicker-connector 绑定此生态；社区含少量恶意样本需留意来源 |
| **AgentPowers** | 国际 | MCP 提交 | 可选 | 基于 MCP 标准、12+ 平台、8 层安全扫描，偏付费/高品质市场 |

## 梯队

- **最值得**：首选全平台铺开
- **实用**：适配运维 / Windows 向平台
- **需改造**：泛化改造后再发，否则留个人仓

## 技能 × 平台（实际状态）

图例：✅ 已发布　○ 未发布　◐ 需处理 / 微调　⚠ 受阻　— 不建议

| 技能 | 梯队 | GitHub（基础层） | LobeHub | 魔搭 ModelScope | 豆包技能中心 | ClawHub | AgentPowers |
|------|:----:|:---:|:---:|:---:|:---:|:---:|:---:|
| `ssh-deploy-skill` | 最值得 | ✅ | ✅ | ✅ | ✅ | ◐ | — |
| `awam-git-skill` | 最值得 | ✅ | ○ | ○ | ○ | ◐ | ◐ |
| `awam-shandianshuo-skill` | 需改造 | ○ | — | ○ | ○ | — | — |
| `github-organize` | 最值得 | ✅ | ○ | ○ | ◐ | ◐ | ◐ |
| `windows-autostart-skill` | 实用 | ✅ | ◐ | ○ | ○ | ◐ | ○ |
| `letsencrypt-windows-skill` | 实用 | ✅ | ◐ | ○ | ○ | ◐ | ○ |
| `quicker-connector` | 实用 | ✅ | ◐ | ◐ | ◐ | ✅ | — |
| `awam-windows-backup-skill` | 需改造 | ✅ | ◐ | ◐ | ◐ | ◐ | — |
| `wiz-migration` | 需改造 | ✅ | — | — | — | — | — |
| `stock-hots-skill` | 需改造 | ○ | ○ | ○ | ○ | — | — |
| `awam-todo-skill` | 需改造 | ✅ | — | ○ | ○ | — | — |

## 明细

### ssh-deploy-skill · 最值得

- 仓库：`awam-skills/ssh-deploy-skill`
- 简介：通用 SSH 部署 / 多服务器 / 批量 / 文件传输 / Docker·MySQL·Nginx 模板 / 国内镜像优化
- 规划：运维刚需、跨平台通用，最优先铺开

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 推荐发布 | ✅ 已发布 |
| 魔搭 ModelScope | 推荐发布 | ✅ 已发布 |
| 豆包技能中心 | 推荐发布 | ✅ 已发布 |
| ClawHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| AgentPowers | 推荐发布 | — 不建议 |

### awam-git-skill · 最值得

- 仓库：`awam-skills/awam-git-skill`
- 简介：Git 提交规范（Conventional Commits + 中文提交信息）
- 规划：纯通用开发习惯，任何 agent 直接可用

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 推荐发布 | ○ 未发布 |
| 魔搭 ModelScope | 推荐发布 | ○ 未发布 |
| 豆包技能中心 | 推荐发布 | ○ 未发布 |
| ClawHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| AgentPowers | 可选 / 需微调 | ◐ 需处理 / 微调 |

### awam-shandianshuo-skill · 需改造

- 仓库：`awam-skills/awam-shandianshuo-skill`
- 简介：读取与更新闪电说（Shandianshuo）模型配置：供应商/模型/槽位 CRUD、开通关闭、备份+原子写
- 规划：绑定闪电说产品配置路径与 v3 schema；脚本已支持 --config 参数化，正式发布前建议再泛化

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ○ 未发布 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 推荐发布 | ○ 未发布 |
| 豆包技能中心 | 推荐发布 | ○ 未发布 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |

### github-organize · 最值得

- 仓库：`awam-skills/github-organize`
- 简介：GitHub 仓库 / 星标整理（找 fork、归档案、可取消/归类星标）
- 规划：开发者高频需求，通用性强

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 推荐发布 | ○ 未发布 |
| 魔搭 ModelScope | 推荐发布 | ○ 未发布 |
| 豆包技能中心 | 可选 / 需微调 | ◐ 需处理 / 微调 |
| ClawHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| AgentPowers | 可选 / 需微调 | ◐ 需处理 / 微调 |

### windows-autostart-skill · 实用

- 仓库：`awam-skills/windows-autostart-skill`
- 简介：Windows 自启动管理（自带 windows-autostart.ps1 CLI，JSON 输出）
- 规划：有 CLI、生态契合，适合运维 / Windows 向平台

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| 魔搭 ModelScope | 推荐发布 | ○ 未发布 |
| 豆包技能中心 | 推荐发布 | ○ 未发布 |
| ClawHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| AgentPowers | 推荐发布 | ○ 未发布 |

### letsencrypt-windows-skill · 实用

- 仓库：`awam-skills/letsencrypt-windows-skill`
- 简介：Windows TLS 证书（win-acme / Posh-ACME / Certify The Web 三选路由，HTTP-01/DNS-01）
- 规划：同类稀缺、差异化价值高

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| 魔搭 ModelScope | 推荐发布 | ○ 未发布 |
| 豆包技能中心 | 推荐发布 | ○ 未发布 |
| ClawHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| AgentPowers | 推荐发布 | ○ 未发布 |

### quicker-connector · 实用

- 仓库：`awam-skills/quicker-connector`
- 简介：OpenClaw 技能，连接 Quicker 自动化工具（读取动作库、自然语言匹配并执行动作）
- 规划：明确绑定 OpenClaw 生态 → ClawHub 首选；可选 ClawMart 付费变现

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| 魔搭 ModelScope | 可选 / 需微调 | ◐ 需处理 / 微调 |
| 豆包技能中心 | 可选 / 需微调 | ◐ 需处理 / 微调 |
| ClawHub | 推荐发布 | ✅ 已发布 |
| AgentPowers | 不建议 | — 不建议 |

### awam-windows-backup-skill · 需改造

- 仓库：`awam-skills/awam-windows-backup-skill`
- 简介：Windows 本机 Kopia 增量备份与恢复（用户目录 + 系统配置导出）
- 规划：绑定个人目录/配置，需把路径、仓库配置参数化泛化后再发

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| 魔搭 ModelScope | 可选 / 需微调 | ◐ 需处理 / 微调 |
| 豆包技能中心 | 可选 / 需微调 | ◐ 需处理 / 微调 |
| ClawHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| AgentPowers | 不建议 | — 不建议 |

### wiz-migration · 需改造

- 仓库：`awam-skills/wiz-migration`
- 简介：为知笔记数据迁移（导出、附件迁移、HTML 转 Markdown，自动修复附件路径）
- 规划：产品已停运、受众极小；除非转为通用笔记迁移再发

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |

### stock-hots-skill · 需改造

- 仓库：`awam-skills/stock-hots-skill`
- 简介：多平台热门股票榜单获取与聚合（WzSLinker 八合一聚合页首选，同花顺/通达信/东方财富/财联社直连兜底）
- 规划：依赖外部榜单页/接口且部分平台直连有反爬；发布前建议把数据源参数化泛化

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ○ 未发布 |
| LobeHub | 可选 / 需微调 | ○ 未发布 |
| 魔搭 ModelScope | 可选 / 需微调 | ○ 未发布 |
| 豆包技能中心 | 可选 / 需微调 | ○ 未发布 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |

### awam-todo-skill · 需改造

- 仓库：`awam-skills/awam-todo-skill`
- 简介：个人待办管理：会话解析自然语言建待办 + 按日期 Markdown 存储 + 索引，支持依赖链/子任务/预案/逾期双出口/月度归档，配本地网页看板
- 规划：绑定本机存储目录与 Windows 能力（Cursor 打开工作空间、工作空间路径）；发布到平台前需把存储路径与系统依赖参数化泛化

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 推荐发布 | ○ 未发布 |
| 豆包技能中心 | 推荐发布 | ○ 未发布 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |

