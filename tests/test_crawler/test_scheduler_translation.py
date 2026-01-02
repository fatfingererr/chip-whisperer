"""
scheduler.py 翻譯整合測試

測試 _format_news_message() 方法的翻譯功能。
"""

import pytest
from unittest.mock import Mock, patch
from src.crawler.scheduler import CrawlerScheduler
from src.crawler.config import CrawlerConfig


class TestSchedulerTranslation:
    """scheduler.py 翻譯功能整合測試"""

    def create_config(self, enable_translation: bool = True) -> CrawlerConfig:
        """建立測試配置"""
        return CrawlerConfig(
            target_url='https://example.com',
            crawl_interval_minutes=5,
            interval_jitter_seconds=15,
            markets_dir='markets',
            enabled=True,
            telegram_notify_groups=[],
            enable_translation=enable_translation,
            translation_target_lang='zh-TW',
            translation_max_retries=3
        )

    def test_format_message_with_translation_enabled(self):
        """測試啟用翻譯時的訊息格式化"""
        config = self.create_config(enable_translation=True)
        scheduler = CrawlerScheduler(config)

        news = {
            'commodity': 'Gold',
            'news_id': 1,
            'text': 'Gold prices surge amid market volatility',
            'time': '2026-01-02T10:00:00Z'
        }

        message = scheduler._format_news_message(news)

        # 訊息應包含基本元素
        assert 'Gold' in message
        assert 'ID: 1' in message
        assert '2026-01-02T10:00:00Z' in message

        # 應包含翻譯後的文本或原文（降級）
        assert len(message) > 0

    def test_format_message_with_translation_disabled(self):
        """測試停用翻譯時的訊息格式化"""
        config = self.create_config(enable_translation=False)
        scheduler = CrawlerScheduler(config)

        news = {
            'commodity': 'Gold',
            'news_id': 1,
            'text': 'Gold prices surge amid market volatility',
            'time': '2026-01-02T10:00:00Z'
        }

        message = scheduler._format_news_message(news)

        # 訊息應包含英文原文
        assert 'Gold prices surge' in message
        assert 'Gold' in message
        assert 'ID: 1' in message

    def test_format_message_with_long_text(self):
        """測試長文本截斷"""
        config = self.create_config(enable_translation=True)
        scheduler = CrawlerScheduler(config)

        # 建立超過 3000 字元的長文本
        long_text = "Gold prices surge. " * 200  # 約 3800 字元

        news = {
            'commodity': 'Gold',
            'news_id': 1,
            'text': long_text,
            'time': '2026-01-02T10:00:00Z'
        }

        message = scheduler._format_news_message(news)

        # 訊息長度應小於 Telegram 限制
        assert len(message) < 4096

        # 應包含截斷標記
        assert '...' in message

    def test_format_message_with_empty_text(self):
        """測試空文本處理"""
        config = self.create_config(enable_translation=True)
        scheduler = CrawlerScheduler(config)

        news = {
            'commodity': 'Gold',
            'news_id': 1,
            'text': '',
            'time': '2026-01-02T10:00:00Z'
        }

        message = scheduler._format_news_message(news)

        # 訊息應能正常生成
        assert 'Gold' in message
        assert 'ID: 1' in message

    def test_format_message_different_commodities(self):
        """測試不同商品的表情符號"""
        config = self.create_config(enable_translation=False)
        scheduler = CrawlerScheduler(config)

        commodities = {
            'Gold': '🟡',
            'Silver': '🔘',
            'Bitcoin': '₿',
            'Copper': '🔶',
        }

        for commodity, emoji in commodities.items():
            news = {
                'commodity': commodity,
                'news_id': 1,
                'text': f'{commodity} prices surge',
                'time': '2026-01-02T10:00:00Z'
            }

            message = scheduler._format_news_message(news)

            # 應包含對應的表情符號
            assert emoji in message
            assert commodity in message
