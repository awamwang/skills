#!/usr/bin/env python3
"""索引仓发布状态提交助手：只 stage state + 人读视图，需显式 --yes 才 commit。

默认（无 --yes）：
  列出将纳入的文件、工作区 diff 摘要，**不** git add / commit。

加 `--yes`：
  git add 下列文件并 commit（仍不 push）。

纳入文件（固定白名单，防误加脚本/凭据）：
  - docs/publishing-state.json
  - docs/publishing-plan.md          （plan_skills.py 生成的视图）

可选：
  --include-plan-json  额外纳入 docs/publishing-plan.json（status 行就地改过时）

用法：
  python skills/awam-skills/scripts/commit_publish_state.py
  python skills/awam-skills/scripts/commit_publish_state.py --yes
  python skills/awam-skills/scripts/commit_publish_state.py --yes --include-plan-json
  python skills/awam-skills/scripts/commit_publish_state.py --yes -m "chore: 记录 awam-todo 0.7.1 发布状态"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402
import runutil  # noqa: E402

INDEX_ROOT = Path(__file__).resolve().parents[3]
STATE = INDEX_ROOT / "docs" / "publishing-state.json"
VIEW = INDEX_ROOT / "docs" / "publishing-plan.md"
PLAN_JSON = INDEX_ROOT / "docs" / "publishing-plan.json"

DEFAULT_MSG = f"chore: 同步发布状态与规划视图（{date.today().isoformat()}）"


def _git(*args: str) -> tuple[int, str]:
    out = runutil.run_utf8(
        ["git", "-C", str(INDEX_ROOT), *args],
        timeout=constants.GIT_OP,
    )
    text = ((out.stdout or "") + (out.stderr or "")).strip()
    return out.returncode, text


def changed_paths(paths: list[Path]) -> list[Path]:
    """相对索引仓根有改动（含未跟踪）的路径。"""
    out: list[Path] = []
    for p in paths:
        if not p.is_file():
            continue
        rel = p.relative_to(INDEX_ROOT).as_posix()
        rc, porcelain = _git("status", "--porcelain", "--", rel)
        if rc == 0 and porcelain.strip():
            out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="索引仓：仅提交 publishing-state + 规划视图（需 --yes）"
    )
    ap.add_argument(
        "--yes", action="store_true",
        help="确认执行 git add + commit（缺省只预览，不改仓库）",
    )
    ap.add_argument(
        "--include-plan-json", action="store_true",
        help="额外纳入 docs/publishing-plan.json",
    )
    ap.add_argument("-m", "--message", default=DEFAULT_MSG, help="commit message")
    ap.add_argument(
        "--allow-empty", action="store_true",
        help="没有改动时也以 0 退出（默认无改动退 1）",
    )
    args = ap.parse_args()

    candidates = [STATE, VIEW]
    if args.include_plan_json:
        candidates.append(PLAN_JSON)

    missing = [p for p in candidates if not p.is_file()]
    if missing:
        for p in missing:
            runutil.log(f"⚠ 文件不存在，跳过：{p.relative_to(INDEX_ROOT).as_posix()}")

    to_commit = changed_paths([p for p in candidates if p.is_file()])
    runutil.log(f"索引仓：{INDEX_ROOT}")
    if not to_commit:
        runutil.log("没有可提交的发布状态/视图改动")
        return 0 if args.allow_empty else 1

    runutil.log("将纳入：")
    for p in to_commit:
        rel = p.relative_to(INDEX_ROOT).as_posix()
        rc, st = _git("status", "--porcelain", "--", rel)
        runutil.log(f"  {st or ('  ' + rel)}")

    # diff 摘要（已跟踪文件）
    for p in to_commit:
        rel = p.relative_to(INDEX_ROOT).as_posix()
        rc, diff = _git("diff", "--stat", "--", rel)
        if diff:
            runutil.log(diff)
        rc2, diff_cached = _git("diff", "--cached", "--stat", "--", rel)
        if diff_cached:
            runutil.log("(已暂存) " + diff_cached)

    if not args.yes:
        runutil.log(
            "\n预览模式：未执行 git add / commit。\n"
            "确认无误后加 --yes，例如：\n"
            f"  python skills/awam-skills/scripts/commit_publish_state.py --yes\n"
            f"  python skills/awam-skills/scripts/commit_publish_state.py --yes -m \"chore: …\""
        )
        return 0

    # 安全：只 add 白名单路径
    for p in to_commit:
        rel = p.relative_to(INDEX_ROOT).as_posix()
        rc, err = _git("add", "--", rel)
        if rc != 0:
            raise SystemExit(f"git add 失败：{rel}\n{err}")

    rc, err = _git("commit", "-m", args.message)
    if rc != 0:
        raise SystemExit(f"git commit 失败：{err}")
    runutil.log(f"✅ 已提交：{args.message}")
    rc, head = _git("log", "-1", "--oneline")
    if head:
        runutil.log(f"  {head}")
    runutil.log("（未 push；需要时请显式 git push）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
