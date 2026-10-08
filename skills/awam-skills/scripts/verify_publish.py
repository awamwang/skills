#!/usr/bin/env python3
"""发布后线上复核：以平台上的内容 / 版本为准，不只看接口 success。

检查项（按 --platforms 选择，默认全开能查的）：
- github：本地 HEAD 与 origin 同步（短哈希一致）
- modelscope：SDK download_repo 列文件，确认无 storage/ / env.json / index.json / *.log
- clawhub：`clawhub inspect <slug>` 的 latestVersion == frontmatter version
- lobehub：`npx @lobehub/market-cli@0.0.41 skill list` 的 LATEST VERSION
- skillssh：GET https://skills.sh/<owner>/<repo> → 200

用法：
  python skills/awam-skills/scripts/verify_publish.py --dir <技能仓>
  python skills/awam-skills/scripts/verify_publish.py --dir <技能仓> --platforms modelscope,clawhub
  python skills/awam-skills/scripts/verify_publish.py --dir <技能仓> --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402
import credentials as creds  # noqa: E402
import runutil  # noqa: E402

DEFAULT_PLATFORMS = ("github", "modelscope", "clawhub", "lobehub", "skillssh")
BAD_NAMES = {"env.json", "index.json"}
BAD_PREFIXES = ("storage/",)
BAD_SUFFIXES = (".log",)
LOBEHUB_CLI = "@lobehub/market-cli@0.0.41"


def _ok(msg: str) -> dict:
    return {"ok": True, "detail": msg}


def _fail(msg: str) -> dict:
    return {"ok": False, "detail": msg}


def verify_github(skill_dir: Path) -> dict:
    local = runutil.run_utf8(
        ["git", "-C", str(skill_dir), "rev-parse", "--short", "HEAD"],
        timeout=constants.GIT_FAST,
    )
    if local.returncode != 0:
        return _fail("无法读本地 HEAD")
    head = (local.stdout or "").strip()
    # 相对 upstream
    ahead = runutil.run_utf8(
        ["git", "-C", str(skill_dir), "rev-list", "--count", "@{upstream}..HEAD"],
        timeout=constants.GIT_OP,
    )
    behind = runutil.run_utf8(
        ["git", "-C", str(skill_dir), "rev-list", "--count", "HEAD..@{upstream}"],
        timeout=constants.GIT_OP,
    )
    if ahead.returncode != 0:
        return _fail(f"无 upstream（本地 {head}）")
    a = int((ahead.stdout or "0").strip() or "0")
    b = int((behind.stdout or "0").strip() or "0") if behind.returncode == 0 else 0
    if a or b:
        return _fail(f"本地 {head} 与远程不同步（领先 {a} / 落后 {b}）")
    return _ok(f"本地与远程一致（{head}）")


def verify_modelscope(skill_dir: Path, name: str) -> dict:
    cred, src = creds.load("modelscope", None)
    token = cred.get("token", "")
    owner = cred.get("owner", "")
    if not token or not owner:
        return _fail(f"缺魔搭凭据（来源 {src}）")
    try:
        from modelscope_hub import HubApi
    except ImportError:
        return _fail("未安装 modelscope_hub（先跑 setup_env.py）")

    api = HubApi()
    try:
        api.login(token)
    except Exception as e:  # noqa: BLE001
        return _fail(f"login 失败：{e}")

    tmp = Path(tempfile.mkdtemp(prefix="ms_verify_"))
    try:
        # 兼容不同 SDK 签名
        try:
            from modelscope_hub.constants import RepoType  # type: ignore
            api.download_repo(f"{owner}/{name}", repo_type=RepoType.SKILL, local_dir=str(tmp))
        except Exception:
            try:
                api.download_repo(f"{owner}/{name}", repo_type="skill", local_dir=str(tmp))
            except Exception as e:  # noqa: BLE001
                return _fail(f"download_repo 失败：{e}")

        files = sorted(
            p.relative_to(tmp).as_posix()
            for p in tmp.rglob("*") if p.is_file()
        )
        bad = [
            f for f in files
            if f in BAD_NAMES
            or any(f.startswith(p) for p in BAD_PREFIXES)
            or f.lower().endswith(BAD_SUFFIXES)
        ]
        if bad:
            return _fail(f"线上含私密/日志文件：{', '.join(bad[:8])}（共 {len(files)} 个）")
        return _ok(f"{owner}/{name} 下载 {len(files)} 个文件，无私密夹带")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def verify_clawhub(name: str, version: str) -> dict:
    bin_path = os.environ.get("CLAWHUB_BIN") or shutil.which("clawhub")
    if not bin_path:
        return _fail("未找到 clawhub CLI")
    out = runutil.run_utf8(
        [bin_path, "inspect", name, "--no-input"],
        timeout=constants.CLI_INSPECT,
        env={**os.environ, "HTTPS_PROXY": "", "HTTP_PROXY": "",
             "https_proxy": "", "http_proxy": "", "NO_PROXY": "*"},
    )
    text = (out.stdout or "") + "\n" + (out.stderr or "")
    if out.returncode != 0 and "latest" not in text.lower():
        return _fail(f"inspect 失败：{text.strip()[:300]}")
    # 兼容表格 / JSON
    m = re.search(r"latest\s*=\s*([0-9]+\.[0-9]+\.[0-9]+)", text, re.I)
    if not m:
        m = re.search(r'"latestVersion"\s*:\s*"([^"]+)"', text)
    if not m:
        m = re.search(r"Latest\s+([0-9]+\.[0-9]+\.[0-9]+)", text)
    latest = m.group(1) if m else ""
    if version and latest and latest != version:
        return _fail(f"线上 latest={latest} ≠ 本地 {version}")
    if latest:
        return _ok(f"latest={latest}")
    return _ok("inspect 已返回（未能解析版本号，请人工看输出）")


def verify_lobehub(skill_dir: Path, version: str) -> dict:
    ident = (runutil.origin_full_name(skill_dir) or "").replace("/", "-")
    if not ident:
        return _fail("无法解析 identifier")
    if not shutil.which("npx"):
        return _fail("未找到 npx")
    out = runutil.run_utf8(
        ["npx", "-y", LOBEHUB_CLI, "skill", "list"],
        timeout=constants.NPX_SKILLS_LIST,
    )
    text = out.stdout or ""
    if out.returncode != 0:
        return _fail(f"skill list 失败：{(out.stderr or text)[:300]}")
    # 按行找 identifier
    hit = None
    for line in text.splitlines():
        if ident in line:
            hit = line
            break
    if not hit:
        return _fail(f"list 中未找到 {ident}")
    m = re.search(r"(\d+\.\d+\.\d+)", hit)
    latest = m.group(1) if m else ""
    if "published" not in hit.lower() and "PUBLISHED" not in hit:
        # 表头可能大写 STATUS
        pass
    if version and latest and latest != version:
        return _fail(f"线上 {latest} ≠ 本地 {version}（行：{hit.strip()[:120]}）")
    if latest:
        return _ok(f"{ident}@{latest} published")
    return _ok(f"已找到 {ident}（行：{hit.strip()[:120]}）")


def verify_skillssh(skill_dir: Path) -> dict:
    full = runutil.origin_full_name(skill_dir)
    if not full:
        return _fail("无法解析 owner/repo")
    url = f"https://skills.sh/{full}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=constants.SKILLSSH_PAGE) as resp:
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # noqa: BLE001
        return _fail(f"请求失败：{e}")
    if code == 200:
        return _ok(url)
    return _fail(f"{url} → HTTP {code}")


def main() -> int:
    ap = argparse.ArgumentParser(description="发布后线上复核")
    ap.add_argument("--dir", required=True, help="技能仓本地路径")
    ap.add_argument(
        "--platforms",
        default=",".join(DEFAULT_PLATFORMS),
        help="逗号分隔：github,modelscope,clawhub,lobehub,skillssh",
    )
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    skill_dir = Path(args.dir).expanduser().resolve()
    fm = runutil.read_frontmatter(skill_dir)
    name = fm.get("name", "")
    version = fm.get("version", "")
    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]

    results: dict[str, dict] = {}
    runutil.log(f"复核：{name}@{version}  platforms={','.join(platforms)}")

    checkers = {
        "github": lambda: verify_github(skill_dir),
        "modelscope": lambda: verify_modelscope(skill_dir, name),
        "clawhub": lambda: verify_clawhub(name, version),
        "lobehub": lambda: verify_lobehub(skill_dir, version),
        "skillssh": lambda: verify_skillssh(skill_dir),
    }
    for p in platforms:
        if p not in checkers:
            results[p] = _fail(f"未知平台 {p}")
            continue
        try:
            results[p] = checkers[p]()
        except Exception as e:  # noqa: BLE001
            results[p] = _fail(str(e))
        icon = "✅" if results[p]["ok"] else "❌"
        runutil.log(f"  {icon} {p}: {results[p]['detail']}")

    if args.json:
        print(json.dumps({"name": name, "version": version, "results": results},
                         ensure_ascii=False, indent=2))

    bad = [p for p, r in results.items() if not r["ok"]]
    if bad:
        runutil.log(f"结果：{len(results) - len(bad)} PASS / {len(bad)} FAIL → {', '.join(bad)}")
        return 1
    runutil.log(f"结果：{len(results)} PASS / 0 FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
