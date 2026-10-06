#!/usr/bin/env python3
"""把组织下技能发布 / 更新到 ClawHub，并刷新发布规划视图。

封装 ClawHub 发布的实测踩坑（详见 references/platforms.md）：
- CLI 必须是无作用域 npm 包 `clawhub`，**不是** `@clawhub/cli`（后者只是 0.0.2 占位包）
- 必须带 `--no-input`：否则遇到「已存在同 slug，是否更新」的交互确认会静默挂死（无输出、只能靠超时杀掉）
- 本机 `HTTPS_PROXY` 会对 registry 的 HTTPS 隧道返回 502，发布子进程里剥离 `*_PROXY` 并置 `NO_PROXY='*'`
- 发布目录用 `git archive` 导出干净副本，避免 `.cache/`、`.workbuddy/` 被打包进去
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
import plan_store  # noqa: E402  （规划就地更新，保留原排版：见 plan_store.py）

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = INDEX_ROOT / "docs" / "publishing-plan.json"
PLAN_SCRIPT = Path(__file__).resolve().parent / "plan_skills.py"

# 会被打进发布包的无关产物
EXCLUDE_DIRS = {".git", ".cache", ".workbuddy", "__pycache__", "node_modules", ".venv", "venv"}

PROXY_KEYS = [
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "ALL_PROXY", "all_proxy",
]


def log(msg: str) -> None:
    print(msg, flush=True)


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
        if target.suffix == ".js":
            node = shutil.which("node")
            if not node:
                raise SystemExit("CLAWHUB_BIN 是 .js 但找不到 node")
            return [node, str(target)]
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
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        nested = skill_dir / "skills" / skill_dir.name / "SKILL.md"
        skill_md = nested if nested.exists() else skill_md
    if not skill_md.exists():
        return None
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^version:\s*([^\s#]+)", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def git_remote_repo(skill_dir: Path) -> str | None:
    """从 origin 远端解析 owner/repo，如 awam-skills/quicker-connector。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(skill_dir), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=20,
        )
        url = out.stdout.strip()
    except Exception:
        return None
    if not url:
        return None
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def git_commit(skill_dir: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(skill_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=20,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def export_clean_dir(skill_dir: Path) -> Path:
    """导出干净发布目录：优先 git archive，否则按排除表复制。"""
    staging = Path(tempfile.mkdtemp(prefix="clawhub_publish_")) / skill_dir.name
    staging.mkdir(parents=True, exist_ok=True)

    archive = subprocess.run(
        ["git", "-C", str(skill_dir), "archive", "--format=tar", "HEAD"],
        capture_output=True, timeout=60,
    )
    if archive.returncode == 0 and archive.stdout:
        subprocess.run(["tar", "-x", "-C", str(staging)], input=archive.stdout, check=True, timeout=120)
        log(f"  发布目录（git archive）：{staging}")
        return staging

    for item in skill_dir.iterdir():
        if item.is_dir() and item.name in EXCLUDE_DIRS:
            continue
        if item.is_dir():
            shutil.copytree(item, staging / item.name, ignore=shutil.ignore_patterns(*EXCLUDE_DIRS))
        else:
            shutil.copy2(item, staging / item.name)
    log(f"  发布目录（复制，非 git 仓）：{staging}")
    return staging


def run(cmd: list[str], env: dict, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)


def update_plan(plan_path: Path, skill_key: str, status: str = "done") -> bool:
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
    return True


def refresh_view() -> None:
    """调用 plan_skills.py 刷新人读视图（不手改 md）。"""
    out = subprocess.run(
        [sys.executable, str(PLAN_SCRIPT)], capture_output=True, text=True, timeout=120
    )
    if out.returncode == 0:
        log(f"  视图已刷新：{out.stdout.strip() or 'docs/publishing-plan.md'}")
    else:
        log(f"  ⚠ 刷新视图失败：{out.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="发布技能到 ClawHub 并刷新发布规划")
    parser.add_argument("--dir", required=True, help="技能仓本地路径（含 SKILL.md）")
    parser.add_argument("--slug", help="ClawHub slug，默认取目录名")
    parser.add_argument("--name", help="展示名，默认取 slug")
    parser.add_argument("--version", help="版本号，默认读 SKILL.md frontmatter")
    parser.add_argument("--tags", default="latest", help="逗号分隔的 tag，默认 latest")
    parser.add_argument("--changelog", default="", help="变更说明")
    parser.add_argument("--skill", help="publishing-plan.json 里的技能 key（默认按 repo 反查）")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="发布规划 JSON 路径")
    parser.add_argument("--no-plan", action="store_true", help="发布后不更新规划")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不真正发布")
    args = parser.parse_args()

    skill_dir = Path(args.dir).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"技能目录不存在：{skill_dir}")

    slug = args.slug or skill_dir.name
    version = args.version or read_frontmatter_version(skill_dir)
    if not version:
        raise SystemExit("读不到版本号，请用 --version 显式指定")
    repo = git_remote_repo(skill_dir)
    commit = git_commit(skill_dir)

    log(f"技能：{slug}@{version}" + (f"  （{repo} @ {commit}）" if repo else ""))

    clawhub = find_clawhub()
    env = clean_env()

    if not args.dry_run:
        whoami = run(clawhub + ["whoami"], env, timeout=60)
        if whoami.returncode != 0:
            raise SystemExit(
                "未登录 ClawHub。先执行（设备流需人工在浏览器确认）：\n"
                f"  {clawhub} login --device --no-browser\n"
                "拿到验证 URL 后打开浏览器完成授权，再重跑本脚本。"
            )
        log(f"  已登录：{whoami.stdout.strip()}")

    staging = export_clean_dir(skill_dir)

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
        cmd.append("--dry-run")

    log("  发布中…（--no-input，已剥离代理；大包上传可能耗时数十秒）")
    result = run(cmd, env, timeout=600)
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
    verify = run(clawhub + ["skill", "verify", slug], env, timeout=120)
    log(f"  发布校验：{(verify.stdout or verify.stderr or '').strip()[:300]}")
    inspect = run(clawhub + ["inspect", slug], env, timeout=60)
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
            if update_plan(plan_path, skill_key):
                refresh_view()
        else:
            log("  ⚠ 未能定位规划里的技能 key，请用 --skill 指定后单独更新")

    log(f"✅ 已发布 {slug}@{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
