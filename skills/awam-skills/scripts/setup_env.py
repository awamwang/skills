#!/usr/bin/env python3
"""awam-skills 依赖初始化：按需安装平台发布用到的第三方包。

为什么需要它：魔搭发布走 **modelscope SDK**（cookie 鉴权），需要 `modelscope` 包；
但该包会拖入 torch 等重依赖，而发布只用它的 hub 上传能力，因此安装时统一加 `--no-deps`，
再补上真正需要的轻量依赖（requests / tqdm / urllib3 / addict）。

幂等：已装则跳过。用法：
  python scripts/setup_env.py            # 检测 + 补齐缺失依赖
  python scripts/setup_env.py --check    # 只检测，不安装（退出码 1 表示缺依赖）
  python scripts/setup_env.py --mirror https://pypi.tuna.tsinghua.edu.cn/simple
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys

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


def pip_install(pkgs: list[str], mirror: str | None) -> bool:
    plain = [p for p in pkgs if p not in NO_DEPS]
    heavy = [p for p in pkgs if p in NO_DEPS]
    ok = True
    for group, extra in ((plain, []), (heavy, ["--no-deps"])):
        if not group:
            continue
        cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *extra, *group]
        if mirror:
            cmd += ["-i", mirror]
        log(f"  → {' '.join(group)} {'(--no-deps)' if extra else ''}")
        r = subprocess.run(cmd)
        ok = ok and r.returncode == 0
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="awam-skills 依赖初始化")
    ap.add_argument("--check", action="store_true", help="只检测不安装")
    ap.add_argument("--mirror", help="pip 镜像源（国内网络慢时用，如清华源）")
    args = ap.parse_args()

    log(f"解释器：{sys.executable}")
    miss = missing()
    if not miss:
        log("✅ 依赖齐备：" + "、".join(REQUIRED))
        return 0

    log(f"缺失：{'、'.join(miss)}")
    if args.check:
        log("（--check 模式，未安装）")
        return 1

    log("开始安装（modelscope 用 --no-deps，避免拖入 torch）…")
    if not pip_install(miss, args.mirror):
        log("⚠ 安装过程有失败，请检查网络或加 --mirror https://pypi.tuna.tsinghua.edu.cn/simple")
        return 1

    left = missing()
    if left:
        log(f"⚠ 仍有缺失：{'、'.join(left)}")
        return 1
    log("✅ 安装完成：" + "、".join(REQUIRED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
