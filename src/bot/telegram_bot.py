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
from loguru import logger

from .config import BotConfig
from .handlers import (
    start_command,
    help_command,
    status_command,
    handle_message,
    handle_error
)


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

        # 建立 Application
        self.application = (
            Application.builder()
            .token(config.telegram_bot_token)
            .build()
        )

        # 儲存設定到 bot_data
        self.application.bot_data['config'] = config

        # 註冊處理器
        self._register_handlers()

        logger.info("Telegram Bot 初始化完成")

    def _register_handlers(self):
        """註冊所有訊息處理器"""

        # 指令處理器
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("status", status_command))

        # 訊息處理器（處理所有非指令的文字訊息）
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        # 錯誤處理器
        self.application.add_error_handler(handle_error)

        logger.info("所有處理器註冊完成")

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

    async def _post_shutdown(self, application: Application):
        """
        關閉後回調

        在 Bot 關閉前執行的清理任務。
        """
        logger.info("Bot 正在關閉...")

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
                drop_pending_updates=True  # 忽略啟動前的訊息
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
