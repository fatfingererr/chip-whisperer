"""
測試 Volume Profile 零成交量修復

測試當 real_volume 全為 0 時，是否會自動切換到 tick_volume。
"""

import sys
from pathlib import Path

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.core.mt5_client import ChipWhispererMT5Client
from src.core.sqlite_cache import SQLiteCacheManager
from src.agent.indicators import calculate_volume_profile_for_range
import pandas as pd


def test_zero_real_volume():
    """測試 real_volume 為 0 的情況"""
    logger.info("=" * 60)
    logger.info("測試：real_volume 為 0 時自動使用 tick_volume")
    logger.info("=" * 60)

    # 1. 初始化 MT5 和 SQLite
    mt5_client = ChipWhispererMT5Client()
    if not mt5_client.connect():
        logger.error("MT5 連線失敗")
        return False

    cache_manager = SQLiteCacheManager()

    # 2. 取得 ALUMINIUM M1 資料（已知 real_volume 為 0）
    symbol = "ALUMINIUM"
    timeframe = "M1"
    count = 500

    logger.info(f"\n取得 {symbol} {timeframe} 最近 {count} 根 K 線")

    # 從 DB 取得（取得所有資料，然後限制數量）
    candles_df = cache_manager.query_candles(
        symbol=symbol,
        timeframe=timeframe
    )

    if candles_df is None or len(candles_df) == 0:
        logger.error("無法從 DB 取得資料")
        return False

    # 取最新的 count 筆
    candles_df = candles_df.head(count).copy()

    logger.info(f"取得 {len(candles_df)} 根 K 線")

    # 3. 檢查成交量欄位
    logger.info("\n成交量統計：")
    logger.info(f"  real_volume 總和: {candles_df['real_volume'].sum():.0f}")
    logger.info(f"  tick_volume 總和: {candles_df['tick_volume'].sum():.0f}")

    # 4. 測試計算 Volume Profile（應該自動使用 tick_volume）
    logger.info("\n開始計算 Volume Profile...")

    try:
        vp_result = calculate_volume_profile_for_range(
            df=candles_df,
            start_idx=0,
            end_idx=len(candles_df) - 1,
            price_levels=25
        )

        logger.info("\n✅ Volume Profile 計算成功!")
        logger.info(f"  總成交量: {vp_result['total_volume']:.0f}")
        logger.info(f"  價格範圍: {vp_result['price_lowest']:.2f} - {vp_result['price_highest']:.2f}")
        logger.info(f"  K 線數量: {vp_result['bar_count']}")

        # 驗證總成交量不為 0
        if vp_result['total_volume'] > 0:
            logger.success("\n✅ 測試通過：成功使用 tick_volume 計算")
            return True
        else:
            logger.error("\n❌ 測試失敗：總成交量仍為 0")
            return False

    except Exception as e:
        logger.exception(f"\n❌ 測試失敗：{e}")
        return False

    finally:
        mt5_client.shutdown()


def test_normal_real_volume():
    """測試正常有 real_volume 的情況"""
    logger.info("\n" + "=" * 60)
    logger.info("測試：有 real_volume 時正常使用 real_volume")
    logger.info("=" * 60)

    # 1. 初始化 MT5 和 SQLite
    mt5_client = ChipWhispererMT5Client()
    if not mt5_client.connect():
        logger.error("MT5 連線失敗")
        return False

    cache_manager = SQLiteCacheManager()

    # 2. 取得 GOLD M30 資料（已知有 real_volume）
    symbol = "GOLD"
    timeframe = "M30"
    count = 500

    logger.info(f"\n取得 {symbol} {timeframe} 最近 {count} 根 K 線")

    # 從 DB 取得（取得所有資料，然後限制數量）
    candles_df = cache_manager.query_candles(
        symbol=symbol,
        timeframe=timeframe
    )

    if candles_df is None or len(candles_df) == 0:
        logger.error("無法從 DB 取得資料")
        return False

    # 取最新的 count 筆
    candles_df = candles_df.head(count).copy()

    logger.info(f"取得 {len(candles_df)} 根 K 線")

    # 3. 檢查成交量欄位
    logger.info("\n成交量統計：")
    logger.info(f"  real_volume 總和: {candles_df['real_volume'].sum():.0f}")
    logger.info(f"  tick_volume 總和: {candles_df['tick_volume'].sum():.0f}")

    # 4. 測試計算 Volume Profile（應該使用 real_volume）
    logger.info("\n開始計算 Volume Profile...")

    try:
        vp_result = calculate_volume_profile_for_range(
            df=candles_df,
            start_idx=0,
            end_idx=len(candles_df) - 1,
            price_levels=25
        )

        logger.info("\n✅ Volume Profile 計算成功!")
        logger.info(f"  總成交量: {vp_result['total_volume']:.0f}")
        logger.info(f"  價格範圍: {vp_result['price_lowest']:.2f} - {vp_result['price_highest']:.2f}")
        logger.info(f"  K 線數量: {vp_result['bar_count']}")

        # 驗證總成交量不為 0
        if vp_result['total_volume'] > 0:
            logger.success("\n✅ 測試通過：成功使用 real_volume 計算")
            return True
        else:
            logger.error("\n❌ 測試失敗：總成交量為 0")
            return False

    except Exception as e:
        logger.exception(f"\n❌ 測試失敗：{e}")
        return False

    finally:
        mt5_client.shutdown()


if __name__ == "__main__":
    # 測試 1：real_volume 為 0 的情況
    test1_passed = test_zero_real_volume()

    # 測試 2：正常有 real_volume 的情況
    test2_passed = test_normal_real_volume()

    # 總結
    logger.info("\n" + "=" * 60)
    logger.info("測試總結")
    logger.info("=" * 60)
    logger.info(f"測試 1 (zero real_volume): {'✅ PASS' if test1_passed else '❌ FAIL'}")
    logger.info(f"測試 2 (normal real_volume): {'✅ PASS' if test2_passed else '❌ FAIL'}")

    if test1_passed and test2_passed:
        logger.success("\n🎉 所有測試通過！")
        sys.exit(0)
    else:
        logger.error("\n❌ 部分測試失敗")
        sys.exit(1)
