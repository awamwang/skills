#!/usr/bin/env python3
"""把组织下技能登记进 skills.sh（find-skills 生态）并刷新发布规划。

skills.sh 的收录机制与其它平台不同：**没有提交 / 上传入口**。索引由
skills CLI 的匿名安装遥测自动触发——任何人执行一次
`npx skills add <owner>/<repo>`（遥测开启时），仓库与技能就会出现在
skills.sh（排名 = 安装量）。因此本脚本的「发布」实质是**触发一次安装并确认收录**：

1. dry-run：`npx -y skills@<ver> add <owner>/<repo> -l -y`
   —— 克隆公开仓并列出可发现的技能，验证「GitHub 公开 + SKILL.md 能被发现」，
   不安装、无遥测。
2. 正式：在临时「项目目录」（含 package.json）里执行
   `npx -y skills@<ver> add <owner>/<repo> --all --json`
   （`--all` = `--skill '*' --agent '*' -y`），project 作用域的安装产物全部落在
   临时目录内，触发一次安装遥测后整目录丢弃。
3. 复核：GET `https://skills.sh/<owner>/<repo>` 轮询至 200（收录有延迟）。

实测要点（2026-10-07，skills CLI 1.7.1）：
- `--json` 必须与 `-y` / `--all` 同用，且**不能与 `-l` 组合**（CLI 直接报错，快败）
- project 作用域会把 `.agents/` `.claude/` `agent/` `skills-lock.json` 全写进 cwd
  （实测一次安装给 79 个 agent 建了链接）——**必须在临时目录里跑**，
  在技能仓里跑等于往工作区倒垃圾；临时目录里放 `package.json` 是判定
  「project 作用域」的关键
- 遥测默认开启；`DISABLE_TELEMETRY` / `DO_NOT_TRACK` 会让安装**不计入**——
  本脚本在触发子进程里剥离这两个变量（检测到会打日志）
- 版本锁定 `skills@1.7.1`（与 LobeHub 锁 `@0.0.41` 同理：`npx -y` 拉包即执行，
  防投毒）。升级前先 `npm view skills version` 核对再改 `--npx-package` 默认值
- skills.sh 收录有延迟：实测触发后几十秒内页面上线（此前 404）；脚本轮询约
  90s，超时用 `--verify-only` 稍后单独确认，**不要反复重装刷安装量**
- skills.sh **无需任何凭据 / 登录**（区别于魔搭 / LobeHub / ClawHub）；
  发布内容即公开 GitHub 仓本身，无上传环节，敏感串扫描不适用——
  靠 preflight.py 的「私密文件已被 git 跟踪」检查兜底
- 代理环境**保持原样**（区别于 ClawHub 剥离 `*_PROXY`）：本机实测走代理安装正常；
  页面探测走 urllib 默认 opener（自动认 `*_PROXY`）

用法（索引仓根任意路径均可，脚本自定位）：
  python skills/awam-skills/scripts/publish_skillssh.py --dir <技能仓路径> --dry-run
  python skills/awam-skills/scripts/publish_skillssh.py --dir <技能仓路径>          # 触发收录 + 刷新规划
  python skills/awam-skills/scripts/publish_skillssh.py --dir <技能仓路径> --verify-only  # 只查页面确认收录
  python skills/awam-skills/scripts/publish_skillssh.py --dir <技能仓路径> --no-plan
  python skills/awam-skills/scripts/publish_skillssh.py --dir <技能仓路径> --customize   # 顺带生成 skills.sh.json 模板
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
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402  （共享超时等常量：见 constants.py）
import credentials as creds  # noqa: E402  （来源校验 + origin 读取：见 credentials.py）
import plan_store  # noqa: E402  （规划就地更新，保留原排版：见 plan_store.py）

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = INDEX_ROOT / "docs" / "publishing-plan.json"
PLAN_SCRIPT = Path(__file__).resolve().parent / "plan_skills.py"
PLATFORM = "skillssh"

# 版本锁定：npx -y 拉包即执行，固定版本防投毒（升级先 `npm view skills version` 核对）
DEFAULT_NPX_PACKAGE = "skills@1.7.1"

PAGE_URL = "https://skills.sh/{repo}"
PAGE_POLL_ATTEMPTS = 10   # 共 10 × 9s ≈ 90s（实测收录在几十秒内）
PAGE_POLL_INTERVAL = 9

# 遥测开关：置任一变量会让安装不计入 skills.sh 排名 —— 触发子进程里必须剥离
TELEMETRY_OFF_KEYS = ["DISABLE_TELEMETRY", "DO_NOT_TRACK"]

# npx 混合输出（进度框 + JSON）时兜底提取 JSON 数组用
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def log(msg: str) -> None:
    print(msg, flush=True)


# 本次运行创建的临时目录；main() 在 finally 里清理（--keep-tmp 可保留）。
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


def find_npx() -> str:
    """定位 npx。

    Windows 上 `shutil.which("npx")` 会先命中 nodejs 目录里**无扩展名的 sh shim**
    （`CreateProcess` 执行它直接 `WinError 193`，实测踩到），必须优先找 `npx.cmd`。
    """
    candidates = ("npx.cmd", "npx.exe", "npx") if os.name == "nt" else ("npx",)
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit(
        "找不到 npx。安装 Node.js（含 npm/npx）后重试：https://nodejs.org/\n"
        "或用 --npx-package 指定其它包管理器可执行的包名（不建议）。"
    )


def child_env(strip_telemetry_off: bool) -> dict:
    """构建子进程环境：禁 git 凭据交互（私仓克隆会静默挂死）；按需剥离遥测开关。

    代理变量**保持原样**——本机实测走代理安装正常（与 ClawHub 剥代理的场景相反）。
    """
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPTS"] = "0"
    if strip_telemetry_off:
        for key in TELEMETRY_OFF_KEYS:
            if env.pop(key, None) is not None:
                log(f"  已剥离 {key}（置位会让安装不计入 skills.sh 排名）")
    return env


def run(cmd: list[str], cwd: Path | None, env: dict, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=timeout,
        stdin=subprocess.DEVNULL,
    )


def make_project_dir() -> Path:
    """建临时「项目目录」：skills CLI 以 cwd 有无 package.json 判定 project 作用域。

    project 作用域的安装产物（.agents/ .claude/ agent/ skills-lock.json…）
    全部落在 cwd 下，不碰用户目录 —— 所以临时目录 + 完事即删就是安全边界。
    """
    tmp = Path(tempfile.mkdtemp(prefix="skillssh_trigger_"))
    _TMP_DIRS.append(tmp)
    (tmp / "package.json").write_text(
        '{ "name": "skillssh-trigger", "private": true }\n', encoding="utf-8"
    )
    return tmp


def dry_run_discover(npx: str, package: str, repo: str) -> None:
    """`add <repo> -l -y`：克隆公开仓并列出可发现技能（不安装、无遥测）。

    返回 None；仓库不可访问 / 找不到技能时 SystemExit。
    """
    tmp = make_project_dir()
    env = child_env(strip_telemetry_off=False)
    log(f"  发现性检查：{npx} -y {package} add {repo} -l -y（克隆公开仓，不安装）")
    result = run(
        [npx, "-y", package, "add", repo, "-l", "-y"],
        cwd=tmp, env=env, timeout=constants.NPX_SKILLS_LIST,
    )
    output = _ANSI_RE.sub("", (result.stdout or "") + (result.stderr or ""))
    if result.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-12:])
        raise SystemExit(
            f"发现性检查失败（exit={result.returncode}）：仓库不可公开克隆或 CLI 出错\n{tail}\n"
            "先确认仓库已在 GitHub 公开（gh repo view <repo> --json visibility）。"
        )
    if re.search(r"No skills found", output, re.IGNORECASE):
        raise SystemExit("CLI 能克隆仓库但没找到技能：确认 SKILL.md 在仓库根或 skills/<name>/ 下")
    # 清单行的技能名格式不稳定，改从「Found N skill(s)」摘要行确认数量即可
    found = re.search(r"Found\s+(\d+)\s+skill", output)
    count = int(found.group(1)) if found else 0
    if count > 0:
        log(f"  发现 {count} 个技能（SKILL.md 可被 CLI 识别）")
    else:
        log("  ⚠ 未解析到「Found N skill」摘要行，但退出码为 0；输出片段：")
        log("    " + output.strip().replace("\n", "\n    ")[:500])


def trigger_install(npx: str, package: str, repo: str) -> None:
    """在临时项目目录里 `add <repo> --all --json`：触发一次计入排名的安装。

    `--all` = `--skill '*' --agent '*' -y`：全技能、全 agent、无交互；
    解析 --json 结果确认每个技能 status == "installed"。
    """
    tmp = make_project_dir()
    env = child_env(strip_telemetry_off=True)
    log(f"  触发收录：{npx} -y {package} add {repo} --all --json（临时目录 {tmp.name}）")
    result = run(
        [npx, "-y", package, "add", repo, "--all", "--json"],
        cwd=tmp, env=env, timeout=constants.NPX_SKILLS_ADD,
    )
    if result.returncode != 0:
        tail = "\n".join(
            _ANSI_RE.sub("", ((result.stdout or "") + (result.stderr or ""))).strip().splitlines()[-12:]
        )
        raise SystemExit(f"安装失败（exit={result.returncode}），收录未触发\n{tail}")

    entries = parse_install_json(result.stdout or "")
    if entries is None:
        # 解析失败但退出码 0：大概率仍触发成功，给出降级判断
        flat = _ANSI_RE.sub("", (result.stdout or "") + (result.stderr or ""))
        if "installed" in flat:
            log("  ⚠ --json 解析失败，但输出含 installed：按安装成功处理（建议 --verify-only 复核页面）")
            return
        raise SystemExit(
            "安装退出码为 0 但既解析不到 JSON 也看不到 installed，无法确认收录。\n"
            "可加 --keep-tmp 重跑排查，或手动在临时目录执行同命令观察输出。"
        )
    bad = [e for e in entries if e.get("status") not in ("installed", None)]
    names = ", ".join(
        str(e.get("skill") or e.get("name") or Path(str(e.get("path", "?"))).name)
        for e in entries
    ) or "(未知名)"
    if bad:
        raise SystemExit(
            f"部分技能未安装成功：{json.dumps(bad, ensure_ascii=False)[:400]}\n收录可能不完整，先排查再重跑。"
        )
    log(f"  安装成功（技能：{names}），安装遥测已触发")


def parse_install_json(stdout: str) -> list[dict] | None:
    """解析 `--json` 的输出：优先整体 json.loads，失败则兜底提取首个 JSON 数组块。

    CLI 在 --json 模式下偶尔会往 stdout 混进度框文本（实测：摘要框 + JSON 同流），
    所以两层解析都要有。返回条目列表；解析不出返回 None。
    """
    text = _ANSI_RE.sub("", stdout).strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return None


def check_page(repo: str) -> bool:
    """轮询 skills.sh 仓库页，200 即已收录。404 = 还没上线，继续等。"""
    url = PAGE_URL.format(repo=repo)
    log(f"  页面复核：GET {url}（收录有延迟，最多等约 {PAGE_POLL_ATTEMPTS * PAGE_POLL_INTERVAL}s）")
    for i in range(1, PAGE_POLL_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=constants.SKILLSSH_PAGE) as resp:
                if resp.status == 200:
                    log(f"  ✅ 页面已上线（第 {i} 次探测，HTTP 200）")
                    return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                log(f"  … 第 {i}/{PAGE_POLL_ATTEMPTS} 次探测：404，索引还没上线，稍候重试")
            else:
                log(f"  … 第 {i}/{PAGE_POLL_ATTEMPTS} 次探测：HTTP {e.code}（非 404，稍后重试）")
        except urllib.error.URLError as e:
            log(f"  … 第 {i}/{PAGE_POLL_ATTEMPTS} 次探测：网络错误 {e.reason}，稍后重试")
        if i < PAGE_POLL_ATTEMPTS:
            time.sleep(PAGE_POLL_INTERVAL)
    return False


def write_customize(skill_dir: Path) -> None:
    """在仓库根生成 skills.sh.json 模板（已存在则不动）。

    skills.sh.json 只影响 skills.sh 仓库页的**分组展示**（groupings / notGrouped），
    单技能仓无必要；一仓多技能（嵌套布局）才有意义。脚本只生成**合法 JSON** 模板
    （skills.sh 会直接解析它，写非法 JSON 会连累仓库页），改好再提交。
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(skill_dir), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=constants.GIT_FAST,
        )
        root = Path(out.stdout.strip()) if out.returncode == 0 else skill_dir
    except Exception:
        root = skill_dir
    target = root / "skills.sh.json"
    if target.exists():
        log(f"  skills.sh.json 已存在，保持不动：{target}")
        return
    template = {
        "$schema": "https://skills.sh/schemas/skills.sh.schema.json",
        "notGrouped": "bottom",
        "groupings": [],
    }
    target.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log(f"  已生成 skills.sh.json 模板：{target}")
    log("  一仓多技能时把分组写进 groupings（title/description/skills），单技能仓可整文件不提交")


def update_plan(plan_path: Path, skill_key: str, status: str = "done") -> bool:
    """就地改 `status.skillssh`，**逐字节保留原排版**（见 plan_store.py 的说明）。"""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    skills = plan.get("skills") or {}
    if skills.get(skill_key) is None:
        log(f"  ⚠ 规划里没有技能 `{skill_key}`，跳过规划更新；请手动补 skills 条目")
        return False
    if not plan_store.set_status(plan_path, skill_key, "skillssh", status):
        log(f"  ⚠ 无法就地更新技能 `{skill_key}` 的 status.skillssh，请手动改")
        return False
    log(f"  规划已更新：skills.{skill_key}.status.skillssh = {status}（保留原排版）")
    return True


def refresh_view() -> None:
    """调用 plan_skills.py 刷新人读视图（不手改 md）。

    Windows 下 `text=True` 默认按 GBK 解码，plan_skills.py 输出中文会炸掉
    读取线程（stdout 变 None，实测踩到），必须显式 `encoding="utf-8"`。
    """
    out = subprocess.run(
        [sys.executable, str(PLAN_SCRIPT)], capture_output=True, timeout=constants.PLAN_SCRIPT,
        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
    )
    if out.returncode == 0:
        log(f"  视图已刷新：{(out.stdout or '').strip() or 'docs/publishing-plan.md'}")
    else:
        log(f"  ⚠ 刷新视图失败：{(out.stderr or '').strip() or f'退出码 {out.returncode}'}")


def resolve_repo(args, skill_dir: Path) -> str:
    repo = args.repo or creds.git_remote_repo(skill_dir)
    if not repo:
        raise SystemExit("读不到 origin 远程仓（或非 GitHub），请用 --repo <owner>/<name> 显式指定")
    if repo.count("/") != 1:
        raise SystemExit(f"--repo 需要 owner/name 形式，当前：{repo}")
    return repo


def _update_plan_block(args, repo: str, status: str) -> None:
    if args.no_plan:
        return
    plan_path = Path(args.plan)
    skill_key = args.skill
    if not skill_key:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for key, entry in (plan.get("skills") or {}).items():
            if entry.get("repo") == repo:
                skill_key = key
                break
    if skill_key:
        if update_plan(plan_path, skill_key, status):
            refresh_view()
    else:
        log("  ⚠ 未能定位规划里的技能 key，请用 --skill 指定后单独更新")


def _run(args) -> int:
    if not args.dir:
        raise SystemExit("需要 --dir 指定技能仓本地路径（含 SKILL.md）")
    skill_dir = Path(args.dir).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"技能目录不存在：{skill_dir}")

    warn = creds.source_guard(skill_dir, allow_any=args.allow_foreign_repo)
    if warn:
        raise SystemExit(f"⛔ 发布来源校验未通过：{warn}\n  待发布目录：{skill_dir}")

    repo = resolve_repo(args, skill_dir)
    log(f"技能仓：{repo} → https://skills.sh/{repo}")

    npx = find_npx()
    package = args.npx_package

    if args.customize:
        write_customize(skill_dir)

    if args.verify_only:
        if check_page(repo):
            _update_plan_block(args, repo, "done")
            log(f"✅ 已确认收录：https://skills.sh/{repo}")
            return 0
        log(
            f"⚠ 页面仍未上线（https://skills.sh/{repo} 404）。\n"
            "  收录延迟较长时稍后再跑一次 --verify-only；确认前不要反复重装刷安装量。"
        )
        _update_plan_block(args, repo, "todo")
        return 1

    dry_run_discover(npx, package, repo)
    if args.dry_run:
        log(f"✅ dry-run 通过：{repo} 可被 skills CLI 公开发现（未触发收录）")
        return 0

    trigger_install(npx, package, repo)

    if check_page(repo):
        _update_plan_block(args, repo, "done")
        log(f"✅ 已收录 skills.sh：https://skills.sh/{repo}")
        return 0

    log(
        "⚠ 安装遥测已触发，但页面在等待窗口内未上线（收录延迟）。\n"
        f"  稍后跑一次确认：python {Path(__file__).name} --dir <技能仓> --verify-only\n"
        "  不要反复重装刷安装量。"
    )
    _update_plan_block(args, repo, "todo")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="触发 skills.sh 收录（skills CLI 安装遥测）并刷新发布规划；无需任何凭据"
    )
    parser.add_argument("--dir", help="技能仓本地路径（含 SKILL.md）")
    parser.add_argument("--repo", help="GitHub owner/name，默认读技能仓 origin")
    parser.add_argument("--skill", help="publishing-plan.json 里的技能 key（默认按 repo 反查）")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="发布规划 JSON 路径")
    parser.add_argument("--no-plan", action="store_true", help="成功后不更新规划")
    parser.add_argument("--dry-run", action="store_true",
                        help="只做发现性检查（-l -y，不安装、无遥测）")
    parser.add_argument("--verify-only", action="store_true",
                        help="跳过安装，只轮询 skills.sh 页面确认收录（收录延迟时用）")
    parser.add_argument("--customize", action="store_true",
                        help="在仓库根生成 skills.sh.json 分组展示模板（已存在则不动）")
    parser.add_argument("--keep-tmp", action="store_true",
                        help="保留临时触发目录（默认完事即删，避免 %%TEMP%% 越堆越多）")
    parser.add_argument("--allow-foreign-repo", action="store_true",
                        help="跳过来源校验（默认要求 origin 属于 awam-skills/ 组织）")
    parser.add_argument("--npx-package", default=DEFAULT_NPX_PACKAGE,
                        help=f"npx 拉的包名（默认 {DEFAULT_NPX_PACKAGE}，版本锁定防投毒）")
    args = parser.parse_args()

    try:
        return _run(args)
    finally:
        cleanup_tmp(args.keep_tmp)


if __name__ == "__main__":
    raise SystemExit(main())
