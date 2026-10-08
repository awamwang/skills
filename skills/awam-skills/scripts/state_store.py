#!/usr/bin/env python3
"""发布状态记录：每个技能 × 平台最近一次发布时的 commit / 版本。

check_publish_drift.py 用它判断「本地又改了，哪些平台没跟上」；
publish_*.py 发布成功后调用 record_publish_from_repo 自动记录；
LobeHub 这类网页手动发布的平台，用 check_publish_drift.py --record 补记。

状态文件 docs/publishing-state.json 是机器写的自有格式，原子落盘
（临时文件 + os.replace）——区别于 publishing-plan.json 的人工排版，
后者必须走 plan_store.py 就地更新，见各自顶部说明。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402  （共享超时等常量：见 constants.py）
import public_files  # noqa: E402  （打包根定位：见 public_files.py）

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = INDEX_ROOT / "docs" / "publishing-state.json"
REPOS_PATH = INDEX_ROOT / "docs" / "repos.json"
PLAN_PATH = INDEX_ROOT / "docs" / "publishing-plan.json"


def load_state(path: Path = STATE_PATH) -> dict:
    """读状态文件；不存在时返回空骨架（首次 --record 前的状态）。"""
    if not path.exists():
        return {"schema_version": 1, "updated": "", "skills": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def git_head(repo_dir: Path) -> str | None:
    """当前 HEAD 短哈希；不是 git 仓 / 尚无提交时返回 None。"""
    import runutil
    out = runutil.run_git(repo_dir, "rev-parse", "--short", "HEAD",
                          timeout=constants.GIT_FAST)
    if out.returncode != 0:
        return None
    return (out.stdout or "").strip() or None


def frontmatter_version(skill_dir: Path) -> str | None:
    """SKILL.md frontmatter 的 version；打包根自动定位，嵌套布局也能读。"""
    root, _note = public_files.find_skill_root(skill_dir)
    if root is None:
        return None
    text = (root / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^version:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def record_publish(state_path: Path, skill_key: str, platform: str,
                   commit: str, version: str | None = None,
                   baseline: bool = False, at: str | None = None) -> bool:
    """记录一次发布，原子写；写失败返回 False（调用方只提示，不中断发布）。"""
    state = load_state(state_path)
    skill = state.setdefault("skills", {}).setdefault(skill_key, {})
    entry: dict = {
        "commit": commit,
        "version": version,
        "at": at or date.today().isoformat(),
    }
    if baseline:
        entry["baseline"] = True  # 回填的基线：之后的差异才算待发布
    skill[platform] = entry
    state["updated"] = date.today().isoformat()
    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(state_path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_name, state_path)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        return False
    return True


def record_publish_from_repo(state_path: Path, skill_dir: Path, skill_key: str,
                             platform: str, baseline: bool = False) -> bool:
    """发布脚本 / --record 用：自动取当前 HEAD 与 frontmatter version 记录。"""
    commit = git_head(skill_dir)
    if not commit:
        return False
    return record_publish(state_path, skill_key, platform, commit,
                          frontmatter_version(skill_dir), baseline=baseline)
