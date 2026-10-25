#!/usr/bin/env python3
"""技能发版升级：刷新版本台账 / 提升 frontmatter version / 可选衔接 release。

权威 version 在技能仓 SKILL.md；索引仓 docs/skill-versions.json 为可提交快照。
不替用户 commit / push。

用法：
  python skills/awam-skills/scripts/upgrade_skill.py --list
  python skills/awam-skills/scripts/upgrade_skill.py --refresh
  python skills/awam-skills/scripts/upgrade_skill.py --skill <key> --part patch
  python skills/awam-skills/scripts/upgrade_skill.py --dir <技能仓> --to 1.2.0
  python skills/awam-skills/scripts/upgrade_skill.py --skill <key> --part patch --dry-run
  python skills/awam-skills/scripts/upgrade_skill.py --skill <key> --part patch --release
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import public_files  # noqa: E402
import runutil  # noqa: E402
import state_store  # noqa: E402
import version_store  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent


def resolve_dir_for_skill(skill_key: str) -> Path:
    try:
        repos = state_store.load_repos().get("repos") or {}
    except FileNotFoundError as e:
        raise SystemExit(str(e)) from e
    meta = repos.get(skill_key) or {}
    path = meta.get("path")
    if not path:
        raise SystemExit(
            f"repos.json 中 `{skill_key}` 无本地 path；先补 docs/repos.json 映射"
        )
    skill_dir = Path(path).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"本机路径不存在：{skill_dir}")
    return skill_dir


def plan_repo_for(skill_key: str) -> str:
    try:
        plan = json.loads(state_store.PLAN_PATH.read_text(encoding="utf-8"))
        entry = (plan.get("skills") or {}).get(skill_key) or {}
        return entry.get("repo") or f"awam-skills/{skill_key}"
    except (OSError, json.JSONDecodeError):
        return f"awam-skills/{skill_key}"


def do_list(data: dict) -> int:
    skills = data.get("skills") or {}
    runutil.log(
        f"版本台账 {version_store.VERSIONS_PATH.name} "
        f"（updated={data.get('updated') or '?'}，共 {len(skills)} 项）"
    )
    if not skills:
        runutil.log("  （空：先跑 --refresh）")
        return 0
    for key in sorted(skills):
        e = skills[key] or {}
        ver = e.get("version")
        name = e.get("name") or "—"
        repo = e.get("repo") or "—"
        if ver:
            runutil.log(f"  {key}: {ver}  ({name})  {repo}")
        else:
            reason = e.get("reason") or "无版本"
            runutil.log(f"  {key}: —  [{reason}]  {repo}")
    return 0


def do_refresh(*, dry_run: bool) -> int:
    skills = version_store.collect_from_plan()
    runutil.log(f"将刷新 {len(skills)} 项到 {version_store.VERSIONS_PATH}")
    ok = sum(1 for e in skills.values() if e.get("version"))
    miss = len(skills) - ok
    runutil.log(f"  有 version: {ok}  |  缺/无路径: {miss}")
    if dry_run:
        for key in sorted(skills):
            e = skills[key]
            runutil.log(
                f"  [dry-run] {key}: {e.get('version') or '—'} "
                f"{('(' + e['reason'] + ')') if e.get('reason') else ''}"
            )
        return 0
    data = version_store.refresh_ledger()
    return do_list(data)


def apply_bump(
    skill_dir: Path,
    *,
    part: str | None,
    to: str | None,
    dry_run: bool,
) -> tuple[str, str, dict]:
    """返回 (old, new, frontmatter)。"""
    root, note = public_files.find_skill_root(skill_dir)
    if root is None:
        raise SystemExit(f"找不到 SKILL.md：{note}")
    fm = runutil.read_frontmatter(skill_dir)
    cur = (fm.get("version") or "").strip()
    if not cur:
        raise SystemExit("frontmatter 缺 version，请先补 `version: 0.0.1`")
    if to:
        if not runutil.parse_semver(to):
            raise SystemExit(f"--to `{to}` 不是合法 semver x.y.z")
        new_ver = to.strip()
    else:
        assert part is not None
        new_ver = runutil.bump_semver(cur, part)

    runutil.log(f"技能：{fm.get('name', '?')}  {cur} → {new_ver}")
    runutil.log(f"打包根：{root}（{note}）")
    if cur == new_ver:
        runutil.log(f"version 已是 {cur}，无需改动")
        return cur, new_ver, fm

    targets = [root / "SKILL.md"]
    zh = root / "SKILL.zh-CN.md"
    if zh.is_file():
        targets.append(zh)

    if dry_run:
        for t in targets:
            runutil.log(f"  [dry-run] 将改 {t.relative_to(skill_dir).as_posix()}")
        return cur, new_ver, fm

    changed = []
    for t in targets:
        if runutil.set_frontmatter_version(t, new_ver):
            changed.append(t.relative_to(skill_dir).as_posix())
            runutil.log(f"  ✅ 已写 {t.relative_to(skill_dir).as_posix()}")
        else:
            runutil.log(
                f"  ⚠ 跳过 {t.relative_to(skill_dir).as_posix()}"
                "（无 version 行或已是目标值）"
            )
    if not changed:
        raise SystemExit("没有文件被改写")
    return cur, new_ver, fm


def update_ledger_entry(
    skill_key: str,
    new_ver: str,
    fm: dict,
    *,
    dry_run: bool,
) -> None:
    name = (fm.get("name") or "").strip()
    repo = plan_repo_for(skill_key)
    if dry_run:
        runutil.log(
            f"  [dry-run] 台账 {skill_key}: → {new_ver} ({name}) {repo}"
        )
        return
    if not version_store.upsert_skill(
        version_store.VERSIONS_PATH,
        skill_key,
        version=new_ver,
        name=name,
        repo=repo,
    ):
        raise SystemExit(f"无法回写台账：{version_store.VERSIONS_PATH}")
    runutil.log(f"  ✅ 台账已更新：{skill_key} = {new_ver}")


def git_dirty(skill_dir: Path) -> bool:
    out = runutil.run_git(skill_dir, "status", "--porcelain")
    if out.returncode != 0:
        return True
    return bool((out.stdout or "").strip())


def do_release(skill_dir: Path, skill_key: str | None, extra: list[str]) -> int:
    if git_dirty(skill_dir):
        runutil.log(
            "✗ 工作区有未提交改动（含刚升的 version）。"
            "请先按 awam-git 规范 commit + push，再单独跑 release，或去掉 --release 分步做。"
        )
        runutil.log(f"  建议提交：feat(skills): 升级至 <新版本>")
        runutil.log(
            f"  随后：python skills/awam-skills/scripts/release.py --dir {skill_dir}"
            + (f" --skill {skill_key}" if skill_key else "")
        )
        return 2
    cmd = [
        sys.executable,
        str(SCRIPTS / "release.py"),
        "--dir",
        str(skill_dir),
    ]
    if skill_key:
        cmd.extend(["--skill", skill_key])
    cmd.extend(extra)
    runutil.log(f"衔接 release：{' '.join(cmd)}")
    return subprocess.call(cmd)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="技能发版升级：台账刷新 / 升 version / 可选衔接 release"
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--list",
        action="store_true",
        help="列出 docs/skill-versions.json（不扫本机）",
    )
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="按 publishing-plan + repos.json 重刷版本台账",
    )
    mode.add_argument("--skill", metavar="KEY", help="按规划 key 升版（需 repos.json）")
    mode.add_argument("--dir", type=Path, help="按技能仓路径升版")

    g = ap.add_mutually_exclusive_group()
    g.add_argument("--part", choices=["major", "minor", "patch"], help="semver 段递增")
    g.add_argument("--to", metavar="X.Y.Z", help="直接设为目标版本")

    ap.add_argument("--dry-run", action="store_true", help="只打印，不写盘")
    ap.add_argument(
        "--release",
        action="store_true",
        help="升版后若工作区干净则调用 release.py；有未提交改动则提示分步",
    )
    ap.add_argument(
        "--release-args",
        default="",
        help="传给 release.py 的额外参数（空格分隔，如 --dry-run --platforms github）",
    )
    args = ap.parse_args(argv)

    if args.list:
        return do_list(version_store.load_versions())

    if args.refresh:
        return do_refresh(dry_run=args.dry_run)

    if not args.part and not args.to:
        raise SystemExit("升版需指定 --part 或 --to")

    skill_dir: Path
    skill_key: str | None
    if args.skill:
        skill_key = args.skill
        skill_dir = resolve_dir_for_skill(skill_key)
    else:
        skill_dir = Path(args.dir).expanduser().resolve()
        if not skill_dir.is_dir():
            raise SystemExit(f"目录不存在：{skill_dir}")
        skill_key = runutil.resolve_skill_key(skill_dir)

    cur, new_ver, fm = apply_bump(
        skill_dir, part=args.part, to=args.to, dry_run=args.dry_run
    )
    if skill_key:
        update_ledger_entry(skill_key, new_ver, fm, dry_run=args.dry_run)
    else:
        runutil.log("  ⚠ 未能解析 planning key，跳过台账回写（可显式 --skill）")

    if cur != new_ver or args.dry_run:
        runutil.log(f"建议提交：feat(skills): 升级至 {new_ver}")
        runutil.log("下一步：commit + push 技能仓，再跑 preflight / release")

    if args.release:
        if args.dry_run:
            runutil.log("  [dry-run] 跳过 --release")
            return 0
        extra = args.release_args.split() if args.release_args.strip() else []
        return do_release(skill_dir, skill_key, extra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
