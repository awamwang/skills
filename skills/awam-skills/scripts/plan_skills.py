#!/usr/bin/env python3
"""从发布规划权威数据生成 / 校验人读视图。

权威数据：docs/publishing-plan.json（技能 × 平台 的 plan 与 status）
人读视图：docs/publishing-plan.md（由本脚本生成，勿手改）

用法（索引仓根任意路径均可，脚本自定位）：
  python skills/awam-skills/scripts/plan_skills.py            # 生成并写 docs/publishing-plan.md
  python skills/awam-skills/scripts/plan_skills.py --check    # 只校验 JSON 结构
  python skills/awam-skills/scripts/plan_skills.py --print    # 把 Markdown 打到 stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = INDEX_ROOT / "docs" / "publishing-plan.json"
DEFAULT_OUT = INDEX_ROOT / "docs" / "publishing-plan.md"

PLATFORM_ORDER = ["github", "lobehub", "modelscope", "doubao", "clawhub", "agentpowers"]

STATUS_SYMBOL = {
    "done": "✅",
    "not_started": "○",
    "todo": "◐",
    "blocked": "⚠",
    "skip": "—",
}


def load_plan(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check(plan: dict, path: Path) -> list[str]:
    problems: list[str] = []
    platforms = plan.get("platforms") or {}
    tiers = plan.get("tiers") or {}
    skills = plan.get("skills") or {}
    status_labels = plan.get("status_labels") or {}
    plan_labels = plan.get("plan_labels") or {}

    for p in PLATFORM_ORDER:
        if p not in platforms:
            problems.append(f"缺平台定义: {p}")

    for name, sk in (skills or {}).items():
        if "tier" not in sk or sk["tier"] not in tiers:
            problems.append(f"{name}: tier 缺失或未定义 ({sk.get('tier')})")
        if "repo" not in sk:
            problems.append(f"{name}: 缺 repo")
        for kind in ("plan", "status"):
            m = sk.get(kind) or {}
            for p in PLATFORM_ORDER:
                val = m.get(p)
                if val is None:
                    problems.append(f"{name}.{kind}: 缺平台 {p}")
                    continue
                labels = status_labels if kind == "status" else plan_labels
                if val not in labels:
                    problems.append(f"{name}.{kind}.{p}: 未知取值 {val!r}")

    # status/plan 的平台键应一致
    for name, sk in (skills or {}).items():
        if set((sk.get("plan") or {}).keys()) != set((sk.get("status") or {}).keys()):
            problems.append(f"{name}: plan 与 status 的平台键不一致")
    return problems


def render(plan: dict) -> str:
    platforms = plan.get("platforms") or {}
    tiers = plan.get("tiers") or {}
    skills = plan.get("skills") or {}
    status_labels = plan.get("status_labels") or {}
    plan_labels = plan.get("plan_labels") or {}
    updated = plan.get("updated", "")

    L: list[str] = []
    L.append("# 技能发布规划")
    L.append("")
    L.append(f"> 权威数据：[publishing-plan.json](publishing-plan.json) · 视图由 `skills/awam-skills/scripts/plan_skills.py` 生成，请勿手改本文件 · 更新：{updated}")
    L.append("")
    L.append("## 平台")
    L.append("")
    L.append("| 平台 | 区域 | 通道 | 优先级 | 说明 |")
    L.append("|------|------|------|:------:|------|")
    for p in PLATFORM_ORDER:
        pf = platforms.get(p, {})
        L.append(
            f"| **{pf.get('name', p)}** | {pf.get('region', '')} | {pf.get('channel', '')} "
            f"| {pf.get('priority', '')} | {pf.get('note', '')} |"
        )
    L.append("")

    L.append("## 梯队")
    L.append("")
    for key in ("t1", "t2", "t3"):
        t = tiers.get(key, {})
        L.append(f"- **{t.get('label', key)}**：{t.get('action', '')}")
    L.append("")

    L.append("## 技能 × 平台（实际状态）")
    L.append("")
    L.append("图例：" + "　".join(f"{STATUS_SYMBOL[k]} {status_labels.get(k, k)}" for k in STATUS_SYMBOL))
    L.append("")
    L.append("| 技能 | 梯队 | " + " | ".join(platforms.get(p, {}).get("name", p) for p in PLATFORM_ORDER) + " |")
    L.append("|------|:----:|" + "|".join([":---:"] * len(PLATFORM_ORDER)) + "|")
    for name, sk in skills.items():
        tier = tiers.get(sk.get("tier", ""), {}).get("label", sk.get("tier", ""))
        cells = []
        for p in PLATFORM_ORDER:
            st = (sk.get("status") or {}).get(p, "")
            cells.append(STATUS_SYMBOL.get(st, "·"))
        L.append(f"| `{name}` | {tier} | " + " | ".join(cells) + " |")
    L.append("")

    L.append("## 明细")
    L.append("")
    for name, sk in skills.items():
        tier = tiers.get(sk.get("tier", ""), {}).get("label", sk.get("tier", ""))
        L.append(f"### {name} · {tier}")
        L.append("")
        L.append(f"- 仓库：`{sk.get('repo', '')}`")
        L.append(f"- 简介：{sk.get('summary', '')}")
        L.append(f"- 规划：{sk.get('notes', '')}")
        L.append("")
        L.append("| 平台 | 规划 | 实际 |")
        L.append("|------|:----:|:----:|")
        plan = sk.get("plan") or {}
        status = sk.get("status") or {}
        for p in PLATFORM_ORDER:
            pl = plan.get(p, "")
            st = status.get(p, "")
            L.append(
                f"| {platforms.get(p, {}).get('name', p)} | {plan_labels.get(pl, pl)} "
                f"| {STATUS_SYMBOL.get(st, '·')} {status_labels.get(st, st)} |"
            )
        L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 / 校验发布规划视图")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN, help="权威 JSON 路径")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Markdown 输出路径")
    parser.add_argument("--print", action="store_true", help="输出到 stdout 而非写文件")
    parser.add_argument("--check", action="store_true", help="只校验结构，不生成")
    args = parser.parse_args(argv)

    if not args.plan.is_file():
        print(f"未找到权威数据: {args.plan}", file=sys.stderr)
        return 1

    try:
        plan = load_plan(args.plan)
    except (OSError, json.JSONDecodeError) as e:
        print(f"权威数据解析失败: {e}", file=sys.stderr)
        return 1

    problems = check(plan, args.plan)
    if problems:
        for msg in problems:
            print(f"- {msg}", file=sys.stderr)
        print(f"校验未通过（{len(problems)} 项）", file=sys.stderr)
        return 1

    if args.check:
        print("校验通过")
        return 0

    md = render(plan)
    if args.print:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
        sys.stdout.write(md + "\n")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md + "\n", encoding="utf-8")
    print(f"已写入: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
