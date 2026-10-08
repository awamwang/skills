#!/usr/bin/env python3
"""发布技能到 LobeHub（multipart 直传，绕过 market-cli Content-Type 坑与 CF 1010）。

前置：
- 技能已在 LobeHub 网页「提交仓库」并 claim（CLI 无法代做）
- 本机已 `npx @lobehub/market-cli@0.0.41` 登录，token 在
  `~/.lobehub-market/user-credentials.json` 的 accessToken

实测（2026-10-08，awam-todo 0.7.1）：
- market-cli `skill publish` 会带错误 Content-Type → Failed to parse form data
- Python urllib 直传会被 Cloudflare 1010 拦
- curl.exe + 浏览器 UA + multipart 可通

用法：
  python skills/awam-skills/scripts/publish_lobehub.py --dir <技能仓> --dry-run
  python skills/awam-skills/scripts/publish_lobehub.py --dir <技能仓>
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402
import credentials as creds  # noqa: E402
import plan_store  # noqa: E402
import public_files  # noqa: E402
import runutil  # noqa: E402
import state_store  # noqa: E402

PLATFORM = "lobehub"
ORG = "awam-skills"
API_TMPL = "https://market.lobehub.com/api/v1/user/skills/{identifier}/versions"
CRED_CANDIDATES = (
    Path.home() / ".lobehub-market" / "user-credentials.json",
    Path.home() / ".lobehub" / "credentials.json",
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_TMP_DIRS: list[Path] = []


def cleanup_tmp(keep: bool = False) -> None:
    if not _TMP_DIRS:
        return
    if keep:
        runutil.log("  保留临时目录（--keep-tmp）：" + "、".join(str(d) for d in _TMP_DIRS))
        return
    for d in _TMP_DIRS:
        shutil.rmtree(d, ignore_errors=True)
    runutil.log(f"  已清理临时目录 {len(_TMP_DIRS)} 个")
    _TMP_DIRS.clear()


def load_token() -> tuple[str, Path]:
    for p in CRED_CANDIDATES:
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        token = data.get("accessToken") or data.get("access_token") or data.get("token")
        if token:
            return token, p
    raise SystemExit(
        "未找到 LobeHub accessToken。请先：\n"
        "  npx -y @lobehub/market-cli@0.0.41 github connect\n"
        f"凭据应落在：{CRED_CANDIDATES[0]}"
    )


def identifier_of(skill_dir: Path) -> str:
    full = runutil.origin_full_name(skill_dir)
    if not full:
        raise SystemExit("无法解析 origin owner/repo")
    # awam-skills/awam-todo-skill → awam-skills-awam-todo-skill
    return full.replace("/", "-")


def build_zip(skill_dir: Path, zip_path: Path, *, skip_secret_scan: bool) -> int:
    if not skip_secret_scan:
        scan = Path(__file__).resolve().parent / "preflight_secrets.py"
        out = runutil.run_utf8(
            [sys.executable, str(scan), "--dir", str(skill_dir)],
            timeout=constants.GIT_ARCHIVE,
        )
        runutil.log((out.stdout or "").strip() or "  敏感串扫描完成")
        if out.returncode != 0:
            raise SystemExit("敏感串扫描未通过，中止发布")

    files, root, source, excluded, outside = public_files.pack_files(skill_dir)
    if root is None or not files:
        raise SystemExit(f"无法打包：{source}")
    runutil.log(f"  发布文件集：{len(files)} 个（{source}）")
    if excluded:
        runutil.log(f"  已排除：{', '.join(excluded[:5])}")
    if outside:
        runutil.log(f"  打包根外跳过：{len(outside)} 个")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_path in files:
            rel = public_files.pack_rel(abs_path, root)
            data = abs_path.read_bytes()
            if rel == "SKILL.md":
                data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            zf.writestr(rel, data)
    return len(files)


def curl_publish(token: str, identifier: str, zip_path: Path, tmp: Path) -> str:
    if not shutil.which("curl.exe") and not shutil.which("curl"):
        raise SystemExit("需要 curl（Windows 自带 curl.exe）")
    curl = "curl.exe" if shutil.which("curl.exe") else "curl"
    hdr = tmp / "auth.hdr"
    # 不把 token 写进 argv
    hdr.write_text(f"Authorization: Bearer {token}\n", encoding="utf-8")
    url = API_TMPL.format(identifier=identifier)
    cmd = [
        curl, "-sS", "-w", "\nHTTP_CODE:%{http_code}\n",
        "-X", "POST", url,
        "-H", "@" + str(hdr),
        "-H", f"User-Agent: {UA}",
        "-H", "Accept: application/json",
        "-H", "Origin: https://market.lobehub.com",
        "-H", "Referer: https://market.lobehub.com/",
        "-F", f"file=@{zip_path};type=application/zip;filename={identifier}.zip",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=constants.CLI_PUBLISH,
            encoding="utf-8", errors="replace",
        )
    finally:
        try:
            hdr.unlink()
        except OSError:
            pass
    out = (proc.stdout or "").replace(token, "***")
    err = (proc.stderr or "").replace(token, "***")
    if err.strip():
        runutil.log(f"  curl stderr：{err.strip()[:300]}")
    if "HTTP_CODE:200" not in out and "HTTP_CODE:201" not in out:
        raise SystemExit(f"LobeHub 发布失败：\n{out[-1500:]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="发布技能到 LobeHub（multipart）")
    ap.add_argument("--dir", required=True, help="技能仓本地路径")
    ap.add_argument("--skill", help="publishing-plan.json 技能 key")
    ap.add_argument("--identifier", help="覆盖 owner-repo 形式的 identifier")
    ap.add_argument("--dry-run", action="store_true", help="只打包 + 校验凭据，不上传")
    ap.add_argument("--no-plan", action="store_true", help="发布后不更新规划")
    ap.add_argument("--skip-secret-scan", action="store_true")
    ap.add_argument("--allow-foreign-repo", action="store_true")
    ap.add_argument("--keep-tmp", action="store_true")
    args = ap.parse_args()

    skill_dir = Path(args.dir).expanduser().resolve()
    warn = creds.source_guard(skill_dir, allow_any=args.allow_foreign_repo)
    if warn:
        raise SystemExit(f"⛔ 发布来源校验未通过：{warn}")

    fm = runutil.read_frontmatter(skill_dir)
    name = fm.get("name", "")
    version = fm.get("version", "")
    ident = args.identifier or identifier_of(skill_dir)
    skill_key = runutil.resolve_skill_key(skill_dir, args.skill)
    runutil.log(f"技能：{name}@{version or '?'}  identifier={ident}  plan_key={skill_key or '?'}")

    token, cred_path = load_token()
    runutil.log(f"  凭据：{cred_path}（已读 accessToken，不打印）")

    tmp = Path(tempfile.mkdtemp(prefix="lobehub_publish_"))
    _TMP_DIRS.append(tmp)
    try:
        zip_path = tmp / f"{ident}.zip"
        n = build_zip(skill_dir, zip_path, skip_secret_scan=args.skip_secret_scan)
        runutil.log(f"  打包完成：{n} 个文件，{zip_path.stat().st_size/1024:.1f} KB")

        if args.dry_run:
            runutil.log("✅ dry-run 通过（未上传）。去掉 --dry-run 即正式发布")
            return 0

        body = curl_publish(token, ident, zip_path, tmp)
        # 打印响应主体（去掉 HTTP_CODE 行）
        lines = [ln for ln in body.splitlines() if not ln.startswith("HTTP_CODE:")]
        runutil.log("  响应：" + " ".join(lines)[:500])

        if not args.no_plan:
            if not skill_key:
                runutil.log("  ⚠ 未能定位规划 key，请用 --skill")
            else:
                if plan_store.set_status(state_store.PLAN_PATH, skill_key, PLATFORM, "done"):
                    runutil.log(f"  规划已更新：skills.{skill_key}.status.lobehub = done")
                if state_store.record_publish_from_repo(
                    state_store.STATE_PATH, skill_dir, skill_key, PLATFORM
                ):
                    runutil.log("  发布状态已记录")
                runutil.refresh_plan_view()

        runutil.log(f"✅ 已发布到 LobeHub：{ident}@{version}")
        return 0
    finally:
        cleanup_tmp(args.keep_tmp)


if __name__ == "__main__":
    raise SystemExit(main())
