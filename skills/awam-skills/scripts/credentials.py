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

统一排查入口（三发布脚本的 `--show-credentials` 都委托到这里）：

    python -m credentials <platform>          # 来源 + 脱敏值
    python -m credentials <platform> --paths  # 只列候选位置

同时提供 `source_guard()` —— 发布前校验待发布目录的 git origin 是否属于受信来源
（`awam-skills/` 组织或 `awamwang/` 个人仓），防止误把陌生仓发到组织平台。
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import constants  # 共享超时等常量（见 constants.py）

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
    """POSIX 下凭据文件权限过宽 / owner 非本人时告警（Windows 无 POSIX mode，跳过）。

    与审计 #16 互补：mode 过宽提示 chmod 600；owner 不是当前 uid 提示属主异常，
    帮助快速定位「凭据文件被别的用户/root 持有」这类配置失误。
    """
    if os.name == "nt":
        return
    try:
        st = p.stat()
        mode = stat.S_IMODE(st.st_mode)
        uid = st.st_uid
    except OSError:
        return
    cur_uid = os.getuid() if hasattr(os, "getuid") else None
    if mode & 0o077:
        _warn_once(
            f"perms:{p}",
            f"凭据文件权限过宽：{p}（{oct(mode)}，同组/其他用户可读）；建议 chmod 600",
        )
    if cur_uid is not None and uid != cur_uid:
        _warn_once(
            f"owner:{p}",
            f"凭据文件属主异常：{p}（uid={uid}，当前 uid={cur_uid}）；"
            "若非本人创建，请核对来源并考虑 chown 后再用",
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


def show(platform: str, explicit_file: str | None = None) -> int:
    """打印某平台的凭据来源与脱敏值（供各发布脚本 `--show-credentials` 统一调用）。

    返回 0 表示拿到了 token，1 表示没有。**绝不打印明文 token**。
    """
    cred, src = load(platform, explicit_file)
    print(f"平台：{platform}")
    print(f"凭据来源：{src}")
    print(f"  owner = {cred.get('owner') or '(空)'}")
    print(f"  token = {mask(cred.get('token', ''))}")
    return 0 if cred.get("token") else 1


# 允许发布的 GitHub 组织/账号前缀；发布前用它校验 --dir 来源，防止误发个人仓。
# 实测两类合法来源：`awam-skills/`（技能组织）与 `awamwang/`（个人仓，如 wiz-migration、
# 以及索引仓自身）。不在此列的前缀将被 source_guard 拦截。
TRUSTED_ORG_PREFIXES = ("awam-skills/", "awamwang/")


def git_remote_repo(skill_dir: Path) -> str | None:
    """从 origin 远端解析 owner/repo（如 `awam-skills/quicker-connector`）。

    非 GitHub 远端 / 无 origin / 无 git 时返回 None。
    """
    import re
    import subprocess

    try:
        import runutil
        out = runutil.run_git(skill_dir, "remote", "get-url", "origin",
                              timeout=constants.GIT_FAST)
        url = (out.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not url:
        return None
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def source_guard(skill_dir: Path, allow_any: bool = False) -> str | None:
    """校验待发布目录的 git 来源是否属于受信组织。

    返回 `None` 表示通过；否则返回一句人类可读的警告文本（调用方决定是中止还是仅提示）。
    `allow_any=True`（对应 `--allow-foreign-repo`）时直接放行，仅回显实际来源。
    """
    repo = git_remote_repo(skill_dir)
    if allow_any:
        return None
    if repo is None:
        return (
            f"无法从 {skill_dir} 的 git origin 解析出 GitHub 仓库；"
            f"若确认要发布该目录，请加 --allow-foreign-repo"
        )
    if not repo.startswith(TRUSTED_ORG_PREFIXES):
        trusted = "、".join(p.rstrip("/") for p in TRUSTED_ORG_PREFIXES)
        return (
            f"待发布目录的 origin 是 `{repo}`，不属于受信来源（{trusted}）；"
            f"误发他人/陌生仓会污染组织平台。确认无误请加 --allow-foreign-repo"
        )
    return None


def describe(platform: str) -> str:
    """给报错信息用的：列出所有候选位置，方便用户一次性补齐。"""
    lines = [f"  {i + 1}. {p}" for i, p in enumerate(candidate_paths(platform))]
    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> int:
    """`python -m credentials <platform> [--file <path>]` 的统一凭据排查入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="credentials",
        description="查看某平台的凭据来源与脱敏值（不打印明文）",
    )
    parser.add_argument("platform", help="平台名，如 modelscope / clawhub / doubao")
    parser.add_argument("--file", dest="file", default=None, help="显式指定凭据文件")
    parser.add_argument("--paths", action="store_true", help="只列出候选凭据位置")
    args = parser.parse_args(argv)

    if args.paths:
        print(f"平台 {args.platform} 的候选凭据位置（按优先级）：")
        print(describe(args.platform))
        return 0
    return show(args.platform, args.file)


if __name__ == "__main__":
    raise SystemExit(_main())
