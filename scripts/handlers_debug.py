"""
調試處理器註冊情況
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot.telegram_bot import TelegramBot
from src.bot.config import BotConfig

# 載入配置
config = BotConfig.from_env()

# 建立 Bot
bot = TelegramBot(config)

# 檢查註冊的處理器
print("=" * 80)
print("已註冊的處理器列表：")
print("=" * 80)

for i, handler in enumerate(bot.application.handlers[0], 1):  # handlers[0] 是 default group
    handler_type = type(handler).__name__
    print(f"{i}. {handler_type}")

    # 如果是 MessageHandler，顯示過濾器
    if handler_type == "MessageHandler":
        print(f"   過濾器: {handler.filters}")
        print(f"   回調函數: {handler.callback.__name__}")

print("=" * 80)
print(f"總共註冊了 {len(bot.application.handlers[0])} 個處理器")
print("=" * 80)
