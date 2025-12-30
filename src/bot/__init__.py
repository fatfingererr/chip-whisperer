"""
Telegram Bot 層模組

此模組提供 Telegram Bot 整合功能，包含設定管理、訊息處理器和 Bot 主程式。
"""

from .config import BotConfig
from .telegram_bot import TelegramBot

__all__ = [
    'BotConfig',
    'TelegramBot',
]

__version__ = '0.1.0'
