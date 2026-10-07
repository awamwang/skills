#!/usr/bin/env python3
"""awam-skills 依赖初始化：按需安装平台发布用到的第三方包。

为什么需要它：魔搭发布走 **modelscope SDK**（cookie 鉴权），需要 `modelscope` 包；
但该包会拖入 torch 等重依赖，而发布只用它的 hub 上传能力，因此安装时统一加 `--no-deps`，
再补上真正需要的轻量依赖（requests / tqdm / urllib3 / addict）。

幂等：已装则跳过。用法：
  python scripts/setup_env.py            # 检测 + 补齐缺失依赖（默认装到 tools/.venv 隔离环境）
  python scripts/setup_env.py --check    # 只检测当前解释器，不安装（退出码 1 表示缺依赖）
  python scripts/setup_env.py --no-venv  # 不建隔离环境，装到当前解释器（会污染全局）
  python scripts/setup_env.py --mirror https://pypi.tuna.tsinghua.edu.cn/simple

隔离说明：默认把依赖装进索引仓 `tools/.venv`（已 gitignore），不污染全局 PYTHONPATH；
已在某个 venv 里运行（sys.prefix != sys.base_prefix）时自动复用当前环境，不再嵌套建 venv。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# skills/awam-skills/scripts → 索引仓根
INDEX_ROOT = Path(__file__).resolve().parents[3]
VENV_DIR = INDEX_ROOT / "tools" / ".venv"

# 已知可信镜像（同时给出白名单，避免 `--mirror` 被指向投毒源）
TRUSTED_MIRROR_HOSTS = (
    "pypi.org",
    "files.pythonhosted.org",
    "pypi.tuna.tsinghua.edu.cn",     # 清华
    "mirrors.aliyun.com",            # 阿里
    "mirrors.cloud.tencent.com",     # 腾讯
    "mirrors.ustc.edu.cn",           # 中科大
    "mirrors.huaweicloud.com",       # 华为
    "pypi.mirrors.ustc.edu.cn",
)


def validate_mirror(url: str) -> str:
    """校验 --mirror：必须 https，且主机在可信白名单内。

    为什么必须校验：`--mirror` 会原样进入 `pip install -i <url>`，
    一个 http 或被投毒的镜像可以直接把恶意包装进环境（供应链攻击）。
    返回规范化后的 URL；不合法则抛 SystemExit。
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SystemExit(
            f"--mirror 必须是 https（当前：{url!r}）；"
            "http 镜像会被中间人替换包内容。"
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise SystemExit(f"--mirror 无法解析主机名：{url!r}")
    if host not in TRUSTED_MIRROR_HOSTS:
        raise SystemExit(
            f"--mirror 主机不在可信白名单内：{host}\n"
            "  可信镜像：" + "、".join(TRUSTED_MIRROR_HOSTS) + "\n"
            "  如确需自定义，请先确认该源可信再手动 pip install（本脚本不代跑）。"
        )
    return url

# 包名 → import 名（不一致的显式写出）
REQUIRED = {
    # 入口包：真正 import 得动才算装好（缺依赖时 find_spec 也会误判为已装）
    "modelscope": "modelscope",         # 魔搭 SDK 主体
    "modelscope_hub": "modelscope_hub", # SDK 1.40+ 拆出的 hub 客户端（skill 上传走这里）
    "requests": "requests",
    # requests / modelscope_hub 的传递依赖（--no-deps 安装时会被一起跳过，必须显式补）
    "idna": "idna",
    "charset-normalizer": "charset_normalizer",
    "certifi": "certifi",
    "urllib3": "urllib3",
    "packaging": "packaging",
    "tqdm": "tqdm",
    "addict": "addict",                 # modelscope hub 内部用到
    "filelock": "filelock",
    "setuptools": "setuptools",
    "cryptography": "cryptography",     # modelscope_hub 的 agent_idp 依赖
}
# 这两个包的元数据会拉 torch 等重依赖，统一 --no-deps
NO_DEPS = {"modelscope", "modelscope_hub"}
# 必须真的能 import；modelscope 主包只用来看版本，不实际调用（发布走 modelscope_hub）
MUST_IMPORT = set(REQUIRED) - {"modelscope"}


def log(msg: str) -> None:
    print(msg, flush=True)


def _importable(mod: str) -> bool:
    """能 import 才算可用——find_spec 在依赖缺失时仍返回 True。"""
    if importlib.util.find_spec(mod) is None:
        return False
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


def missing() -> list[str]:
    out: list[str] = []
    for pkg, mod in REQUIRED.items():
        if importlib.util.find_spec(mod) is None:
            out.append(pkg)
        elif pkg in MUST_IMPORT and not _importable(mod):
            out.append(pkg)
    return out


# 在目标解释器里执行的检测脚本：只依赖标准库，输出缺失包名的 JSON 列表。
_DETECT_SNIPPET = r'''
import importlib.util, json
REQUIRED = {required}
MUST_IMPORT = {must_import}
def _importable(mod):
    if importlib.util.find_spec(mod) is None:
        return False
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False
out = []
for pkg, mod in REQUIRED.items():
    if importlib.util.find_spec(mod) is None:
        out.append(pkg)
    elif pkg in MUST_IMPORT and not _importable(mod):
        out.append(pkg)
print(json.dumps(out))
'''


def missing_in(python: str) -> list[str]:
    """在指定 python 解释器里检测缺失依赖（用于检测 venv 而非当前进程）。"""
    snippet = _DETECT_SNIPPET.format(
        required=json.dumps(REQUIRED, ensure_ascii=False),
        must_import=json.dumps(sorted(MUST_IMPORT), ensure_ascii=False),
    )
    try:
        r = subprocess.run(
            [python, "-c", snippet], capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as e:
        log(f"⚠ 无法在 {python} 里检测依赖：{e}")
        return []
    try:
        return json.loads((r.stdout or "").strip())
    except json.JSONDecodeError:
        log(f"⚠ 在 {python} 里检测依赖失败：{(r.stderr or r.stdout or '').strip()[:200]}")
        return []


def pip_install(pkgs: list[str], mirror: str | None, python: str) -> bool:
    plain = [p for p in pkgs if p not in NO_DEPS]
    heavy = [p for p in pkgs if p in NO_DEPS]
    ok = True
    for group, extra in ((plain, []), (heavy, ["--no-deps"])):
        if not group:
            continue
        cmd = [python, "-m", "pip", "install", "--disable-pip-version-check", *extra, *group]
        if mirror:
            cmd += ["-i", mirror]
        log(f"  → {' '.join(group)} {'(--no-deps)' if extra else ''}")
        r = subprocess.run(cmd)
        ok = ok and r.returncode == 0
    return ok


def _venv_python() -> str:
    """返回 venv 内 python 可执行路径（Windows 在 Scripts/，POSIX 在 bin/）。"""
    if os.name == "nt":
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def _in_venv() -> bool:
    """是否已运行在某个 venv 里（sys.prefix != sys.base_prefix）。"""
    return sys.prefix != sys.base_prefix


def _ensure_venv() -> str:
    """确保 tools/.venv 存在并可用，返回其 python 路径。"""
    py = _venv_python()
    if Path(py).is_file():
        return py
    log(f"首次使用，创建隔离环境：{VENV_DIR}")
    VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if r.returncode != 0:
        raise SystemExit("创建 venv 失败；可加 --no-venv 装到当前解释器（会污染全局环境）")
    if not Path(py).is_file():
        raise SystemExit(f"venv 创建后找不到 {py}；可加 --no-venv 装到当前解释器")
    return py


def main() -> int:
    ap = argparse.ArgumentParser(description="awam-skills 依赖初始化")
    ap.add_argument("--check", action="store_true", help="只检测不安装")
    ap.add_argument("--mirror", help="pip 镜像源（仅 https 且在白名单内，如清华源）")
    ap.add_argument("--no-venv", action="store_true",
                    help="不建隔离环境，装到当前解释器（会污染全局 PYTHONPATH）")
    args = ap.parse_args()

    mirror = validate_mirror(args.mirror) if args.mirror else None

    # 选择安装目标：默认隔离 venv；已处于 venv / 显式 --no-venv 则用当前解释器。
    # --check 不触发创建，只检测当前解释器。
    if args.check:
        target_py = sys.executable
        log(f"检测目标：{target_py}")
        miss = missing()
        if not miss:
            log("✅ 依赖齐备：" + "、".join(REQUIRED))
            return 0
        log(f"缺失：{'、'.join(miss)}")
        log("（--check 模式，未安装）")
        return 1

    if args.no_venv or _in_venv():
        target_py = sys.executable
        log(f"安装目标：当前解释器 {target_py}")
    else:
        target_py = _ensure_venv()
        log(f"安装目标：隔离环境 {target_py}")

    # 检测与安装都针对目标解释器 —— 在目标解释器里跑一次 import 检测，
    # 而非用当前进程（当前进程装的是全局包，检测结果会错）。
    miss = missing_in(target_py)
    if not miss:
        log("✅ 依赖齐备：" + "、".join(REQUIRED))
        return 0

    log(f"缺失：{'、'.join(miss)}")
    log("开始安装（modelscope 用 --no-deps，避免拖入 torch）…")
    if not pip_install(miss, mirror, target_py):
        log("⚠ 安装过程有失败，请检查网络或加 --mirror https://pypi.tuna.tsinghua.edu.cn/simple")
        return 1

    left = missing_in(target_py)
    if left:
        log(f"⚠ 仍有缺失：{'、'.join(left)}")
        return 1
    log("✅ 安装完成：" + "、".join(REQUIRED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
