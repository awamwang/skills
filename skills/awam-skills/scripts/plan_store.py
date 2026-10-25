#!/usr/bin/env python3
"""就地更新 `docs/publishing-plan.json` 里某技能的 `plan.<platform>` / `status.<platform>`。

为什么需要它：规划文件是**手写**的「对象单行紧凑」格式，例如

    "plan":   { "github": "publish", "lobehub": "optional", ... },
    "status": { "github": "done", "lobehub": "todo", ... },

若用 `json.dumps(plan, indent=2)` 整体重序列化，每个 6 平台对象都会被拆成 6 行，
一次发布就产生上百行纯格式噪音，把真正的 1 行内容改动淹没在 diff 里（已踩过）。

因此这里只做**块级重写**：

1. `json.loads` 拿到对象 → 在**对象层**改 `plan|status.<platform>`（值正确性由此保证，不用正则）；
2. 用括号配对扫描器定位该技能块在原文中的区间（跳过字符串，正确处理花括号）；
3. 只重生成该块内的 `plan` / `status` 那一行（统一紧凑格式，**每行一个平台对象**）；
4. 其余所有行原样保留 —— 其他技能、platforms 段、tiers 段都不动；
5. 原子写盘（临时文件 + `os.replace`），避免中途崩溃截断文件。

对外：`set_status(...)` / `set_plan(...)`。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

_MAP_FIELDS = frozenset({"plan", "status"})


def _value_span(text: str, key: str) -> tuple[int, int] | None:
    """定位 `"key": { ... }` 的值区间（下标含两端花括号），扫描时跳过字符串内部。

    找不到返回 None。用「括号配对 + 跳过字符串」而非正则，才能正确处理含
    花括号 / 转义引号的字符串值。
    """
    # 先找到 `"key"` 字面量，再从其后第一个 `{` 开始配对。
    marker = '"%s"' % key
    kpos = text.find(marker)
    if kpos < 0:
        return None
    start = text.find("{", kpos + len(marker))
    if start < 0:
        return None
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


def _line_span(text: str, pos: int) -> tuple[int, int]:
    """返回包含下标 `pos` 的整行区间 [行首, 换行符位置或文末]。"""
    lo = text.rfind("\n", 0, pos) + 1
    hi = text.find("\n", pos)
    if hi < 0:
        hi = len(text)
    return lo, hi


def _compact(obj: dict) -> str:
    """把扁平 dict 序列化为单行紧凑 JSON：`{ "k": "v", "k2": "v2" }`。

    保持与手写风格一致的「大括号内两侧各一个空格、键值间 `: `」写法；
    中文不转义。仅用于 `status` / `plan` 这类一层扁平的字符串映射。
    """
    if not obj:
        return "{ }"
    inner = ", ".join(
        '%s: %s' % (json.dumps(k, ensure_ascii=False), json.dumps(v, ensure_ascii=False))
        for k, v in obj.items()
    )
    return "{ " + inner + " }"


def _atomic_write(path: Path, text: str) -> None:
    """原子写：同目录临时文件 → fsync → os.replace 覆盖。"""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _set_skill_map_field(
    plan_path: Path,
    skill_key: str,
    platform: str,
    value: str,
    *,
    field: str,
) -> bool:
    """把 `skills.<skill_key>.<field>.<platform>` 就地改成 `value`。

    `field` 仅允许 `plan` / `status`。
    成功返回 True（含「值本来就相同，无需改动」）；定位失败 / JSON 非法返回 False。
    """
    if field not in _MAP_FIELDS:
        raise ValueError(f"field 须为 plan|status，收到 {field!r}")

    plan_path = Path(plan_path)
    text = plan_path.read_text(encoding="utf-8")
    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        return False

    skills = plan.get("skills") or {}
    entry = skills.get(skill_key)
    if not isinstance(entry, dict):
        return False

    # 1) 先在对象层改值 —— 保证写出的内容正确
    mapping = entry.get(field)
    if not isinstance(mapping, dict):
        return False
    if mapping.get(platform) == value:
        return True  # 值本来就相同
    mapping[platform] = value

    # 2) 定位该技能块，只重写块内 field 那一行
    span = _value_span(text, skill_key)
    if span is None:
        return False
    lo, hi = span
    block = text[lo:hi + 1]

    field_span = _value_span(block, field)
    if field_span is None:
        return False
    flo, fhi = field_span
    # 相对原文的绝对区间
    abs_flo, abs_fhi = lo + flo, lo + fhi
    line_lo, _line_hi = _line_span(text, abs_flo)
    prefix = text[line_lo:abs_flo]  # 缩进 + `"plan": ` / `"status": `
    # 对象结束位置到它所在行末的字符：单行时通常是 "" 或尾随逗号 ","；
    # 对象若跨多行（如文件被 indent=2 格式化过），这里会吃掉收尾行余下内容。
    end_line_hi = _line_span(text, abs_fhi)[1]
    suffix = text[abs_fhi + 1:end_line_hi]
    new_text = text[:line_lo] + prefix + _compact(mapping) + suffix + text[end_line_hi:]

    if new_text == text:
        return True
    try:
        json.loads(new_text)  # 写前自校验，防止改坏文件
    except json.JSONDecodeError:
        return False
    _atomic_write(plan_path, new_text)
    return True


def set_status(plan_path: Path, skill_key: str, platform: str, status: str = "done") -> bool:
    """把 `skills.<skill_key>.status.<platform>` 就地改成 `status`。"""
    return _set_skill_map_field(
        plan_path, skill_key, platform, status, field="status"
    )


def set_plan(plan_path: Path, skill_key: str, platform: str, value: str) -> bool:
    """把 `skills.<skill_key>.plan.<platform>` 就地改成 `value`（publish/optional/skip）。"""
    return _set_skill_map_field(
        plan_path, skill_key, platform, value, field="plan"
    )
