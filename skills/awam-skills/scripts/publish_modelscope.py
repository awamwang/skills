#!/usr/bin/env python3
"""把组织下技能发布到魔搭 ModelScope（Skills Central），并刷新发布规划视图。

流程（详见 references/platforms.md）：打包 zip → 上传取 file_id → 创建 Skill → 列表接口验证。
已内置两个实测坑：
- zip 根目录必须**恰好 1 个** SKILL.md；SKILL.md 为 CRLF 会报 `must contain 'name' field`，
  故打包时所有文本文件统一转 LF（二进制写回，防止 \\r\\n 被重新引入）
- 详情接口 `/skills/@owner/name` 可能 404，验证只用列表接口 `/skills?filter.owner=`

鉴权：凭据由 [credentials.py](credentials.py) 自动查找，无需每次手填：
命令行 --token/--owner > 环境变量 MODELSCOPE_API_TOKEN/MODELSCOPE_OWNER
> ~/.workbuddy/secrets/modelscope.json（推荐落点，不在 git 内）
> ~/.config/awam-skills/credentials.json > 索引仓 .credentials.local.json
凭据永不入库，日志只打印来源路径与脱敏后的 token。

用法（索引仓根任意路径均可，脚本自定位）：
  python skills/awam-skills/scripts/publish_modelscope.py --dir <技能仓> --dry-run
  python ... --dir <技能仓>                # 凭据自动查，发布后自动刷新规划
  python ... --dir <技能仓> --no-plan      # 发布但不改规划
  python ... --show-credentials            # 只查凭据来源（脱敏），便于排查
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
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = INDEX_ROOT / "docs" / "publishing-plan.json"
PLAN_SCRIPT = Path(__file__).resolve().parent / "plan_skills.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import credentials as creds  # noqa: E402  （凭据查找：见 credentials.py）

PLATFORM = "modelscope"

API_BASE = "https://modelscope.cn/openapi/v1"
MAX_ZIP_BYTES = 5 * 1024 * 1024  # 魔搭限制 5MB

EXCLUDE_DIRS = {".git", ".cache", ".workbuddy", "__pycache__", "node_modules", ".venv", "venv"}
TEXT_EXT = {".md", ".py", ".json", ".txt", ".yml", ".yaml", ".cfg", ".toml", ".sh"}


def log(msg: str) -> None:
    print(msg, flush=True)


def read_frontmatter(skill_dir: Path) -> tuple[str, str, str]:
    """从 SKILL.md frontmatter 取 (name, version, description)。"""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        nested = skill_dir / "skills" / skill_dir.name / "SKILL.md"
        skill_md = nested if nested.exists() else skill_md
    if not skill_md.exists():
        raise SystemExit(f"找不到 SKILL.md：{skill_dir}")
    text = skill_md.read_text(encoding="utf-8", errors="replace")

    def pick(key: str, default: str = "") -> str:
        m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
        return m.group(1).strip() if m else default

    return pick("name", skill_dir.name), pick("version"), pick("description")


def build_zip(skill_dir: Path, zip_path: Path) -> tuple[int, int]:
    """打包：根目录恰好 1 个 SKILL.md，文本文件统一 LF。"""
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(skill_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                p = Path(root) / f
                rel = p.relative_to(skill_dir).as_posix()
                data = p.read_bytes()
                if p.suffix.lower() in TEXT_EXT:
                    data = data.replace(b"\r\n", b"\n")
                z.writestr(rel, data)
                n += 1

    with zipfile.ZipFile(zip_path) as z:
        root_items = [x for x in z.namelist() if x.count("/") == 0]
        count = root_items.count("SKILL.md")
    if count != 1:
        raise SystemExit(f"zip 根目录的 SKILL.md 必须恰好 1 个，当前 {count} 个：{root_items}")
    return n, zip_path.stat().st_size


def http_json(url: str, token: str, data: bytes | None = None,
              headers: dict | None = None, method: str | None = None,
              timeout: int = 120) -> dict:
    req_headers = {"Authorization": f"Bearer {token}"}
    req_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        # 强制直连：本机 HTTPS_PROXY 对国内站的 HTTPS 隧道会返回 502
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        if e.code == 401:
            raise SystemExit(
                f"HTTP 401 鉴权失败 {url}\n{raw[:400]}\n\n"
                "魔搭 OpenAPI 只认「API Key」（魔搭个人中心 → Access Token / API Key，"
                "通常为 ms_ 开头的字符串），**SDK 令牌（UUID 格式）不能用于 OpenAPI**。\n"
                "若凭据文件里填的是 SDK token，请把 API Key 写入 api_key 字段：\n"
                f"  {creds.candidate_paths(PLATFORM)[0]}\n"
                '  {"owner": "<用户名>", "api_key": "ms_xxx...", "sdk_token": "<保留供 SDK 用>"}'
            )
        raise SystemExit(f"HTTP {e.code} {url}\n{raw[:800]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"网络失败 {url}：{e}")
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit(f"响应不是 JSON：{raw[:300]}")


def multipart_upload(url: str, token: str, file_path: Path, timeout: int = 300) -> dict:
    boundary = uuid.uuid4().hex
    payload = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return http_json(
        url, token, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=timeout,
    )


def update_plan(plan_path: Path, skill_key: str, status: str = "done") -> bool:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    entry = (plan.get("skills") or {}).get(skill_key)
    if entry is None:
        log(f"  ⚠ 规划里没有技能 `{skill_key}`，跳过规划更新")
        return False
    entry.setdefault("status", {})["modelscope"] = status
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"  规划已更新：skills.{skill_key}.status.modelscope = {status}")
    return True


def refresh_view() -> None:
    out = subprocess.run([sys.executable, str(PLAN_SCRIPT)], capture_output=True, text=True, timeout=120)
    if out.returncode == 0:
        log(f"  视图已刷新：{out.stdout.strip() or 'docs/publishing-plan.md'}")
    else:
        log(f"  ⚠ 刷新视图失败：{out.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="发布技能到魔搭 ModelScope")
    parser.add_argument("--dir", required=True, help="技能仓本地路径（含 SKILL.md）")
    parser.add_argument("--owner", help="魔搭用户名（也可 MODELSCOPE_OWNER）")
    parser.add_argument("--token", help="魔搭 API token（也可 MODELSCOPE_API_TOKEN；不建议写在命令行历史里）")
    parser.add_argument("--credentials", help="凭据 JSON 路径（默认自动查找，见 credentials.py）")
    parser.add_argument("--show-credentials", action="store_true",
                        help="只打印凭据来源（脱敏）后退出，用于排查")
    parser.add_argument("--name", help="技能名，默认取 SKILL.md frontmatter 的 name")
    parser.add_argument("--display-name", help="展示名，默认同名")
    parser.add_argument("--license", default="MIT", help="许可证，默认 MIT")
    parser.add_argument("--category", default="other", help="魔搭分类枚举，默认 other")
    parser.add_argument("--body-json", help="自定义创建请求 JSON 模板，可用 {file_id}/{name}/{display_name}/{license}/{category}/{description} 占位")
    parser.add_argument("--skill", help="publishing-plan.json 里的技能 key（默认按 repo 反查）")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="发布规划 JSON 路径")
    parser.add_argument("--no-plan", action="store_true", help="发布后不更新规划")
    parser.add_argument("--dry-run", action="store_true", help="只打包并校验，不上传")
    args = parser.parse_args()

    if args.show_credentials:
        cred, src = creds.load(PLATFORM, args.credentials)
        log(f"凭据来源：{src}")
        log(f"  owner = {cred.get('owner') or '(空)'}")
        log(f"  token = {creds.mask(cred.get('token', ''))}")
        return 0 if cred.get("token") else 1

    skill_dir = Path(args.dir).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"技能目录不存在：{skill_dir}")

    fm_name, version, description = read_frontmatter(skill_dir)
    name = args.name or fm_name
    log(f"技能：{name}@{version or '(未声明版本)'}")

    tmp = Path(tempfile.mkdtemp(prefix="modelscope_publish_"))
    zip_path = tmp / f"{name}.zip"
    count, size = build_zip(skill_dir, zip_path)
    log(f"  打包完成：{count} 个文件，{size/1024:.1f} KB → {zip_path}")
    if size > MAX_ZIP_BYTES:
        raise SystemExit(f"zip 超过魔搭 5MB 限制（{size/1024:.1f} KB），请先瘦身")

    cred, src = creds.load(PLATFORM, args.credentials)
    token = args.token or cred.get("token", "")
    owner = args.owner or cred.get("owner", "")

    if args.dry_run:
        log(f"  凭据来源：{src}｜owner={owner or '(空)'}｜token={creds.mask(token)}")
        if not token or not owner:
            log("⚠ 凭据不完整，正式发布会失败。补齐方式（任选其一）：")
            log(creds.describe(PLATFORM))
        else:
            log("✅ dry-run 通过（未上传）。去掉 --dry-run 即正式发布")
        return 0

    if not token:
        raise SystemExit(
            "缺少魔搭 API token。已查找以下位置均未找到：\n"
            f"{creds.describe(PLATFORM)}\n"
            "任选其一写入（推荐 ~/.workbuddy/secrets/modelscope.json，不在 git 内）：\n"
            '  {"owner": "<魔搭用户名>", "sdk_token": "<token>"}\n'
            "token 获取：魔搭个人中心 → API token / SDK token（不要写进仓库）"
        )
    if not owner:
        raise SystemExit("缺少魔搭用户名：--owner <用户名>、MODELSCOPE_OWNER，或凭据文件里的 owner 字段")
    log(f"  凭据来源：{src}｜owner={owner}｜token={creds.mask(token)}")

    log("  上传 zip…")
    up = multipart_upload(f"{API_BASE}/files/upload", token, zip_path)
    file_id = (up.get("data") or {}).get("id") or up.get("id")
    if not file_id:
        raise SystemExit(f"上传未返回 file_id：{json.dumps(up, ensure_ascii=False)[:400]}")
    log(f"  file_id = {file_id}")

    if args.body_json:
        body_text = args.body_json.format(
            file_id=file_id, name=name, display_name=args.display_name or name,
            license=args.license, category=args.category, description=description,
        )
        body = json.loads(body_text)
    else:
        body = {
            "file_id": file_id,
            "name": name,
            "display_name": args.display_name or name,
            "description": description,
            "license": args.license,
            "category": args.category,
        }
    log("  创建 Skill…")
    try:
        created = http_json(
            f"{API_BASE}/skills", token,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
    except SystemExit as e:
        msg = str(e)
        if "409" in msg:
            log("  ⚠ 已存在同名技能（409 DuplicateEntity）——如需更新版本，请在魔搭后台操作或用 --body-json 调整")
        else:
            log("  ⚠ 创建失败。若报字段错误，用 --body-json 自定义请求体（占位符见 --help）")
        raise
    log(f"  创建成功：{json.dumps(created, ensure_ascii=False)[:300]}")

    listing = http_json(f"{API_BASE}/skills?filter.owner={owner}&page_size=50", token)
    items = (listing.get("data") or {}).get("items") or listing.get("items") or []
    hit = [x for x in items if (x.get("name") or x.get("display_name")) in (name, args.display_name)]
    log(f"  列表接口验证：{'命中 ' + str(hit[0].get('name')) if hit else '未命中（可能异步生效）'}")

    if not args.no_plan:
        plan_path = Path(args.plan)
        key = args.skill
        if not key:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            for k, entry in (plan.get("skills") or {}).items():
                if k == name or k == f"{name}-skill":
                    key = k
                    break
        if key and update_plan(plan_path, key):
            refresh_view()
        else:
            log("  ⚠ 未能定位规划里的技能 key，请用 --skill 指定后单独更新")

    log(f"✅ 已发布到魔搭：{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
