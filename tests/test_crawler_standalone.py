# -*- coding: utf-8 -*-
'''
獨立測試爬蟲功能

注意：此腳本會實際訪問網站，請謹慎使用。
根據計畫要求，不執行實際的網頁爬取測試以避免觸發反爬蟲機制。
'''
import asyncio
import sys
import os

# 確保可以導入 src 模組
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.crawler.config import CrawlerConfig
from src.crawler.news_crawler import NewsCrawler
from loguru import logger


async def test_crawl():
    '''測試爬取功能（僅測試結構，不實際執行）'''
    logger.info("=== 爬蟲獨立測試（結構測試） ===")

    # 載入配置
    config = CrawlerConfig.from_env()
    logger.info(f"配置載入完成：{config.target_url}")

    # 創建爬蟲
    crawler = NewsCrawler(config)
    logger.info("爬蟲實例創建完成")

    # 測試 HTML 解析（使用模擬 HTML）
    test_html = '''
    <html>
        <body>
            <div class="stream-item">
                <h3>Gold prices surge amid market volatility</h3>
                <p>Gold reached new highs as investors seek safe haven assets.</p>
                <time datetime="2026-01-02T10:00:00Z">Jan 2, 2026</time>
            </div>
            <div class="stream-item">
                <h3>Bitcoin breaks resistance level</h3>
                <p>Bitcoin surged past $100,000 in early trading.</p>
                <time datetime="2026-01-02T11:00:00Z">Jan 2, 2026</time>
            </div>
        </body>
    </html>
    '''

    logger.info("測試 HTML 解析功能...")
    news_list = crawler.parse_news(test_html)
    logger.info(f"成功解析 {len(news_list)} 則模擬新聞")

    for i, news in enumerate(news_list, 1):
        logger.info(f"新聞 {i}:")
        logger.info(f"  標題: {news['title']}")
        logger.info(f"  內容: {news['content'][:50]}...")
        logger.info(f"  時間: {news['time']}")

    # 測試處理和保存
    logger.info("\n測試新聞處理和保存...")
    saved_news = await crawler.process_and_save(news_list)
    logger.info(f"測試完成，共保存 {len(saved_news)} 則新聞")

    for news in saved_news:
        logger.info(f"  - {news['commodity']} (ID: {news['news_id']}): {news['text'][:50]}...")

    logger.info("\n=== 測試完成 ===")
    logger.info("注意：此測試僅驗證程式碼結構，未執行實際網頁爬取")
    logger.info("實際部署時，爬蟲會自動根據網站 HTML 結構嘗試多個選擇器")


if __name__ == '__main__':
    asyncio.run(test_crawl())
