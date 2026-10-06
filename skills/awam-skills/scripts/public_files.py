#!/usr/bin/env python3
"""发布用「公开文件集」判定：只把作者已经公开到 GitHub 的那部分内容打进发布包。

为什么必须有这个模块
--------------------
平台发布包是**公开物**。早期 publish_modelscope.py / publish_doubao.py 的打包器
只排除了 `.git` / `.workbuddy` / `__pycache__` 这类工程目录，于是把
`storage/`（真实待办数据）、`env.json`（本机路径、主机名）、`index.json`、
`web/*.log` 一并打了进去 —— 等于把本地私密数据传给平台。
（publish_clawhub.py 走 `git archive`，天然只含跟踪文件，所以它是干净的。）

规则（两层，从严）
------------------
1. **git 跟踪清单为准**：技能目录在 git 工作树里时，用 `git ls-files` 取跟踪文件。
   这正是作者选择公开的表面（也是平台发布的前置：技能仓须已在 GitHub 公开）。
2. **硬黑名单兜底**：即使被 git 跟踪也一律排除敏感目录 / 文件名 / 后缀。
   防止有人误把 storage/ 提交进仓库后再发布。
非 git 目录（例如 `~/.agents/skills/awam/xxx` 这种部署副本）退回按黑名单遍历。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# 目录级：命中即整棵子树排除
SENSITIVE_DIRS = {
    "storage",        # 待办/日志类真实数据
    ".workbuddy",     # 会话记忆
    ".git",
    ".cache",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

# 文件级：精确名字
SENSITIVE_NAMES = {
    "env.json",          # 本机环境探测结果（主机名、cwd、编辑器路径）
    "index.json",        # 派生索引（含全部待办内容）
    "credentials.json",
    "secrets.json",
    ".env",
}

# 后缀级
SENSITIVE_SUFFIXES = (".log", ".pyc", ".pyo", ".sqlite", ".sqlite3", ".db")


def _is_sensitive(rel: str) -> bool:
    parts = Path(rel).parts
    if any(seg in SENSITIVE_DIRS for seg in parts[:-1]):
        return True
    name = parts[-1]
    if name in SENSITIVE_NAMES:
        return True
    return name.lower().endswith(SENSITIVE_SUFFIXES)


def _git_tracked(skill_dir: Path) -> list[str] | None:
    """返回 git 跟踪的相对路径列表；不在 git 工作树里则返回 None。"""
    try:
        r = subprocess.run(
            ["git", "ls-files", "-z", "--", "."],
            cwd=str(skill_dir), capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = r.stdout.decode("utf-8", errors="replace")
    return [p for p in out.split("\0") if p]


def public_files(skill_dir: Path) -> tuple[list[Path], str, list[str]]:
    """列出可发布文件。

    返回 (文件绝对路径列表, 来源说明, 被排除的相对路径列表)。
    列表按相对路径排序，保证打包结果可复现。
    """
    skill_dir = Path(skill_dir)
    tracked = _git_tracked(skill_dir)
    excluded: list[str] = []
    selected: list[Path] = []

    if tracked is not None:
        source = "git 跟踪清单"
        for rel in sorted(tracked):
            if _is_sensitive(rel):
                excluded.append(rel)
                continue
            p = skill_dir / rel
            if p.is_file():
                selected.append(p)
    else:
        source = "黑名单遍历（非 git 目录）"
        for p in sorted(skill_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(skill_dir).as_posix()
            if _is_sensitive(rel):
                excluded.append(rel)
                continue
            selected.append(p)

    return selected, source, excluded


def describe(skill_dir: Path) -> str:
    """给日志用的一行摘要。"""
    files, source, excluded = public_files(skill_dir)
    msg = f"发布文件集：{len(files)} 个（来源：{source}）"
    if excluded:
        msg += f"；已排除 {len(excluded)} 个私密/工程文件"
    return msg
