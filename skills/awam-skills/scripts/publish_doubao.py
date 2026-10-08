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
import constants  # noqa: E402  （共享超时等常量：见 constants.py）
import credentials as creds  # noqa: E402  （凭据查找 + 来源校验：见 credentials.py）
import plan_store  # noqa: E402  （规划就地更新，保留原排版：见 plan_store.py）
import state_store  # noqa: E402  （发布状态记录，漂移检测基线：见 state_store.py）
import preflight_secrets  # noqa: E402  （发布前敏感串扫描：见 preflight_secrets.py）
import public_files  # noqa: E402  （公开文件集：见 public_files.py）

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = INDEX_ROOT / "docs" / "publishing-plan.json"
PLAN_SCRIPT = Path(__file__).resolve().parent / "plan_skills.py"
PLATFORM = "doubao"

TEXT_EXT = {".md", ".py", ".json", ".txt", ".yml", ".yaml", ".cfg", ".toml", ".sh"}

# 默认输出到仓库**外**：写进技能仓会被 `git status` 看见，容易误提交进公开仓库
# （技能仓里那个 zip 正是 `public_files` 认定的私密数据集合的反面教材）。
DEFAULT_OUT_DIR = Path.home() / ".awam-publish"


def log(msg: str) -> None:
    print(msg, flush=True)


def read_frontmatter_name(skill_dir: Path) -> str:
    root, _note = public_files.find_skill_root(skill_dir)
    if root is None:
        return skill_dir.name
    text = (root / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else skill_dir.name


def build_zip(skill_dir: Path, zip_path: Path, top: str,
              skip_secret_scan: bool = False) -> tuple[int, int]:
    """打包。只打 `public_files` 判定的公开文件——导入包会被上传到平台，属公开物，
    绝不能把 storage/、env.json、index.json 这类本地私密数据带进去。
    路径按**打包根**（SKILL.md 所在目录）取，嵌套布局也能得到「顶层文件夹下就是 SKILL.md」。

    打包前先跑敏感串扫描（`preflight_secrets`）：上传公开平台**不可逆**。
    """
    files, root, source, excluded, outside = public_files.pack_files(skill_dir)
    log(f"  {public_files.describe(skill_dir)}")
    for rel in excluded:
        log(f"    ⤫ 排除 {rel}")
    if root is None:
        raise SystemExit(f"无法确定打包根：{source}")

    if not skip_secret_scan:
        problems = preflight_secrets.scan_files(files, root)
        if problems:
            raise SystemExit(
                preflight_secrets.format_problems(problems)
                + "\n  确需发布请加 --skip-secret-scan（自行承担凭据泄露风险）"
            )
        log("  敏感串扫描：✅ 未发现疑似凭据")

    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = public_files.pack_rel(p, root)
            data = p.read_bytes()
            if p.suffix.lower() in TEXT_EXT:
                data = data.replace(b"\r\n", b"\n")
            z.writestr(f"{top}/{rel}", data)
            n += 1
    if not any(public_files.pack_rel(p, root) == "SKILL.md" for p in files):
        raise SystemExit("导入包顶层缺 SKILL.md，豆包会导入失败")
    return n, zip_path.stat().st_size


def update_plan(plan_path: Path, skill_key: str, status: str = "done",
                skill_dir: Path | None = None) -> bool:
    """就地改 `status.doubao`，**逐字节保留原排版**（见 plan_store.py 的说明）。"""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (plan.get("skills") or {}).get(skill_key) is None:
        log(f"  ⚠ 规划里没有技能 `{skill_key}`，跳过规划更新")
        return False
    if not plan_store.set_status(plan_path, skill_key, "doubao", status):
        log(f"  ⚠ 无法就地更新技能 `{skill_key}` 的 status.doubao，请手动改")
        return False
    log(f"  规划已更新：skills.{skill_key}.status.doubao = {status}（保留原排版）")
    if status == "done" and skill_dir is not None:
        if state_store.record_publish_from_repo(state_store.STATE_PATH, skill_dir, skill_key, "doubao"):
            log("  发布状态已记录（check_publish_drift.py 以此为基线）")
        else:
            log("  ⚠ 发布状态记录失败；可稍后用 check_publish_drift.py --record 补记")
    return True


def refresh_view() -> None:
    """调用 plan_skills.py 刷新人读视图（不手改 md）。

    捕获失败并提示——早先这里 `subprocess.run` 不看 returncode，
    视图刷新失败时用户以为成功了（与 publish_modelscope 的 refresh_view 对齐）。
    """
    try:
        out = subprocess.run(
            [sys.executable, str(PLAN_SCRIPT)], capture_output=True, text=True, timeout=constants.PLAN_SCRIPT
        )
    except (OSError, subprocess.SubprocessError) as e:
        log(f"  ⚠ 刷新视图失败（无法执行）：{e}")
        return
    if out.returncode == 0:
        log(f"  视图已刷新：{out.stdout.strip() or 'docs/publishing-plan.md'}")
    else:
        detail = (out.stderr or out.stdout or "").strip()
        log(f"  ⚠ 刷新视图失败（exit={out.returncode}）：{detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="为豆包技能中心准备导入包")
    parser.add_argument("--dir", help="技能仓本地路径（含 SKILL.md）")
    parser.add_argument("--out", help=f"输出 zip 路径，默认 {DEFAULT_OUT_DIR}\\<name>-doubao.zip（仓外）")
    parser.add_argument("--skill", help="publishing-plan.json 里的技能 key（默认按名字反查）")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="发布规划 JSON 路径")
    parser.add_argument("--mark-done", action="store_true", help="确认已导入成功后，更新规划并刷新视图")
    parser.add_argument("--skip-secret-scan", action="store_true",
                        help="跳过打包前的敏感串扫描（默认开启；跳过即自行承担凭据泄露风险）")
    parser.add_argument("--allow-foreign-repo", action="store_true",
                        help="跳过来源校验（默认要求 origin 属于 awam-skills/ 组织）")
    parser.add_argument("--show-credentials", action="store_true",
                        help="只打印凭据来源（脱敏）后退出，用于排查")
    args = parser.parse_args()

    if args.show_credentials:
        return creds.show(PLATFORM)

    if not args.dir:
        raise SystemExit("需要 --dir 指定技能仓本地路径（含 SKILL.md）")
    skill_dir = Path(args.dir).expanduser().resolve()
    if not skill_dir.is_dir():
        raise SystemExit(f"技能目录不存在：{skill_dir}")

    warn = creds.source_guard(skill_dir, allow_any=args.allow_foreign_repo)
    if warn:
        raise SystemExit(
            f"⛔ 发布来源校验未通过：{warn}\n"
            f"  待发布目录：{skill_dir}"
        )

    name = read_frontmatter_name(skill_dir)
    out = Path(args.out).expanduser().resolve() if args.out else DEFAULT_OUT_DIR / f"{name}-doubao.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    count, size = build_zip(skill_dir, out, name, skip_secret_scan=args.skip_secret_scan)
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
        if key and update_plan(plan_path, key, skill_dir=skill_dir):
            refresh_view()
        else:
            log("  ⚠ 未能定位规划里的技能 key，请用 --skill 指定")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
