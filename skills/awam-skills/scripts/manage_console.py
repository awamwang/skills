#!/usr/bin/env python3
"""本机技能管理控制台：改发布规划 + 批量升级 / 移出管理 / 发布。

仅绑定 127.0.0.1。规划保存与真正发版分开；不替用户 commit / push。

用法：
  python skills/awam-skills/scripts/manage_console.py
  python skills/awam-skills/scripts/manage_console.py --port 8754 --open
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import sys
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import constants  # noqa: E402
import plan_store  # noqa: E402
import runutil  # noqa: E402
import state_store  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
STATIC_DIR = SCRIPTS / "manage_console"
INDEX_ROOT = state_store.INDEX_ROOT

# release.py 已支持的平台（与 PLATFORM_SCRIPTS 对齐；不含 agentpowers）
RELEASE_PLATFORMS = (
    "github",
    "modelscope",
    "clawhub",
    "lobehub",
    "skillssh",
    "doubao",
)
PLAN_VALUES = frozenset({"publish", "optional", "skip"})
BUMP_PARTS = frozenset({"major", "minor", "patch"})


def _load_plan() -> dict:
    return json.loads(state_store.PLAN_PATH.read_text(encoding="utf-8"))


def _load_repos_safe() -> dict:
    try:
        return state_store.load_repos()
    except FileNotFoundError:
        return {"repos": {}}


def api_skills() -> dict:
    plan = _load_plan()
    repos = (_load_repos_safe().get("repos") or {})
    platforms_meta = plan.get("platforms") or {}
    # 规划展示用全部平台；发布勾选仅 RELEASE_PLATFORMS
    platform_order = [
        p for p in (
            "github", "lobehub", "modelscope", "doubao",
            "clawhub", "agentpowers", "skillssh",
        )
        if p in platforms_meta
    ] or list(platforms_meta.keys())

    skills_out: list[dict] = []
    for key, sk in (plan.get("skills") or {}).items():
        if not isinstance(sk, dict):
            continue
        meta = repos.get(key) or {}
        skills_out.append({
            "key": key,
            "tier": sk.get("tier") or "",
            "repo": sk.get("repo") or meta.get("repo") or "",
            "summary": sk.get("summary") or "",
            "notes": sk.get("notes") or "",
            "plan": dict(sk.get("plan") or {}),
            "status": dict(sk.get("status") or {}),
            "version": meta.get("version"),
            "name": meta.get("name") or "",
            "path": meta.get("path"),
            "version_reason": meta.get("version_reason"),
        })
    skills_out.sort(key=lambda s: (s.get("tier") or "z", s["key"]))

    return {
        "platforms": [
            {
                "id": pid,
                "name": (platforms_meta.get(pid) or {}).get("name") or pid,
                "releasable": pid in RELEASE_PLATFORMS,
            }
            for pid in platform_order
        ],
        "release_platforms": list(RELEASE_PLATFORMS),
        "plan_labels": plan.get("plan_labels") or {},
        "status_labels": plan.get("status_labels") or {},
        "tiers": plan.get("tiers") or {},
        "skills": skills_out,
        "updated": plan.get("updated") or "",
    }


def api_save_plan(body: dict) -> dict:
    changes = body.get("changes") or []
    if not isinstance(changes, list):
        raise ValueError("changes 须为数组")

    plan = _load_plan()
    plan_labels = set((plan.get("plan_labels") or {}).keys()) or PLAN_VALUES
    platforms = set((plan.get("platforms") or {}).keys())
    skills = plan.get("skills") or {}

    applied: list[dict] = []
    failed: list[dict] = []

    for item in changes:
        if not isinstance(item, dict):
            failed.append({"error": "条目非对象"})
            continue
        skill = (item.get("skill") or "").strip()
        pmap = item.get("plan") or {}
        if not skill or skill not in skills:
            failed.append({"skill": skill, "error": "未知技能"})
            continue
        if not isinstance(pmap, dict):
            failed.append({"skill": skill, "error": "plan 须为对象"})
            continue
        for platform, value in pmap.items():
            if platform not in platforms:
                failed.append({
                    "skill": skill, "platform": platform, "error": "未知平台",
                })
                continue
            if value not in plan_labels:
                failed.append({
                    "skill": skill, "platform": platform,
                    "error": f"非法 plan 值 {value!r}",
                })
                continue
            ok = plan_store.set_plan(
                state_store.PLAN_PATH, skill, platform, value
            )
            if ok:
                applied.append({
                    "skill": skill, "platform": platform, "value": value,
                })
            else:
                failed.append({
                    "skill": skill, "platform": platform, "error": "写入失败",
                })

    view_log = ""
    if applied:
        out = runutil.run_utf8(
            [sys.executable, str(SCRIPTS / "plan_skills.py")],
            cwd=INDEX_ROOT,
            timeout=constants.PLAN_SCRIPT,
        )
        view_log = ((out.stdout or "") + (out.stderr or "")).strip()
        if out.returncode != 0:
            failed.append({
                "error": f"plan_skills.py 退出 {out.returncode}",
                "log": view_log,
            })

    return {
        "ok": not failed,
        "applied": applied,
        "failed": failed,
        "view_log": view_log,
    }


def _run_script(script: str, args: list[str], *, timeout: int | None) -> dict:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    try:
        out = runutil.run_utf8(cmd, cwd=INDEX_ROOT, timeout=timeout)
        log = ((out.stdout or "") + (out.stderr or "")).rstrip()
        return {
            "cmd": " ".join(cmd),
            "exit": out.returncode,
            "log": log,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": " ".join(cmd),
            "exit": -1,
            "log": f"超时（{timeout}s）：{e}",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "cmd": " ".join(cmd),
            "exit": 1,
            "log": f"异常：{e}\n{traceback.format_exc()}",
        }


def _resolve_skill_path(skill_key: str, repos: dict) -> Path | None:
    meta = (repos.get("repos") or {}).get(skill_key) or {}
    path = meta.get("path")
    if not path:
        return None
    p = Path(path).expanduser().resolve()
    return p if p.is_dir() else None


def api_upgrade(body: dict) -> dict:
    skills = body.get("skills") or []
    part = (body.get("part") or "patch").strip().lower()
    if part not in BUMP_PARTS:
        raise ValueError(f"part 须为 major|minor|patch，收到 {part!r}")
    if not skills:
        raise ValueError("未指定技能")

    results = []
    for key in skills:
        key = (key or "").strip()
        if not key:
            continue
        results.append({
            "skill": key,
            **_run_script(
                "upgrade_skill.py",
                ["--skill", key, "--part", part],
                timeout=constants.GIT_OP + 60,
            ),
        })
    return {
        "ok": all(r.get("exit") == 0 for r in results),
        "results": results,
    }


def api_unmanage(body: dict) -> dict:
    skills = [((s or "").strip()) for s in (body.get("skills") or []) if s]
    if not skills:
        raise ValueError("未指定技能")
    args: list[str] = []
    for k in skills:
        args.extend(["--skill", k])
    r = _run_script(
        "unmanage_skill.py",
        args,
        timeout=constants.PLAN_SCRIPT + 60,
    )
    return {
        "ok": r["exit"] == 0,
        "results": [{"skill": ",".join(skills), **r}],
    }


def api_release(body: dict) -> dict:
    skills = [((s or "").strip()) for s in (body.get("skills") or []) if s]
    platforms = [
        (p or "").strip().lower()
        for p in (body.get("platforms") or [])
        if p
    ]
    if not skills:
        raise ValueError("未指定技能")
    if not platforms:
        raise ValueError("未指定发布平台")
    bad = [p for p in platforms if p not in RELEASE_PLATFORMS]
    if bad:
        raise ValueError(f"不支持发布的平台：{', '.join(bad)}")

    repos = _load_repos_safe()
    results = []
    for key in skills:
        skill_dir = _resolve_skill_path(key, repos)
        if skill_dir is None:
            results.append({
                "skill": key,
                "exit": 1,
                "cmd": "",
                "log": f"repos.json 无有效本机 path：{key}",
            })
            continue
        # 单技能超时：预检 + 各平台上限粗算
        timeout = constants.RELEASE_PLATFORM * max(1, len(platforms)) + 120
        results.append({
            "skill": key,
            **_run_script(
                "release.py",
                [
                    "--dir", str(skill_dir),
                    "--skill", key,
                    "--platforms", ",".join(platforms),
                ],
                timeout=timeout,
            ),
        })
    return {
        "ok": all(r.get("exit") == 0 for r in results),
        "results": results,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AwamManageConsole/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 2_000_000:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON 根须为对象")
        return data

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/skills":
            try:
                self._json(200, api_skills())
            except Exception as e:  # noqa: BLE001
                self._json(500, {"ok": False, "error": str(e)})
            return
        if path in ("/", "/index.html"):
            self._serve_static("index.html")
            return
        # 静态资源：仅允许 manage_console 目录下的相对文件名
        if path.startswith("/") and ".." not in path:
            name = path.lstrip("/")
            if name and (STATIC_DIR / name).is_file():
                self._serve_static(name)
                return
        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        handlers = {
            "/api/plan": api_save_plan,
            "/api/upgrade": api_upgrade,
            "/api/unmanage": api_unmanage,
            "/api/release": api_release,
        }
        fn = handlers.get(path)
        if not fn:
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            body = self._read_json()
            result = fn(body)
            code = 200 if result.get("ok", True) else 400
            self._json(code, result)
        except ValueError as e:
            self._json(400, {"ok": False, "error": str(e)})
        except Exception as e:  # noqa: BLE001
            self._json(500, {
                "ok": False,
                "error": str(e),
                "trace": traceback.format_exc(),
            })

    def _serve_static(self, name: str) -> None:
        target = (STATIC_DIR / name).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        if not target.is_file():
            self._json(404, {"ok": False, "error": "not found"})
            return
        data = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype = f"{ctype}; charset=utf-8"
        self._send(200, data, ctype)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="本机技能管理控制台")
    ap.add_argument("--host", default="127.0.0.1", help="绑定地址（默认仅本机）")
    ap.add_argument("--port", type=int, default=8754)
    ap.add_argument("--open", action="store_true", help="启动后打开浏览器")
    args = ap.parse_args(argv)

    if not STATIC_DIR.is_dir():
        raise SystemExit(f"缺少静态目录：{STATIC_DIR}")
    if not (STATIC_DIR / "index.html").is_file():
        raise SystemExit(f"缺少 {STATIC_DIR / 'index.html'}")

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    runutil.log(f"管理控制台：{url}")
    runutil.log("Ctrl+C 停止")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        runutil.log("\n已停止")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
