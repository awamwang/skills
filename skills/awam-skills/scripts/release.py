#!/usr/bin/env python3
"""一键发布编排：preflight →（可选 bump 提示）→ 多平台 publish → verify。

不替用户 commit / push；preflight 在「本地领先远程」时会 FAIL。
豆包无公开上传 API：本编排对其只跑打包脚本，导入仍需人工。

用法：
  python skills/awam-skills/scripts/release.py --dir <技能仓>
  python skills/awam-skills/scripts/release.py --dir <技能仓> --platforms github,modelscope,clawhub
  python skills/awam-skills/scripts/release.py --dir <技能仓> --dry-run
  python skills/awam-skills/scripts/release.py --dir <技能仓> --skip-verify
  python skills/awam-skills/scripts/release.py --dir <技能仓> --continue-on-error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402
import runutil  # noqa: E402
import state_store  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent

# 平台 → 脚本文件名（相对 scripts/）
PLATFORM_SCRIPTS = {
    "github": "publish_github.py",
    "modelscope": "publish_modelscope.py",
    "clawhub": "publish_clawhub.py",
    "lobehub": "publish_lobehub.py",
    "skillssh": "publish_skillssh.py",
    "doubao": "publish_doubao.py",
}

# 默认编排顺序（上传型在前，遥测 / 打包在后）
DEFAULT_ORDER = ("github", "modelscope", "clawhub", "lobehub", "skillssh", "doubao")


def default_platforms(skill_key: str | None) -> list[str]:
    """按规划：plan=publish 且有脚本的平台；无规划则用 DEFAULT_ORDER 去掉 doubao。"""
    if not skill_key:
        return [p for p in DEFAULT_ORDER if p != "doubao"]
    try:
        plan = json.loads(state_store.PLAN_PATH.read_text(encoding="utf-8"))
        entry = (plan.get("skills") or {}).get(skill_key) or {}
        pmap = entry.get("plan") or {}
    except (OSError, json.JSONDecodeError):
        return [p for p in DEFAULT_ORDER if p != "doubao"]
    out = []
    for p in DEFAULT_ORDER:
        if p not in PLATFORM_SCRIPTS:
            continue
        if pmap.get(p) == "publish":
            out.append(p)
    return out or [p for p in DEFAULT_ORDER if p != "doubao"]


def run_script(script: str, args: list[str], *, dry_run: bool) -> int:
    cmd = [sys.executable, str(SCRIPTS / script)] + args
    if dry_run and "--dry-run" not in args:
        # 各脚本均支持 --dry-run（doubao 打包本身就是 dry）
        if script != "publish_doubao.py":
            cmd.append("--dry-run")
    runutil.log(f"\n>>> {' '.join(cmd)}")
    # 子进程直接继承 stdout，便于看进度；用 run_utf8 会吞掉实时输出
    import subprocess
    proc = subprocess.run(cmd, timeout=constants.CLI_PUBLISH + 120)
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="技能多平台发布编排")
    ap.add_argument("--dir", required=True, help="技能仓本地路径")
    ap.add_argument(
        "--platforms",
        help="逗号分隔平台；默认按 publishing-plan 的 plan=publish 自动选",
    )
    ap.add_argument("--skill", help="planning key")
    ap.add_argument("--dry-run", action="store_true", help="预检 + 各平台 dry-run")
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--skip-verify", action="store_true")
    ap.add_argument("--continue-on-error", action="store_true",
                    help="某平台失败后继续后续平台")
    ap.add_argument("--allow-foreign-repo", action="store_true")
    args = ap.parse_args()

    skill_dir = Path(args.dir).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"技能目录不存在：{skill_dir}")

    fm = runutil.read_frontmatter(skill_dir)
    skill_key = runutil.resolve_skill_key(skill_dir, args.skill)
    platforms = (
        [p.strip().lower() for p in args.platforms.split(",") if p.strip()]
        if args.platforms else default_platforms(skill_key)
    )
    unknown = [p for p in platforms if p not in PLATFORM_SCRIPTS]
    if unknown:
        raise SystemExit(f"未知平台：{', '.join(unknown)}")

    runutil.log(
        f"release：{fm.get('name', '?')}@{fm.get('version', '?')}  "
        f"key={skill_key or '?'}  platforms={','.join(platforms)}"
        + ("  [dry-run]" if args.dry_run else "")
    )

    if not args.skip_preflight:
        rc = run_script("preflight.py", ["--dir", str(skill_dir)], dry_run=False)
        if rc != 0:
            runutil.log("❌ preflight FAIL——中止发布（可用 --skip-preflight 强行跳过，不推荐）")
            return rc
    else:
        runutil.log("⚠ 已跳过 preflight")

    results: dict[str, int] = {}
    for p in platforms:
        extra = ["--dir", str(skill_dir)]
        if skill_key and p != "doubao":
            # 多数脚本支持 --skill
            extra.extend(["--skill", skill_key])
        if args.allow_foreign_repo and p in (
            "modelscope", "clawhub", "lobehub", "skillssh", "doubao"
        ):
            extra.append("--allow-foreign-repo")
        rc = run_script(PLATFORM_SCRIPTS[p], extra, dry_run=args.dry_run)
        results[p] = rc
        if rc != 0 and not args.continue_on_error:
            runutil.log(f"❌ {p} 失败（exit {rc}），中止后续（可用 --continue-on-error）")
            break
        if rc != 0:
            runutil.log(f"⚠ {p} 失败（exit {rc}），继续下一个")

    # verify：只核对应成功的上传型平台；dry-run 跳过
    verify_targets = [
        p for p, rc in results.items()
        if rc == 0 and p in ("github", "modelscope", "clawhub", "lobehub", "skillssh")
    ]
    if not args.skip_verify and not args.dry_run and verify_targets:
        vrc = run_script(
            "verify_publish.py",
            ["--dir", str(skill_dir), "--platforms", ",".join(verify_targets)],
            dry_run=False,
        )
        results["verify"] = vrc
    elif args.dry_run:
        runutil.log("（dry-run：跳过 verify）")

    runutil.log("\n==== 汇总 ====")
    for p, rc in results.items():
        runutil.log(f"  {'✅' if rc == 0 else '❌'} {p}: exit {rc}")
    failed = [p for p, rc in results.items() if rc != 0]
    if failed:
        runutil.log(f"失败：{', '.join(failed)}")
        return 1
    runutil.log("全部成功")
    if "doubao" in platforms and results.get("doubao", 1) == 0:
        runutil.log(
            "豆包：导入包已生成（见 ~/.awam-publish/）。客户端导入成功后跑：\n"
            f"  python {SCRIPTS / 'publish_doubao.py'} --dir {skill_dir} --mark-done"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
