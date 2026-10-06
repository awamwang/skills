#!/usr/bin/env python3
"""发布前就绪检查（preflight）：一次跑完，输出 PASS / WARN / FAIL 与退出码。

为什么需要
----------
平台发布是「发出去就收不回」的动作，而踩过的坑几乎都是发布前 30 秒能查出来的：

- **本地领先 `origin/main`** → 发出去的内容与 GitHub 上的仓对不上。
  （2026-10-07 发 awam-todo-skill 时就带着 1 个未推提交。）
- **技能目录根本不是 git 仓库** → ClawHub 走 `git archive` 会直接失败；打包器还会
  退化成黑名单遍历，安全兜底失去「作者已公开的表面」这层依据。
  （同批次的 windows-autostart 就是这种情况。）
- **frontmatter 缺 `version`** → 魔搭硬性要求 `name` / `version` / `description`。
- **索引仓副本与 `~/.workbuddy/skills/` 下的安装副本不一致** → 会照着过期文档操作
  （本次真的踩到：读到了旧版 platforms.md，白走一段路）。

这些都不是平台侧的问题，是本机状态问题，所以统一在发之前查一遍。

用法：
  python skills/awam-skills/scripts/preflight.py --dir <技能仓>
  python skills/awam-skills/scripts/preflight.py --dir <仓A> --dir <仓B>      # 批量
  python skills/awam-skills/scripts/preflight.py --dir <技能仓> --json        # 给脚本用
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import public_files  # noqa: E402  （公开文件集判定：见 public_files.py）

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]

ORG = "awam-skills"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
INSTALL_CANDIDATES = (
    Path.home() / ".workbuddy" / "skills",          # Agent 安装副本（复制）
    Path.home() / ".agents" / "skills",             # 常见 junction 落点
    Path.home() / ".agents" / "skills" / "awam",
)

LEVEL_ICON = {"pass": "✅", "warn": "⚠ ", "fail": "❌"}


@dataclass
class Finding:
    level: str          # pass | warn | fail
    title: str
    detail: str = ""


@dataclass
class Report:
    dir: str
    findings: list = field(default_factory=list)
    public_file_count: int = 0
    excluded: list = field(default_factory=list)

    def add(self, level: str, title: str, detail: str = "") -> None:
        self.findings.append(Finding(level, title, detail))

    @property
    def ok(self) -> bool:
        return not any(f.level == "fail" for f in self.findings)

    @property
    def counts(self) -> dict:
        c = {"pass": 0, "warn": 0, "fail": 0}
        for f in self.findings:
            c[f.level] = c.get(f.level, 0) + 1
        return c


def git(skill_dir: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(skill_dir), *args],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)
    return r.returncode, (r.stdout or r.stderr).strip()


def read_skill_md(skill_dir: Path) -> Path | None:
    """SKILL.md 路径（扁平在仓库根，嵌套在 skills/<name>/）。"""
    root, _note = public_files.find_skill_root(skill_dir)
    return (root / "SKILL.md") if root else None


def frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not m:
        return {}
    fm: dict = {}
    # 只取单行标量；本脚本只需要 name / version / description
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km and not line.startswith((" ", "\t")):
            fm[km.group(1)] = km.group(2).strip().strip("'\"")
    return fm


# ---------------------------------------------------------------- 单项检查


def check_layout(skill_dir: Path, rep: Report) -> Path | None:
    if not skill_dir.is_dir():
        rep.add("fail", "技能目录存在", f"找不到目录：{skill_dir}")
        return None
    skill_md = read_skill_md(skill_dir)
    if skill_md is None:
        rep.add("fail", "SKILL.md 存在", "根目录或 skills/<name>/ 下都没有 SKILL.md")
        return None
    rel = skill_md.relative_to(skill_dir).as_posix()
    rep.add("pass", "SKILL.md 存在", rel)
    return skill_md


def is_index_bundled(skill_dir: Path) -> bool:
    """技能目录是否是「索引仓自带的技能」（索引仓根含 `skills.overrides.json`）。

    这类技能不单独发组织仓（见 SKILL.md「本机发现」），所以 origin 指向
    `awamwang/skills` 而非 `awam-skills/*` 是**正常**的。不特判的话，在索引仓里
    跑预检会恒亮一条无意义的 WARN —— 恒亮告警会训练人忽略告警（同 CRLF 那条）。
    """
    rc, top = git(skill_dir, "rev-parse", "--show-toplevel")
    if rc != 0 or not top:
        return False
    return (Path(top) / "skills.overrides.json").is_file()


def check_git(skill_dir: Path, rep: Report) -> bool:
    rc, _ = git(skill_dir, "rev-parse", "--is-inside-work-tree")
    if rc != 0:
        rep.add(
            "fail", "是 git 仓库",
            "不是 git 仓库：ClawHub 发布走 `git archive` 会失败，"
            "打包器也会退化成黑名单遍历（安全兜底降级）",
        )
        return False
    rep.add("pass", "是 git 仓库")

    rc, url = git(skill_dir, "remote", "get-url", "origin")
    if rc != 0 or not url:
        rep.add("warn", "origin remote 已配置", "没有 origin：无法核对「发布内容 = 仓库内容」")
    elif f"{ORG}/" in url:
        m = re.search(rf"{ORG}/([\w.-]+?)(?:\.git)?$", url)
        rep.add("pass", "origin 指向组织仓", f"{ORG}/{m.group(1) if m else '?'}")
    elif is_index_bundled(skill_dir):
        rep.add("pass", "origin 指向索引仓", f"{url}（索引仓自带技能，不单独发组织仓）")
    else:
        rep.add("warn", "origin 指向组织仓", f"origin 不是 {ORG}/…：{url}")

    rc, out = git(skill_dir, "status", "--porcelain")
    if rc == 0 and out:
        n = len([x for x in out.splitlines() if x.strip()])
        rep.add(
            "warn", "工作区干净",
            f"{n} 处未提交改动：平台发的是工作区内容，与仓库 HEAD 不一致；"
            "先按 awam-git 规范提交（或确认这些改动本就该发）",
        )
    elif rc == 0:
        rep.add("pass", "工作区干净")
    return True


def check_sync(skill_dir: Path, rep: Report) -> None:
    rc, branch = git(skill_dir, "rev-parse", "--abbrev-ref", "HEAD")
    if rc != 0:
        return
    branch = branch or "HEAD"
    if branch == "HEAD":
        rep.add("warn", "分支与远程同步", "处于 detached HEAD，无法判断领先/落后")
        return

    rc, upstream = git(skill_dir, "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}")
    if rc != 0:
        rep.add("warn", "分支与远程同步", f"{branch} 没有 upstream，可能是还没 push 过")
        return

    rc, counts = git(skill_dir, "rev-list", "--left-right", "--count", f"{upstream}...{branch}")
    if rc != 0:
        return
    try:
        behind, ahead = (int(x) for x in counts.split())
    except ValueError:
        return

    if ahead and behind:
        rep.add("warn", "分支与远程同步", f"本地领先 {ahead} / 落后 {behind}：先 push 或 pull")
    elif ahead:
        rep.add(
            "fail", "分支与远程同步",
            f"本地领先 {ahead} 个提交：发出去的内容会比 GitHub 上的仓新，"
            "两者对不上。先 `git push`（这是 2026-10-07 实际踩到的坑）",
        )
    elif behind:
        rep.add("warn", "分支与远程同步", f"本地落后 {behind} 个提交：先 `git pull --ff-only`")
    else:
        rep.add("pass", "分支与远程同步", f"{branch} 与 {upstream} 一致")


def check_frontmatter(skill_md: Path | None, rep: Report) -> None:
    if skill_md is None:
        return
    fm = frontmatter(skill_md)
    missing = [k for k in ("name", "version", "description") if not fm.get(k)]
    if missing:
        rep.add(
            "fail", "frontmatter 三要素",
            f"缺 {' / '.join(missing)}：魔搭与 LobeHub 都硬性要求 name / version / description"
            "（老仓常见只缺 version，补 `version: 0.0.1` 即可）",
        )
    else:
        rep.add("pass", "frontmatter 三要素", f"name={fm['name']} version={fm['version']}")

    ver = fm.get("version", "")
    if ver and not SEMVER_RE.match(ver):
        rep.add("warn", "version 是合法 semver", f"`{ver}` 不是 x.y.z：平台可能拒绝或排序异常")


def check_text_hygiene(skill_dir: Path, skill_md: Path | None, rep: Report) -> None:
    if skill_md is None:
        return
    raw = skill_md.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        rep.add("warn", "UTF-8 无 BOM", "SKILL.md 带 BOM，部分平台解析 frontmatter 会失败")
    if b"\r\n" in raw:
        # core.autocrlf=true 时工作区必然是 CRLF，属正常；打包器也会统一转 LF。
        # 不区分的话这条 WARN 会对每个技能恒亮，等于训练人忽略告警。
        rc, val = git(skill_dir, "config", "--get", "core.autocrlf")
        if rc == 0 and val.strip().lower() in ("true", "input"):
            rep.add("pass", "行尾为 LF", f"CRLF，但本仓 core.autocrlf={val.strip()}，属正常；发布时会自动转 LF")
        else:
            rep.add(
                "warn", "行尾为 LF",
                "SKILL.md 是 CRLF：发布脚本会自动转成 LF，但仓库里留 CRLF 会在别处咬人"
                "（魔搭曾报 `must contain 'name' field`，查到最后是行尾问题）。建议改成 LF",
            )
        return
    rep.add("pass", "文本卫生（无 BOM / LF）")


def check_public_files(skill_dir: Path, rep: Report) -> None:
    if not skill_dir.is_dir():
        return
    files, root, source, excluded, outside = public_files.pack_files(skill_dir)
    rep.public_file_count = len(files)
    rep.excluded = excluded

    if root is None:
        rep.add("fail", "能确定打包根", source)
    else:
        rel = root.relative_to(skill_dir).as_posix() or "."
        if rel == ".":
            rep.add("pass", "打包根", "扁平布局（SKILL.md 在仓库根）")
        else:
            rep.add("pass", "打包根", f"嵌套布局 → {rel}/（zip 根下仍是 1 个 SKILL.md）")

    if not files:
        rep.add("fail", "发布文件集非空", "判定的公开文件集为空，发布包会没有内容")
    elif "git 跟踪清单" in source:
        rep.add("pass", "发布文件集", f"{len(files)} 个文件（git 跟踪清单）")
    else:
        rep.add(
            "warn", "发布文件集",
            f"{len(files)} 个文件（黑名单兜底，非 git 目录）：无法保证没夹带本机数据；"
            "发布源请用索引仓里的技能目录",
        )

    if outside:
        rep.add(
            "pass", "打包根外的文件被跳过",
            f"{len(outside)} 个（如 {outside[0]}）——仓库级 README / .github 不会进发布包",
        )

    if excluded:
        if "git 跟踪清单" in source:
            rep.add(
                "fail", "私密文件未被 git 跟踪",
                f"{len(excluded)} 个敏感文件已被 git 跟踪，等于已公开：{', '.join(excluded[:5])}"
                "。发布包已自动排除，但仓库里已经泄漏 —— 先 git rm --cached 并补 .gitignore",
            )
        else:
            rep.add("pass", "私密文件已排除", f"{len(excluded)} 个：{', '.join(excluded[:5])}")


def _file_digest(root: Path) -> dict:
    """相对路径 → 内容 sha1（跳过缓存与宿主注入的元数据）。

    **必须比内容而不是比文件名**：安装副本常见的情形是文件名一样、内容是旧的
    （本次实测 `~/.workbuddy/skills/awam-skills` 就是这种 —— 文件数相同，
    但里面的脚本还是上一版），只比清单会直接漏判。
    """
    import hashlib
    skip = {"__pycache__", "_user_meta.json"}
    out: dict = {}
    for p in root.rglob("*"):
        if not p.is_file() or (skip & set(p.parts)):
            continue
        try:
            out[p.relative_to(root).as_posix()] = hashlib.sha1(p.read_bytes()).hexdigest()
        except OSError:
            continue
    return out


def check_installed_copy(skill_dir: Path, rep: Report) -> None:
    """索引仓里的技能 vs 已安装副本：不一致时照它读到的可能是过期文档。

    2026-10-07 实际踩到：改了索引仓的 platforms.md，但执行时用的是
    `~/.workbuddy/skills/awam-skills` 下的**复制副本**，于是按旧文档走了一段弯路。
    """
    name = skill_dir.name
    src = _file_digest(skill_dir)
    same: list[str] = []
    stale: list[str] = []
    for base in INSTALL_CANDIDATES:
        cand = base / name
        if not cand.exists():
            continue
        real = Path(os.path.realpath(cand))
        if real == Path(os.path.realpath(skill_dir)):
            same.append(f"{cand}（同一份）")
            continue
        dst = _file_digest(real)
        diff = sorted(k for k in set(src) | set(dst) if src.get(k) != dst.get(k))
        if not diff:
            same.append(str(cand))
        else:
            stale.append(f"{cand}（{len(diff)} 个文件内容不同，如 {diff[0]}）")

    if not same and not stale:
        rep.add("pass", "已安装副本", "未发现安装副本，无需同步")
    elif stale:
        rep.add(
            "warn", "已安装副本与索引仓一致",
            "；".join(stale[:3]) + "。复制型副本会随时间过期，照它读文档 / 跑脚本会走弯路 —— "
            "把索引仓的 SKILL.md / references / scripts / templates 覆盖过去，"
            "或改用 junction 指向索引仓（见 SKILL.md「本机发现」）",
        )
    else:
        rep.add("pass", "已安装副本与索引仓一致", "；".join(same[:3]))


# ---------------------------------------------------------------- 驱动


def inspect(skill_dir: Path) -> Report:
    skill_dir = Path(skill_dir).expanduser().resolve()
    rep = Report(dir=str(skill_dir))
    skill_md = check_layout(skill_dir, rep)
    if skill_md is None:
        return rep
    is_git = check_git(skill_dir, rep)
    if is_git:
        check_sync(skill_dir, rep)
    check_frontmatter(skill_md, rep)
    check_text_hygiene(skill_dir, skill_md, rep)
    check_public_files(skill_dir, rep)
    check_installed_copy(skill_dir, rep)
    return rep


def render(rep: Report) -> str:
    lines = [f"===== {rep.dir} ====="]
    for f in rep.findings:
        lines.append(f"{LEVEL_ICON.get(f.level, '?')} {f.title}" + (f"  |  {f.detail}" if f.detail else ""))
    c = rep.counts
    verdict = "可以发布" if rep.ok else "不要发布，先处理上面的 ❌"
    lines.append(f"结果：{c['pass']} PASS / {c['warn']} WARN / {c['fail']} FAIL → {verdict}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="发布前就绪检查（preflight）")
    parser.add_argument("--dir", nargs="+", required=True, help="技能仓本地路径（可多个）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    reports = [inspect(Path(d)) for d in args.dir]

    if args.json:
        print(json.dumps(
            [dict(asdict(r), ok=r.ok, counts=r.counts) for r in reports],
            ensure_ascii=False, indent=2,
        ))
    else:
        for i, rep in enumerate(reports):
            if i:
                print()
            print(render(rep))
        if len(reports) > 1:
            bad = [r.dir for r in reports if not r.ok]
            print()
            print(f"合计：{len(reports)} 个目录，{len(bad)} 个有 FAIL"
                  + (f" → {', '.join(Path(b).name for b in bad)}" if bad else ""))

    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
