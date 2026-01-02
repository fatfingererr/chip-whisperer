"""
爬蟲定時任務管理模組

負責啟動和管理新聞爬蟲的定時任務。
"""

from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from telegram.ext import Application

from .config import CrawlerConfig
from .news_crawler import NewsCrawler


class CrawlerScheduler:
    """
    爬蟲定時任務管理器

    使用 APScheduler 管理爬蟲的定時執行。
    """

    def __init__(
        self,
        config: CrawlerConfig,
        telegram_app: Optional[Application] = None
    ):
        """
        初始化調度器

        參數:
            config: 爬蟲配置
            telegram_app: Telegram Application 實例（用於發送通知）
        """
        self.config = config
        self.telegram_app = telegram_app
        self.crawler = NewsCrawler(config)
        self.scheduler = AsyncIOScheduler()

        logger.info("爬蟲調度器初始化完成")

    async def _crawl_and_notify(self):
        """
        爬取新聞並發送 Telegram 通知
        """
        try:
            # 執行爬取
            saved_news = await self.crawler.crawl()

            # 發送 Telegram 通知
            if saved_news and self.telegram_app and self.config.telegram_notify_groups:
                await self._send_telegram_notifications(saved_news)

        except Exception as e:
            logger.exception(f"爬蟲執行失敗：{e}")

    async def _send_telegram_notifications(self, saved_news: list):
        """
        發送 Telegram 通知

        參數:
            saved_news: 已保存的新聞列表
        """
        for news in saved_news:
            # 格式化訊息
            message = self._format_news_message(news)

            # 發送到所有配置的群組
            for group_id in self.config.telegram_notify_groups:
                try:
                    await self.telegram_app.bot.send_message(
                        chat_id=group_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    logger.info(f"已發送通知到群組 {group_id}")

                except Exception as e:
                    logger.error(f"發送通知到群組 {group_id} 失敗：{e}")

    def _format_news_message(self, news: dict) -> str:
        """
        格式化新聞訊息

        參數:
            news: 新聞資料

        回傳:
            格式化後的 Markdown 訊息
        """
        commodity = news['commodity']
        news_id = news['news_id']
        text = news['text']
        time = news.get('time', 'N/A')

        # 限制文本長度（Telegram 單則訊息最多 4096 字元）
        max_length = 3000
        if len(text) > max_length:
            text = text[:max_length] + "..."

        # 根據商品類型選擇表情符號
        emoji_map = {
            'Gold': '🥇',
            'Silver': '🥈',
            'Bitcoin': '₿',
            'Ethereum': '⟠',
            'Brent': '🛢️',
            'Wti': '🛢️',
            'Copper': '🔶',
            'Corn': '🌽',
            'Coffee': '☕',
            'Wheat': '🌾',
        }
        emoji = emoji_map.get(commodity, '📊')

        message = (
            f"{emoji} **{commodity} 商品新聞** (ID: {news_id})\n"
            f"{'─' * 40}\n\n"
            f"{text}\n\n"
            f"{'─' * 40}\n"
            f"⏰ {time}"
        )

        return message

    def start(self):
        """
        啟動定時任務
        """
        if not self.config.enabled:
            logger.info("爬蟲已停用（CRAWLER_ENABLED=false），不啟動定時任務")
            return

        # 計算 jitter（隨機化範圍）
        jitter = self.config.interval_jitter_seconds

        # 新增任務
        self.scheduler.add_job(
            self._crawl_and_notify,
            trigger=IntervalTrigger(
                minutes=self.config.crawl_interval_minutes,
                jitter=jitter
            ),
            id='news_crawler',
            name='商品新聞爬蟲',
            replace_existing=True
        )

        # 啟動調度器
        self.scheduler.start()

        logger.info(
            f"爬蟲定時任務已啟動：每 {self.config.crawl_interval_minutes} 分鐘 "
            f"(±{jitter} 秒) 執行一次"
        )

    def stop(self):
        """
        停止定時任務
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("爬蟲定時任務已停止")
