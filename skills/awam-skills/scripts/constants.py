#!/usr/bin/env python3
"""共享常量：超时时间集中管理，避免各脚本散落魔法数字。

背景：发布链路里 `subprocess.run` / `urlopen` 的 timeout 原先散落成
20 / 30 / 60 / 120 / 300 / 600 多个裸数字，改一处漏一处。这里按语义收拢，
各脚本 `import constants` 后引用；数值与原实现一致，纯迁移不改变行为。
"""

from __future__ import annotations

# --- git / 文件操作（秒） ---
GIT_FAST = 20        # git remote get-url / rev-parse 等快速只读命令
GIT_OP = 30          # git status / ls-files 等常规命令
GIT_ARCHIVE = 60     # git archive 导出干净发布目录
TAR_EXTRACT = 120    # tar -x 解包

# --- clawhub CLI（秒） ---
CLI_WHOAMI = 60      # 登录态检查
CLI_INSPECT = 60     # 发布后 inspect 核对
CLI_VERIFY = 120     # 发布后 skill verify 轮询扫描/上线进度
CLI_PUBLISH = 600    # skill publish（大包上传可能耗时数十秒）
CLI_RUN_DEFAULT = 300  # clawhub run() 缺省超时

# --- skills CLI / skills.sh（秒） ---
NPX_SKILLS_LIST = 180   # npx skills add -l -y 发现性检查（含克隆公开仓）
NPX_SKILLS_ADD = 300    # npx skills add --all --json 触发收录（含克隆 + 全 agent 安装）
SKILLSSH_PAGE = 30      # skills.sh 页面探测单次 HTTP 超时（收录轮询用）

# --- 其它 ---
PLAN_SCRIPT = 120    # 调 plan_skills.py 刷新视图
