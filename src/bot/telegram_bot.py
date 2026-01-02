"""
Telegram Bot 主程式

此模組定義 Bot 的主要邏輯和啟動流程。
"""

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest
from loguru import logger
from datetime import datetime
import pytz

from .config import BotConfig
from .handlers import (
    start_command,
    help_command,
    status_command,
    handle_message,
    handle_error
)

# 新增：導入爬蟲模組
from src.crawler.config import CrawlerConfig
from src.crawler.scheduler import CrawlerScheduler

# 新增：導入 AgentManager 和 AgentScheduler
from src.agent.agent_manager import AgentManager
from src.agent.agent_scheduler import AgentScheduler


class TelegramBot:
    """
    Telegram Bot 主類別

    管理 Bot 的生命週期和訊息處理。
    """

    def __init__(self, config: BotConfig):
        """
        初始化 Bot

        參數：
            config: Bot 設定
        """
        self.config = config

        # 建立自訂的 HTTPXRequest，設定更長的超時時間（用於發送大圖片）
        request = HTTPXRequest(
            connection_pool_size=8,
            read_timeout=60.0,    # 讀取超時 60 秒
            write_timeout=60.0,   # 寫入超時 60 秒
            connect_timeout=10.0  # 連線超時 10 秒
        )

        # 建立 Application
        self.application = (
            Application.builder()
            .token(config.telegram_bot_token)
            .request(request)
            .build()
        )

        # 儲存設定到 bot_data
        self.application.bot_data['config'] = config

        # 註冊處理器
        self._register_handlers()

        # 新增：初始化 AgentManager
        self.agent_manager = AgentManager(
            api_key=config.anthropic_api_key,
            model=config.claude_model
        )
        self.application.bot_data['agent_manager'] = self.agent_manager

        # 新增：初始化 AgentScheduler
        self.agent_scheduler = AgentScheduler(agent_manager=self.agent_manager)
        self.application.bot_data['agent_scheduler'] = self.agent_scheduler

        # 新增：初始化爬蟲調度器
        crawler_config = CrawlerConfig.from_env()
        self.crawler_scheduler = CrawlerScheduler(
            config=crawler_config,
            telegram_app=self.application
        )

        # 新增：儲存到 bot_data，供指令處理器使用
        self.application.bot_data['crawler_scheduler'] = self.crawler_scheduler

        logger.info("Telegram Bot 初始化完成")

    def _register_handlers(self):
        """註冊所有訊息處理器"""

        # 指令處理器（群組中的指令）
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("status", status_command))

        # 新增：手動爬取指令
        from .handlers import crawl_now_command
        self.application.add_handler(CommandHandler("crawl_now", crawl_now_command))

        # 訊息處理器：接收所有非指令文字訊息（在處理器內部檢查群組）
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                handle_message
            )
        )

        # 錯誤處理器
        self.application.add_error_handler(handle_error)

        logger.info("所有處理器註冊完成（純群組模式）")

    async def _post_init(self, application: Application):
        """
        初始化後回調

        在 Bot 啟動後執行的初始化任務。
        """
        logger.info("Bot 啟動後初始化...")

        # 取得 Bot 資訊
        bot = await application.bot.get_me()
        logger.info(f"Bot 用戶名：@{bot.username}")
        logger.info(f"Bot ID：{bot.id}")

        # 發送開張訊息到所有配置的群組
        await self._send_startup_message(application)

        # 新增：啟動爬蟲定時任務
        self.crawler_scheduler.start()
        logger.info("爬蟲定時任務已整合到 Bot 生命週期")

        # 新增：啟動 Agent 定時任務
        self.agent_scheduler.start()
        logger.info("Agent 定時任務已整合到 Bot 生命週期")

    async def _send_startup_message(self, application: Application):
        """
        發送開張訊息到所有配置的群組

        在 Bot 啟動時向每個允許的群組發送開張通知。
        """
        # 取得台灣時區的當前日期
        taiwan_tz = pytz.timezone('Asia/Taipei')
        now = datetime.now(taiwan_tz)
        date_str = now.strftime('%Y/%m/%d')

        # 開張訊息
        startup_message = f"Chip House 傳出工作聲，辦公室今日有人 ({date_str})。"

        # 向每個配置的群組發送訊息
        for group_id in self.config.telegram_group_ids:
            try:
                await application.bot.send_message(
                    chat_id=group_id,
                    text=startup_message
                )
                logger.info(f"已發送開張訊息到群組 {group_id}")
            except Exception as e:
                logger.error(f"發送開張訊息到群組 {group_id} 失敗：{e}")

    async def _send_shutdown_message(self, application: Application):
        """
        發送關閉訊息到所有配置的群組

        在 Bot 關閉時向每個允許的群組發送關閉通知。
        """
        # 關閉訊息
        shutdown_message = "辦公室人都出門了，Chip House 現在沒有人在。"

        # 向每個配置的群組發送訊息
        for group_id in self.config.telegram_group_ids:
            try:
                await application.bot.send_message(
                    chat_id=group_id,
                    text=shutdown_message
                )
                logger.info(f"已發送關閉訊息到群組 {group_id}")
            except Exception as e:
                logger.error(f"發送關閉訊息到群組 {group_id} 失敗：{e}")

    async def _post_shutdown(self, application: Application):
        """
        關閉後回調

        在 Bot 關閉前執行的清理任務。
        """
        logger.info("Bot 正在關閉...")

        # 發送關閉訊息到所有配置的群組
        await self._send_shutdown_message(application)

        # 新增：停止爬蟲定時任務
        self.crawler_scheduler.stop()
        logger.info("爬蟲定時任務已停止")

        # 新增：停止 Agent 定時任務
        self.agent_scheduler.stop()
        logger.info("Agent 定時任務已停止")

    def run(self):
        """
        啟動 Bot

        使用 polling 模式持續運行。
        """
        logger.info("啟動 Telegram Bot（polling 模式）")

        # 設定回調
        self.application.post_init = self._post_init
        self.application.post_shutdown = self._post_shutdown

        # 啟動 Bot
        try:
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False  # 不忽略待處理的訊息，方便調試
            )
        except KeyboardInterrupt:
            logger.info("收到中斷信號，正在關閉...")
        except Exception as e:
            logger.exception(f"Bot 運行時發生錯誤：{e}")
            raise

    async def run_webhook(self, webhook_url: str, port: int = 8443):
        """
        啟動 Bot（Webhook 模式）

        參數：
            webhook_url: Webhook URL
            port: 監聽端口
        """
        logger.info(f"啟動 Telegram Bot（webhook 模式）")
        logger.info(f"Webhook URL：{webhook_url}")
        logger.info(f"監聽端口：{port}")

        # 設定 webhook
        await self.application.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )

        # 啟動 webhook
        self.application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url
        )


def create_bot(config: BotConfig = None) -> TelegramBot:
    """
    建立 Bot 實例

    參數：
        config: Bot 設定（若未提供則從環境變數載入）

    回傳：
        TelegramBot 實例
    """
    if config is None:
        config = BotConfig.from_env()

    bot = TelegramBot(config)
    return bot
