#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MT5 Telegram Bot 啟動腳本

此腳本用於啟動 MT5 交易助手 Telegram Bot。

使用方式：
    python scripts/run_bot.py

環境變數：
    - TELEGRAM_BOT_TOKEN: Telegram Bot Token（必要）
    - ANTHROPIC_API_KEY: Anthropic API Key（必要）
    - TELEGRAM_ADMIN_IDS: 管理員用戶 ID，用逗號分隔（可選）
    - CLAUDE_MODEL: Claude 模型名稱（可選）
    - DEBUG: 除錯模式（可選）
"""

import sys
from pathlib import Path

# 確保可以匯入 src 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.bot.config import BotConfig
from src.bot.telegram_bot import create_bot


def setup_logging(debug: bool = False):
    """
    設定日誌系統

    參數：
        debug: 是否啟用除錯模式
    """
    # 移除預設處理器
    logger.remove()

    # 設定日誌級別
    log_level = "DEBUG" if debug else "INFO"

    # 新增控制台輸出
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level=log_level,
        colorize=True
    )

    # 新增檔案輸出
    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # 每天午夜輪換
        retention="30 days",  # 保留 30 天
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8"
    )

    logger.info(f"日誌系統初始化完成（級別：{log_level}）")


def main():
    """主函式"""
    try:
        # 載入設定
        logger.info("載入 Bot 設定...")
        config = BotConfig.from_env()

        # 設定日誌
        setup_logging(debug=config.debug)

        # 顯示啟動資訊
        logger.info("=" * 60)
        logger.info("MT5 Telegram Bot 啟動中...")
        logger.info("=" * 60)
        logger.info(f"Claude 模型：{config.claude_model}")
        logger.info(f"除錯模式：{'開啟' if config.debug else '關閉'}")
        if config.telegram_admin_ids:
            logger.info(f"管理員數量：{len(config.telegram_admin_ids)}")
        else:
            logger.warning("未設定管理員 ID，所有用戶都可使用")
        logger.info("=" * 60)

        # 建立並啟動 Bot
        bot = create_bot(config)
        logger.info("Bot 建立成功，準備啟動...")

        # 啟動 Bot（polling 模式）
        bot.run()

    except ValueError as e:
        logger.error(f"設定錯誤：{e}")
        logger.error("請檢查 .env 檔案中的設定")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("收到中斷信號")
        logger.info("Bot 已停止")
        sys.exit(0)

    except Exception as e:
        logger.exception(f"發生未預期的錯誤：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
