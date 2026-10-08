#!/usr/bin/env python3
"""发布脚本共享工具：UTF-8 子进程、技能 key 解析、frontmatter 读写、刷新规划视图。

Windows 下 `subprocess.run(..., text=True)` 默认按 GBK 解码，`plan_skills.py`
输出中文时会炸掉读取线程（stdout 变 None）——所有调计划脚本的地方必须走这里。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import constants  # noqa: F401  （超时）
import public_files
import state_store

INDEX_ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = INDEX_ROOT / "docs" / "publishing-plan.json"
PLAN_SCRIPT = Path(__file__).resolve().parent / "plan_skills.py"
OVERRIDES_PATH = INDEX_ROOT / "skills.overrides.json"

ORG = "awam-skills"
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:([-][0-9A-Za-z.-]+)?(?:[+][0-9A-Za-z.-]+)?)?$")
FM_BLOCK_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
VERSION_LINE_RE = re.compile(r"^(version:\s*)(.+)$", re.MULTILINE)


def log(msg: str) -> None:
    print(msg, flush=True)


def run_utf8(cmd: list[str], *, cwd: Path | str | None = None,
             timeout: int | None = None, env: dict | None = None,
             input_text: str | None = None,
             capture: bool = True) -> subprocess.CompletedProcess:
    """跑子进程并用 UTF-8 解码 stdout/stderr（errors=replace），避免 GBK 崩线程。

    - `capture=True`（默认）：捕获输出为 str
    - `capture=False`：继承当前终端（实时进度）；此时不要依赖返回的 stdout
    二进制管道（`git archive | tar`）请直接用 `subprocess.run` 字节模式，勿走本函数。
    """
    kwargs: dict = {
        "cwd": str(cwd) if cwd else None,
        "env": env,
        "timeout": timeout,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if capture:
        kwargs["capture_output"] = True
        if input_text is not None:
            kwargs["input"] = input_text
        else:
            kwargs["stdin"] = subprocess.DEVNULL
    else:
        if input_text is not None:
            kwargs["input"] = input_text
            kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def run_git(repo_dir: Path | str, *args: str,
            timeout: int | None = None) -> subprocess.CompletedProcess:
    """在指定仓跑 `git -C <repo> …`，UTF-8 捕获输出。"""
    return run_utf8(
        ["git", "-C", str(repo_dir), *args],
        timeout=timeout if timeout is not None else constants.GIT_OP,
    )


def refresh_plan_view() -> None:
    """调用 plan_skills.py 刷新人读视图。"""
    out = run_utf8(
        [sys.executable, str(PLAN_SCRIPT)],
        timeout=constants.PLAN_SCRIPT,
    )
    if out.returncode == 0:
        log(f"  视图已刷新：{(out.stdout or '').strip() or 'docs/publishing-plan.md'}")
    else:
        log(f"  ⚠ 刷新视图失败：{(out.stderr or out.stdout or '').strip()}")


def skill_root(skill_dir: Path) -> Path:
    root, note = public_files.find_skill_root(skill_dir)
    if root is None:
        raise SystemExit(f"找不到 SKILL.md：{note}")
    return root


def read_frontmatter(skill_dir: Path) -> dict[str, str]:
    """读打包根 SKILL.md 的 frontmatter 标量（单行）。"""
    md = skill_root(skill_dir) / "SKILL.md"
    text = md.read_text(encoding="utf-8", errors="replace")
    m = FM_BLOCK_RE.match(text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km and not line.startswith((" ", "\t")):
            fm[km.group(1)] = km.group(2).strip().strip("'\"")
    return fm


def origin_full_name(skill_dir: Path) -> str | None:
    """返回 origin 的 owner/repo（无 .git 后缀）；失败返回 None。"""
    out = run_utf8(
        ["git", "-C", str(skill_dir), "remote", "get-url", "origin"],
        timeout=constants.GIT_FAST,
    )
    if out.returncode != 0:
        return None
    url = (out.stdout or "").strip()
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def resolve_skill_key(skill_dir: Path, explicit: str | None = None,
                      plan_path: Path = PLAN_PATH) -> str | None:
    """解析 publishing-plan.json 里的技能 key。

    顺序：显式 --skill → repos.json 路径反查 → frontmatter name / name-skill → origin repo 名。
    """
    if explicit:
        return explicit
    skill_dir = Path(skill_dir).resolve()
    repos = {}
    try:
        repos = json.loads(state_store.REPOS_PATH.read_text(encoding="utf-8")).get("repos") or {}
    except (OSError, json.JSONDecodeError):
        pass
    for key, meta in repos.items():
        p = (meta or {}).get("path")
        if p and Path(p).resolve() == skill_dir:
            return key

    fm = read_frontmatter(skill_dir)
    name = fm.get("name", "")
    candidates = []
    if name:
        candidates.extend([name, f"{name}-skill"])
    full = origin_full_name(skill_dir)
    if full and "/" in full:
        candidates.append(full.split("/", 1)[1])

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        skills = plan.get("skills") or {}
    except (OSError, json.JSONDecodeError):
        return candidates[0] if candidates else None
    for c in candidates:
        if c in skills:
            return c
    for c in candidates:
        for k in skills:
            if k == c or k.endswith(c) or c.endswith(k):
                return k
    return candidates[0] if candidates else None


def parse_semver(ver: str) -> tuple[int, int, int, str] | None:
    m = SEMVER_RE.match((ver or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or ""


def bump_semver(ver: str, part: str) -> str:
    parsed = parse_semver(ver)
    if not parsed:
        raise SystemExit(f"当前 version `{ver}` 不是 x.y.z，无法自动 bump")
    major, minor, patch, _pre = parsed
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        raise SystemExit(f"未知 bump 段：{part}（用 major/minor/patch）")
    return f"{major}.{minor}.{patch}"


def set_frontmatter_version(md_path: Path, new_version: str) -> bool:
    """改 SKILL.md / 镜像里的 version 行；改了返回 True。"""
    text = md_path.read_text(encoding="utf-8")
    if not VERSION_LINE_RE.search(text):
        return False
    new_text, n = VERSION_LINE_RE.subn(rf"\g<1>{new_version}", text, count=1)
    if n == 0 or new_text == text:
        return False
    # 保持原换行风格
    newline = "\r\n" if "\r\n" in text else "\n"
    if newline == "\r\n":
        new_text = new_text.replace("\r\n", "\n").replace("\n", "\r\n")
    md_path.write_text(new_text, encoding="utf-8", newline="")
    return True
