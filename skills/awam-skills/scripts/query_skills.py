#!/usr/bin/env python3
"""查询并对比三处技能来源：组织仓、索引仓远程、本机技能目录。

用法：
  cd <索引仓> && python skills/awam-skills/scripts/query_skills.py   # 在索引仓里跑最稳
  python <任意路径>/query_skills.py --index-root <索引仓>              # 或显式指定索引仓根
  python skills/awam-skills/scripts/query_skills.py --only org
  python skills/awam-skills/scripts/query_skills.py --format json

索引仓根定位顺序：--index-root > 环境变量 AWAM_SKILLS_INDEX_ROOT > 从当前目录向上找
（含 skills.overrides.json + README.md）> 脚本相对位置。定位失败会明确报错并给解法 ——
在 `~/.workbuddy/skills/` 这类安装副本下跑，脚本相对位置会推错（见 resolve_index_root）。

本机扫描根：--local-dir > 环境变量 / 索引仓根 .env 的 AWAM_SKILLS_LOCAL_DIR >
默认 G:\\Projects\\19AI\\skills。支持子目录嵌套的 SKILL.md；排除名单见
AWAM_SKILLS_LOCAL_EXCLUDE / --exclude（按目录名）。
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
# 本机技能扫描根目录默认值；可被 .env / 环境变量 / --local-dir 覆盖
DEFAULT_LOCAL_DIR = Path(r"G:\Projects\19AI\skills")

# .env / 环境变量键
ENV_LOCAL_DIR = "AWAM_SKILLS_LOCAL_DIR"
ENV_LOCAL_EXCLUDE = "AWAM_SKILLS_LOCAL_EXCLUDE"

# 递归扫描时跳过的目录名（不区分大小写）
SKIP_DIR_NAMES = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".cache", ".workbuddy",
    # 常见大数据 / 产物目录，避免拖慢扫描
    "vendor", "target", ".next", "coverage", "tmp", "temp",
})

# 相对扫描根的最大下钻深度（repo/skills/<name> 约 3 层；留余量）
LOCAL_SCAN_MAX_DEPTH = 5

# HTTP 超时（秒）：避免网络挂死时调用方一直等
HTTP_TIMEOUT = 30

# 索引仓根的标记文件（都在 ⇒ 认定是索引仓）
INDEX_MARKERS = ("skills.overrides.json", "README.md")


def _looks_like_index_root(p: Path) -> bool:
    try:
        return p.is_dir() and all((p / m).exists() for m in INDEX_MARKERS)
    except OSError:
        return False


def load_dotenv(path: Path) -> bool:
    """从 .env 加载键值到 os.environ（不覆盖已有环境变量）。返回是否成功读到文件。"""
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        os.environ[key] = val
    return True


def load_dotenv_for_index(index_root: Path) -> Path | None:
    """优先读索引仓根 .env，其次当前工作目录 .env。返回实际加载的路径。"""
    for cand in (index_root / ".env", Path.cwd() / ".env"):
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if load_dotenv(resolved):
            return resolved
    return None


def parse_exclude_names(*sources: str | None) -> set[str]:
    """解析排除名单：逗号 / 分号 / 空白分隔的目录名，小写归一。"""
    names: set[str] = set()
    for src in sources:
        if not src:
            continue
        for part in re.split(r"[,;\s]+", src.strip()):
            name = part.strip().strip("/\\")
            if name:
                names.add(name.lower())
    return names


def resolve_local_dir(explicit: Path | str | None = None) -> Path:
    """本机扫描根：--local-dir > 环境变量 AWAM_SKILLS_LOCAL_DIR > 默认 G:\\Projects\\19AI\\skills。"""
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get(ENV_LOCAL_DIR, "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_LOCAL_DIR.expanduser().resolve()


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


def gh_request(path: str, token: str | None, timeout: int = HTTP_TIMEOUT) -> object:
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {e.code} for {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"GitHub API 网络失败 {url}（{timeout}s 超时）：{e}") from e


def gh_paginate(path: str, token: str | None, timeout: int = HTTP_TIMEOUT) -> list:
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
        # 每页独立计超时：分页多时也不会因累计耗时而误杀
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def _should_skip_dir(name: str, exclude: set[str]) -> bool:
    """隐藏目录、常见工程垃圾目录、排除名单中的目录名一律不进扫描。"""
    if name.startswith(".") or name.startswith("_"):
        return True
    lower = name.lower()
    if lower in SKIP_DIR_NAMES:
        return True
    if lower in exclude:
        return True
    return False


def collect_local(
    local_dir: Path,
    exclude: set[str] | None = None,
    max_depth: int = LOCAL_SCAN_MAX_DEPTH,
) -> list[SkillEntry]:
    """递归扫描本机技能根：凡含 SKILL.md 的目录视为一项技能（不再继续下钻）。

    支持扁平（`<name>/SKILL.md`）与嵌套（`<repo>/skills/<name>/SKILL.md`、
    `<repo>/<name>/SKILL.md`）。排除名单按**技能目录名**（含 SKILL.md 的那一层，
    以及路径上任意祖先目录名）匹配，命中则跳过。
    """
    entries: list[SkillEntry] = []
    ex = {n.lower() for n in (exclude or set())}
    if not local_dir.is_dir():
        return entries

    # (dirpath, depth_from_root)；depth=0 为扫描根本身
    stack: list[tuple[Path, int]] = [(local_dir, 0)]
    seen_paths: set[str] = set()

    while stack:
        current, depth = stack.pop()
        # 用绝对路径字符串去重；不 resolve 软链目标，避免 junction 把扫描拖出根外
        try:
            key = str(current.absolute())
        except OSError:
            continue
        if key in seen_paths:
            continue
        seen_paths.add(key)

        if depth >= max_depth:
            continue

        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue

        for child in children:
            # 不跟随 symlink/junction 继续下钻，只允许把其自身当作技能叶（若含 SKILL.md）
            is_link = False
            try:
                is_link = os.path.islink(child) or _is_junction(child)
            except OSError:
                continue
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue
            if _should_skip_dir(child.name, ex):
                continue

            skill_md = child / "SKILL.md"
            has_skill = False
            try:
                has_skill = skill_md.is_file()
            except OSError:
                continue

            if has_skill:
                link_type = "link" if is_link else ""
                target = ""
                if is_link:
                    try:
                        target = str(os.readlink(child))
                    except OSError:
                        target = ""
                try:
                    rel = str(child.relative_to(local_dir)).replace("\\", "/")
                except ValueError:
                    rel = child.name
                entries.append(
                    SkillEntry(
                        key=normalize_key(child.name),
                        display=child.name,
                        source="local",
                        path_or_url=str(child),
                        has_skill_md=True,
                        extra={
                            "link_type": link_type,
                            "target": target,
                            "rel": rel,
                        },
                    )
                )
                # 已是技能叶节点，不再下钻（避免扫进技能仓内的 fixture / 副本）
                continue

            if is_link:
                continue
            stack.append((child, depth + 1))

    return sorted(entries, key=lambda e: (e.extra.get("rel") or e.display).lower())


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
            gaps.append("组织有、本机无")
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
        f"- 仅本机: {len(only_local)}"
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
    lines.append("### 本机技能目录")
    if not local:
        lines.append("_（目录不存在、为空，或全部被排除）_")
    else:
        for e in local:
            rel = e.extra.get("rel") or e.display
            flag = "SKILL.md" if e.has_skill_md else "缺 SKILL.md"
            lines.append(f"- {e.display} ({rel}) [{flag}] — {e.path_or_url}")
    lines.append("")
    return "\n".join(lines)


def _mask_host_path(value: str, home: str) -> str:
    """脱敏本机绝对路径，避免 JSON 输出泄露主机目录结构。

    规则（按序）：
    1. 去掉 Windows 长路径前缀 `\\\\?\\`（junction target 常见）；
    2. home 目录内 → `~/...`；
    3. 其它盘符绝对路径（如 `G:\\Projects\\19AI\\...`）→ `G:/…/<末段>`（隐藏中间层级，只留盘符+末段）；
    4. 其余（URL、相对路径）原样返回。
    """
    if not value:
        return value
    v = value
    if v.startswith("\\\\?\\"):
        v = v[4:]
    norm = v.replace("\\", "/")
    home_norm = home.replace("\\", "/").rstrip("/")
    if norm.lower().startswith(home_norm.lower() + "/"):
        return "~/" + norm[len(home_norm) + 1:]
    m = re.match(r"^([A-Za-z]):/(.+)$", norm)
    if m:
        drive = m.group(1)
        tail = m.group(2).rstrip("/").rsplit("/", 1)[-1]
        return f"{drive}:/…/{tail}"
    return value


def mask_json_payload(payload: dict, home: str) -> dict:
    """对 JSON 输出的主机路径字段做脱敏：meta 根目录、local 的 path/target、compare 的 local_path。"""
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for k in ("index_root", "local_dir", "dotenv"):
            if isinstance(meta.get(k), str) and meta[k]:
                meta[k] = _mask_host_path(meta[k], home)

    for item in payload.get("local", []) or []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("path_or_url"), str):
            item["path_or_url"] = _mask_host_path(item["path_or_url"], home)
        extra = item.get("extra")
        if isinstance(extra, dict) and isinstance(extra.get("target"), str):
            extra["target"] = _mask_host_path(extra["target"], home)

    for row in payload.get("compare", []) or []:
        if isinstance(row, dict) and isinstance(row.get("local_path"), str):
            row["local_path"] = _mask_host_path(row["local_path"], home)

    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="查询并对比组织 / 索引仓 / 本机技能目录")
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
        default=None,
        help=(
            f"本机技能扫描根目录（默认读 .env/{ENV_LOCAL_DIR}，"
            f"再回退 {DEFAULT_LOCAL_DIR}）"
        ),
    )
    parser.add_argument(
        "--exclude",
        default="",
        help=(
            "按目录名排除技能（逗号分隔；与 .env 的 "
            f"{ENV_LOCAL_EXCLUDE} 合并）。匹配含 SKILL.md 的目录名及其祖先目录名"
        ),
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

    dotenv_path = load_dotenv_for_index(INDEX_ROOT)
    local_dir = resolve_local_dir(args.local_dir)
    exclude = parse_exclude_names(
        os.environ.get(ENV_LOCAL_EXCLUDE),
        args.exclude,
    )

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
        local = collect_local(local_dir, exclude=exclude)

    compare = build_compare(org, index, local) if need_org or need_index or need_local else []
    meta = {
        "index_root": str(INDEX_ROOT),
        "index_origin": index_origin,
        "local_dir": str(local_dir),
        "local_exclude": sorted(exclude),
        "dotenv": str(dotenv_path) if dotenv_path else "",
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
        payload = mask_json_payload(payload, str(Path.home()))
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
