#!/usr/bin/env python3
"""就地更新 `docs/publishing-plan.json` 里某技能的 `status.<platform>`，且**逐字节保留原排版**。

为什么需要它：规划文件是**手写**的「对象单行紧凑」格式，例如

    "plan":   { "github": "publish", "lobehub": "optional", ... },
    "status": { "github": "done", "lobehub": "todo", ... },

若用 `json.dumps(plan, indent=2)` 整体重序列化，每个 6 平台对象都会被拆成 6 行，
一次发布就产生上百行纯格式噪音，把真正的 1 行内容改动淹没在 diff 里（已踩过）。

因此这里只做**文本级精确定位替换**：找到该技能块 → 找到其 `status` 对象 →
只替换目标平台的字符串值，其余字节原样保留；写盘前再用 `json.loads` 自校验。

对外只暴露一个函数：`set_status(plan_path, skill_key, platform, status) -> bool`。
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _value_span(text: str, key: str) -> tuple[int, int] | None:
    """定位 `"key": { ... }` 的值区间（下标含两端花括号），扫描时跳过字符串内部。

    找不到返回 None。用「括号配对 + 跳过字符串」而非正则，才能正确处理含
    花括号 / 转义引号的字符串值。
    """
    m = re.search(r'"%s"\s*:\s*\{' % re.escape(key), text)
    if not m:
        return None
    start = text.index("{", m.start())
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i
        i += 1
    return None


def set_status(plan_path: Path, skill_key: str, platform: str, status: str = "done") -> bool:
    """把 `skills.<skill_key>.status.<platform>` 就地改成 `status`。

    成功返回 True（含「值本来就相同，无需改动」）；定位失败 / JSON 非法返回 False。
    """
    plan_path = Path(plan_path)
    text = plan_path.read_text(encoding="utf-8")
    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        return False
    if (plan.get("skills") or {}).get(skill_key) is None:
        return False

    span = _value_span(text, skill_key)
    if span is None:
        return False
    lo, hi = span
    block = text[lo:hi + 1]

    st = _value_span(block, "status")
    if st is None:
        return False
    slo, shi = st
    obj = block[slo:shi + 1]

    val = json.dumps(status, ensure_ascii=False)
    if re.search(r'"%s"\s*:' % re.escape(platform), obj):
        # 已有该平台键：只换值
        new_obj = re.sub(
            r'("%s"\s*:\s*)"[^"]*"' % re.escape(platform),
            lambda m: m.group(1) + val,
            obj,
        )
    else:
        # 缺该平台键：插到 status 对象末尾（保持原有单行紧凑风格）
        inner = obj[1:-1]
        if inner.strip():
            new_obj = "{" + inner.rstrip() + f', "{platform}": {val}' + "}"
        else:
            new_obj = '{ "' + platform + '": ' + val + " }"

    new_text = text[:lo] + block[:slo] + new_obj + block[shi + 1:] + text[hi + 1:]
    if new_text == text:
        return True
    json.loads(new_text)  # 写前自校验，防止改坏文件
    plan_path.write_text(new_text, encoding="utf-8")
    return True
