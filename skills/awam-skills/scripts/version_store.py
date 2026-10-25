#!/usr/bin/env python3
"""技能版本管理数据：写在 docs/repos.json 各 repo 记录上。

权威 version 仍在各技能仓 SKILL.md frontmatter。本机私有 repos.json（gitignore）
在 path 之外保存 version / name / repo / version_updated / version_reason，
供升级流程对照。管理范围以 publishing-plan.json 的 skills 键为准。

字段（见 docs/repos.example.json）：
  path             本机克隆路径（null = 未找到）
  version          frontmatter 快照（null = 读不到）
  name             frontmatter name
  repo             GitHub owner/repo（通常来自 publishing-plan）
  version_updated  版本字段最近刷新日
  version_reason   version 为 null 时的原因（有 version 时不写）
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import public_files  # noqa: E402
import runutil  # noqa: E402
import state_store  # noqa: E402

INDEX_ROOT = Path(__file__).resolve().parents[3]
REPOS_PATH = state_store.REPOS_PATH
REPOS_EXAMPLE_PATH = state_store.REPOS_EXAMPLE_PATH

# 版本相关字段名（写入 repo 记录）
VERSION_FIELDS = ("version", "name", "repo", "version_updated", "version_reason")


def empty_ledger() -> dict:
    """与旧 skill-versions 形状兼容的视图：{updated, skills: {key: {...}}}。"""
    return {"schema_version": 1, "updated": "", "skills": {}}


def _version_view_from_repos(repos_doc: dict) -> dict:
    skills: dict[str, dict] = {}
    for key, meta in (repos_doc.get("repos") or {}).items():
        meta = meta or {}
        entry: dict = {
            "version": meta.get("version"),
            "name": meta.get("name") or "",
            "repo": meta.get("repo") or "",
            "updated": meta.get("version_updated") or "",
        }
        if not entry["version"] and meta.get("version_reason"):
            entry["reason"] = meta["version_reason"]
        skills[key] = entry
    return {
        "schema_version": 1,
        "updated": repos_doc.get("updated") or "",
        "skills": skills,
    }


def load_versions(path: Path | None = None) -> dict:
    """从 repos.json 读出版本视图（兼容 upgrade_skill --list）。"""
    repos_path = path or REPOS_PATH
    try:
        doc = state_store.load_repos(repos_path)
    except FileNotFoundError:
        return empty_ledger()
    except (OSError, json.JSONDecodeError):
        return empty_ledger()
    return _version_view_from_repos(doc)


def apply_version_fields(
    entry: dict,
    *,
    version: str | None,
    name: str = "",
    repo: str = "",
    reason: str | None = None,
    updated: str | None = None,
    keep_path: bool = True,
) -> dict:
    """合并版本字段到一条 repo 记录；返回新 dict。"""
    out = dict(entry or {})
    if not keep_path and "path" not in out:
        out["path"] = None
    out["version"] = version
    out["name"] = name or ""
    if repo:
        out["repo"] = repo
    elif "repo" not in out:
        out["repo"] = ""
    out["version_updated"] = updated or date.today().isoformat()
    if version:
        out.pop("version_reason", None)
    elif reason:
        out["version_reason"] = reason
    else:
        out.pop("version_reason", None)
    return out


def upsert_skill(
    skill_key: str,
    *,
    version: str | None,
    name: str = "",
    repo: str = "",
    reason: str | None = None,
    updated: str | None = None,
    path: Path | None = None,
) -> bool:
    """更新 repos.json 中单条技能的版本字段。"""
    repos_path = path or REPOS_PATH
    try:
        doc = state_store.load_repos(repos_path)
    except FileNotFoundError:
        doc = {
            "schema_version": 1,
            "updated": "",
            "note": "本机私有（已 gitignore）：模板见 repos.example.json",
            "repos": {},
        }
    repos = doc.setdefault("repos", {})
    repos[skill_key] = apply_version_fields(
        repos.get(skill_key) or {"path": None},
        version=version,
        name=name,
        repo=repo,
        reason=reason,
        updated=updated,
    )
    return state_store.save_repos(doc, repos_path)


def collect_from_plan(
    plan_path: Path | None = None,
    repos_path: Path | None = None,
) -> dict[str, dict]:
    """按 plan 技能键扫本机 frontmatter，返回将写入 repos 的版本字段映射。"""
    plan_path = plan_path or state_store.PLAN_PATH
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_skills = plan.get("skills") or {}

    repos: dict = {}
    try:
        repos = state_store.load_repos(repos_path or REPOS_PATH).get("repos") or {}
    except FileNotFoundError:
        repos = {}
    except (OSError, json.JSONDecodeError):
        repos = {}

    today = date.today().isoformat()
    out: dict[str, dict] = {}
    for skill_key, meta in plan_skills.items():
        gh_repo = (meta or {}).get("repo") or f"awam-skills/{skill_key}"
        existing = repos.get(skill_key) or {}
        local = existing.get("path")
        if not local:
            out[skill_key] = {
                "version": None,
                "name": "",
                "repo": gh_repo,
                "updated": today,
                "reason": "本机未映射（docs/repos.json 无 path）",
            }
            continue
        skill_dir = Path(local)
        if not skill_dir.is_dir():
            out[skill_key] = {
                "version": None,
                "name": "",
                "repo": gh_repo,
                "updated": today,
                "reason": "本机路径不存在",
            }
            continue
        root, note = public_files.find_skill_root(skill_dir)
        if root is None:
            out[skill_key] = {
                "version": None,
                "name": "",
                "repo": gh_repo,
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
            "repo": gh_repo,
            "updated": today,
        }
        if not ver:
            entry["reason"] = "frontmatter 缺 version"
        out[skill_key] = entry
    return out


def refresh_ledger(repos_path: Path | None = None) -> dict:
    """把 collect_from_plan 结果写回 repos.json 各条目的版本字段，并同步 example。"""
    repos_path = repos_path or REPOS_PATH
    collected = collect_from_plan(repos_path=repos_path)

    try:
        doc = state_store.load_repos(repos_path)
    except FileNotFoundError:
        doc = {
            "schema_version": 1,
            "updated": "",
            "note": (
                "本机私有（已 gitignore）：技能 key → 本地路径与版本管理字段；"
                "模板见 repos.example.json"
            ),
            "repos": {},
        }

    repos = doc.setdefault("repos", {})
    for skill_key, ver_meta in collected.items():
        cur = repos.get(skill_key) or {"path": None}
        repos[skill_key] = apply_version_fields(
            cur,
            version=ver_meta.get("version"),
            name=ver_meta.get("name") or "",
            repo=ver_meta.get("repo") or "",
            reason=ver_meta.get("reason"),
            updated=ver_meta.get("updated"),
        )

    # 规划里已删除的 key 不在此删除 path 映射（避免误伤）
    doc["note"] = (
        "本机私有（已 gitignore）：技能 key → 本地克隆路径与版本管理字段"
        "（version / name / repo / version_updated / version_reason）；"
        "path 为 null 表示本机未找到。模板见 repos.example.json"
    )
    if not state_store.save_repos(doc, repos_path):
        raise OSError(f"无法写入 repos.json：{repos_path}")

    write_example_from_plan()
    return load_versions(repos_path)


def write_example_from_plan(example_path: Path | None = None) -> None:
    """按 publishing-plan 重写 repos.example.json（path/version 均为 null 占位）。"""
    example_path = example_path or REPOS_EXAMPLE_PATH
    plan = json.loads(state_store.PLAN_PATH.read_text(encoding="utf-8"))
    skills = plan.get("skills") or {}
    repos: dict[str, dict] = {}
    for key in sorted(skills):
        meta = skills[key] or {}
        repos[key] = {
            "path": None,
            "version": None,
            "name": "",
            "repo": meta.get("repo") or f"awam-skills/{key}",
            "version_updated": None,
        }
    doc = {
        "schema_version": 1,
        "updated": "YYYY-MM-DD",
        "note": (
            "本机私有：复制为 docs/repos.json 后填入克隆路径；"
            "version / name / repo / version_updated / version_reason 由 "
            "upgrade_skill.py --refresh 或升版时写入（勿手改代替脚本）。"
            "repos.json 已 gitignore，勿提交。path 为 null 表示本机未找到克隆。"
        ),
        "repos": repos,
    }
    example_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
