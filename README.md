# awam-skills

罗列并整理我（Awam M Wang）创建的 AI 技能（Skill），按用途分类，便于查找与选用。

> 本目录由 GitHub Actions 定时从 `awam-skills` 组织仓库，以及个人账号（awamwang）带 `skill` Topic 的仓库自动同步。

本仓库另含流程 Skill：[`skills/awam-skills`](skills/awam-skills/SKILL.md)（按个人约定**创建** / **发布** / **查询**技能）。

## 技能目录

### 桌面自动化

| 技能 | 简介 |
|------|------|
| [quicker-connector](https://github.com/awam-skills/quicker-connector) | OpenClaw 技能，连接 Quicker 自动化工具；支持读取动作库、自然语言匹配并执行动作 |

### 运维部署

| 技能 | 简介 |
|------|------|
| [ssh-deploy-skill](https://github.com/awam-skills/ssh-deploy-skill) | 通用 SSH 远程部署工具；多服务器管理、批量执行、文件传输，以及 Docker / MySQL / Nginx 等安装模板，并针对国内镜像做了优化 |

### 数据迁移

| 技能 | 简介 |
|------|------|
| [wiz-migration](https://github.com/awam-skills/wiz-migration) | 为知笔记数据迁移技能；引导导出、附件迁移、HTML 转 Markdown，并自动修复附件路径 |

### GitHub 整理

| 技能 | 简介 |
|------|------|
| [github-organize](https://github.com/awam-skills/github-organize) | 审计并整理个人 GitHub 仓库与星标；找出无新提交的 fork、建议归档的自有仓、可取消/归类的星标，支持导出 Excel 并按表执行处理 |

### 开发工具

| 技能 | 简介 |
|------|------|
| [awam-git-skill](https://github.com/awam-skills/awam-git-skill) | 为仓库安装 Awam Git 提交规范（Conventional Commits + 中文提交信息）；写入 .cursor/rules/git-commit.mdc 与 .cursorrules，供 Agent 与 Source Control ✨ 共用 |

### 备份恢复

| 技能 | 简介 |
|------|------|
| [awam-windows-backup-skill](https://github.com/awam-skills/awam-windows-backup-skill) | Windows 本机 Kopia 增量备份与恢复（用户目录 + 系统配置导出） |

### 影音图像

| 技能 | 简介 |
|------|------|
| [ximalaya-downloader-skill](https://github.com/awam-skills/ximalaya-downloader-skill) | 下载喜马拉雅免费专辑音频到本地。用自带 Python 脚本走公开接口，支持整专辑或区间下载为 m4a、默认生成 Markdown 清单、可选 ffmpeg 转 mp3；付费/VIP 集只跳过不绕过。 |

### 其他

| 技能 | 简介 |
|------|------|
| [letsencrypt-windows-skill](https://github.com/awam-skills/letsencrypt-windows-skill) | Issue, renew, and maintain Let's Encrypt TLS certificates on Windows via ACME. Routes among win-acme, Posh-ACME, and Certify The Web; covers HTTP-01/DNS-01,… |
| [windows-autostart-skill](https://github.com/awam-skills/windows-autostart-skill) | Create, inspect, and remove current-user Windows logon/scheduled startup entries through the repo's windows-autostart.ps1 CLI (JSON output). |

## 说明

- 各技能的安装方式、配置与用法见对应仓库的 README / `SKILL.md`
- 本仓库以技能索引为主；另含 `skills/awam-skills`（创建 / 发布 / 查询个人技能的流程 Skill）
- 分类可在 `skills.overrides.json` 中指定；也可给仓库打上 `cat-*` 类 Topic（见该文件）
- 索引 README 由 GitHub Actions 同步生成；发布流程勿与本地 `sync_skills.py` 同时改 README

## License

各技能仓库采用各自声明的许可证，请以对应仓库为准。
