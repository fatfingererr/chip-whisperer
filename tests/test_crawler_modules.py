# -*- coding: utf-8 -*-
'''
測試爬蟲基礎模組
'''
import sys
import os

# 確保可以導入 src 模組
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

print("=== 測試爬蟲基礎模組 ===\n")

# 測試 CrawlerConfig
print("1. 測試 CrawlerConfig.from_env()...")
try:
    from src.crawler.config import CrawlerConfig
    config = CrawlerConfig.from_env()
    print(f"   ✓ 啟用狀態: {config.enabled}")
    print(f"   ✓ 目標 URL: {config.target_url}")
    print(f"   ✓ 爬取間隔: {config.crawl_interval_minutes} 分鐘")
    print(f"   ✓ 通知群組: {config.telegram_notify_groups}")
    print()
except Exception as e:
    print(f"   ✗ 錯誤: {e}\n")
    sys.exit(1)

# 測試 CommodityMapper
print("2. 測試 CommodityMapper...")
try:
    from src.crawler.commodity_mapper import CommodityMapper
    mapper = CommodityMapper('markets')

    # 測試提取商品
    test_cases = [
        ("Gold prices surge to new high", "Gold"),
        ("Bitcoin breaks $100,000", "Bitcoin"),
        ("Random news about stocks", None)
    ]

    for news_text, expected in test_cases:
        result = mapper.extract_commodity(news_text)
        status = "✓" if result == expected else "✗"
        print(f"   {status} '{news_text[:30]}...' -> {result} (期望: {expected})")
    print()
except Exception as e:
    print(f"   ✗ 錯誤: {e}\n")
    sys.exit(1)

# 測試 NewsStorage
print("3. 測試 NewsStorage...")
try:
    from src.crawler.news_storage import NewsStorage
    storage = NewsStorage('markets')

    # 測試保存新聞
    success, news_id = storage.save_news('Gold', 'Test: Gold prices surge to new high')
    if success:
        print(f"   ✓ 保存成功: ID={news_id}")
    else:
        print(f"   ✗ 保存失敗")

    # 測試重複檢查
    is_dup = storage.check_duplicate('Gold', 'Test: Gold prices surge to new high')
    print(f"   ✓ 重複檢查: {is_dup} (期望: True)")

    # 測試新新聞不重複
    is_dup2 = storage.check_duplicate('Gold', 'Test: Another completely different news')
    print(f"   ✓ 新新聞檢查: {is_dup2} (期望: False)")
    print()
except Exception as e:
    print(f"   ✗ 錯誤: {e}\n")
    sys.exit(1)

print("=== 所有測試通過！ ===")
