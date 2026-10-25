#!/usr/bin/env python3
"""技能版本台账：docs/skill-versions.json。

权威 version 仍在各技能仓 SKILL.md frontmatter；本文件是索引仓内可提交的快照，
供查询与升级流程对照。管理范围以 publishing-plan.json 的 skills 键为准。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import public_files  # noqa: E402
import runutil  # noqa: E402
import state_store  # noqa: E402

INDEX_ROOT = Path(__file__).resolve().parents[3]
VERSIONS_PATH = INDEX_ROOT / "docs" / "skill-versions.json"


def empty_ledger() -> dict:
    return {"schema_version": 1, "updated": "", "skills": {}}


def load_versions(path: Path = VERSIONS_PATH) -> dict:
    if not path.exists():
        return empty_ledger()
    return json.loads(path.read_text(encoding="utf-8"))


def save_versions(data: dict, path: Path = VERSIONS_PATH) -> bool:
    """原子写台账；失败返回 False。"""
    data = dict(data)
    data["updated"] = date.today().isoformat()
    data.setdefault("schema_version", 1)
    data.setdefault("skills", {})
    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_name, path)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        return False
    return True


def upsert_skill(
    path: Path,
    skill_key: str,
    *,
    version: str | None,
    name: str = "",
    repo: str = "",
    reason: str | None = None,
    updated: str | None = None,
) -> bool:
    """写入或更新单条技能版本；成功返回 True。有 version 时不保留 reason。"""
    data = load_versions(path)
    entry: dict = {
        "version": version,
        "name": name,
        "repo": repo,
        "updated": updated or date.today().isoformat(),
    }
    if not version and reason:
        entry["reason"] = reason
    data.setdefault("skills", {})[skill_key] = entry
    return save_versions(data, path)


def collect_from_plan(
    plan_path: Path | None = None,
    repos_path: Path | None = None,
) -> dict[str, dict]:
    """按 plan 技能键扫本机 frontmatter，返回 skills 映射（不落盘）。"""
    plan_path = plan_path or state_store.PLAN_PATH
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_skills = plan.get("skills") or {}

    repos: dict = {}
    try:
        repos = state_store.load_repos(repos_path or state_store.REPOS_PATH).get(
            "repos"
        ) or {}
    except FileNotFoundError:
        repos = {}
    except (OSError, json.JSONDecodeError):
        repos = {}

    today = date.today().isoformat()
    out: dict[str, dict] = {}
    for skill_key, meta in plan_skills.items():
        repo = (meta or {}).get("repo") or f"awam-skills/{skill_key}"
        local = (repos.get(skill_key) or {}).get("path")
        if not local:
            out[skill_key] = {
                "version": None,
                "name": "",
                "repo": repo,
                "updated": today,
                "reason": "本机未映射（docs/repos.json 无 path）",
            }
            continue
        skill_dir = Path(local)
        if not skill_dir.is_dir():
            out[skill_key] = {
                "version": None,
                "name": "",
                "repo": repo,
                "updated": today,
                "reason": "本机路径不存在",
            }
            continue
        root, note = public_files.find_skill_root(skill_dir)
        if root is None:
            out[skill_key] = {
                "version": None,
                "name": "",
                "repo": repo,
                "updated": today,
                "reason": f"找不到 SKILL.md（{note}）",
            }
            continue
        fm = runutil.read_frontmatter(skill_dir)
        ver = (fm.get("version") or "").strip() or None
        name = (fm.get("name") or "").strip()
        entry: dict = {
            "version": ver,
            "name": name,
            "repo": repo,
            "updated": today,
        }
        if not ver:
            entry["reason"] = "frontmatter 缺 version"
        out[skill_key] = entry
    return out


def refresh_ledger(path: Path = VERSIONS_PATH) -> dict:
    """全量刷新台账并落盘；返回写入后的数据。"""
    skills = collect_from_plan()
    data = {
        "schema_version": 1,
        "updated": date.today().isoformat(),
        "skills": skills,
    }
    if not save_versions(data, path):
        raise OSError(f"无法写入版本台账：{path}")
    return load_versions(path)
