#!/usr/bin/env python3
"""GitHub 侧收口：Topics / description / 规划 status / 发布 state。

不做 commit / push（技能仓内容推送由用户或 Agent 显式完成；preflight 会拦「本地领先」）。
不替用户写 skills.overrides.json 的 category（索引语义需人拍板）；缺登记时 WARN。

用法：
  python skills/awam-skills/scripts/publish_github.py --dir <技能仓>
  python skills/awam-skills/scripts/publish_github.py --dir <技能仓> --dry-run
  python skills/awam-skills/scripts/publish_github.py --dir <技能仓> --no-plan
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402
import plan_store  # noqa: E402
import runutil  # noqa: E402
import state_store  # noqa: E402

PLATFORM = "github"
DEFAULT_TOPICS = ("skill", "skills")


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def main() -> int:
    ap = argparse.ArgumentParser(description="GitHub Topics/description + 规划/state 收口")
    ap.add_argument("--dir", required=True, help="技能仓本地路径")
    ap.add_argument("--skill", help="publishing-plan.json 技能 key")
    ap.add_argument("--description", help="覆盖 frontmatter description（默认取 SKILL.md）")
    ap.add_argument("--add-topic", action="append", default=[], help="额外 topic（可重复）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行的操作")
    ap.add_argument("--no-plan", action="store_true", help="不更新规划 / state")
    ap.add_argument("--skip-gh", action="store_true", help="不调 gh（只记 state / 规划）")
    args = ap.parse_args()

    skill_dir = Path(args.dir).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"技能目录不存在：{skill_dir}")

    fm = runutil.read_frontmatter(skill_dir)
    name = fm.get("name", "")
    version = fm.get("version", "")
    desc = args.description or fm.get("description", "")
    full = runutil.origin_full_name(skill_dir)
    if not full:
        raise SystemExit("无法解析 origin（需要 github.com owner/repo）")
    if not full.startswith(f"{runutil.ORG}/"):
        runutil.log(f"⚠ origin 不是 {runutil.ORG}/…：{full}")

    skill_key = runutil.resolve_skill_key(skill_dir, args.skill)
    runutil.log(f"技能：{name}@{version or '?'}  repo={full}  plan_key={skill_key or '(未定位)'}")

    # overrides 提示
    if runutil.OVERRIDES_PATH.is_file():
        try:
            ov = json.loads(runutil.OVERRIDES_PATH.read_text(encoding="utf-8"))
            if full not in (ov.get("overrides") or {}) and full not in set(ov.get("exclude") or []):
                runutil.log(
                    f"⚠ {full} 未在 skills.overrides.json 登记："
                    "首次发布请人工补 category + description（本脚本不替你拍板分类）"
                )
            else:
                runutil.log(f"  overrides：已登记 {full}")
        except (OSError, json.JSONDecodeError) as e:
            runutil.log(f"⚠ 读 overrides 失败：{e}")

    topics = list(DEFAULT_TOPICS) + list(args.add_topic or [])
    # 去重保序
    seen: set[str] = set()
    topics = [t for t in topics if not (t in seen or seen.add(t))]

    if args.dry_run:
        runutil.log(f"  [dry-run] gh repo edit {full} --description … --add-topic {' --add-topic '.join(topics)}")
        if not args.no_plan and skill_key:
            runutil.log(f"  [dry-run] status.github=done + record state ({skill_key})")
        return 0

    if not args.skip_gh:
        if not _gh_available():
            raise SystemExit("未找到 gh CLI，请先安装 GitHub CLI 或加 --skip-gh")
        cmd = ["gh", "repo", "edit", full, "--description", desc or name]
        for t in topics:
            cmd.extend(["--add-topic", t])
        out = runutil.run_utf8(cmd, timeout=constants.GIT_OP)
        if out.returncode != 0:
            raise SystemExit(f"gh repo edit 失败：{(out.stderr or out.stdout or '').strip()}")
        runutil.log(f"  ✅ Topics/description 已更新（topics={','.join(topics)}）")
    else:
        runutil.log("  （--skip-gh：跳过 gh repo edit）")

    if not args.no_plan:
        if not skill_key:
            runutil.log("  ⚠ 未能定位规划 key，请用 --skill；state 未写入")
            return 1
        if plan_store.set_status(state_store.PLAN_PATH, skill_key, PLATFORM, "done"):
            runutil.log(f"  规划已更新：skills.{skill_key}.status.github = done")
        if state_store.record_publish_from_repo(
            state_store.STATE_PATH, skill_dir, skill_key, PLATFORM
        ):
            runutil.log("  发布状态已记录（check_publish_drift.py 以此为基线）")
        else:
            runutil.log("  ⚠ 发布状态记录失败")
        runutil.refresh_plan_view()

    runutil.log(f"✅ GitHub 收口完成：{full}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
