"""
爬蟲配置模組

管理爬蟲相關的配置參數。
"""

from dataclasses import dataclass
from typing import List
import os
from dotenv import load_dotenv


@dataclass
class CrawlerConfig:
    """
    爬蟲配置資料類別

    屬性:
        target_url: 目標網站 URL
        crawl_interval_minutes: 爬取間隔（分鐘）
        interval_jitter_seconds: 間隔隨機化範圍（秒）
        markets_dir: markets 目錄路徑
        enabled: 是否啟用爬蟲
        telegram_notify_groups: 要通知的 Telegram 群組 ID 列表
    """

    target_url: str
    crawl_interval_minutes: int
    interval_jitter_seconds: int
    markets_dir: str
    enabled: bool
    telegram_notify_groups: List[int]

    @classmethod
    def from_env(cls) -> 'CrawlerConfig':
        """
        從環境變數載入配置

        回傳:
            CrawlerConfig 實例
        """
        load_dotenv()

        return cls(
            target_url=os.getenv(
                'CRAWLER_TARGET_URL',
                'https://tradingeconomics.com/stream?c=commodity'
            ),
            crawl_interval_minutes=int(os.getenv('CRAWLER_INTERVAL_MINUTES', '5')),
            interval_jitter_seconds=int(os.getenv('CRAWLER_JITTER_SECONDS', '15')),
            markets_dir=os.getenv('MARKETS_DIR', 'markets'),
            enabled=os.getenv('CRAWLER_ENABLED', 'true').lower() in ('true', '1', 'yes'),
            telegram_notify_groups=[
                int(gid.strip())
                for gid in os.getenv('CRAWLER_NOTIFY_GROUPS', '').split(',')
                if gid.strip()
            ]
        )
