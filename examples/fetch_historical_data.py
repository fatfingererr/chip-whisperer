#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基本 K 線資料取得範例

此範例展示如何使用 Chip Whisperer 從 MT5 取得歷史 K 線資料。

使用方式：
    python examples/fetch_historical_data.py

注意事項：
    1. 執行前請先設定 .env 檔案（複製 .env.example 並填入您的 MT5 帳號資訊）
    2. 確保 MT5 終端機已安裝並可正常連線
    3. 確保有足夠的歷史資料權限
"""

import sys
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from loguru import logger
from core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher


def setup_logger():
    """設定日誌系統"""
    # 移除預設的 handler
    logger.remove()

    # 加入控制台輸出（彩色）
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # 加入檔案輸出
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / 'fetch_historical_data.log',
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days"
    )


def main():
    """主函式"""
    setup_logger()

    logger.info("=" * 60)
    logger.info("Chip Whisperer - 基本 K 線資料取得範例")
    logger.info("=" * 60)

    try:
        # 1. 載入設定
        logger.info("步驟 1：載入 MT5 設定")
        config = MT5Config()
        logger.info(f"設定載入完成：{config}")

        # 2. 使用 context manager 建立連線（自動管理連線生命週期）
        logger.info("步驟 2：連線到 MT5")
        with ChipWhispererMT5Client(config) as client:
            logger.info(f"客戶端狀態：{client}")

            # 3. 建立資料取得器
            logger.info("步驟 3：建立歷史資料取得器")
            fetcher = HistoricalDataFetcher(client)

            # 4. 範例 1：取得最新 100 根 H1 K 線
            logger.info("\n" + "=" * 60)
            logger.info("範例 1：取得 GOLD 最新 100 根 H1 K 線")
            logger.info("=" * 60)

            df_latest = fetcher.get_candles_latest(
                symbol='GOLD',
                timeframe='H1',
                count=100
            )

            logger.info(f"取得資料筆數：{len(df_latest)}")
            logger.info(f"資料欄位：{df_latest.columns.tolist()}")
            logger.info(f"\n最新 5 根 K 線：\n{df_latest.head()}")

            # 儲存到快取
            cache_file = fetcher.save_to_cache(df_latest, 'GOLD', 'H1', 'csv')
            logger.info(f"資料已儲存到：{cache_file}")

            # 5. 範例 2：取得指定日期範圍的資料
            logger.info("\n" + "=" * 60)
            logger.info("範例 2：取得 SILVER 指定日期範圍的 D1 K 線")
            logger.info("=" * 60)

            df_range = fetcher.get_candles_by_date(
                symbol='SILVER',
                timeframe='D1',
                from_date='2024-01-01',
                to_date='2024-12-31'
            )

            logger.info(f"取得資料筆數：{len(df_range)}")
            logger.info(f"日期範圍：{df_range['time'].min()} ~ {df_range['time'].max()}")
            logger.info(f"\n最新 5 根 K 線：\n{df_range.head()}")

            # 儲存到快取
            cache_file = fetcher.save_to_cache(df_range, 'SILVER', 'D1', 'csv')
            logger.info(f"資料已儲存到：{cache_file}")

            # 6. 範例 3：取得從指定日期開始的資料
            logger.info("\n" + "=" * 60)
            logger.info("範例 3：取得 BITCOIN 從 2024-12-01 開始的 H4 K 線")
            logger.info("=" * 60)

            df_from = fetcher.get_candles_by_date(
                symbol='BITCOIN',
                timeframe='H4',
                from_date='2024-12-01',
                default_count=200
            )

            logger.info(f"取得資料筆數：{len(df_from)}")
            logger.info(f"日期範圍：{df_from['time'].min()} ~ {df_from['time'].max()}")
            logger.info(f"\n最新 5 根 K 線：\n{df_from.head()}")

            # 7. 顯示資料統計
            logger.info("\n" + "=" * 60)
            logger.info("資料統計資訊")
            logger.info("=" * 60)

            logger.info(f"\nGOLD H1 統計：")
            logger.info(f"  最高價：{df_latest['high'].max():.2f}")
            logger.info(f"  最低價：{df_latest['low'].min():.2f}")
            logger.info(f"  平均收盤價：{df_latest['close'].mean():.2f}")
            logger.info(f"  總成交量：{df_latest['real_volume'].sum():.0f}")

        logger.info("\n" + "=" * 60)
        logger.info("範例執行完成")
        logger.info("=" * 60)

    except ValueError as e:
        logger.error(f"設定錯誤：{e}")
        logger.error("請檢查 .env 檔案或 config/mt5_config.yaml 是否正確設定")
        sys.exit(1)

    except RuntimeError as e:
        logger.error(f"執行錯誤：{e}")
        logger.error("請確保 MT5 終端機正常運作，且帳號密碼正確")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("使用者中斷執行")
        sys.exit(0)

    except Exception as e:
        logger.exception(f"未預期的錯誤：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
