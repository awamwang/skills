#!/usr/bin/env python3
"""发布漂移检测：列出「本地已改但平台没跟上」的技能 × 平台。

数据三处对齐：
- docs/publishing-plan.json —— 哪些平台 status=done（只有 done 才值得问要不要重发）
- docs/repos.json           —— 技能仓本地克隆路径（path=null 表示本机没有）
- docs/publishing-state.json —— 各平台最近发布时的 commit / version（state_store.py 写）

判定规则：
- 本地 HEAD ≠ 已发布 commit → 内容已前进（待发布）
- github / skillssh 平台本地有未推送提交 → 待推送（这两个平台的「发布」就是 push / 随 GitHub 同步）
- clawhub 且版本号没升 → 额外提示（ClawHub 同版本不能重发，先升 version）
- 工作区有未提交改动 → 技能级警告（发布前 preflight 也会拦）

用法（索引仓根任意路径均可，脚本自定位）：
  python skills/awam-skills/scripts/check_publish_drift.py                  # 人读报告
  python skills/awam-skills/scripts/check_publish_drift.py --json           # 给 agent 消费
  python skills/awam-skills/scripts/check_publish_drift.py --record <技能 key> <platform>
      # 网页手动发布（如 LobeHub）完成后补记当前 HEAD
  python skills/awam-skills/scripts/check_publish_drift.py --record-baseline
      # 给存量 done 平台批量回填基线（基线之后的新提交才算待发布）

退出码：0 无漂移 / 1 有待发布 / 2 用法或数据错误。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402  （共享超时等常量：见 constants.py）
import state_store  # noqa: E402  （发布状态读写：见 state_store.py）

TODAY = date.today().isoformat()


def log(msg: str) -> None:
    print(msg, flush=True)


def _git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess:
    import runutil
    return runutil.run_git(repo_dir, *args, timeout=constants.GIT_OP)


def git_info(repo_dir: Path) -> dict:
    """一次取全该仓的 git 状态：HEAD / 未提交数 / 未推送数。"""
    info: dict = {"head": None, "dirty": 0, "unpushed": None, "no_upstream": False}
    head = _git(repo_dir, "rev-parse", "--short", "HEAD")
    if head.returncode != 0:
        info["error"] = (head.stderr or "").strip()
        return info
    info["head"] = head.stdout.strip()
    status = _git(repo_dir, "status", "--porcelain")
    if status.returncode == 0:
        info["dirty"] = len([l for l in status.stdout.splitlines() if l.strip()])
    ahead = _git(repo_dir, "rev-list", "--count", "@{upstream}..HEAD")
    if ahead.returncode == 0 and ahead.stdout.strip().isdigit():
        info["unpushed"] = int(ahead.stdout.strip())
    else:
        info["no_upstream"] = True
    return info


def collect_rows() -> tuple[list[dict], list[str]]:
    """汇总所有 status=done 的技能 × 平台为行列表；返回 (rows, 全局提示)。"""
    plan = json.loads(state_store.PLAN_PATH.read_text(encoding="utf-8"))
    repos_cfg = json.loads(state_store.REPOS_PATH.read_text(encoding="utf-8"))
    state = state_store.load_state()
    platform_order = list((plan.get("platforms") or {}).keys())
    notes: list[str] = []
    rows: list[dict] = []

    for skill_key, entry in (plan.get("skills") or {}).items():
        status = entry.get("status") or {}
        done = [p for p in platform_order if status.get(p) == "done"]
        if not done:
            continue  # 全 skip / 全 todo 的技能不打扰
        repo = (repos_cfg.get("repos") or {}).get(skill_key) or {}
        repo_path = repo.get("path")
        if not repo_path:
            for p in done:
                rows.append({"skill": skill_key, "platform": p, "status": "no_repo",
                             "reasons": ["本机未找到克隆（docs/repos.json 里 path 为空）"],
                             "head": None, "dirty": 0})
            continue
        repo_dir = Path(repo_path)
        if not repo_dir.is_dir():
            notes.append(f"{skill_key}: repos.json 指向的目录不存在 {repo_path}，请更新映射")
            continue
        info = git_info(repo_dir)
        if info.get("error"):
            notes.append(f"{skill_key}: git 读取失败 {info['error']}")
            continue
        version = state_store.frontmatter_version(repo_dir)
        for p in done:
            rec = ((state.get("skills") or {}).get(skill_key) or {}).get(p)
            reasons: list[str] = []
            st = "clean"
            if rec is None:
                st = "no_record"
                reasons.append("无发布记录（新标 done？用 --record-baseline 或 --record 补记）")
            elif info["head"] != rec.get("commit"):
                st = "drift"
                reasons.append(f"本地 {info['head']} 已前进（发布于 {rec.get('commit')}）")
                if p == "clawhub" and version == rec.get("version"):
                    reasons.append(f"版本号仍是 {version}，ClawHub 同版本不能重发，先升 version")
            if p in ("github", "skillssh"):
                if info["unpushed"]:
                    st = "drift" if st == "clean" else st
                    reasons.append(f"{info['unpushed']} 个提交未推送 GitHub")
                elif info["no_upstream"]:
                    reasons.append("无上游跟踪分支（从未 push？）")
            rows.append({
                "skill": skill_key, "platform": p, "status": st, "reasons": reasons,
                "head": info["head"], "dirty": info["dirty"],
                "published_commit": (rec or {}).get("commit"),
                "published_version": (rec or {}).get("version"),
                "local_version": version, "repo": repo_path,
                "baseline": (rec or {}).get("baseline", False),
            })
    return rows, notes


def print_report(rows: list[dict], notes: list[str]) -> int:
    log(f"发布漂移检查 · {TODAY}")
    log("=" * 60)
    pending = 0
    for row in rows:
        if row["status"] == "clean":
            continue
        pending += 1
        loc = f"{row['head']}, 工作区{'有未提交改动' if row['dirty'] else '干净'}" if row["head"] else "无本地仓"
        log(f"\n⚠ {row['skill']} × {row['platform']}（{loc}）")
        for r in row["reasons"]:
            log(f"    - {r}")
    clean = [r for r in rows if r["status"] == "clean"]
    if clean:
        names = ", ".join(f"{r['skill']}×{r['platform']}" for r in clean)
        log(f"\n✅ 无漂移 {len(clean)} 项：{names}")
    for n in notes:
        log(f"\n⚠ {n}")
    log(f"\n汇总：{pending} 项待发布（共 {len(rows)} 项 done）")
    return 1 if pending else 0


def do_record(skill_key: str, platform: str) -> int:
    repos_cfg = json.loads(state_store.REPOS_PATH.read_text(encoding="utf-8"))
    repo = (repos_cfg.get("repos") or {}).get(skill_key)
    if not repo or not repo.get("path"):
        log(f"✗ repos.json 里没有 {skill_key} 的本地路径，先补映射")
        return 2
    repo_dir = Path(repo["path"])
    if not repo_dir.is_dir():
        log(f"✗ 目录不存在：{repo['path']}")
        return 2
    if state_store.record_publish_from_repo(state_store.STATE_PATH, repo_dir, skill_key, platform):
        head = state_store.git_head(repo_dir)
        log(f"✅ 已记录 {skill_key} × {platform} = {head}（{state_store.frontmatter_version(repo_dir)}）")
        return 0
    log("✗ 记录失败（不是 git 仓 / 写文件出错）")
    return 2


def do_record_baseline() -> int:
    plan = json.loads(state_store.PLAN_PATH.read_text(encoding="utf-8"))
    repos_cfg = json.loads(state_store.REPOS_PATH.read_text(encoding="utf-8"))
    state = state_store.load_state()
    platform_order = list((plan.get("platforms") or {}).keys())
    n = 0
    for skill_key, entry in (plan.get("skills") or {}).items():
        status = entry.get("status") or {}
        done = [p for p in platform_order if status.get(p) == "done"]
        if not done:
            continue
        repo = (repos_cfg.get("repos") or {}).get(skill_key) or {}
        if not repo.get("path") or not Path(repo["path"]).is_dir():
            log(f"⤫ {skill_key}: 本地无克隆，跳过（done: {', '.join(done)}）")
            continue
        existing = ((state.get("skills") or {}).get(skill_key) or {})
        for p in done:
            if p in existing:
                continue  # 只补缺，不覆盖已有记录
            if state_store.record_publish_from_repo(
                    state_store.STATE_PATH, Path(repo["path"]), skill_key, p, baseline=True):
                n += 1
                log(f"✅ 基线 {skill_key} × {p} = {state_store.git_head(Path(repo['path']))}")
    log(f"\n回填完成：新记 {n} 条基线（已有记录不动）")
    return 0


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="发布漂移检测：本地已改但平台没跟上的技能 × 平台")
    parser.add_argument("--json", action="store_true", help="输出 JSON（给 agent 消费）")
    parser.add_argument("--record", nargs=2, metavar=("技能key", "platform"),
                        help="手动发布（如 LobeHub 网页）后补记当前 HEAD")
    parser.add_argument("--record-baseline", action="store_true",
                        help="给存量 done 平台批量回填基线")
    args = parser.parse_args()

    if args.record:
        return do_record(args.record[0], args.record[1])
    if args.record_baseline:
        return do_record_baseline()

    try:
        rows, notes = collect_rows()
    except (OSError, json.JSONDecodeError) as e:
        log(f"✗ 数据读取失败：{e}")
        return 2
    if args.json:
        print(json.dumps({"date": TODAY, "pending": sum(
            1 for r in rows if r["status"] != "clean"), "rows": rows, "notes": notes},
            ensure_ascii=False, indent=2))
        return 1 if any(r["status"] != "clean" for r in rows) else 0
    return print_report(rows, notes)


if __name__ == "__main__":
    raise SystemExit(main())
