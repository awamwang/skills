#!/usr/bin/env python3
"""提升技能 frontmatter version（SKILL.md + SKILL.zh-CN.md 同步）。

只改文件、不提交——提交仍由用户 / Agent 按 awam-git 规范显式执行。

用法：
  python skills/awam-skills/scripts/bump_version.py --dir <技能仓> --part patch
  python skills/awam-skills/scripts/bump_version.py --dir <技能仓> --to 0.7.1
  python skills/awam-skills/scripts/bump_version.py --dir <技能仓> --part minor --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import public_files  # noqa: E402
import runutil  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="提升技能 SKILL.md frontmatter version")
    ap.add_argument("--dir", required=True, help="技能仓本地路径")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--part", choices=["major", "minor", "patch"], help="按 semver 段递增")
    g.add_argument("--to", metavar="X.Y.Z", help="直接设为目标版本")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要改成什么，不写盘")
    args = ap.parse_args()

    skill_dir = Path(args.dir).expanduser().resolve()
    root, note = public_files.find_skill_root(skill_dir)
    if root is None:
        raise SystemExit(f"找不到 SKILL.md：{note}")

    fm = runutil.read_frontmatter(skill_dir)
    cur = fm.get("version", "")
    if not cur:
        raise SystemExit("frontmatter 缺 version，请先补 `version: 0.0.1`")

    if args.to:
        if not runutil.parse_semver(args.to):
            raise SystemExit(f"--to `{args.to}` 不是合法 semver x.y.z")
        new_ver = args.to.strip()
    else:
        new_ver = runutil.bump_semver(cur, args.part)

    if new_ver == cur:
        runutil.log(f"version 已是 {cur}，无需改动")
        return 0

    targets = [root / "SKILL.md"]
    zh = root / "SKILL.zh-CN.md"
    if zh.is_file():
        targets.append(zh)

    runutil.log(f"技能：{fm.get('name', '?')}  {cur} → {new_ver}")
    runutil.log(f"打包根：{root}（{note}）")
    if args.dry_run:
        for t in targets:
            runutil.log(f"  [dry-run] 将改 {t.relative_to(skill_dir).as_posix()}")
        runutil.log(f"建议提交：feat(skills): 升级至 {new_ver}")
        return 0

    changed = []
    for t in targets:
        if runutil.set_frontmatter_version(t, new_ver):
            changed.append(t.relative_to(skill_dir).as_posix())
            runutil.log(f"  ✅ 已写 {t.relative_to(skill_dir).as_posix()}")
        else:
            runutil.log(f"  ⚠ 跳过 {t.relative_to(skill_dir).as_posix()}（无 version 行或已是目标值）")

    if not changed:
        raise SystemExit("没有文件被改写")
    runutil.log(f"建议提交：feat(skills): 升级至 {new_ver}")
    runutil.log("下一步：按 awam-git 规范 commit + push，再跑 preflight / release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
