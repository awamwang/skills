#!/usr/bin/env python3
"""为豆包技能中心准备导入包（zip），并在确认导入后刷新发布规划。

豆包技能中心只能从**豆包电脑版客户端**导入（侧边栏「技能·连接器·伙伴」→ 我的技能 → 新建 →
上传技能），没有可用的公开上传 API，因此本脚本只做打包与步骤引导，不代传。

打包规则：zip **顶层为技能同名文件夹**，内含 SKILL.md；文本文件统一转 LF。

用法（索引仓根任意路径均可，脚本自定位）：
  python skills/awam-skills/scripts/publish_doubao.py --dir <技能仓>          # 只打包，打印导入步骤
  python skills/awam-skills/scripts/publish_doubao.py --dir <技能仓> --mark-done
      # 你已在豆包客户端导入成功后，把 publishing-plan.json 的 status.doubao 置为 done 并刷新视图
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_store  # noqa: E402  （规划就地更新，保留原排版：见 plan_store.py）

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = INDEX_ROOT / "docs" / "publishing-plan.json"
PLAN_SCRIPT = Path(__file__).resolve().parent / "plan_skills.py"

EXCLUDE_DIRS = {".git", ".cache", ".workbuddy", "__pycache__", "node_modules", ".venv", "venv"}
TEXT_EXT = {".md", ".py", ".json", ".txt", ".yml", ".yaml", ".cfg", ".toml", ".sh"}


def log(msg: str) -> None:
    print(msg, flush=True)


def read_frontmatter_name(skill_dir: Path) -> str:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        nested = skill_dir / "skills" / skill_dir.name / "SKILL.md"
        skill_md = nested if nested.exists() else skill_md
    if not skill_md.exists():
        return skill_dir.name
    m = re.search(r"^name:\s*(.+)$", skill_md.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    return m.group(1).strip() if m else skill_dir.name


def build_zip(skill_dir: Path, zip_path: Path, top: str) -> tuple[int, int]:
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
                z.writestr(f"{top}/{rel}", data)
                n += 1
    return n, zip_path.stat().st_size


def update_plan(plan_path: Path, skill_key: str, status: str = "done") -> bool:
    """就地改 `status.doubao`，**逐字节保留原排版**（见 plan_store.py 的说明）。"""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (plan.get("skills") or {}).get(skill_key) is None:
        log(f"  ⚠ 规划里没有技能 `{skill_key}`，跳过规划更新")
        return False
    if not plan_store.set_status(plan_path, skill_key, "doubao", status):
        log(f"  ⚠ 无法就地更新技能 `{skill_key}` 的 status.doubao，请手动改")
        return False
    log(f"  规划已更新：skills.{skill_key}.status.doubao = {status}（保留原排版）")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="为豆包技能中心准备导入包")
    parser.add_argument("--dir", required=True, help="技能仓本地路径（含 SKILL.md）")
    parser.add_argument("--out", help="输出 zip 路径，默认 <技能仓>/<name>-doubao.zip")
    parser.add_argument("--skill", help="publishing-plan.json 里的技能 key（默认按名字反查）")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="发布规划 JSON 路径")
    parser.add_argument("--mark-done", action="store_true", help="确认已导入成功后，更新规划并刷新视图")
    args = parser.parse_args()

    skill_dir = Path(args.dir).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"技能目录不存在：{skill_dir}")

    name = read_frontmatter_name(skill_dir)
    out = Path(args.out).expanduser().resolve() if args.out else skill_dir / f"{name}-doubao.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    count, size = build_zip(skill_dir, out, name)
    log(f"✅ 导入包已生成：{out}（{count} 个文件，{size/1024:.1f} KB，顶层目录 `{name}/`）")
    log("\n导入步骤（需你在豆包客户端完成，无公开上传 API）：")
    log("  1. 打开豆包电脑版 → 侧边栏「技能·连接器·伙伴」")
    log("  2. 我的技能 → 新建 → 上传技能")
    log(f"  3. 拖入上面的 zip（或解压后的 `{name}` 文件夹，名称须与技能同名）")
    log("  4. 导入成功后回跑本脚本加 --mark-done 更新发布规划")

    if args.mark_done:
        plan_path = Path(args.plan)
        key = args.skill
        if not key:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            for k in (plan.get("skills") or {}):
                if k == name or k == f"{name}-skill":
                    key = k
                    break
        if key and update_plan(plan_path, key):
            subprocess.run([sys.executable, str(PLAN_SCRIPT)], timeout=120)
            log("  视图已刷新")
        else:
            log("  ⚠ 未能定位规划里的技能 key，请用 --skill 指定")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
