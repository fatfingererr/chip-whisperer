#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安裝驗證腳本

檢查所有必要的依賴套件是否已正確安裝。
"""

import sys
from pathlib import Path

def check_module(module_name, package_name=None):
    """檢查模組是否可匯入"""
    if package_name is None:
        package_name = module_name

    try:
        __import__(module_name)
        print(f"✓ {package_name:20s} - 已安裝")
        return True
    except ImportError:
        print(f"✗ {package_name:20s} - 未安裝")
        return False

def main():
    print("=" * 60)
    print("Chip Whisperer - 安裝驗證")
    print("=" * 60)
    print()

    # 檢查 Python 版本
    print(f"Python 版本: {sys.version}")
    if sys.version_info < (3, 10):
        print("⚠ 警告：建議使用 Python 3.10 或更高版本")
    print()

    # 檢查必要套件
    print("檢查必要套件：")
    print("-" * 60)

    required_modules = {
        'MetaTrader5': 'MetaTrader5',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'yaml': 'pyyaml',
        'dotenv': 'python-dotenv',
        'loguru': 'loguru',
    }

    all_installed = True
    for module, package in required_modules.items():
        if not check_module(module, package):
            all_installed = False

    print()

    # 檢查開發套件
    print("檢查開發套件（選用）：")
    print("-" * 60)

    dev_modules = {
        'pytest': 'pytest',
        'black': 'black',
        'flake8': 'flake8',
    }

    for module, package in dev_modules.items():
        check_module(module, package)

    print()
    print("=" * 60)

    if all_installed:
        print("✓ 所有必要套件已安裝")
        print()
        print("下一步：")
        print("1. 設定 .env 檔案或 config/mt5_config.yaml")
        print("2. 執行範例程式：python examples/fetch_historical_data.py")
        return 0
    else:
        print("✗ 部分必要套件未安裝")
        print()
        print("請執行以下指令安裝：")
        print("  pip install -r requirements.txt")
        return 1

if __name__ == '__main__':
    sys.exit(main())
