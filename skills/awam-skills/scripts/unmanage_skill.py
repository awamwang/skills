#!/usr/bin/env python3
"""移出管理：从发布规划 / repos / publishing-state 去掉技能，不再纳入升级与漂移流程。

不删除本机技能目录、不改技能仓 git、不改索引 README（仍由 Actions 同步）、
默认不改 skills.overrides.json。

用法：
  python skills/awam-skills/scripts/unmanage_skill.py --skill github-skill
  python skills/awam-skills/scripts/unmanage_skill.py --skill a --skill b
  python skills/awam-skills/scripts/unmanage_skill.py github-skill tutor-skill
  python skills/awam-skills/scripts/unmanage_skill.py --skill github-skill --dry-run
  python skills/awam-skills/scripts/unmanage_skill.py --skill x --also-overrides
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runutil  # noqa: E402
import state_store  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
TODAY = date.today().isoformat()
OVERRIDES_PATH = state_store.INDEX_ROOT / "skills.overrides.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def resolve_keys(raw: list[str]) -> list[str]:
    """去重、保序；空键丢弃。"""
    seen: set[str] = set()
    out: list[str] = []
    for k in raw:
        k = (k or "").strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def unmanage(
    keys: list[str],
    *,
    dry_run: bool = False,
    also_overrides: bool = False,
    refresh_view: bool = True,
) -> dict:
    """从管理面移除 keys。返回各数据源命中统计。"""
    keys = resolve_keys(keys)
    if not keys:
        raise SystemExit("未指定技能 key")

    report = {
        "keys": keys,
        "repos": [],
        "plan": [],
        "state": [],
        "overrides": [],
        "missing": [],
    }

    # --- repos ---
    try:
        repos_doc = state_store.load_repos()
    except FileNotFoundError:
        repos_doc = {"schema_version": 1, "updated": "", "repos": {}}
    repos = repos_doc.setdefault("repos", {})

    # --- plan ---
    plan = _load_json(state_store.PLAN_PATH)
    plan_skills = plan.setdefault("skills", {})

    # --- state ---
    state: dict = {"schema_version": 1, "updated": "", "skills": {}}
    if state_store.STATE_PATH.exists():
        state = _load_json(state_store.STATE_PATH)
    state_skills = state.setdefault("skills", {})

    # --- overrides（可选）---
    overrides_doc: dict | None = None
    overrides_map: dict = {}
    if also_overrides and OVERRIDES_PATH.is_file():
        overrides_doc = _load_json(OVERRIDES_PATH)
        overrides_map = overrides_doc.setdefault("overrides", {})

    for key in keys:
        hit = False
        if key in repos:
            report["repos"].append(key)
            hit = True
            if not dry_run:
                del repos[key]
        if key in plan_skills:
            report["plan"].append(key)
            hit = True
            if not dry_run:
                del plan_skills[key]
        if key in state_skills:
            report["state"].append(key)
            hit = True
            if not dry_run:
                del state_skills[key]
        if also_overrides and overrides_doc is not None:
            # overrides 键常为 owner/repo
            drop_ov = [
                full
                for full in list(overrides_map)
                if full == key
                or full.endswith("/" + key)
                or full.split("/")[-1] == key
            ]
            for full in drop_ov:
                report["overrides"].append(full)
                hit = True
                if not dry_run:
                    del overrides_map[full]
        if not hit:
            report["missing"].append(key)

    if dry_run:
        return report

    repos_doc["updated"] = TODAY
    if not state_store.save_repos(repos_doc):
        raise SystemExit(f"无法写入 {state_store.REPOS_PATH}")

    plan["updated"] = TODAY
    _dump_json(state_store.PLAN_PATH, plan)

    if state_store.STATE_PATH.exists() or report["state"]:
        state["updated"] = TODAY
        _dump_json(state_store.STATE_PATH, state)

    if also_overrides and overrides_doc is not None:
        _dump_json(OVERRIDES_PATH, overrides_doc)

    if refresh_view:
        view = subprocess.run(
            [sys.executable, str(SCRIPTS / "plan_skills.py")],
            cwd=str(state_store.INDEX_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if view.returncode != 0:
            runutil.log(
                f"  ⚠ plan_skills.py 退出 {view.returncode}："
                f"{(view.stderr or view.stdout or '').strip()}"
            )
        else:
            runutil.log((view.stdout or "").strip() or "  已刷新 publishing-plan.md")

    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="移出管理：从 plan / repos / state 去掉技能（不删本机目录）"
    )
    ap.add_argument(
        "--skill",
        action="append",
        default=[],
        metavar="KEY",
        help="规划 key（可重复）；也可用位置参数",
    )
    ap.add_argument(
        "skills",
        nargs="*",
        help="规划 key（位置参数，与 --skill 合并）",
    )
    ap.add_argument("--dry-run", action="store_true", help="只打印将移除何处，不写盘")
    ap.add_argument(
        "--also-overrides",
        action="store_true",
        help="同时从 skills.overrides.json 去掉匹配条目（默认不改）",
    )
    ap.add_argument(
        "--no-refresh-view",
        action="store_true",
        help="不跑 plan_skills.py 刷新 publishing-plan.md",
    )
    args = ap.parse_args(argv)
    keys = resolve_keys([*(args.skill or []), *(args.skills or [])])
    if not keys:
        ap.error("请用 --skill <key> 或位置参数指定至少一个技能")

    report = unmanage(
        keys,
        dry_run=args.dry_run,
        also_overrides=args.also_overrides,
        refresh_view=not args.no_refresh_view,
    )

    prefix = "[dry-run] " if args.dry_run else ""
    runutil.log(f"{prefix}移出管理：{', '.join(report['keys'])}")
    runutil.log(f"  repos.json: {', '.join(report['repos']) or '—'}")
    runutil.log(f"  publishing-plan.json: {', '.join(report['plan']) or '—'}")
    runutil.log(f"  publishing-state.json: {', '.join(report['state']) or '—'}")
    if args.also_overrides:
        runutil.log(f"  skills.overrides.json: {', '.join(report['overrides']) or '—'}")
    if report["missing"]:
        runutil.log(
            f"  ⚠ 未在任何管理面找到：{', '.join(report['missing'])}"
        )
    if not args.dry_run:
        runutil.log("  未改本机技能目录 / 技能仓 git / 索引 README / repos.example.json")
        runutil.log("  索引仓变更需你确认后再 commit（repos.json 勿提交）")
    return 0 if not report["missing"] or report["repos"] or report["plan"] else 1


if __name__ == "__main__":
    sys.exit(main())
