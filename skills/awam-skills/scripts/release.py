#!/usr/bin/env python3
"""一键发布编排：一次 preflight → 多平台 publish（可并行）→ verify。

并行策略（默认开启）：
- **可并行**：modelscope / clawhub / skillssh（各自脚本已处理代理差异）
- 并行子进程一律加 `--no-plan`，避免同时改 `publishing-plan.json` / state
- 并行结束后由本脚本**串行**回写 status + state，并刷新一次视图
- github / lobehub / doubao 仍串行（gh / CF / 本地打包）

不替用户 commit / push；preflight 在「本地领先远程」时会 FAIL。
豆包无公开上传 API：本编排对其只跑打包脚本，导入仍需人工。

用法：
  python skills/awam-skills/scripts/release.py --dir <技能仓>
  python skills/awam-skills/scripts/release.py --dir <技能仓> --platforms github,modelscope,clawhub
  python skills/awam-skills/scripts/release.py --dir <技能仓> --no-parallel
  python skills/awam-skills/scripts/release.py --dir <技能仓> --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402
import plan_store  # noqa: E402
import runutil  # noqa: E402
import state_store  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent

PLATFORM_SCRIPTS = {
    "github": "publish_github.py",
    "modelscope": "publish_modelscope.py",
    "clawhub": "publish_clawhub.py",
    "lobehub": "publish_lobehub.py",
    "skillssh": "publish_skillssh.py",
    "doubao": "publish_doubao.py",
}

DEFAULT_ORDER = ("github", "modelscope", "clawhub", "lobehub", "skillssh", "doubao")
PARALLEL_CAPABLE = frozenset(constants.RELEASE_PARALLEL_PLATFORMS)

# 并行日志锁：避免多线程 print 交错成乱码
_LOG_LOCK = threading.Lock()


def _plog(msg: str) -> None:
    with _LOG_LOCK:
        runutil.log(msg)


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


def build_cmd(script: str, args: list[str], *, dry_run: bool,
              no_plan: bool = False) -> list[str]:
    cmd = [sys.executable, str(SCRIPTS / script)] + list(args)
    if dry_run and "--dry-run" not in cmd and script != "publish_doubao.py":
        cmd.append("--dry-run")
    if no_plan and "--no-plan" not in cmd and script != "preflight.py":
        # preflight / verify 无此开关
        if script.startswith("publish_"):
            cmd.append("--no-plan")
    return cmd


def run_script(script: str, args: list[str], *, dry_run: bool,
               no_plan: bool = False, inherit_tty: bool = True) -> int:
    """串行跑脚本。inherit_tty=True 时继承终端看实时进度。"""
    cmd = build_cmd(script, args, dry_run=dry_run, no_plan=no_plan)
    runutil.log(f"\n>>> {' '.join(cmd)}")
    if inherit_tty:
        import subprocess
        return subprocess.run(cmd, timeout=constants.RELEASE_PLATFORM).returncode
    out = runutil.run_utf8(cmd, timeout=constants.RELEASE_PLATFORM)
    if out.stdout:
        runutil.log(out.stdout.rstrip())
    if out.stderr:
        runutil.log(out.stderr.rstrip())
    return out.returncode


def run_script_captured(script: str, args: list[str], *, dry_run: bool,
                        no_plan: bool, label: str) -> tuple[str, int, str]:
    """并行用：捕获输出，返回 (平台, exit, 合并日志)。"""
    cmd = build_cmd(script, args, dry_run=dry_run, no_plan=no_plan)
    _plog(f"\n>>> [{label}] {' '.join(cmd)}")
    try:
        out = runutil.run_utf8(cmd, timeout=constants.RELEASE_PLATFORM)
        text = ((out.stdout or "") + (out.stderr or "")).rstrip()
        return label, out.returncode, text
    except Exception as e:  # noqa: BLE001
        return label, 1, f"[{label}] 子进程异常：{e}"


def platform_args(p: str, skill_dir: Path, skill_key: str | None,
                  allow_foreign: bool) -> list[str]:
    extra = ["--dir", str(skill_dir)]
    if skill_key and p != "doubao":
        extra.extend(["--skill", skill_key])
    if allow_foreign and p in (
        "modelscope", "clawhub", "lobehub", "skillssh", "doubao"
    ):
        extra.append("--allow-foreign-repo")
    return extra


def schedule_waves(platforms: list[str], *, parallel: bool) -> list[tuple[str, list[str]]]:
    """把平台列表拆成若干波次：('serial'|'parallel', [platforms…])。

    保留原列表相对顺序：先遇到的串行平台先跑；第一次碰到可并行平台时，
    把**全部**可并行平台收成一波并行，其后剩余串行平台再跑。
    """
    if not parallel:
        return [("serial", [p]) for p in platforms]

    waves: list[tuple[str, list[str]]] = []
    parallel_batch = [p for p in platforms if p in PARALLEL_CAPABLE]
    parallel_emitted = False
    for p in platforms:
        if p in PARALLEL_CAPABLE:
            if not parallel_emitted and parallel_batch:
                waves.append(("parallel", parallel_batch))
                parallel_emitted = True
            continue
        waves.append(("serial", [p]))
    return waves


def finalize_plan_state(skill_dir: Path, skill_key: str,
                        platforms_ok: list[str]) -> None:
    """并行波次成功后，串行回写规划 status + state，并刷新视图。"""
    if not platforms_ok:
        return
    runutil.log(f"\n串行回写规划/state：{', '.join(platforms_ok)}")
    for p in platforms_ok:
        if plan_store.set_status(state_store.PLAN_PATH, skill_key, p, "done"):
            runutil.log(f"  规划：skills.{skill_key}.status.{p} = done")
        else:
            runutil.log(f"  ⚠ 无法更新 status.{p}")
        if state_store.record_publish_from_repo(
            state_store.STATE_PATH, skill_dir, skill_key, p
        ):
            runutil.log(f"  state：已记录 {skill_key} × {p}")
        else:
            runutil.log(f"  ⚠ state 记录失败：{p}")
    runutil.refresh_plan_view()


def main() -> int:
    ap = argparse.ArgumentParser(description="技能多平台发布编排（支持并行）")
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
                    help="某平台失败后继续后续平台/波次")
    ap.add_argument("--allow-foreign-repo", action="store_true")
    ap.add_argument(
        "--no-parallel", action="store_true",
        help="关闭并行：modelscope/clawhub/skillssh 也串行（调试用）",
    )
    ap.add_argument(
        "--parallel-max", type=int, default=3,
        help="并行波次最大并发（默认 3）",
    )
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

    parallel = not args.no_parallel
    waves = schedule_waves(platforms, parallel=parallel)
    wave_desc = " → ".join(
        f"{'∥' if k == 'parallel' else ''}{','.join(ps)}" for k, ps in waves
    )
    runutil.log(
        f"release：{fm.get('name', '?')}@{fm.get('version', '?')}  "
        f"key={skill_key or '?'}  platforms={','.join(platforms)}"
        + ("  [dry-run]" if args.dry_run else "")
        + (f"\n  波次：{wave_desc}" if wave_desc else "")
        + ("" if parallel else "  [no-parallel]")
    )

    if not args.skip_preflight:
        rc = run_script("preflight.py", ["--dir", str(skill_dir)], dry_run=False)
        if rc != 0:
            runutil.log("❌ preflight FAIL——中止发布（可用 --skip-preflight 强行跳过，不推荐）")
            return rc
    else:
        runutil.log("⚠ 已跳过 preflight")

    results: dict[str, int] = {}
    abort = False

    for kind, batch in waves:
        if abort:
            break
        if kind == "serial":
            for p in batch:
                rc = run_script(
                    PLATFORM_SCRIPTS[p],
                    platform_args(p, skill_dir, skill_key, args.allow_foreign_repo),
                    dry_run=args.dry_run,
                )
                results[p] = rc
                if rc != 0 and not args.continue_on_error:
                    runutil.log(f"❌ {p} 失败（exit {rc}），中止后续（可用 --continue-on-error）")
                    abort = True
                    break
                if rc != 0:
                    runutil.log(f"⚠ {p} 失败（exit {rc}），继续下一个")
            continue

        # parallel wave
        runutil.log(
            f"\n∥ 并行发布：{', '.join(batch)}"
            f"（--no-plan，结束后串行回写；并发≤{args.parallel_max}）"
        )
        ok_for_plan: list[str] = []
        with ThreadPoolExecutor(max_workers=max(1, args.parallel_max)) as pool:
            futs = {
                pool.submit(
                    run_script_captured,
                    PLATFORM_SCRIPTS[p],
                    platform_args(p, skill_dir, skill_key, args.allow_foreign_repo),
                    dry_run=args.dry_run,
                    no_plan=True,
                    label=p,
                ): p
                for p in batch
            }
            for fut in as_completed(futs):
                label, rc, text = fut.result()
                results[label] = rc
                _plog(f"\n----- [{label}] exit={rc} -----")
                if text:
                    _plog(text)
                _plog(f"----- [{label}] end -----")
                if rc == 0:
                    ok_for_plan.append(label)
                elif not args.continue_on_error:
                    abort = True

        # 若有失败且不允许继续，取消已无意义——线程已全部跑完（as_completed）
        if abort and any(results.get(p, 0) != 0 for p in batch):
            failed = [p for p in batch if results.get(p, 0) != 0]
            runutil.log(f"❌ 并行波次有失败：{', '.join(failed)}")

        if ok_for_plan and not args.dry_run:
            if not skill_key:
                runutil.log("⚠ 无 plan key，跳过串行回写（请用 --skill）")
            else:
                # 保持 DEFAULT_ORDER 顺序回写
                ordered = [p for p in DEFAULT_ORDER if p in ok_for_plan]
                finalize_plan_state(skill_dir, skill_key, ordered)
        elif ok_for_plan and args.dry_run:
            runutil.log(f"（dry-run：跳过规划回写，成功平台：{', '.join(ok_for_plan)}）")

    # verify
    verify_targets = [
        p for p, rc in results.items()
        if rc == 0 and p in ("github", "modelscope", "clawhub", "lobehub", "skillssh")
    ]
    if not args.skip_verify and not args.dry_run and verify_targets and not abort:
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
