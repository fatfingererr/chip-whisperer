#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模組匯入測試腳本

此腳本用於測試所有模組是否可以正確匯入。
"""

import sys
from pathlib import Path

# 確保可以匯入 src 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("模組匯入測試")
print("=" * 60)

# 測試核心模組
try:
    print("\n[1/3] 測試 Core 模組...")
    from src.core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher
    print("✓ Core 模組匯入成功")
except Exception as e:
    print(f"✗ Core 模組匯入失敗：{e}")

# 測試 Agent 模組
try:
    print("\n[2/3] 測試 Agent 模組...")
    from src.agent.indicators import calculate_volume_profile, calculate_sma, calculate_rsi
    print("✓ Agent indicators 模組匯入成功")

    from src.agent.tools import TOOLS, execute_tool
    print("✓ Agent tools 模組匯入成功")

    from src.agent.agent import MT5Agent
    print("✓ Agent agent 模組匯入成功")
except Exception as e:
    print(f"✗ Agent 模組匯入失敗：{e}")

# 測試 Bot 模組
try:
    print("\n[3/3] 測試 Bot 模組...")
    from src.bot.config import BotConfig
    print("✓ Bot config 模組匯入成功")

    from src.bot.telegram_bot import TelegramBot, create_bot
    print("✓ Bot telegram_bot 模組匯入成功")
except Exception as e:
    print(f"✗ Bot 模組匯入失敗：{e}")

print("\n" + "=" * 60)
print("所有模組匯入測試完成")
print("=" * 60)
