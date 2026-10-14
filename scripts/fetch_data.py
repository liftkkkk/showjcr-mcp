#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 hitfyd/ShowJCR 项目下载期刊数据 CSV 到本仓库 ./data 目录。

用法：
    python scripts/fetch_data.py

数据版权归原始机构所有（中科院分区表：中科院文献情报中心；CCF 目录：中国计算机学会；
JCR：Clarivate）。本脚本仅从开源项目 hitfyd/ShowJCR 转存，请遵循原项目的使用条款。
"""

import os
import sys
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")

# hitfyd/ShowJCR 仓库中的数据文件（含中文路径，URL 需转义）
BASE = "https://raw.githubusercontent.com/hitfyd/ShowJCR/master/%E4%B8%AD%E7%A7%91%E9%99%A2%E5%88%86%E5%8C%BA%E8%A1%A8%E5%8F%8AJCR%E5%8E%9F%E5%A7%8B%E6%95%B0%E6%8D%AE%E6%96%87%E4%BB%B6"

FILES = [
    "FQBJCR2021-UTF8.csv", "FQBJCR2022-UTF8.csv", "FQBJCR2023-UTF8.csv", "FQBJCR2025-UTF8.csv",
    "JCR2020-UTF8.csv", "JCR2021-UTF8.csv", "JCR2022-UTF8.csv", "JCR2023-UTF8.csv",
    "JCR2024-UTF8.csv", "JCR2025-UTF8.csv",
    "XR2026-UTF8.csv", "XR2026Conferences-UTF8.csv",
    "CCF2026-UTF8.csv", "CCFT2022-UTF8.csv", "CCFT2025-UTF8.csv",
    "GJQKYJMD2020.csv", "GJQKYJMD2021.csv", "GJQKYJMD2023.csv", "GJQKYJMD2024.csv", "GJQKYJMD2025.csv",
]


def main() -> int:
    os.makedirs(DATA_DIR, exist_ok=True)
    failed = []
    for fn in FILES:
        dest = os.path.join(DATA_DIR, fn)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print(f"[skip] {fn} 已存在")
            continue
        url = f"{BASE}/{urllib.request.quote(fn)}"
        try:
            print(f"[down] {fn} ...", end=" ", flush=True)
            urllib.request.urlretrieve(url, dest)
            size = os.path.getsize(dest)
            print(f"{size / 1024:.0f} KB")
        except Exception as e:
            failed.append(fn)
            print(f"失败: {e}")
    if failed:
        print(f"\n{len(failed)} 个文件下载失败: {', '.join(failed)}")
        print("可手动从 https://github.com/hitfyd/ShowJCR 下载后放入 data/ 目录。")
        return 1
    print(f"\n全部完成，共 {len(FILES)} 个文件，位于 {DATA_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
