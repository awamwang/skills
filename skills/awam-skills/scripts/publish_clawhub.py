#!/usr/bin/env python3
"""把组织下技能发布 / 更新到 ClawHub，并刷新发布规划视图。

封装 ClawHub 发布的实测踩坑（详见 references/platforms.md）：
- CLI 必须是无作用域 npm 包 `clawhub`，**不是** `@clawhub/cli`（后者只是 0.0.2 占位包）
- 必须带 `--no-input`：否则遇到「已存在同 slug，是否更新」的交互确认会静默挂死（无输出、只能靠超时杀掉）
- 本机 `HTTPS_PROXY` 会对 registry 的 HTTPS 隧道返回 502，发布子进程里剥离 `*_PROXY` 并置 `NO_PROXY='*'`
- 发布目录：优先 `git archive` 导出跟踪文件；非 git 仓回退到 public_files 的公开文件集
  （不能用排除表 —— 会漏掉 storage/、env.json、index.json）。返回的是**打包根**
  （SKILL.md 所在目录），嵌套布局的仓库才不会把仓库根交给平台
- 临时目录在 finally 里清理，`--keep-tmp` 可保留
- 发布前建议先跑 preflight.py（git 状态 / 与远程同步 / frontmatter / 打包根）
- dry-run 免登录；正式发布需先 `clawhub login --device`（设备流要人工在浏览器确认）

用法（索引仓根任意路径均可，脚本自定位）：
  python skills/awam-skills/scripts/publish_clawhub.py --dir <技能仓路径> --dry-run
  python skills/awam-skills/scripts/publish_clawhub.py --dir <技能仓路径>          # 正式发布并刷新规划
  python skills/awam-skills/scripts/publish_clawhub.py --dir <技能仓路径> --no-plan # 发布但不改规划
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402  （共享超时等常量：见 constants.py）
import credentials as creds  # noqa: E402  （凭据查找 + 来源校验：见 credentials.py）
import plan_store  # noqa: E402  （规划就地更新，保留原排版：见 plan_store.py）
import state_store  # noqa: E402  （发布状态记录，漂移检测基线：见 state_store.py）
import preflight_secrets  # noqa: E402  （发布前敏感串扫描：见 preflight_secrets.py）
import public_files  # noqa: E402  （公开文件集判定：见 public_files.py）

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = INDEX_ROOT / "docs" / "publishing-plan.json"
PLAN_SCRIPT = Path(__file__).resolve().parent / "plan_skills.py"
PLATFORM = "clawhub"

# 发布目录一律由 public_files.py 判定（git archive 或公开文件集）；
# 不再维护「排除表」—— 本地那份 EXCLUDE_DIRS 只跳过工程目录，漏掉 storage/ env.json，
# 正是它把本机数据放进了公开包（见 public_files.py 顶部说明）。

PROXY_KEYS = [
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "ALL_PROXY", "all_proxy",
]


def log(msg: str) -> None:
    print(msg, flush=True)


# 本次运行创建的临时目录；main() 在 finally 里清理（--keep-tmp 可保留）。
# 早先不清理，%%TEMP%% 下越堆越多 —— 用户一次就要手工删掉 26 项。
_TMP_DIRS: list[Path] = []


def cleanup_tmp(keep: bool = False) -> None:
    """清理本次运行创建的临时目录。`keep=True`（--keep-tmp）时只打印不删。"""
    if not _TMP_DIRS:
        return
    if keep:
        log("  保留临时目录（--keep-tmp）：" + "、".join(str(d) for d in _TMP_DIRS))
        return
    for d in _TMP_DIRS:
        shutil.rmtree(d, ignore_errors=True)
    log(f"  已清理临时目录 {len(_TMP_DIRS)} 个")


def _looks_like_clawhub(target: Path) -> tuple[bool, str]:
    """校验 CLAWHUB_BIN 指向的确实是 clawhub CLI。

    环境变量可以来自 `.env` / shell 配置 / 上层进程注入，**不能无条件信任**——
    否则被污染时会执行任意二进制。这里做三重确认（满足其一即可）：
    1. 文件名以 clawhub 开头（`clawhub` / `clawhub.cmd` / `clawhub.exe`）；
    2. 位于 npm / node 的 bin 或 node_modules 路径下，且路径中含 `clawhub` 段
       （覆盖包的真实入口 `bin/clawdhub.js`）；
    3. `dist/cli.js` / `dist/index.js` 这类入口（父目录名含 clawhub）。
    返回 (是否通过, 拒绝原因)。
    """
    name = target.name.lower()
    if name.startswith("clawhub"):
        return True, ""
    # 入口形如 .../node_modules/clawhub/bin/clawdhub.js —— 目录链里含 clawhub 段即可
    parts_lower = [seg.lower() for seg in target.parts]
    if any(seg.startswith("clawhub") for seg in parts_lower):
        return True, ""
    return False, (
        f"CLAWHUB_BIN 指向的名称不像 clawhub CLI：{target.name}。\n"
        "为防环境变量被污染后执行任意程序，只接受文件名以 `clawhub` 开头，"
        "或路径中含 `clawhub` 目录段（如 node_modules/clawhub/bin/clawdhub.js）。"
    )


def find_clawhub() -> list[str]:
    """定位 clawhub CLI，返回可直接 subprocess 执行的命令前缀。

    顺序：环境变量 CLAWHUB_BIN（.js 会自动补 node）> PATH 里的 clawhub(.cmd/.exe)。
    Windows 上 npm 的 `.bin/clawhub` 是 bash 脚本，不能直接 CreateProcess，
    需退到同名的 `.cmd`，或用 node 跑 `dist/cli.js`。
    """
    env_bin = os.environ.get("CLAWHUB_BIN")
    if env_bin:
        target = Path(env_bin)
        if not target.exists():
            raise SystemExit(f"CLAWHUB_BIN 指向的文件不存在：{env_bin}")
        ok, why = _looks_like_clawhub(target)
        if not ok:
            raise SystemExit(why)
        target = target.resolve()
        if target.suffix == ".js":
            node = shutil.which("node")
            if not node:
                raise SystemExit("CLAWHUB_BIN 是 .js 但找不到 node")
            return [node, str(target)]
        if os.name != "nt" and not os.access(target, os.X_OK):
            raise SystemExit(f"CLAWHUB_BIN 指向的文件不可执行：{target}")
        return [str(target)]

    for name in ("clawhub", "clawhub.cmd", "clawhub.exe"):
        found = shutil.which(name)
        if not found:
            continue
        target = Path(found)
        if target.suffix in (".cmd", ".exe", ".bat"):
            return [str(target)]
        # 无后缀（npm 的 bash 包装）→ 退到同名 .cmd，否则用 node 跑
        sibling = target.with_suffix(".cmd")
        if sibling.exists():
            return [str(sibling)]
        return [str(target)]

    raise SystemExit(
        "找不到 clawhub CLI。安装：npm install clawhub\n"
        "注意官方包是无作用域的 `clawhub`（@clawhub/cli 是占位包，不要用）。\n"
        "也可用 CLAWHUB_BIN 指向 clawhub.cmd 或 dist/cli.js。"
    )


def clean_env() -> dict:
    """剥离代理环境变量——本机 HTTPS_PROXY 会让 registry 的 HTTPS 隧道返回 502。"""
    env = os.environ.copy()
    for key in PROXY_KEYS:
        env.pop(key, None)
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    return env


def read_frontmatter_version(skill_dir: Path) -> str | None:
    """从 SKILL.md frontmatter 读 version（找不到返回 None）。"""
    root, _note = public_files.find_skill_root(skill_dir)
    if root is None:
        return None
    text = (root / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^version:\s*([^\s#]+)", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def git_commit(skill_dir: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(skill_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=constants.GIT_FAST,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def export_clean_dir(skill_dir: Path, skip_secret_scan: bool = False) -> tuple[Path, Path]:
    """导出干净发布目录，返回 (发布目录, 临时根目录)。

    - 优先 `git archive`（只含跟踪文件）；
    - 非 git 仓回退到 public_files 的公开文件集 —— **不能**只是跳过 EXCLUDE_DIRS，
      否则 `storage/`（真实数据）、`env.json`（本机路径）、`index.json` 会被原样复制进
      发布目录。魔搭/豆包那两个打包器当初就是这么把本机数据发上公开平台的
      （见 public_files.py 顶部说明），ClawHub 这条只是刚好一直是 git 仓才没触发。
    - 两者都返回**打包根**（SKILL.md 所在目录）：嵌套布局的仓库若把仓库根交给平台，
      ClawHub 会找不到技能根。
    - 交给平台前跑敏感串扫描（`preflight_secrets`）：上传公开平台**不可逆**。
    """
    tmp = Path(tempfile.mkdtemp(prefix="clawhub_publish_"))
    _TMP_DIRS.append(tmp)
    staging = tmp / skill_dir.name
    staging.mkdir(parents=True, exist_ok=True)

    archive = subprocess.run(
        ["git", "-C", str(skill_dir), "archive", "--format=tar", "HEAD"],
        capture_output=True, timeout=constants.GIT_ARCHIVE,
    )
    if archive.returncode == 0 and archive.stdout:
        subprocess.run(["tar", "-x", "-C", str(staging)], input=archive.stdout, check=True, timeout=constants.TAR_EXTRACT)
        root, note = public_files.find_skill_root(staging)
        if root is None:
            raise SystemExit(f"发布目录里找不到 SKILL.md：{note}")
        log(f"  发布目录（git archive，只含跟踪文件）：{root}  [{note}]")
        if not skip_secret_scan:
            scan_staging(root)
        return root, tmp

    files, root, source, excluded, _outside = public_files.pack_files(skill_dir)
    log(f"  {public_files.describe(skill_dir)}")
    for rel in excluded:
        log(f"    ⤫ 排除 {rel}")
    if root is None:
        raise SystemExit(f"无法确定打包根：{source}")
    for p in files:
        dst = staging / public_files.pack_rel(p, root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
    log(f"  发布目录（非 git 仓，按公开文件集复制）：{staging}")
    if not skip_secret_scan:
        scan_staging(staging)
    return staging, tmp


def scan_staging(root: Path) -> None:
    """扫描发布目录，命中疑似凭据即中止发布。"""
    files = [p for p in sorted(root.rglob("*")) if p.is_file()]
    problems = preflight_secrets.scan_files(files, root)
    if problems:
        raise SystemExit(
            preflight_secrets.format_problems(problems)
            + "\n  确需发布请加 --skip-secret-scan（自行承担凭据泄露风险）"
        )
    log("  敏感串扫描：✅ 未发现疑似凭据")


def run(cmd: list[str], env: dict, timeout: int = constants.CLI_RUN_DEFAULT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)


def check_channel(clawhub: list[str], env: dict) -> str:
    """dry-run 时自检通道可用性：CLI 是否就绪 + 是否已登录。

    与 publish_modelscope 的 check_channel 对齐：CLI 在 `find_clawhub` 阶段已
    校验存在性，这里补登录态探测（whoami 一次），让 dry-run 也能提前暴露
    「未登录」而不是等到正式发布才撞上。
    """
    whoami = run(clawhub + ["whoami"], env, timeout=constants.CLI_WHOAMI)
    if whoami.returncode == 0:
        user = (whoami.stdout or "").strip() or "(已登录)"
        return f"CLI 就绪：{' '.join(clawhub)} ｜ 登录态：{user}"
    return (
        f"CLI 就绪：{' '.join(clawhub)} ｜ 未登录（正式发布前需 `clawhub login --device`）"
    )


def update_plan(plan_path: Path, skill_key: str, status: str = "done",
                skill_dir: Path | None = None) -> bool:
    """就地改 `status.clawhub`，**逐字节保留原排版**（见 plan_store.py 的说明）。"""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    skills = plan.get("skills") or {}
    if skills.get(skill_key) is None:
        log(f"  ⚠ 规划里没有技能 `{skill_key}`，跳过规划更新；请手动补 skills 条目")
        return False
    if not plan_store.set_status(plan_path, skill_key, "clawhub", status):
        log(f"  ⚠ 无法就地更新技能 `{skill_key}` 的 status.clawhub，请手动改")
        return False
    log(f"  规划已更新：skills.{skill_key}.status.clawhub = {status}（保留原排版）")
    if status == "done" and skill_dir is not None:
        if state_store.record_publish_from_repo(state_store.STATE_PATH, skill_dir, skill_key, "clawhub"):
            log("  发布状态已记录（check_publish_drift.py 以此为基线）")
        else:
            log("  ⚠ 发布状态记录失败；可稍后用 check_publish_drift.py --record 补记")
    return True


def refresh_view() -> None:
    """调用 plan_skills.py 刷新人读视图（不手改 md）。"""
    out = subprocess.run(
        [sys.executable, str(PLAN_SCRIPT)], capture_output=True, text=True, timeout=constants.PLAN_SCRIPT
    )
    if out.returncode == 0:
        log(f"  视图已刷新：{out.stdout.strip() or 'docs/publishing-plan.md'}")
    else:
        log(f"  ⚠ 刷新视图失败：{out.stderr.strip()}")


def _run(args) -> int:
    if not args.dir:
        raise SystemExit("需要 --dir 指定技能仓本地路径（含 SKILL.md）")
    skill_dir = Path(args.dir).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"技能目录不存在：{skill_dir}")

    warn = creds.source_guard(skill_dir, allow_any=args.allow_foreign_repo)
    if warn:
        raise SystemExit(
            f"⛔ 发布来源校验未通过：{warn}\n"
            f"  待发布目录：{skill_dir}"
        )

    slug = args.slug or skill_dir.name
    version = args.version or read_frontmatter_version(skill_dir)
    if not version:
        raise SystemExit("读不到版本号，请用 --version 显式指定")
    repo = creds.git_remote_repo(skill_dir)
    commit = git_commit(skill_dir)

    log(f"技能：{slug}@{version}" + (f"  （{repo} @ {commit}）" if repo else ""))

    clawhub = find_clawhub()
    env = clean_env()

    if not args.dry_run:
        whoami = run(clawhub + ["whoami"], env, timeout=constants.CLI_WHOAMI)
        if whoami.returncode != 0:
            raise SystemExit(
                "未登录 ClawHub。先执行（设备流需人工在浏览器确认）：\n"
                f"  {clawhub} login --device --no-browser\n"
                "拿到验证 URL 后打开浏览器完成授权，再重跑本脚本。"
            )
        log(f"  已登录：{whoami.stdout.strip()}")

    staging, _tmp = export_clean_dir(skill_dir, skip_secret_scan=args.skip_secret_scan)

    cmd = clawhub + ["--no-input", "skill", "publish", str(staging),
           "--slug", slug, "--name", args.name or slug, "--version", version,
           "--tags", args.tags, "--json"]
    if repo:
        cmd += ["--source-repo", repo]
    if commit:
        cmd += ["--source-commit", commit]
    if args.changelog:
        cmd += ["--changelog", args.changelog]
    if args.dry_run:
        log(f"  通道自检：{check_channel(clawhub, env)}")
        cmd.append("--dry-run")

    log("  发布中…（--no-input，已剥离代理；大包上传可能耗时数十秒）")
    result = run(cmd, env, timeout=constants.CLI_PUBLISH)
    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    if output:
        log(f"  CLI 输出：{output}")
    if result.returncode != 0:
        raise SystemExit(f"发布失败（exit={result.returncode}）\n{output}")

    if args.dry_run:
        log(f"✅ dry-run 通过：{slug}@{version}（未实际发布）")
        return 0

    # 发布后核对线上版本
    # publication 是异步的：刚发布时仍显示旧版本，用 verify 轮询扫描/上线进度
    verify = run(clawhub + ["skill", "verify", slug], env, timeout=constants.CLI_VERIFY)
    log(f"  发布校验：{(verify.stdout or verify.stderr or '').strip()[:300]}")
    inspect = run(clawhub + ["inspect", slug], env, timeout=constants.CLI_INSPECT)
    latest = ""
    for line in (inspect.stdout or "").splitlines():
        if "Latest" in line or "· v" in line:
            latest = line.strip()
            break
    log(f"  线上版本：{latest or '（读取失败）'}（publication 异步，可能仍显示旧版本）")

    if not args.no_plan:
        plan_path = Path(args.plan)
        skill_key = args.skill
        if not skill_key:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            for key, entry in (plan.get("skills") or {}).items():
                if repo and entry.get("repo") == repo:
                    skill_key = key
                    break
                if key == slug or key == f"{slug}-skill":
                    skill_key = key
                    break
        if skill_key:
            if update_plan(plan_path, skill_key, skill_dir=skill_dir):
                refresh_view()
        else:
            log("  ⚠ 未能定位规划里的技能 key，请用 --skill 指定后单独更新")

    log(f"✅ 已发布 {slug}@{version}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="发布技能到 ClawHub 并刷新发布规划")
    parser.add_argument("--dir", help="技能仓本地路径（含 SKILL.md）")
    parser.add_argument("--slug", help="ClawHub slug，默认取目录名")
    parser.add_argument("--name", help="展示名，默认取 slug")
    parser.add_argument("--version", help="版本号，默认读 SKILL.md frontmatter")
    parser.add_argument("--tags", default="latest", help="逗号分隔的 tag，默认 latest")
    parser.add_argument("--changelog", default="", help="变更说明")
    parser.add_argument("--skill", help="publishing-plan.json 里的技能 key（默认按 repo 反查）")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="发布规划 JSON 路径")
    parser.add_argument("--no-plan", action="store_true", help="发布后不更新规划")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不真正发布")
    parser.add_argument("--keep-tmp", action="store_true",
                        help="保留临时发布目录（默认发完即删，避免 %%TEMP%% 越堆越多）")
    parser.add_argument("--skip-secret-scan", action="store_true",
                        help="跳过发布前的敏感串扫描（默认开启；跳过即自行承担凭据泄露风险）")
    parser.add_argument("--allow-foreign-repo", action="store_true",
                        help="跳过来源校验（默认要求 origin 属于 awam-skills/ 组织）")
    parser.add_argument("--show-credentials", action="store_true",
                        help="只打印凭据来源（脱敏）后退出，用于排查")
    args = parser.parse_args()

    if args.show_credentials:
        return creds.show(PLATFORM)

    try:
        return _run(args)
    finally:
        cleanup_tmp(args.keep_tmp)


if __name__ == "__main__":
    raise SystemExit(main())
