"""
Bot 設定管理模組

此模組定義 Bot 的設定資料結構和載入邏輯。
"""

from dataclasses import dataclass
from typing import List
import os
from loguru import logger
from dotenv import load_dotenv


@dataclass
class BotConfig:
    """
    Bot 設定資料類別

    屬性：
        telegram_bot_token: Telegram Bot Token
        telegram_group_ids: 允許的群組 ID 清單（必要）
        anthropic_api_key: Anthropic API Key
        claude_model: Claude 模型名稱
        debug: 是否啟用除錯模式
    """

    # Telegram 設定
    telegram_bot_token: str
    telegram_group_ids: List[int]  # 允許的群組 ID 清單

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
            ValueError: 必要設定缺失時
        """
        # 載入 .env 檔案
        load_dotenv()

        # 讀取必要設定
        telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not telegram_bot_token:
            raise ValueError('未設定 TELEGRAM_BOT_TOKEN 環境變數')

        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            raise ValueError('未設定 ANTHROPIC_API_KEY 環境變數')

        # 讀取群組 ID（必要）
        group_ids_str = os.getenv('TELEGRAM_GROUP_IDS', '')
        if not group_ids_str:
            raise ValueError(
                '未設定 TELEGRAM_GROUP_IDS 環境變數。'
                'Bot 只能在指定群組中運作，請設定至少一個群組 ID。'
            )

        telegram_group_ids = []
        try:
            telegram_group_ids = [
                int(id_str.strip())
                for id_str in group_ids_str.split(',')
                if id_str.strip()
            ]
        except ValueError as e:
            raise ValueError(f'解析 TELEGRAM_GROUP_IDS 失敗：{e}')

        if not telegram_group_ids:
            raise ValueError('TELEGRAM_GROUP_IDS 必須包含至少一個有效的群組 ID')

        logger.info(f'已載入 {len(telegram_group_ids)} 個允許的群組 ID')

        # 讀取其他設定
        claude_model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
        debug = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')

        return cls(
            telegram_bot_token=telegram_bot_token,
            telegram_group_ids=telegram_group_ids,
            anthropic_api_key=anthropic_api_key,
            claude_model=claude_model,
            debug=debug
        )

    def is_allowed_group(self, chat_id: int) -> bool:
        """
        檢查群組是否在允許清單中

        參數：
            chat_id: Telegram Chat ID（群組 ID）

        回傳：
            是否為允許的群組
        """
        return chat_id in self.telegram_group_ids
