#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試 Selenium 爬蟲

執行方式：
    python tests/test_crawler_selenium.py
"""

import sys
import asyncio
from pathlib import Path

# 確保可以匯入 src 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.crawler.config import CrawlerConfig
from src.crawler.news_crawler import NewsCrawler


async def test_selenium_crawler():
    """測試 Selenium 爬蟲"""

    logger.info("=" * 60)
    logger.info("測試 Selenium 爬蟲")
    logger.info("=" * 60)

    # 建立配置
    config = CrawlerConfig(
        target_url='https://tradingeconomics.com/stream?c=commodity',
        crawl_interval_minutes=5,
        interval_jitter_seconds=15,
        markets_dir='markets',
        enabled=True,
        telegram_notify_groups=[]
    )

    # 建立爬蟲
    crawler = NewsCrawler(config)

    # 執行爬取
    logger.info("開始爬取...")
    saved_news = await crawler.crawl()

    logger.info("=" * 60)
    logger.info(f"爬取完成！共保存 {len(saved_news)} 則新聞")
    logger.info("=" * 60)

    # 顯示結果
    for news in saved_news:
        logger.info(f"商品：{news['commodity']}, ID: {news['news_id']}")
        logger.info(f"內容：{news['text'][:100]}...")
        logger.info("-" * 60)

    if not saved_news:
        logger.warning("未保存任何新聞！")
        logger.warning("請檢查 debug_page.html 檔案（如果有生成）")
        logger.warning("並使用瀏覽器的開發者工具（F12）找出正確的 CSS 選擇器")


if __name__ == "__main__":
    asyncio.run(test_selenium_crawler())
