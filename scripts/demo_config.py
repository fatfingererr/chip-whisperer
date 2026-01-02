#!/usr/bin/env python3
"""
配置載入測試腳本

測試翻譯配置是否正確從環境變數載入。
"""

import os
from dotenv import load_dotenv
from src.crawler.config import CrawlerConfig

# 載入 .env
load_dotenv()

# 載入配置
config = CrawlerConfig.from_env()

print("=" * 70)
print("爬蟲配置載入結果")
print("=" * 70)

# 顯示原有配置
print("\n【原有配置】")
print(f"目標 URL: {config.target_url}")
print(f"爬取間隔: {config.crawl_interval_minutes} 分鐘")
print(f"爬蟲啟用: {config.enabled}")
print(f"通知群組: {config.telegram_notify_groups}")

# 顯示翻譯配置
print("\n【翻譯配置】")
print(f"啟用翻譯: {config.enable_translation}")
print(f"目標語言: {config.translation_target_lang}")
print(f"重試次數: {config.translation_max_retries}")

# 驗證預設值
print("\n【驗證結果】")
errors = []

if not isinstance(config.enable_translation, bool):
    errors.append("enable_translation 應為 bool 類型")

if config.translation_target_lang not in ['zh-TW', 'zh-CN', 'ja', 'ko', 'en']:
    errors.append(f"translation_target_lang 值異常: {config.translation_target_lang}")

if not isinstance(config.translation_max_retries, int) or config.translation_max_retries < 0:
    errors.append("translation_max_retries 應為非負整數")

if errors:
    print("配置驗證失敗：")
    for error in errors:
        print(f"   - {error}")
else:
    print("配置載入成功，所有欄位類型正確")

print("\n" + "=" * 70)
