#!/usr/bin/env python3
"""查询并对比三处技能来源：组织仓、索引仓远程、本机 awam 目录。

用法：
  cd <索引仓> && python skills/awam-skills/scripts/query_skills.py   # 在索引仓里跑最稳
  python <任意路径>/query_skills.py --index-root <索引仓>              # 或显式指定索引仓根
  python skills/awam-skills/scripts/query_skills.py --only org
  python skills/awam-skills/scripts/query_skills.py --format json

索引仓根定位顺序：--index-root > 环境变量 AWAM_SKILLS_INDEX_ROOT > 从当前目录向上找
（含 skills.overrides.json + README.md）> 脚本相对位置。定位失败会明确报错并给解法 ——
在 `~/.workbuddy/skills/` 这类安装副本下跑，脚本相对位置会推错（见 resolve_index_root）。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

API = "https://api.github.com"
ORG = "awam-skills"
DEFAULT_LOCAL_AWAM = Path.home() / ".agents" / "skills" / "awam"

# 索引仓根的标记文件（都在 ⇒ 认定是索引仓）
INDEX_MARKERS = ("skills.overrides.json", "README.md")


def _looks_like_index_root(p: Path) -> bool:
    try:
        return p.is_dir() and all((p / m).exists() for m in INDEX_MARKERS)
    except OSError:
        return False


def resolve_index_root(explicit: str | None = None) -> Path | None:
    """定位索引仓根：「显式 > 环境变量 > 从 cwd 向上找 > 脚本相对位置」。

    为什么不能只靠「脚本相对位置」：本脚本按 `parents[3]` 推索引仓根，这只在
    索引仓内部成立。装在 `~/.workbuddy/skills/awam-skills` 这类**安装副本**下时，
    `parents[3]` 会算成 `~/.workbuddy` —— 恰好也像是个目录，于是脚本不报错，
    只是查出一堆空结果，很难判断是「真没有」还是「根找错了」。
    """
    cands: list[Path] = []
    if explicit:
        cands.append(Path(explicit).expanduser())
    env = os.environ.get("AWAM_SKILLS_INDEX_ROOT")
    if env:
        cands.append(Path(env).expanduser())
    cwd = Path.cwd()
    cands.extend([cwd, *cwd.parents])
    cands.append(Path(__file__).resolve().parents[3])
    for c in cands:
        if _looks_like_index_root(c):
            return c.resolve()
    return None


# skills/awam-skills/scripts → 索引仓根（能被 resolve 覆盖，见 _apply_index_root）
INDEX_ROOT = resolve_index_root() or Path(__file__).resolve().parents[3]
OVERRIDES_PATH = INDEX_ROOT / "skills.overrides.json"
README_PATH = INDEX_ROOT / "README.md"
BUNDLED_SKILLS_DIR = INDEX_ROOT / "skills"


def _apply_index_root(root: Path) -> None:
    """重绑模块级路径常量（argparse 之后调用）。"""
    global INDEX_ROOT, OVERRIDES_PATH, README_PATH, BUNDLED_SKILLS_DIR
    INDEX_ROOT = Path(root).resolve()
    OVERRIDES_PATH = INDEX_ROOT / "skills.overrides.json"
    README_PATH = INDEX_ROOT / "README.md"
    BUNDLED_SKILLS_DIR = INDEX_ROOT / "skills"

SKILL_LINK_RE = re.compile(
    r"\|\s*\[([^\]]+)\]\((https://github\.com/[^)\s]+)\)\s*\|",
    re.IGNORECASE,
)


@dataclass
class SkillEntry:
    key: str
    display: str
    source: str
    path_or_url: str = ""
    full_name: str = ""
    has_skill_md: bool | None = None
    extra: dict = field(default_factory=dict)


def normalize_key(name: str) -> str:
    """统一对比键：小写，去掉末尾 -skill（保留 -skills 等其它后缀）。"""
    n = (name or "").strip().lower()
    if n.endswith("-skill") and not n.endswith("-skills"):
        n = n[: -len("-skill")]
    return n


def resolve_token() -> str | None:
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env
    try:
        raw = subprocess.check_output(
            ["gh", "auth", "token"], stderr=subprocess.DEVNULL
        )
        return raw.decode("utf-8", errors="replace").strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def gh_request(path: str, token: str | None) -> object:
    url = path if path.startswith("http") else f"{API}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "awam-skills-query",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {e.code} for {url}: {detail}") from e


def gh_paginate(path: str, token: str | None) -> list:
    items: list = []
    next_url: str | None = path if path.startswith("http") else f"{API}{path}"
    while next_url:
        url = next_url
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "awam-skills-query",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            page = json.loads(resp.read().decode("utf-8"))
            if isinstance(page, list):
                items.extend(page)
            elif isinstance(page, dict) and "items" in page:
                items.extend(page["items"])
            else:
                raise RuntimeError(f"Unexpected paginate payload from {url}")
            link = resp.headers.get("Link", "")
            next_url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    next_url = part[part.find("<") + 1 : part.find(">")]
                    break
    return items


def git_show(ref_path: str) -> str | None:
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(INDEX_ROOT), "show", ref_path],
            stderr=subprocess.DEVNULL,
        )
        return raw.decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return None


def git_remote_owner_repo() -> tuple[str, str] | None:
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(INDEX_ROOT), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
        )
        out = raw.decode("utf-8", errors="replace").strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    # https://github.com/owner/repo(.git) 或 git@github.com:owner/repo.git
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?/?$", out)
    if not m:
        return None
    return m.group(1), m.group(2)


def parse_readme_skills(readme: str) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    seen: set[str] = set()
    for m in SKILL_LINK_RE.finditer(readme):
        display = m.group(1).strip()
        url = m.group(2).strip()
        key = normalize_key(display)
        if key in seen:
            continue
        seen.add(key)
        full = ""
        um = re.search(r"github\.com/([^/]+/[^/]+)", url)
        if um:
            full = um.group(1).rstrip("/")
        entries.append(
            SkillEntry(
                key=key,
                display=display,
                source="index",
                path_or_url=url,
                full_name=full,
                extra={"via": "readme"},
            )
        )
    return entries


def collect_org(token: str | None) -> list[SkillEntry]:
    repos = gh_paginate(
        f"/orgs/{ORG}/repos?per_page=100&type=public&sort=full_name", token
    )
    exclude: set[str] = set()
    if OVERRIDES_PATH.is_file():
        try:
            cfg = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
            exclude = set(cfg.get("exclude") or [])
        except (OSError, json.JSONDecodeError):
            pass

    entries: list[SkillEntry] = []
    for repo in repos:
        if repo.get("archived") or repo.get("fork"):
            continue
        name = repo.get("name") or ""
        full = repo.get("full_name") or f"{ORG}/{name}"
        if full in exclude or name in {"skills", "awam-skills"}:
            # 索引仓误放组织下时跳过；流程 Skill 不在组织仓
            continue
        entries.append(
            SkillEntry(
                key=normalize_key(name),
                display=name,
                source="org",
                path_or_url=repo.get("html_url") or f"https://github.com/{full}",
                full_name=full,
                extra={
                    "description": (repo.get("description") or "").strip(),
                    "topics": repo.get("topics") or [],
                },
            )
        )
    return sorted(entries, key=lambda e: e.display.lower())


def collect_index_bundled_local() -> list[SkillEntry]:
    """索引仓内嵌套 skills/<name>/SKILL.md（如流程 Skill awam-skills）。"""
    entries: list[SkillEntry] = []
    if not BUNDLED_SKILLS_DIR.is_dir():
        return entries
    for child in sorted(BUNDLED_SKILLS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        entries.append(
            SkillEntry(
                key=normalize_key(child.name),
                display=child.name,
                source="index",
                path_or_url=str(skill_md.relative_to(INDEX_ROOT)).replace("\\", "/"),
                has_skill_md=True,
                extra={"via": "bundled"},
            )
        )
    return entries


def collect_index(token: str | None, prefer_remote: bool) -> tuple[list[SkillEntry], str]:
    """返回 (entries, origin_label)。优先读远程 README，失败则本地。"""
    origin = git_remote_owner_repo()
    readme_text: str | None = None
    origin_label = "local"

    if prefer_remote and origin:
        owner, repo = origin
        # 1) git show origin/HEAD:README.md
        for ref in ("origin/HEAD:README.md", "origin/main:README.md", "origin/master:README.md"):
            readme_text = git_show(ref)
            if readme_text is not None:
                origin_label = f"git:{ref.split(':')[0]}"
                break
        # 2) GitHub Contents API
        if readme_text is None and token is not None:
            try:
                payload = gh_request(f"/repos/{owner}/{repo}/contents/README.md", token)
                if isinstance(payload, dict) and payload.get("encoding") == "base64":
                    raw = (payload.get("content") or "").replace("\n", "")
                    readme_text = base64.b64decode(raw).decode("utf-8", errors="replace")
                    origin_label = f"api:{owner}/{repo}"
            except RuntimeError:
                pass

    if readme_text is None:
        if README_PATH.is_file():
            readme_text = README_PATH.read_text(encoding="utf-8")
            origin_label = "local:README.md"
        else:
            readme_text = ""
            origin_label = "missing"

    entries = parse_readme_skills(readme_text)

    # overrides 中有、README 尚未同步到的条目
    if OVERRIDES_PATH.is_file():
        try:
            cfg = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
            known = {e.key for e in entries}
            for full, meta in (cfg.get("overrides") or {}).items():
                name = full.split("/")[-1]
                key = normalize_key(name)
                if key in known:
                    continue
                entries.append(
                    SkillEntry(
                        key=key,
                        display=name,
                        source="index",
                        path_or_url=f"https://github.com/{full}",
                        full_name=full,
                        extra={
                            "via": "overrides",
                            "description": (meta or {}).get("description") or "",
                        },
                    )
                )
                known.add(key)
        except (OSError, json.JSONDecodeError):
            pass

    # 仓内流程 Skill 等
    known = {e.key for e in entries}
    for bundled in collect_index_bundled_local():
        if bundled.key in known:
            # 已在 README 则标记 bundled
            for e in entries:
                if e.key == bundled.key:
                    e.extra["bundled"] = True
                    e.has_skill_md = True
                    break
        else:
            entries.append(bundled)
            known.add(bundled.key)

    return sorted(entries, key=lambda e: e.display.lower()), origin_label


def collect_local(local_dir: Path) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    if not local_dir.is_dir():
        return entries
    for child in sorted(local_dir.iterdir()):
        if child.name.startswith(".") or child.name.startswith("_"):
            continue
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        has = skill_md.is_file()
        # 目录即视为一项；无 SKILL.md 仍列出以便对比缺口
        link_type = ""
        target = ""
        # Windows Junction：Path.is_symlink 可能为 False
        if os.path.islink(child) or _is_junction(child):
            link_type = "link"
            try:
                target = str(os.readlink(child))
            except OSError:
                target = ""

        entries.append(
            SkillEntry(
                key=normalize_key(child.name),
                display=child.name,
                source="local",
                path_or_url=str(child),
                has_skill_md=has,
                extra={
                    "link_type": link_type,
                    "target": target,
                },
            )
        )
    return entries


def _is_junction(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        GetFileAttributesW.restype = wintypes.DWORD
        attrs = GetFileAttributesW(str(path))
        if attrs == 0xFFFFFFFF:
            return False
        # FILE_ATTRIBUTE_REPARSE_POINT
        return bool(attrs & 0x400)
    except (AttributeError, OSError, ValueError):
        return False


def build_compare(
    org: list[SkillEntry],
    index: list[SkillEntry],
    local: list[SkillEntry],
) -> list[dict]:
    by_key: dict[str, dict] = {}

    def ensure(key: str) -> dict:
        if key not in by_key:
            by_key[key] = {
                "key": key,
                "org": False,
                "index": False,
                "local": False,
                "org_name": "",
                "index_name": "",
                "local_name": "",
                "org_url": "",
                "index_url": "",
                "local_path": "",
                "local_has_skill_md": None,
                "gaps": [],
            }
        return by_key[key]

    for e in org:
        row = ensure(e.key)
        row["org"] = True
        row["org_name"] = e.display
        row["org_url"] = e.path_or_url

    for e in index:
        row = ensure(e.key)
        row["index"] = True
        row["index_name"] = e.display
        row["index_url"] = e.path_or_url

    for e in local:
        row = ensure(e.key)
        row["local"] = True
        row["local_name"] = e.display
        row["local_path"] = e.path_or_url
        row["local_has_skill_md"] = e.has_skill_md

    for row in by_key.values():
        gaps: list[str] = []
        if row["org"] and not row["index"]:
            gaps.append("组织有、索引无")
        if row["index"] and not row["org"] and row["key"] != "awam-skills":
            # 流程 Skill 仅活在索引仓，不算缺口
            gaps.append("索引有、组织无")
        if row["org"] and not row["local"]:
            gaps.append("组织有、本机 awam 无")
        if row["local"] and not row["org"]:
            gaps.append("本机有、组织无")
        if row["local"] and row["local_has_skill_md"] is False:
            gaps.append("本机目录缺 SKILL.md")
        row["gaps"] = gaps

    return sorted(by_key.values(), key=lambda r: r["key"])


def mark(ok: bool) -> str:
    return "✓" if ok else "·"


def render_table(
    compare: list[dict],
    org: list[SkillEntry],
    index: list[SkillEntry],
    local: list[SkillEntry],
    meta: dict,
) -> str:
    lines: list[str] = []
    lines.append("## 技能三方对比")
    lines.append("")
    lines.append(
        f"组织 `awam-skills`: {len(org)} | "
        f"索引仓远程({meta.get('index_origin', '?')}): {len(index)} | "
        f"本机 `{meta.get('local_dir', '')}`: {len(local)}"
    )
    lines.append("")
    lines.append("| 键 | 组织 | 索引 | 本机 | 显示名 | 缺口 |")
    lines.append("|----|:----:|:----:|:----:|--------|------|")
    for r in compare:
        names = " / ".join(
            dict.fromkeys(
                n
                for n in (r["org_name"], r["index_name"], r["local_name"])
                if n
            )
        )
        gaps = "；".join(r["gaps"]) if r["gaps"] else ""
        lines.append(
            f"| `{r['key']}` | {mark(r['org'])} | {mark(r['index'])} | "
            f"{mark(r['local'])} | {names} | {gaps} |"
        )
    lines.append("")

    only_org = [r for r in compare if r["org"] and not r["index"] and not r["local"]]
    only_index = [r for r in compare if r["index"] and not r["org"] and not r["local"]]
    only_local = [r for r in compare if r["local"] and not r["org"] and not r["index"]]
    all_three = [r for r in compare if r["org"] and r["index"] and r["local"]]

    lines.append("### 摘要")
    lines.append("")
    lines.append(f"- 三方皆有: {len(all_three)}")
    lines.append(f"- 仅组织: {len(only_org)}" + (f" — {', '.join(r['key'] for r in only_org)}" if only_org else ""))
    lines.append(
        f"- 仅索引: {len(only_index)}"
        + (f" — {', '.join(r['key'] for r in only_index)}" if only_index else "")
    )
    lines.append(
        f"- 仅本机 awam: {len(only_local)}"
        + (f" — {', '.join(r['key'] for r in only_local)}" if only_local else "")
    )
    lines.append("")
    return "\n".join(lines)


def render_lists(org: list[SkillEntry], index: list[SkillEntry], local: list[SkillEntry]) -> str:
    lines = ["## 分源列表", ""]
    lines.append("### 组织 awam-skills")
    if not org:
        lines.append("_（无）_")
    else:
        for e in org:
            lines.append(f"- [{e.display}]({e.path_or_url})")
    lines.append("")
    lines.append("### 索引仓")
    if not index:
        lines.append("_（无）_")
    else:
        for e in index:
            via = e.extra.get("via", "")
            suffix = f" ({via})" if via else ""
            lines.append(f"- {e.display}{suffix} — {e.path_or_url}")
    lines.append("")
    lines.append("### 本机 ~/.agents/skills/awam")
    if not local:
        lines.append("_（目录不存在或为空）_")
    else:
        for e in local:
            flag = "SKILL.md" if e.has_skill_md else "缺 SKILL.md"
            lines.append(f"- {e.display} [{flag}] — {e.path_or_url}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="查询并对比组织 / 索引仓 / 本机 awam 技能")
    parser.add_argument(
        "--only",
        choices=("all", "org", "index", "local", "compare"),
        default="all",
        help="只输出某一源，或仅对比表（默认 all）",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="输出格式",
    )
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=DEFAULT_LOCAL_AWAM,
        help=f"本机 awam 技能目录（默认 {DEFAULT_LOCAL_AWAM}）",
    )
    parser.add_argument(
        "--no-remote",
        action="store_true",
        help="索引仓只用本地 README，不读 origin",
    )
    parser.add_argument(
        "--index-root",
        help="索引仓根目录（默认自动定位：环境变量 AWAM_SKILLS_INDEX_ROOT > 从 cwd 向上找 > 脚本位置）",
    )
    args = parser.parse_args(argv)

    if args.index_root:
        _apply_index_root(Path(args.index_root))
    if not _looks_like_index_root(INDEX_ROOT):
        print(
            "找不到索引仓根（需同时含 skills.overrides.json 与 README.md）。\n"
            f"  当前判定为：{INDEX_ROOT}\n"
            "  常见原因：用的是 ~/.workbuddy/skills/ 下的**安装副本**，"
            "脚本按相对位置推不出索引仓。\n"
            "  三种解法（任选）：\n"
            "    1) 在索引仓目录下执行：cd <索引仓> && python skills/awam-skills/scripts/query_skills.py\n"
            "    2) 显式指定：--index-root <索引仓路径>\n"
            "    3) 设环境变量：AWAM_SKILLS_INDEX_ROOT=<索引仓路径>",
            file=sys.stderr,
        )
        return 2

    token = resolve_token()
    org: list[SkillEntry] = []
    index: list[SkillEntry] = []
    local: list[SkillEntry] = []
    index_origin = ""

    need_org = args.only in ("all", "org", "compare")
    need_index = args.only in ("all", "index", "compare")
    need_local = args.only in ("all", "local", "compare")

    errors: list[str] = []

    if need_org:
        try:
            org = collect_org(token)
        except Exception as e:  # noqa: BLE001 — CLI 汇总错误
            errors.append(f"org: {e}")

    if need_index:
        try:
            index, index_origin = collect_index(token, prefer_remote=not args.no_remote)
        except Exception as e:  # noqa: BLE001
            errors.append(f"index: {e}")

    if need_local:
        local = collect_local(args.local_dir.resolve())

    compare = build_compare(org, index, local) if need_org or need_index or need_local else []
    meta = {
        "index_root": str(INDEX_ROOT),
        "index_origin": index_origin,
        "local_dir": str(args.local_dir.resolve()),
        "errors": errors,
    }

    if args.format == "json":
        payload = {
            "meta": meta,
            "org": [asdict(e) for e in org],
            "index": [asdict(e) for e in index],
            "local": [asdict(e) for e in local],
            "compare": compare,
        }
        if args.only == "org":
            payload = {"meta": meta, "org": payload["org"]}
        elif args.only == "index":
            payload = {"meta": meta, "index": payload["index"]}
        elif args.only == "local":
            payload = {"meta": meta, "local": payload["local"]}
        elif args.only == "compare":
            payload = {"meta": meta, "compare": compare}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if errors:
            print("## 错误", file=sys.stderr)
            for err in errors:
                print(f"- {err}", file=sys.stderr)
            print("", file=sys.stderr)
        if args.only in ("all", "compare"):
            print(render_table(compare, org, index, local, meta))
        if args.only == "all":
            print(render_lists(org, index, local))
        elif args.only == "org":
            print(render_lists(org, [], []))
        elif args.only == "index":
            print(f"_索引来源: {index_origin}_\n")
            print(render_lists([], index, []))
        elif args.only == "local":
            print(render_lists([], [], local))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
