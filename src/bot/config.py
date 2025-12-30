"""
Bot 設定管理模組

此模組管理 Telegram Bot 的所有設定參數。
"""

import os
from typing import List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from loguru import logger


@dataclass
class BotConfig:
    """
    Telegram Bot 設定類別

    包含所有 Bot 運作所需的設定參數。
    """

    # Telegram 設定
    telegram_bot_token: str
    telegram_admin_ids: List[int]

    # Claude API 設定
    anthropic_api_key: str
    claude_model: str

    # 其他設定
    debug: bool

    @classmethod
    def from_env(cls) -> 'BotConfig':
        """
        從環境變數載入設定

        回傳：
            BotConfig 實例

        例外：
            ValueError: 必要設定未設定時
        """
        # 載入 .env 檔案
        load_dotenv()

        # 讀取 Telegram Bot Token
        telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not telegram_bot_token:
            raise ValueError('未設定 TELEGRAM_BOT_TOKEN 環境變數')

        # 讀取管理員 ID 列表
        admin_ids_str = os.getenv('TELEGRAM_ADMIN_IDS', '')
        telegram_admin_ids = []
        if admin_ids_str:
            try:
                telegram_admin_ids = [
                    int(id_str.strip())
                    for id_str in admin_ids_str.split(',')
                    if id_str.strip()
                ]
            except ValueError as e:
                logger.warning(f'解析 TELEGRAM_ADMIN_IDS 失敗：{e}')

        # 讀取 Anthropic API Key
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            raise ValueError('未設定 ANTHROPIC_API_KEY 環境變數')

        # 讀取 Claude 模型
        claude_model = os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')

        # 讀取除錯模式
        debug = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')

        config = cls(
            telegram_bot_token=telegram_bot_token,
            telegram_admin_ids=telegram_admin_ids,
            anthropic_api_key=anthropic_api_key,
            claude_model=claude_model,
            debug=debug
        )

        logger.info(f'Bot 設定載入完成（除錯模式：{debug}）')
        if telegram_admin_ids:
            logger.info(f'管理員 ID：{telegram_admin_ids}')

        return config

    def is_admin(self, user_id: int) -> bool:
        """
        檢查用戶是否為管理員

        參數：
            user_id: Telegram 用戶 ID

        回傳：
            是否為管理員
        """
        # 如果未設定管理員，則所有人都是管理員
        if not self.telegram_admin_ids:
            return True

        return user_id in self.telegram_admin_ids
