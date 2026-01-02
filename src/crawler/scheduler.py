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
from .translator import get_translator


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
        text = news['text']  # 英文原文
        time = news.get('time', 'N/A')

        # ========== 新增：根據配置決定是否翻譯 ==========
        if self.config.enable_translation:
            try:
                # 取得翻譯器實例
                translator = get_translator(
                    target_lang=self.config.translation_target_lang,
                    max_retries=self.config.translation_max_retries
                )

                # 翻譯新聞文本（失敗時自動降級回原文）
                translated_text = translator.translate(text, fallback_to_original=True)

                logger.debug(
                    f"新聞翻譯成功：{commodity} (ID: {news_id}), "
                    f"{len(text)} 字元 -> {len(translated_text)} 字元"
                )

            except Exception as e:
                # 翻譯失敗，降級回原文
                logger.error(f"翻譯失敗（{commodity}, ID: {news_id}），使用原文：{e}")
                translated_text = text
        else:
            # 未啟用翻譯，直接使用原文
            translated_text = text
            logger.debug(f"翻譯已停用，使用原文：{commodity} (ID: {news_id})")
        # ================================================

        # 限制文本長度（Telegram 單則訊息最多 4096 字元）
        max_length = 3000
        if len(translated_text) > max_length:
            translated_text = translated_text[:max_length] + "..."

        message = (
            f"**最新消息**\n"
            f"{translated_text}\n\n"  # 使用翻譯後的文本
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
