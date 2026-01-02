#!/usr/bin/env python3
"""
歷史數據批次回填腳本

此腳本會對指定的商品不斷往回抓取指定週期的數據，直到沒有更多數據為止，
並將所有數據保存到 SQLite 資料庫中。

使用方式：
    python scripts/backfill_data.py GOLD
    python scripts/backfill_data.py GOLD --timeframe M5
    python scripts/backfill_data.py GOLD --timeframe H1 --batch-size 5000
    python scripts/backfill_data.py GOLD --db-path data/my_cache.db
"""

import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger

from src.core.mt5_config import MT5Config
from src.core.mt5_client import ChipWhispererMT5Client
from src.core.sqlite_cache import SQLiteCacheManager


# MT5 時間週期對應表
TIMEFRAME_MAP = {
    'M1': mt5.TIMEFRAME_M1,      # 1 分鐘
    'M2': mt5.TIMEFRAME_M2,      # 2 分鐘
    'M3': mt5.TIMEFRAME_M3,      # 3 分鐘
    'M4': mt5.TIMEFRAME_M4,      # 4 分鐘
    'M5': mt5.TIMEFRAME_M5,      # 5 分鐘
    'M6': mt5.TIMEFRAME_M6,      # 6 分鐘
    'M10': mt5.TIMEFRAME_M10,    # 10 分鐘
    'M12': mt5.TIMEFRAME_M12,    # 12 分鐘
    'M15': mt5.TIMEFRAME_M15,    # 15 分鐘
    'M20': mt5.TIMEFRAME_M20,    # 20 分鐘
    'M30': mt5.TIMEFRAME_M30,    # 30 分鐘
    'H1': mt5.TIMEFRAME_H1,      # 1 小時
    'H2': mt5.TIMEFRAME_H2,      # 2 小時
    'H3': mt5.TIMEFRAME_H3,      # 3 小時
    'H4': mt5.TIMEFRAME_H4,      # 4 小時
    'H6': mt5.TIMEFRAME_H6,      # 6 小時
    'H8': mt5.TIMEFRAME_H8,      # 8 小時
    'H12': mt5.TIMEFRAME_H12,    # 12 小時
    'D1': mt5.TIMEFRAME_D1,      # 日線
    'W1': mt5.TIMEFRAME_W1,      # 週線
    'MN1': mt5.TIMEFRAME_MN1,    # 月線
}

# 時間週期對應的分鐘數（用於計算時間偏移）
TIMEFRAME_MINUTES = {
    'M1': 1,
    'M2': 2,
    'M3': 3,
    'M4': 4,
    'M5': 5,
    'M6': 6,
    'M10': 10,
    'M12': 12,
    'M15': 15,
    'M20': 20,
    'M30': 30,
    'H1': 60,
    'H2': 120,
    'H3': 180,
    'H4': 240,
    'H6': 360,
    'H8': 480,
    'H12': 720,
    'D1': 1440,
    'W1': 10080,
    'MN1': 43200,
}


def backfill_data(
    symbol: str,
    timeframe: str = "M1",
    db_path: str = "data/candles.db",
    batch_size: int = 10000,
    max_retries: int = 3
) -> dict:
    """
    批次回填歷史數據

    參數：
        symbol: 商品代碼（例如 'GOLD', 'EURUSD'）
        timeframe: 時間週期（例如 'M1', 'M5', 'H1', 'D1'）
        db_path: SQLite 資料庫路徑
        batch_size: 每次請求的 K 線數量
        max_retries: 失敗時的最大重試次數

    回傳：
        包含統計資訊的字典
    """
    # 驗證時間週期
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAME_MAP:
        raise ValueError(f"無效的時間週期：{timeframe}，支援的週期：{', '.join(TIMEFRAME_MAP.keys())}")

    tf_constant = TIMEFRAME_MAP[timeframe]
    tf_minutes = TIMEFRAME_MINUTES[timeframe]

    # 統計資訊
    stats = {
        'symbol': symbol,
        'timeframe': timeframe,
        'total_records': 0,
        'batches_fetched': 0,
        'oldest_time': None,
        'newest_time': None,
        'start_time': datetime.now(),
        'end_time': None,
        'status': 'running'
    }

    logger.info(f"=" * 60)
    logger.info(f"開始回填 {symbol} {timeframe} 歷史數據")
    logger.info(f"批次大小：{batch_size}，資料庫：{db_path}")
    logger.info(f"=" * 60)

    # 初始化 MT5 連線
    config = MT5Config()
    client = ChipWhispererMT5Client(config)

    try:
        client.connect()
        logger.info("MT5 連線成功")

        # 驗證商品
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise ValueError(f"商品不存在：{symbol}")

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                raise ValueError(f"無法啟用商品：{symbol}")
            logger.info(f"已啟用商品：{symbol}")

        # 初始化 SQLite 快取
        cache = SQLiteCacheManager(db_path)
        logger.info(f"SQLite 快取已初始化：{db_path}")

        # 檢查現有數據的最早時間
        existing_oldest = cache.get_oldest_time(symbol, timeframe)
        if existing_oldest:
            logger.info(f"資料庫中已有數據，最早時間：{existing_oldest}")
            # 從現有最早時間往前抓
            current_end_time = existing_oldest
        else:
            logger.info("資料庫中無現有數據，從現在開始往回抓")
            current_end_time = datetime.now(timezone.utc)

        # 開始批次抓取
        consecutive_empty = 0
        max_consecutive_empty = 3  # 連續空結果次數上限

        while consecutive_empty < max_consecutive_empty:
            retry_count = 0

            while retry_count < max_retries:
                try:
                    # 從指定時間往前抓取
                    logger.info(f"抓取批次 {stats['batches_fetched'] + 1}：{current_end_time} 往前 {batch_size} 根")

                    rates = mt5.copy_rates_from(
                        symbol,
                        tf_constant,
                        current_end_time,
                        batch_size
                    )

                    if rates is None or len(rates) == 0:
                        error = mt5.last_error()
                        if error[0] == 1:  # 無更多數據
                            logger.info(f"已無更多歷史數據（MT5 回傳空結果）")
                            consecutive_empty += 1
                            # 往前推一段時間再試
                            current_end_time = current_end_time - timedelta(days=30)
                            break
                        else:
                            raise RuntimeError(f"MT5 錯誤：{error}")

                    # 轉換為 DataFrame
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

                    # 取得這批數據的時間範圍
                    batch_oldest = df['time'].min()
                    batch_newest = df['time'].max()

                    logger.info(f"取得 {len(df)} 根 K 線：{batch_oldest} ~ {batch_newest}")

                    # 保存到資料庫
                    inserted = cache.insert_candles(df, symbol, timeframe)
                    logger.info(f"已保存 {inserted} 筆新數據到資料庫")

                    # 更新統計
                    stats['total_records'] += inserted
                    stats['batches_fetched'] += 1

                    if stats['newest_time'] is None or batch_newest > stats['newest_time']:
                        stats['newest_time'] = batch_newest

                    if stats['oldest_time'] is None or batch_oldest < stats['oldest_time']:
                        stats['oldest_time'] = batch_oldest

                    # 檢查是否還有更早的數據
                    if len(df) < batch_size:
                        logger.info(f"本批次數據不足 {batch_size} 根，可能已到達歷史數據起點")
                        consecutive_empty += 1
                    else:
                        consecutive_empty = 0  # 重置計數

                    # 更新下一批的結束時間（從最早的時間往前）
                    current_end_time = batch_oldest - timedelta(minutes=tf_minutes)

                    # 顯示進度
                    logger.info(f"累計進度：{stats['total_records']} 筆，{stats['batches_fetched']} 批次")
                    logger.info("-" * 40)

                    break  # 成功，跳出重試迴圈

                except Exception as e:
                    retry_count += 1
                    logger.warning(f"抓取失敗（重試 {retry_count}/{max_retries}）：{e}")
                    if retry_count >= max_retries:
                        logger.error(f"達到最大重試次數，跳過此批次")
                        consecutive_empty += 1
                        current_end_time = current_end_time - timedelta(days=1)

        # 完成
        stats['status'] = 'completed'
        stats['end_time'] = datetime.now()
        duration = stats['end_time'] - stats['start_time']

        logger.info(f"=" * 60)
        logger.info(f"回填完成！")
        logger.info(f"商品：{symbol}")
        logger.info(f"週期：{timeframe}")
        logger.info(f"總筆數：{stats['total_records']}")
        logger.info(f"批次數：{stats['batches_fetched']}")
        logger.info(f"時間範圍：{stats['oldest_time']} ~ {stats['newest_time']}")
        logger.info(f"耗時：{duration}")
        logger.info(f"=" * 60)

    except Exception as e:
        stats['status'] = 'failed'
        stats['error'] = str(e)
        logger.error(f"回填失敗：{e}")
        raise

    finally:
        client.disconnect()
        logger.info("MT5 連線已關閉")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='歷史數據批次回填腳本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
    python scripts/backfill_data.py GOLD
    python scripts/backfill_data.py GOLD --timeframe M5
    python scripts/backfill_data.py EURUSD --timeframe H1 --batch-size 5000
    python scripts/backfill_data.py GOLD --timeframe D1 --db-path data/my_cache.db

支援的時間週期：
    M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30
    H1, H2, H3, H4, H6, H8, H12
    D1, W1, MN1
        """
    )

    parser.add_argument(
        'symbol',
        type=str,
        help='商品代碼（例如：GOLD, EURUSD, USDJPY）'
    )

    parser.add_argument(
        '--timeframe',
        type=str,
        default='M1',
        help='時間週期（預設：M1）'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=10000,
        help='每次請求的 K 線數量（預設：10000）'
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default='data/candles.db',
        help='SQLite 資料庫路徑（預設：data/candles.db）'
    )

    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='失敗時的最大重試次數（預設：3）'
    )

    args = parser.parse_args()

    # 確保資料庫目錄存在
    db_dir = Path(args.db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    # 執行回填
    try:
        stats = backfill_data(
            symbol=args.symbol.upper(),
            timeframe=args.timeframe.upper(),
            db_path=args.db_path,
            batch_size=args.batch_size,
            max_retries=args.max_retries
        )

        if stats['status'] == 'completed':
            print(f"\n✅ 回填成功！共 {stats['total_records']} 筆 {stats['timeframe']} 數據")
            sys.exit(0)
        else:
            print(f"\n❌ 回填失敗：{stats.get('error', '未知錯誤')}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️ 使用者中斷，已保存的數據不受影響")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ 錯誤：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
