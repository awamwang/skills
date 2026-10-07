#!/usr/bin/env python3
"""平台凭据查找：让发布脚本自己知道去哪找 token，不必每次问用户。

设计原则（见 references/platforms.md「凭据管理」）：
- **凭据绝不入库**：只落在 git 管不到的位置（用户级目录 / gitignored 的 .local 文件）
- **优先级固定**：命令行 > 环境变量 > 用户级配置 > 仓内 .local 配置
- **只回传来源，不回传明文**：日志里打印凭据文件来源路径，禁止打印 token 本身
- **仓内兜底路径需 gitignore 双重确认**：`.credentials.local.json` 只在确实被
  `.gitignore` 覆盖时才启用（见 `_repo_local_allowed`），避免 gitignore 被删 /
  fork 不带 gitignore 时凭据静默入库。

查找顺序（以 modelscope 为例）：
1. 显式传入（--token / --owner）
2. 环境变量 MODELSCOPE_API_TOKEN / MODELSCOPE_OWNER
3. 环境变量 <PLATFORM>_CREDENTIALS 指向的 JSON 文件
4. ~/.workbuddy/secrets/<platform>.json          ← 推荐落点，不在任何 git 仓库内
5. ~/.config/awam-skills/credentials.json        （platforms.<platform> 段）
6. 索引仓 .credentials.local.json                （platforms.<platform> 段，需已 gitignore）

配置文件两种写法都支持：
- 平台专属：{"owner": "...", "sdk_token": "...", "api_key": "..."}
- 统一文件：{"platforms": {"modelscope": {"owner": "...", "token": "..."}}}
token 字段按 token > api_key > sdk_token > access_token 顺序取第一个非空值。
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]

TOKEN_KEYS = ("token", "api_key", "sdk_token", "access_token")
OWNER_KEYS = ("owner", "username", "user")

# 仓内兜底配置文件名；启用前必须确认已被 .gitignore 覆盖
REPO_LOCAL_NAME = ".credentials.local.json"
GITIGNORE_PATH = INDEX_ROOT / ".gitignore"

# 本次运行已打印过的告警（去重，避免 load() 多次调用刷屏）
_WARNED: set[str] = set()


def _warn_once(key: str, msg: str) -> None:
    if key in _WARNED:
        return
    _WARNED.add(key)
    print(f"⚠ {msg}", file=sys.stderr, flush=True)


def _repo_local_allowed() -> tuple[bool, str]:
    """判断索引仓内 `.credentials.local.json` 是否可作为凭据来源。

    只有在 `.gitignore` 存在且确实覆盖该文件名时才允许 —— 否则一旦
    gitignore 被误删 / 被 fork 仓遗漏，凭据就会静默进入版本库。
    返回 (是否允许, 原因说明)。
    """
    if not GITIGNORE_PATH.is_file():
        return False, f"索引仓缺 {GITIGNORE_PATH.name}，无法确认该文件不会被提交"
    try:
        text = GITIGNORE_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return False, f"读取 {GITIGNORE_PATH.name} 失败：{e}"
    patterns = {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    # 覆盖判断：精确名 / 通配后缀（*.credentials.json）/ 目录级忽略
    if REPO_LOCAL_NAME in patterns or "*.credentials.json" in patterns:
        return True, f"{GITIGNORE_PATH.name} 已覆盖 {REPO_LOCAL_NAME}"
    return False, f"{GITIGNORE_PATH.name} 未覆盖 {REPO_LOCAL_NAME}"


def candidate_paths(platform: str) -> list[Path]:
    """按优先级返回候选配置文件路径。

    索引仓兜底路径仅在 gitignore 确认覆盖时返回（见 `_repo_local_allowed`）。
    """
    home = Path.home()
    paths = [
        home / ".workbuddy" / "secrets" / f"{platform}.json",
        home / ".config" / "awam-skills" / "credentials.json",
    ]
    allowed, reason = _repo_local_allowed()
    if allowed:
        paths.append(INDEX_ROOT / REPO_LOCAL_NAME)
    else:
        _warn_once(
            "repo-local-skipped",
            f"已跳过仓内 {REPO_LOCAL_NAME}（{reason}）；"
            "请改用 ~/.workbuddy/secrets/<platform>.json 存放凭据",
        )
    return paths


def _check_file_perms(p: Path) -> None:
    """POSIX 下凭据文件权限过宽时告警（Windows 无 POSIX mode，跳过）。"""
    if os.name == "nt":
        return
    try:
        mode = stat.S_IMODE(p.stat().st_mode)
    except OSError:
        return
    if mode & 0o077:
        _warn_once(
            f"perms:{p}",
            f"凭据文件权限过宽：{p}（{oct(mode)}，同组/其他用户可读）；建议 chmod 600",
        )


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
            _check_file_perms(p)
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
        _check_file_perms(p)
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
    """脱敏显示：只留前 4 + 后 4 位与长度。

    只留前缀是不够的——`ms_` / `ghp_` / `sk-` 这类前缀可预测，前 8 位几乎等于
    明文前缀 + 少量随机字符；短 token 更会直接暴露一半。改为「首尾各 4 位」，
    既能在排查时区分不同凭据，又不泄露可用内容；长度 < 12 时只留长度。
    """
    if not token:
        return "(空)"
    n = len(token)
    if n < 12:
        return f"…({n} 位，已隐去)"
    return f"{token[:4]}…{token[-4:]}({n} 位)"
