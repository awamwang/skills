#!/usr/bin/env python3
"""发布用「公开文件集」判定：只把作者已经公开到 GitHub 的那部分内容打进发布包。

为什么必须有这个模块
--------------------
平台发布包是**公开物**。早期 publish_modelscope.py / publish_doubao.py 的打包器
只排除了 `.git` / `.workbuddy` / `__pycache__` 这类工程目录，于是把
`storage/`（真实待办数据）、`env.json`（本机路径、主机名）、`index.json`、
`web/*.log` 一并打了进去 —— 等于把本地私密数据传给平台。
（publish_clawhub.py 走 `git archive`，天然只含跟踪文件，所以它是干净的；
但它**非 git 目录时的复制回退分支**有同一个漏洞，现已一并改为走本模块。）

规则（两层，从严）
------------------
1. **git 跟踪清单为准**：技能目录在 git 工作树里时，用 `git ls-files` 取跟踪文件。
   这正是作者选择公开的表面（也是平台发布的前置：技能仓须已在 GitHub 公开）。
2. **硬黑名单兜底**：即使被 git 跟踪也一律排除敏感目录 / 文件名 / 后缀。
   防止有人误把 storage/ 提交进仓库后再发布。
非 git 目录（例如 `~/.workbuddy/skills/xxx` 这种安装副本）退回按黑名单遍历，
此时**兜底不再是「作者已公开的表面」而是猜测**，调用方应把该情况提示给用户
（`describe()` 会自动附警告）。发布源应始终是索引仓里的技能目录。
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
    "_user_meta.json",   # 宿主往「已安装副本」里注入的元数据，不属于技能内容
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


def find_skill_root(repo_dir: Path) -> tuple[Path | None, str]:
    """定位 SKILL.md 所在目录（= 打包根），返回 (目录, 说明)。

    **为什么必须区分「仓库根」与「打包根」**：平台要求 zip 根目录恰好 1 个 `SKILL.md`。
    嵌套布局（`skills/<name>/SKILL.md`）的仓库若按仓库根打包，zip 根下就没有 SKILL.md，
    魔搭会直接报「zip 根目录的 SKILL.md 必须恰好 1 个，当前 0 个」，豆包导入也会失配。
    （2026-10-07 发现：`starup-skill` 仓的 `skills/windows-autostart/SKILL.md` 就属于这种，
    当时的三个打包器都是按仓库根取路径 —— 也就是说这个技能根本发不出去。）

    顺序：仓库根有 SKILL.md → 用它；否则 `skills/*/SKILL.md`；再退到 `<任意子目录>/SKILL.md`。
    """
    repo_dir = Path(repo_dir)
    if (repo_dir / "SKILL.md").is_file():
        return repo_dir, "扁平布局（SKILL.md 在仓库根）"

    nested = sorted(p.parent for p in repo_dir.glob("skills/*/SKILL.md"))
    if not nested:
        nested = sorted(
            p.parent for p in repo_dir.glob("*/SKILL.md")
            if p.parent.name not in (".git", "node_modules")
        )
    if len(nested) == 1:
        return nested[0], f"嵌套布局（{nested[0].relative_to(repo_dir).as_posix()}/SKILL.md）"
    if len(nested) > 1:
        names = ", ".join(p.relative_to(repo_dir).as_posix() for p in nested)
        return None, f"一个仓库里有多个 SKILL.md，无法自动判定打包根：{names}（请把技能拆成一仓一技能）"
    return None, "找不到 SKILL.md（仓库根与 skills/*/ 下都没有）"


def pack_files(repo_dir: Path) -> tuple[list[Path], Path | None, str, list[str], list[str]]:
    """按「打包根」整理公开文件。

    返回 (打包根下的文件, 打包根, 来源说明, 被排除的敏感文件, 打包根之外被跳过的文件)。
    文件为绝对路径，列表按相对打包根的路径排序，保证打包结果可复现。
    """
    repo_dir = Path(repo_dir)
    root, note = find_skill_root(repo_dir)
    files, source, excluded = public_files(repo_dir)
    if root is None:
        return [], None, note, excluded, []

    inside: list[Path] = []
    outside: list[str] = []
    for p in files:
        try:
            p.relative_to(root)
        except ValueError:
            outside.append(p.relative_to(repo_dir).as_posix())
            continue
        inside.append(p)
    inside.sort(key=lambda p: p.relative_to(root).as_posix())
    return inside, root, f"{note}；{source}", excluded, sorted(outside)


def pack_rel(p: Path, root: Path) -> str:
    """打包用的相对路径（正斜杠），相对打包根。"""
    return Path(p).relative_to(root).as_posix()


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
    """给日志用的一行摘要（含打包根、被排除项、非 git 警告）。"""
    files, root, source, excluded, outside = pack_files(skill_dir)
    msg = f"发布文件集：{len(files)} 个（{source}）"
    if excluded:
        msg += f"；已排除 {len(excluded)} 个私密/工程文件"
    if outside:
        msg += f"；打包根外跳过 {len(outside)} 个（如 {outside[0]}）"
    if root is None:
        msg += f"\n  ❌ 无法确定打包根：{source}"
    elif _git_tracked(Path(skill_dir)) is None:
        msg += (
            "\n  ⚠ 该目录不在 git 工作树里，只能按黑名单兜底 —— "
            "无法保证没夹带本机数据。发布源请用索引仓里的技能目录，不要用 ~/.workbuddy/skills 下的安装副本"
        )
    return msg
