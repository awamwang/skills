#!/usr/bin/env python3
"""平台凭据查找：让发布脚本自己知道去哪找 token，不必每次问用户。

设计原则（见 references/platforms.md「凭据管理」）：
- **凭据绝不入库**：只落在 git 管不到的位置（用户级目录 / gitignored 的 .local 文件）
- **优先级固定**：命令行 > 环境变量 > 用户级配置 > 仓内 .local 配置
- **只回传来源，不回传明文**：日志里打印凭据文件来源路径，禁止打印 token 本身

查找顺序（以 modelscope 为例）：
1. 显式传入（--token / --owner）
2. 环境变量 MODELSCOPE_API_TOKEN / MODELSCOPE_OWNER
3. 环境变量 <PLATFORM>_CREDENTIALS 指向的 JSON 文件
4. ~/.workbuddy/secrets/<platform>.json          ← 推荐落点，不在任何 git 仓库内
5. ~/.config/awam-skills/credentials.json        （platforms.<platform> 段）
6. 索引仓 .credentials.local.json                （platforms.<platform> 段，已 gitignore）

配置文件两种写法都支持：
- 平台专属：{"owner": "...", "sdk_token": "...", "api_key": "..."}
- 统一文件：{"platforms": {"modelscope": {"owner": "...", "token": "..."}}}
token 字段按 token > api_key > sdk_token > access_token 顺序取第一个非空值。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]

TOKEN_KEYS = ("token", "api_key", "sdk_token", "access_token")
OWNER_KEYS = ("owner", "username", "user")


def candidate_paths(platform: str) -> list[Path]:
    """按优先级返回候选配置文件路径。"""
    home = Path.home()
    return [
        home / ".workbuddy" / "secrets" / f"{platform}.json",
        home / ".config" / "awam-skills" / "credentials.json",
        INDEX_ROOT / ".credentials.local.json",
    ]


def _pick(d: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _extract(raw: dict, platform: str) -> dict:
    """从配置文件内容里取出该平台的凭据段。"""
    platforms = raw.get("platforms")
    if isinstance(platforms, dict):
        seg = platforms.get(platform)
        if isinstance(seg, dict):
            return seg
    return raw


def load(platform: str, explicit_file: str | None = None) -> tuple[dict, str]:
    """返回 (凭据字典, 来源描述)。找不到时凭据为空字典、来源为 '未找到'。

    凭据字典至少包含 token / owner 两个键（可能为空字符串）。
    """
    env_pfx = platform.upper()

    # 1) 环境变量直接给值
    env_token = os.environ.get(f"{env_pfx}_API_TOKEN", "").strip()
    env_owner = os.environ.get(f"{env_pfx}_OWNER", "").strip()
    if env_token or env_owner:
        return {"token": env_token, "owner": env_owner}, f"环境变量 {env_pfx}_*"

    # 2) 环境变量指定文件 / 命令行 --credentials
    path_str = explicit_file or os.environ.get(f"{env_pfx}_CREDENTIALS", "")
    if path_str:
        p = Path(path_str).expanduser()
        if p.is_file():
            try:
                seg = _extract(json.loads(p.read_text(encoding="utf-8")), platform)
                return {"token": _pick(seg, TOKEN_KEYS), "owner": _pick(seg, OWNER_KEYS)}, str(p)
            except (json.JSONDecodeError, OSError) as e:
                return {}, f"{p}（解析失败：{e}）"
        return {}, f"{p}（不存在）"

    # 3) 候选路径
    for p in candidate_paths(platform):
        if not p.is_file():
            continue
        try:
            seg = _extract(json.loads(p.read_text(encoding="utf-8")), platform)
        except (json.JSONDecodeError, OSError):
            continue
        token, owner = _pick(seg, TOKEN_KEYS), _pick(seg, OWNER_KEYS)
        if token or owner:
            return {"token": token, "owner": owner}, str(p)

    return {}, "未找到"


def describe(platform: str) -> str:
    """给报错信息用的：列出所有候选位置，方便用户一次性补齐。"""
    lines = [f"  {i + 1}. {p}" for i, p in enumerate(candidate_paths(platform))]
    return "\n".join(lines)


def mask(token: str) -> str:
    """脱敏显示：只留前 8 位 + 长度，避免凭据进入日志。"""
    if not token:
        return "(空)"
    return f"{token[:8]}…({len(token)} 位)"
