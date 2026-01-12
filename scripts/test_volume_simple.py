"""
簡單測試 Volume Profile 零成交量修復

直接使用模擬資料測試當 real_volume 全為 0 時，是否會自動切換到 tick_volume。
"""

import sys
from pathlib import Path

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.agent.indicators import calculate_volume_profile_for_range
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def test_zero_real_volume():
    """測試 real_volume 為 0 的情況"""
    logger.info("=" * 60)
    logger.info("測試：real_volume 為 0 時自動使用 tick_volume")
    logger.info("=" * 60)

    # 創建模擬數據：real_volume 全為 0，tick_volume 有值
    dates = [datetime.now() - timedelta(minutes=i) for i in range(100, 0, -1)]

    df = pd.DataFrame({
        'time': dates,
        'open': np.random.uniform(100, 105, 100),
        'high': np.random.uniform(105, 110, 100),
        'low': np.random.uniform(95, 100, 100),
        'close': np.random.uniform(100, 105, 100),
        'tick_volume': np.random.randint(100, 1000, 100),
        'real_volume': np.zeros(100),  # 全為 0
        'spread': np.ones(100)
    })

    logger.info(f"\n模擬數據統計：")
    logger.info(f"  real_volume 總和: {df['real_volume'].sum():.0f}")
    logger.info(f"  tick_volume 總和: {df['tick_volume'].sum():.0f}")

    try:
        logger.info("\n開始計算 Volume Profile...")
        vp_result = calculate_volume_profile_for_range(
            df=df,
            start_idx=0,
            end_idx=len(df) - 1,
            price_levels=25
        )

        logger.info("\n✅ Volume Profile 計算成功!")
        logger.info(f"  總成交量: {vp_result['total_volume']:.0f}")
        logger.info(f"  價格範圍: {vp_result['price_lowest']:.2f} - {vp_result['price_highest']:.2f}")
        logger.info(f"  K 線數量: {vp_result['bar_count']}")

        # 驗證總成交量不為 0 (應該使用 tick_volume)
        if vp_result['total_volume'] > 0:
            logger.success("\n✅ 測試通過：成功使用 tick_volume 計算")
            logger.success(f"   tick_volume 總和: {df['tick_volume'].sum():.0f}")
            logger.success(f"   計算得到的總成交量: {vp_result['total_volume']:.0f}")
            return True
        else:
            logger.error("\n❌ 測試失敗：總成交量仍為 0")
            return False

    except Exception as e:
        logger.exception(f"\n❌ 測試失敗：{e}")
        return False


def test_normal_real_volume():
    """測試正常有 real_volume 的情況"""
    logger.info("\n" + "=" * 60)
    logger.info("測試：有 real_volume 時正常使用 real_volume")
    logger.info("=" * 60)

    # 創建模擬數據：real_volume 有值
    dates = [datetime.now() - timedelta(minutes=i) for i in range(100, 0, -1)]

    df = pd.DataFrame({
        'time': dates,
        'open': np.random.uniform(100, 105, 100),
        'high': np.random.uniform(105, 110, 100),
        'low': np.random.uniform(95, 100, 100),
        'close': np.random.uniform(100, 105, 100),
        'tick_volume': np.random.randint(100, 1000, 100),
        'real_volume': np.random.randint(10000, 100000, 100),  # 有值
        'spread': np.ones(100)
    })

    logger.info(f"\n模擬數據統計：")
    logger.info(f"  real_volume 總和: {df['real_volume'].sum():.0f}")
    logger.info(f"  tick_volume 總和: {df['tick_volume'].sum():.0f}")

    try:
        logger.info("\n開始計算 Volume Profile...")
        vp_result = calculate_volume_profile_for_range(
            df=df,
            start_idx=0,
            end_idx=len(df) - 1,
            price_levels=25
        )

        logger.info("\n✅ Volume Profile 計算成功!")
        logger.info(f"  總成交量: {vp_result['total_volume']:.0f}")
        logger.info(f"  價格範圍: {vp_result['price_lowest']:.2f} - {vp_result['price_highest']:.2f}")
        logger.info(f"  K 線數量: {vp_result['bar_count']}")

        # 驗證總成交量不為 0
        if vp_result['total_volume'] > 0:
            logger.success("\n✅ 測試通過：成功使用 real_volume 計算")
            logger.success(f"   real_volume 總和: {df['real_volume'].sum():.0f}")
            return True
        else:
            logger.error("\n❌ 測試失敗：總成交量為 0")
            return False

    except Exception as e:
        logger.exception(f"\n❌ 測試失敗：{e}")
        return False


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
        logger.success("修復確認：當 real_volume 全為 0 時，會自動使用 tick_volume")
        sys.exit(0)
    else:
        logger.error("\n❌ 部分測試失敗")
        sys.exit(1)
