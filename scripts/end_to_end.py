#!/usr/bin/env python3
"""
端到端翻譯測試腳本

模擬完整的新聞格式化流程。
"""

from src.crawler.scheduler import CrawlerScheduler
from src.crawler.config import CrawlerConfig

# 載入配置（從 .env）
config = CrawlerConfig.from_env()

# 建立 scheduler（不需要 telegram_app）
scheduler = CrawlerScheduler(config, telegram_app=None)

# 模擬新聞資料
test_news_list = [
    {
        'commodity': 'Gold',
        'news_id': 1,
        'text': 'Gold prices surge amid market volatility and geopolitical tensions in the Middle East.',
        'time': '2026-01-02T10:00:00Z'
    },
    {
        'commodity': 'Bitcoin',
        'news_id': 2,
        'text': 'Bitcoin breaks resistance level at $100,000 as institutional investors show renewed interest.',
        'time': '2026-01-02T10:05:00Z'
    },
    {
        'commodity': 'Copper',
        'news_id': 3,
        'text': 'Copper demand rises in China as manufacturing activity rebounds in December.',
        'time': '2026-01-02T10:10:00Z'
    }
]

print("=" * 80)
print("端到端翻譯測試")
print("=" * 80)
print(f"翻譯啟用: {config.enable_translation}")
print(f"目標語言: {config.translation_target_lang}")
print(f"重試次數: {config.translation_max_retries}")
print("=" * 80)

# 格式化並顯示每則新聞
for news in test_news_list:
    message = scheduler._format_news_message(news)

    print(f"\n新聞 ID: {news['news_id']}")
    print("-" * 80)
    print(message)
    print("-" * 80)

print("\n" + "=" * 80)
print("測試完成")
print("=" * 80)
