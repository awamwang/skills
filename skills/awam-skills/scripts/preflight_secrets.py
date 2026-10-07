#!/usr/bin/env python3
"""发布前敏感串扫描：在把包传到公开平台（不可逆）之前拦一道。

为什么必须有
------------
发布到魔搭 / ClawHub / 豆包 等平台是**不可逆**的：一旦把含密钥的内容传上去，
即使随后替换版本，旧内容也可能已被缓存 / 索引 / 抓取。
`public_files.py` 解决的是「哪些文件该发」，本模块解决的是「该发的文件里
有没有不该出现的凭据字符串」—— 两者互补，缺一不可。

检测规则（分层）
----------------
1. **文件名**：`.env` / `*.pem` / `*.key` / `*credentials*` / `*secret*` 等；
2. **内容正则**：常见平台的 token 前缀、私钥块头、AWS 密钥、连接串口令等；
3. **高熵串**（可选）：长且字符分布随机的疑似密钥。

命中即返回问题列表，调用方应中止发布并打印路径。
允许通过 `# awam-allow-secret` 注释或路径白名单豁免误报。
"""

from __future__ import annotations

import math
import re
from pathlib import Path

# 文件名级：命中即视为可疑（小写匹配）
SUSPECT_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "id_rsa",
    "id_ed25519",
    ".npmrc",
    ".pypirc",
    ".netrc",
}
SUSPECT_SUFFIXES = (".pem", ".key", ".pfx", ".p12", ".jks", ".keystore")
SUSPECT_NAME_PARTS = ("credential", "secret", "password", "passwd", "apikey", "api_key")

# 文件名豁免：这些是**处理**凭据的源码/文档，本身就是公开内容，不该按名字拦。
# （否则 credentials.py 这类模块永远无法发布——见 2026-10-07 实测）
EXEMPT_NAMES = {
    "credentials.py",        # 凭据查找模块
    "preflight_secrets.py",  # 本扫描器自身
}

# 只在「文本文件」里扫内容，避免二进制误判
TEXT_SUFFIXES = {
    ".md", ".py", ".json", ".txt", ".yml", ".yaml", ".cfg", ".toml", ".sh",
    ".ini", ".env", ".js", ".ts", ".html", ".css", ".xml", "",
}
MAX_SCAN_BYTES = 2 * 1024 * 1024  # 单文件扫描上限，防止卡在大文件上

# 内容级：正则 → 说明
CONTENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
     "私钥块（PRIVATE KEY）"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "GitHub personal access token (ghp_)"),
    (re.compile(r"\bgho_[A-Za-z0-9]{20,}\b"), "GitHub OAuth token (gho_)"),
    (re.compile(r"\bghs_[A-Za-z0-9]{20,}\b"), "GitHub app token (ghs_)"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "GitHub fine-grained PAT"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "OpenAI 风格密钥 (sk-)"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id (AKIA)"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "AWS 临时 access key id (ASIA)"),
    (re.compile(r"\bms-[A-Za-z0-9_-]{20,}\b"), "魔搭 ModelScope token (ms-)"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token (xox*)"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "Google API key (AIza)"),
    (re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b"), "Stripe 密钥"),
    (re.compile(r"(?i)\b(?:mysql|postgres|postgresql|mongodb|redis|amqp)"
                r"://[^:/\s]+:[^@/\s]+@"), "数据库连接串（含明文口令）"),
    (re.compile(r"(?i)(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token"
                r"|sdk[_-]?token|auth[_-]?token)\s*[:=]\s*[\"']?[A-Za-z0-9._\-/+]{16,}[\"']?"),
     "疑似凭据赋值（key = 长随机值）"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
     "JWT（可能含敏感声明）"),
]

# 允许豁免的标记：同行含该注释即跳过
ALLOW_MARKER = "awam-allow-secret"


def _entropy(s: str) -> float:
    """香农熵（bit/char），用于判断疑似随机串。"""
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def check_filename(rel: str) -> str | None:
    """文件名级检查，命中返回原因。

    豁免规则：`credentials.py` 这类**处理**凭据的源码、以及 `.md` 文档
    本身就是公开内容，不该仅凭文件名拦截（正文扫描仍会生效）。
    """
    p = Path(rel)
    name = p.name.lower()
    if name in EXEMPT_NAMES:
        return None
    if name in SUSPECT_NAMES:
        return f"敏感文件名：{p.name}"
    if name.startswith(".env"):
        return f"环境变量文件：{p.name}"
    if name.endswith(SUSPECT_SUFFIXES):
        return f"密钥/证书文件：{p.name}"
    stem = p.stem.lower()
    for part in SUSPECT_NAME_PARTS:
        if part in stem:
            return f"文件名含 `{part}`：{p.name}"
    return None


def check_content(text: str) -> str | None:
    """内容级检查，命中返回原因。"""
    for lineno, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line:
            continue
        for pattern, desc in CONTENT_PATTERNS:
            m = pattern.search(line)
            if m:
                return f"第 {lineno} 行：{desc}"
    return None


def scan_text(text: str) -> list[str]:
    """扫描单段文本，返回问题描述列表（用于单测 / 复用）。"""
    problems: list[str] = []
    if ALLOW_MARKER in text and check_content(text) is None:
        return problems
    hit = check_content(text)
    if hit:
        problems.append(hit)
    return problems


def scan_files(files: list[Path], root: Path | None = None) -> list[tuple[str, str]]:
    """扫描待发布文件，返回 [(相对路径, 原因)]；空列表表示通过。

    root 用于算相对路径（默认取文件本身路径）。
    """
    problems: list[tuple[str, str]] = []
    for p in files:
        p = Path(p)
        try:
            rel = p.relative_to(root).as_posix() if root else p.as_posix()
        except ValueError:
            rel = p.as_posix()

        name_hit = check_filename(rel)
        if name_hit:
            problems.append((rel, name_hit))
            continue

        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if p.stat().st_size > MAX_SCAN_BYTES:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        content_hit = check_content(text)
        if content_hit:
            problems.append((rel, content_hit))

    return problems


def format_problems(problems: list[tuple[str, str]]) -> str:
    """把扫描结果整理成可直接打印的文本。"""
    if not problems:
        return "✅ 敏感串扫描通过：未发现疑似凭据"
    lines = [f"❌ 敏感串扫描发现 {len(problems)} 处问题（发布是**不可逆**的，已中止）："]
    for rel, why in problems:
        lines.append(f"  - {rel} — {why}")
    lines.append("")
    lines.append(f"  确认无误可豁免：在对应行加 `# {ALLOW_MARKER}` 注释，")
    lines.append("  或把该文件排除出发布集（见 public_files.py）。")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="扫描待发布目录是否含疑似凭据")
    ap.add_argument("--dir", required=True, help="技能目录（含 SKILL.md）")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import public_files  # noqa: E402

    skill_dir = Path(args.dir).expanduser().resolve()
    files, root, source, _excluded, _outside = public_files.pack_files(skill_dir)
    if root is None:
        print(f"无法确定打包根：{source}", file=sys.stderr)
        raise SystemExit(2)
    problems = scan_files(files, root)
    print(format_problems(problems))
    raise SystemExit(1 if problems else 0)
