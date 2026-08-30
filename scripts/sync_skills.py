#!/usr/bin/env python3
"""从 awam-skills 组织与个人账号 topic:skill 仓库同步生成 README.md。"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES_PATH = ROOT / "skills.overrides.json"
README_PATH = ROOT / "README.md"

ORG = "awam-skills"
USER = "awamwang"
OTHER_CATEGORY = "其他"

API = "https://api.github.com"


def load_config() -> dict:
    with OVERRIDES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def gh_request(path: str, token: str | None, accept: str = "application/vnd.github+json") -> object:
    url = path if path.startswith("http") else f"{API}{path}"
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "awam-skills-sync",
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
            "User-Agent": "awam-skills-sync",
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


def resolve_token() -> str | None:
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env
    try:
        out = subprocess.check_output(["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL)
        return out.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def normalize_desc(text: str | None) -> str:
    if not text:
        return ""
    text = text.strip().strip('"').strip("'")
    text = re.sub(r"\s+", " ", text)
    return text


def truncate_desc(text: str, limit: int = 160) -> str:
    text = normalize_desc(text)
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return (cut or text[: limit - 1]) + "…"


def parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end < 0:
        return {}
    block = content[3:end].strip()
    data: dict[str, str] = {}
    key: str | None = None
    buf: list[str] = []
    for line in block.splitlines():
        if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            if key is not None:
                data[key] = "\n".join(buf).strip().strip('"').strip("'")
            k, _, v = line.partition(":")
            key = k.strip()
            val = v.strip()
            if val in (">-", "|", ">"):
                buf = []
            else:
                buf = [val] if val else []
        elif key is not None and (line.startswith("  ") or line.startswith("\t") or not line.strip()):
            buf.append(line.strip())
    if key is not None:
        data[key] = "\n".join(buf).strip().strip('"').strip("'")
    return data


def fetch_skill_md(full_name: str, token: str | None) -> dict:
    try:
        payload = gh_request(f"/repos/{full_name}/contents/SKILL.md", token)
    except RuntimeError:
        return {}
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        return {}
    raw = payload.get("content") or ""
    text = base64.b64decode(raw.replace("\n", "")).decode("utf-8", errors="replace")
    return parse_frontmatter(text)


def fetch_org_repos(token: str | None) -> list[dict]:
    return gh_paginate(f"/orgs/{ORG}/repos?per_page=100&type=public&sort=full_name", token)


def fetch_user_topic_skill_repos(token: str | None) -> list[dict]:
    q = urllib.parse.quote(f"user:{USER} topic:skill")
    items = gh_paginate(f"/search/repositories?q={q}&per_page=100", token)
    return items


def repo_full_name(repo: dict) -> str:
    return repo.get("full_name") or f"{repo['owner']['login']}/{repo['name']}"


def resolve_category(full_name: str, topics: list[str], config: dict) -> str:
    overrides = config.get("overrides") or {}
    if full_name in overrides and overrides[full_name].get("category"):
        cat_id = overrides[full_name]["category"]
        for cat in config.get("categories") or []:
            if cat["id"] == cat_id:
                return cat["title"]
        return cat_id

    topic_set = {t.lower() for t in topics}
    for cat in config.get("categories") or []:
        for t in cat.get("topics") or []:
            if t.lower() in topic_set:
                return cat["title"]
    return OTHER_CATEGORY


def resolve_description(full_name: str, repo: dict, frontmatter: dict, config: dict) -> str:
    overrides = config.get("overrides") or {}
    if full_name in overrides and overrides[full_name].get("description"):
        return normalize_desc(overrides[full_name]["description"])
    if frontmatter.get("description"):
        return truncate_desc(frontmatter["description"])
    return truncate_desc(repo.get("description") or "") or "（暂无简介）"


def collect_skills(token: str | None, config: dict) -> list[dict]:
    exclude = set(config.get("exclude") or [])
    by_name: dict[str, dict] = {}

    for repo in fetch_org_repos(token):
        if repo.get("archived") or repo.get("fork"):
            continue
        full = repo_full_name(repo)
        if full in exclude or repo.get("name") == "skills":
            continue
        by_name[full] = repo

    for repo in fetch_user_topic_skill_repos(token):
        if repo.get("archived") or repo.get("fork"):
            continue
        full = repo_full_name(repo)
        if full in exclude:
            continue
        # 组织仓已收录时保留组织侧元数据；个人仓同名不覆盖
        if full not in by_name:
            by_name[full] = repo

    skills: list[dict] = []
    for full, repo in sorted(by_name.items()):
        topics = repo.get("topics") or []
        # search API 可能不带 topics，补拉一次
        if "topics" not in repo or repo.get("topics") is None:
            try:
                detail = gh_request(f"/repos/{full}", token)
                if isinstance(detail, dict):
                    topics = detail.get("topics") or []
                    repo = {**repo, **detail}
            except RuntimeError:
                pass
        frontmatter = fetch_skill_md(full, token)
        skills.append(
            {
                "full_name": full,
                "name": repo.get("name") or full.split("/")[-1],
                "url": repo.get("html_url") or f"https://github.com/{full}",
                "category": resolve_category(full, topics, config),
                "description": resolve_description(full, repo, frontmatter, config),
            }
        )
    return skills


def render_readme(skills: list[dict], config: dict) -> str:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for s in skills:
        by_cat[s["category"]].append(s)

    ordered_titles = [c["title"] for c in config.get("categories") or []]
    extra = sorted(t for t in by_cat if t not in ordered_titles and t != OTHER_CATEGORY)
    category_order = ordered_titles + extra
    if OTHER_CATEGORY in by_cat:
        category_order.append(OTHER_CATEGORY)

    lines = [
        "# awam-skills",
        "",
        "罗列并整理我（Awam M Wang）创建的 AI 技能（Skill），按用途分类，便于查找与选用。",
        "",
        "> 本目录由 GitHub Actions 定时从 `awam-skills` 组织仓库，以及个人账号（awamwang）带 `skill` Topic 的仓库自动同步。",
        "",
        "## 技能目录",
        "",
    ]

    wrote_any = False
    for title in category_order:
        items = by_cat.get(title) or []
        if not items:
            continue
        wrote_any = True
        lines.append(f"### {title}")
        lines.append("")
        lines.append("| 技能 | 简介 |")
        lines.append("|------|------|")
        for s in sorted(items, key=lambda x: x["name"].lower()):
            desc = s["description"].replace("|", "\\|")
            lines.append(f"| [{s['name']}]({s['url']}) | {desc} |")
        lines.append("")

    if not wrote_any:
        lines.append("_暂无技能仓库_")
        lines.append("")

    lines.extend(
        [
            "## 说明",
            "",
            "- 各技能的安装方式、配置与用法见对应仓库的 README / `SKILL.md`",
            "- 本仓库仅作技能索引，不包含技能实现代码",
            "- 分类可在 `skills.overrides.json` 中指定；也可给仓库打上 `cat-*` 类 Topic（见该文件）",
            "",
            "## License",
            "",
            "各技能仓库采用各自声明的许可证，请以对应仓库为准。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    config = load_config()
    token = resolve_token()
    skills = collect_skills(token, config)
    readme = render_readme(skills, config)
    README_PATH.write_text(readme, encoding="utf-8", newline="\n")
    print(f"Wrote {README_PATH} with {len(skills)} skill(s).")
    for s in skills:
        print(f"  - [{s['category']}] {s['full_name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
