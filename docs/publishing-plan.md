# 技能发布规划

> 权威数据：[publishing-plan.json](publishing-plan.json) · 视图由 `skills/awam-skills/scripts/plan_skills.py` 生成，请勿手改本文件 · 更新：2026-10-25 00:00

## 平台

| 平台 | 区域 | 通道 | 优先级 | 说明 |
|------|------|------|:------:|------|
| **GitHub（基础层）** | — | 组织仓 + 索引 | 基础 | 现有分发与索引基础；第三方平台发布以已公开的 GitHub 仓为前提 |
| **LobeHub** | 国际 | SKILL.md bundle / CLI | 主推 | 330k+ 技能、跨 Claude/Cursor 等，官方 CLI @lobehub/market-cli，分发量最大 |
| **魔搭 ModelScope** | 国内 | Skills Central / modelscope-skill-upload | 主推 | 中文开源生态最大，有现成上传 Skill 走 OpenAPI（zip→file_id→创建） |
| **豆包技能中心** | 国内 | 技能中心导入 | 主推 | 豆包电脑版侧边栏技能入口，可挂自定义技能，成本最低 |
| **ClawHub** | 国际 | clawhub CLI | 定向 | OpenClaw 官方 registry；quicker-connector 绑定此生态；社区含少量恶意样本需留意来源 |
| **AgentPowers** | 国际 | MCP 提交 | 可选 | 基于 MCP 标准、12+ 平台、8 层安全扫描，偏付费/高品质市场 |
| **skills.sh** | 国际 | skills CLI 安装遥测（npx skills add） | 主推 | find-skills 生态默认发现面；无提交通道，一次安装即收录，排名=安装量；触发成本≈0 |

## 梯队

- **最值得**：首选全平台铺开
- **实用**：适配运维 / Windows 向平台
- **需改造**：泛化改造后再发，否则留个人仓

## 技能 × 平台（实际状态）

图例：✅ 已发布　○ 未发布　◐ 需处理 / 微调　⚠ 受阻　— 不建议

| 技能 | 梯队 | GitHub（基础层） | LobeHub | 魔搭 ModelScope | 豆包技能中心 | ClawHub | AgentPowers | skills.sh |
|------|:----:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `ssh-deploy-skill` | 最值得 | ✅ | ✅ | ✅ | ✅ | ◐ | — | ✅ |
| `awam-git-skill` | 最值得 | ✅ | ○ | ○ | ○ | ◐ | ◐ | ✅ |
| `awam-shandianshuo-skill` | 需改造 | — | — | — | — | — | — | — |
| `github-organize` | 最值得 | ✅ | ○ | ○ | ◐ | ◐ | ◐ | ✅ |
| `windows-autostart-skill` | 实用 | ✅ | ◐ | ○ | ○ | ◐ | ○ | ○ |
| `letsencrypt-windows-skill` | 实用 | ✅ | ◐ | ○ | ○ | ◐ | ○ | ○ |
| `quicker-connector` | 实用 | ✅ | ◐ | ✅ | ◐ | ✅ | — | ✅ |
| `awam-windows-backup-skill` | 实用 | ✅ | ◐ | ◐ | ◐ | ◐ | — | ○ |
| `wiz-migration` | 需改造 | ✅ | — | — | — | — | — | — |
| `stock-hots-skill` | 需改造 | — | — | — | — | — | — | — |
| `awam-todo-skill` | 需改造 | ✅ | ✅ | ✅ | ○ | ✅ | — | ✅ |
| `awam-skill` | 需改造 | — | — | — | — | — | — | — |
| `awam-aliyun-skill` | 需改造 | — | — | — | — | — | — | — |
| `awam-ark-skill` | 需改造 | — | — | — | — | — | — | — |
| `stock-code-list-skill` | 需改造 | — | — | — | — | — | — | — |
| `awam-tax-skill` | 需改造 | — | — | — | — | — | — | — |
| `awam-tencent-cloud-skill` | 需改造 | — | — | — | — | — | — | — |
| `awam-tool-manager-skill` | 需改造 | — | — | — | — | — | — | — |
| `html-anim-video-maker-skill` | 需改造 | — | — | — | — | — | — | — |
| `html-ppt-maker-skill` | 需改造 | — | — | — | — | — | — | — |
| `material-collector-skill` | 需改造 | — | — | — | — | — | — | — |
| `pptx-maker-skill` | 需改造 | — | — | — | — | — | — | — |
| `pptx-maker-local-skill` | 需改造 | — | — | — | — | — | — | — |
| `screenshot-video-maker-skill` | 需改造 | — | — | — | — | — | — | — |
| `video-chapters-export-skill` | 需改造 | — | — | — | — | — | — | — |
| `video-content-cleaner-skill` | 需改造 | — | — | — | — | — | — | — |
| `video-publisher-skill` | 需改造 | — | — | — | — | — | — | — |
| `video-segment-semantics-skill` | 需改造 | — | — | — | — | — | — | — |
| `workspace-project-registry-skill` | 需改造 | — | — | — | — | — | — | — |
| `video-use-skill` | 需改造 | — | — | — | — | — | — | — |
| `a-stock-data-skill` | 需改造 | — | — | — | — | — | — | — |
| `economic-calendar-skill` | 需改造 | — | — | — | — | — | — | — |
| `lark-send-skill` | 需改造 | — | — | — | — | — | — | — |
| `limellm-config-skill` | 需改造 | — | — | — | — | — | — | — |
| `obs-skill` | 需改造 | — | — | — | — | — | — | — |
| `remote-tarball-install-skill` | 需改造 | — | — | — | — | — | — | — |
| `site-deploy-skill` | 需改造 | — | — | — | — | — | — | — |
| `toolport-skill` | 需改造 | — | — | — | — | — | — | — |
| `awam-pc-assets-skill` | 需改造 | — | — | — | — | — | — | — |
| `windows-clean-skill` | 需改造 | — | — | — | — | — | — | — |
| `windows-view-mode-skill` | 需改造 | — | — | — | — | — | — | — |
| `ximalaya-downloader-skill` | 需改造 | ✅ | — | — | — | — | — | — |

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
| skills.sh | 推荐发布 | ✅ 已发布 |

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
| skills.sh | 推荐发布 | ✅ 已发布 |

### awam-shandianshuo-skill · 需改造

- 仓库：`awam-skills/awam-shandianshuo-skill`
- 简介：读取与更新闪电说（Shandianshuo）模型配置：供应商/模型/槽位 CRUD、开通关闭、备份+原子写
- 规划：2026-10-08 已完成泛化改造（配置自动发现 SHANDIANSHUO_CONFIG→APPDATA→LOCALAPPDATA、schema v3 降级提示、文档去个人化，本地提交 9b9ed05）；但属 Awam 个人本机工具类技能，标记不发布（不上传 GitHub、不发布各平台）

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

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
| skills.sh | 推荐发布 | ✅ 已发布 |

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
| skills.sh | 可选 / 需微调 | ○ 未发布 |

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
| skills.sh | 可选 / 需微调 | ○ 未发布 |

### quicker-connector · 实用

- 仓库：`awam-skills/quicker-connector`
- 简介：OpenClaw 技能，连接 Quicker 自动化工具（读取动作库、自然语言匹配并执行动作）
- 规划：明确绑定 OpenClaw 生态 → ClawHub 首选；可选 ClawMart 付费变现

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| 魔搭 ModelScope | 可选 / 需微调 | ✅ 已发布 |
| 豆包技能中心 | 可选 / 需微调 | ◐ 需处理 / 微调 |
| ClawHub | 推荐发布 | ✅ 已发布 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 可选 / 需微调 | ✅ 已发布 |

### awam-windows-backup-skill · 实用

- 仓库：`awam-skills/awam-windows-backup-skill`
- 简介：Windows 本机 Kopia 增量备份与恢复（用户目录 + 系统配置导出）
- 规划：2026-10-08 完成参数化泛化（默认路径兜底技能根 _data、EXTRA_PROGRAM_DIRS 应用探测、模板去个人化）并补充新机 onboarding 文档，已提交并推送 e8f8042；定位国内：魔搭/豆包优先，国际平台可选

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| 魔搭 ModelScope | 推荐发布 | ◐ 需处理 / 微调 |
| 豆包技能中心 | 推荐发布 | ◐ 需处理 / 微调 |
| ClawHub | 可选 / 需微调 | ◐ 需处理 / 微调 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 可选 / 需微调 | ○ 未发布 |

### wiz-migration · 需改造

- 仓库：`awam-skills/wiz-migration`
- 简介：为知笔记数据迁移（导出、附件迁移、HTML 转 Markdown，自动修复附件路径）
- 规划：产品已停运、受众极小；除非转为通用笔记迁移再发。2026-10-08 完成公开仓最小清理（个人路径泛化 + WIZ_DATA_DIR 环境变量、migrator 占位符死逻辑修复、移除 __pycache__ 并补 .gitignore、修正 SKILL.md/测试/文档失效引用），提交 723d5f0 已推送；发布规划维持全 skip

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### stock-hots-skill · 需改造

- 仓库：`awam-skills/stock-hots-skill`
- 简介：多平台热门股票榜单获取与聚合（WzSLinker 八合一聚合页首选，同花顺/通达信/东方财富/财联社直连兜底）
- 规划：2026-10-08 完成三项结构优化（sources.json 数据源配置化、--check 时效自检、失败平台明确上报）并本地提交 f240402；依赖外部榜单接口且经个人代理，标记不发送：不上传 GitHub、不发布各平台，仅本地使用

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### awam-todo-skill · 需改造

- 仓库：`awam-skills/awam-todo-skill`
- 简介：个人待办管理：会话解析自然语言建待办 + 按日期 Markdown 存储 + 索引，支持依赖链/子任务/预案/逾期双出口/月度归档，配本地网页看板
- 规划：存储目录与编辑器已参数化（env --set storage_dir / editor.path，搬迁有校验与回滚）。2026-10-07 首次发布时打包器把 storage/、env.json、index.json 一起发上了魔搭，已修复为「只发 git 跟踪文件」（scripts/public_files.py）并替换线上内容、下载复核清除；豆包导入包已按新规则重新生成。lobehub 已于 2026-10-08 在网页完成「提交仓库」claim（CLI 无法代做，手动完成）

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 推荐发布 | ✅ 已发布 |
| 魔搭 ModelScope | 推荐发布 | ✅ 已发布 |
| 豆包技能中心 | 推荐发布 | ○ 未发布 |
| ClawHub | 推荐发布 | ✅ 已发布 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 推荐发布 | ✅ 已发布 |

### awam-skill · 需改造

- 仓库：`awam-skills/awam-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### awam-aliyun-skill · 需改造

- 仓库：`awam-skills/awam-aliyun-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-aliyun

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### awam-ark-skill · 需改造

- 仓库：`awam-skills/awam-ark-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-ark

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### stock-code-list-skill · 需改造

- 仓库：`awam-skills/stock-code-list-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-stock/stock-code-list

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### awam-tax-skill · 需改造

- 仓库：`awam-skills/awam-tax-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-tax

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### awam-tencent-cloud-skill · 需改造

- 仓库：`awam-skills/awam-tencent-cloud-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-tencent-cloud

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### awam-tool-manager-skill · 需改造

- 仓库：`awam-skills/awam-tool-manager-skill`
- 简介：统一工具管理器，维护本机工具名单，提供统一的工具注册、搜索、启动能力。作为 MCP Server 暴露给 AI 客户端，支持搜索工具、列出工具、启动工具、路由调用后端 MCP、管理后端进程等。调用入参：目标工具一律用 `tool_id…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-tool-manager

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### html-anim-video-maker-skill · 需改造

- 仓库：`awam-skills/html-anim-video-maker-skill`
- 简介：用 HTML/CSS/SVG 动画做动态片头或动态背景，并把动画逐帧渲染导出为 MP4
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/html-anim-video-maker

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### html-ppt-maker-skill · 需改造

- 仓库：`awam-skills/html-ppt-maker-skill`
- 简介：在有初步素材（截图/图片、文档、写好的文案、思路点子）时，用 AI 辅助独立产出一份可分享的自包含 HTML 幻灯片的技能；面向视频时按 references 的版式规范逐页验证到占满画幅
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/html-ppt-maker

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### material-collector-skill · 需改造

- 仓库：`awam-skills/material-collector-skill`
- 简介：根据用户给出的素材搜集范围，在网上检索无版权限制的图片、网页（默认）与短视频（可选），以 URL 形式记录并打标签（编号/类型/内容描述/来源/许可），产出 collection.md + collection.json 收集清单的技能
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/material-collector

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### pptx-maker-skill · 需改造

- 仓库：`awam-skills/pptx-maker-skill`
- 简介：在有初步素材（截图/图片、文档、写好的文案、思路点子）时，用 AI 辅助独立产出一份标准 PowerPoint 文件（.pptx）、生成后可在 PowerPoint/WPS 中手动修改的技能
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/pptx-maker

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### pptx-maker-local-skill · 需改造

- 仓库：`awam-skills/pptx-maker-local-skill`
- 简介：本机发现：pptx-maker-local（awam-video/skills/pptx-maker-local）
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/pptx-maker-local

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### screenshot-video-maker-skill · 需改造

- 仓库：`awam-skills/screenshot-video-maker-skill`
- 简介：在有视频创作灵感和初步素材时，用 AI 辅助一步步完成视频创建的技能
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/screenshot-video-maker

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### video-chapters-export-skill · 需改造

- 仓库：`awam-skills/video-chapters-export-skill`
- 简介：成片完成后，面向各平台（B站/YouTube等）自动生成分段章节时间轴与全片 SRT 字幕——基于配音分段时长与句级 ASR 时间轴计算章节/字幕时间，文本优先取脚本原文，输出可直接上传平台的产物并按平台规则校验；⑦ 质检通过后的可选阶段
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/video-chapters-export

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### video-content-cleaner-skill · 需改造

- 仓库：`awam-skills/video-content-cleaner-skill`
- 简介：转写稿 → 内容语义清洗（口误 / 说错重说 / 相邻重复 / 句内词级重复）+ 配音内容检查（voice-check：术语一致性/虚词/数字/段末 + LLM 可选语义检查）；产出保留稿 + 删除明细，须人工确认后进脚本；配合 vi…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/video-content-cleaner

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### video-publisher-skill · 需改造

- 仓库：`awam-skills/video-publisher-skill`
- 简介：视频成片完成后、面向 B 站等平台投稿的发布准备技能——自动生成标题候选、标签推荐、简介多版本、封面选择/生成建议、发布时间推荐，并衔接分段章节与字幕导出。当用户要求"准备发布""生成简介/标题/标签/封面""投稿文案""发布准备"，…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/video-publisher

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### video-segment-semantics-skill · 需改造

- 仓库：`awam-skills/video-segment-semantics-skill`
- 简介：视频/音频素材 → 素材语义层一键构建：抽音轨、引用式静音清洗、分片 ASR 转写（真实句级时间戳）、有声/无声区间（audio_segments）、语义清洗（-clean）、场景切分与关键帧对齐（video_scenes）、按脚本删…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/video-segment-semantics

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### workspace-project-registry-skill · 需改造

- 仓库：`awam-skills/workspace-project-registry-skill`
- 简介：工作空间项目清单——一个子工作空间 = 一个项目，记录目录/类型/进展阶段/发布计划/是否发布/主要交付件；进展类字段扫描产物推导，发布类字段人工登记；含新开项目（ADR-0012 骨架）与清理项目（只归档/不删文件）。CLI pro…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/skills/workspace-project-registry

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### video-use-skill · 需改造

- 仓库：`awam-skills/video-use-skill`
- 简介：Edit any video by conversation. Transcribe, cut, color grade, generate overlay animations, burn subtitles — for talki…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 awam-video/workspace/删句重排-探索/video-use

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### a-stock-data-skill · 需改造

- 仓库：`awam-skills/a-stock-data-skill`
- 简介：A股全栈数据工具包 — 覆盖行情(mootdx+腾讯+百度K线)、研报(东财+同花顺+iwencai)、信号(同花顺热点+北向+龙虎榜+解禁+行业)、资金面(融资融券+大宗交易+股东户数+分红+资金流分钟级+资金流120日)、新闻(东…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 A股全栈数据

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### economic-calendar-skill · 需改造

- 仓库：`awam-skills/economic-calendar-skill`
- 简介：本机发现：economic-calendar（economic-calendar/economic-calendar）
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 economic-calendar/economic-calendar

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### lark-send-skill · 需改造

- 仓库：`awam-skills/lark-send-skill`
- 简介：按本地保存的飞书（Lark）应用配置，给一个会话 ID（oc_ 群）或用户 ID（ou_ 用户）自动发消息。内置多应用路由：根据目标 ID 自动选出正确的飞书应用，完成权限获取后用该应用发送。当需要"给这个群/这个人发条飞书消息""新…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 lark-send

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### limellm-config-skill · 需改造

- 仓库：`awam-skills/limellm-config-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 litellm-config

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### obs-skill · 需改造

- 仓库：`awam-skills/obs-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 obs-skill

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### remote-tarball-install-skill · 需改造

- 仓库：`awam-skills/remote-tarball-install-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 remote-tarball-install

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### site-deploy-skill · 需改造

- 仓库：`awam-skills/site-deploy-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 site-deploy

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### toolport-skill · 需改造

- 仓库：`awam-skills/toolport-skill`
- 简介：>-
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 toolport

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### awam-pc-assets-skill · 需改造

- 仓库：`awam-skills/awam-pc-assets-skill`
- 简介：磁盘/目录空间分析与报表生成。当用户要求遍历某个盘符或目录（如 C 盘、D 盘、某项目目录）、从上到下判断各个文件/目录的作用，分析是否存在无用、异常、超大、重复的内容，并给出"清理/迁移归档/保留/卸载重装"等处理建议、生成空间分析…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 windows/awam-pc-assets

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### windows-clean-skill · 需改造

- 仓库：`awam-skills/windows-clean-skill`
- 简介：Windows C 盘临时文件安全清理。当用户要求清理 C 盘、清理临时文件、Temp 目录占用过大、磁盘空间不足、释放空间，或提到"C盘清理/磁盘清理/清理临时文件/空间不足"时使用。基于白名单目录的清理流程：先统计大小、用户确认后…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 windows/windows-clean

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### windows-view-mode-skill · 需改造

- 仓库：`awam-skills/windows-view-mode-skill`
- 简介：使用 WinSetView 安全地设置 Windows 资源管理器（Explorer）文件夹视图（大图标/详细信息/列表等）。技能初始化时自动检查并安装 WinSetView；支持按文件夹类型的全局默认、按单目录/特殊位置定向设置；底…
- 规划：2026-10-25 本机扫描纳入管理；发布安排暂定全 skip（尚未真实发布）。本地 windows/windows-view-mode

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 不建议 | — 不建议 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

### ximalaya-downloader-skill · 需改造

- 仓库：`awam-skills/ximalaya-downloader-skill`
- 简介：下载喜马拉雅免费专辑音频到本地。用本技能自带 Python 脚本走公开接口（无需登录），支持整专辑或区间下载为 m4a、默认生成 Markdown 清单、可选 ffmpeg 转 mp3；付费/VIP 集只跳过不绕过。在用户提供 xim…
- 规划：2026-10-25 本机扫描纳入；索引 README 已有 → github 记为已发布，其余平台暂定 skip。本地映射已写入 repos.json

| 平台 | 规划 | 实际 |
|------|:----:|:----:|
| GitHub（基础层） | 推荐发布 | ✅ 已发布 |
| LobeHub | 不建议 | — 不建议 |
| 魔搭 ModelScope | 不建议 | — 不建议 |
| 豆包技能中心 | 不建议 | — 不建议 |
| ClawHub | 不建议 | — 不建议 |
| AgentPowers | 不建议 | — 不建议 |
| skills.sh | 不建议 | — 不建议 |

