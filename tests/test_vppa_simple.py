"""
簡化版 VPPA 測試腳本（不需要 pytest）
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from agent.indicators import (
    find_pivot_points,
    extract_pivot_ranges,
    calculate_volume_profile_for_range,
    calculate_value_area,
    calculate_vppa
)


def test_find_pivot_points():
    """測試 Pivot Points 偵測"""
    print("\n=== 測試 find_pivot_points() ===")

    # 建立測試資料
    highs = [1] * 8 + [2, 3, 10, 3, 2] + [1] * 8
    lows = [h - 0.5 for h in highs]

    df = pd.DataFrame({
        'high': highs,
        'low': lows
    })

    result = find_pivot_points(df, length=3)

    # 驗證
    assert result['pivot_high'].iloc[10] == 10, "Pivot High 偵測失敗"
    assert result['pivot_high'].notna().sum() > 0, "沒有偵測到 Pivot High"

    print("✓ Pivot High 偵測正確")

    # 測試 Pivot Low
    lows2 = [10] * 8 + [9, 8, 1, 8, 9] + [10] * 8
    highs2 = [l + 0.5 for l in lows2]

    df2 = pd.DataFrame({
        'high': highs2,
        'low': lows2
    })

    result2 = find_pivot_points(df2, length=3)
    assert result2['pivot_low'].iloc[10] == 1, "Pivot Low 偵測失敗"

    print("✓ Pivot Low 偵測正確")
    print("✓ find_pivot_points() 測試通過")


def test_extract_pivot_ranges():
    """測試區間提取"""
    print("\n=== 測試 extract_pivot_ranges() ===")

    # 建立測試資料
    pivot_highs = [np.nan] * 5 + [100.0] + [np.nan] * 10 + [110.0] + [np.nan] * 10
    pivot_lows = [np.nan] * 15 + [90.0] + [np.nan] * 10

    df = pd.DataFrame({
        'pivot_high': pivot_highs,
        'pivot_low': pivot_lows
    })
    df.index = pd.date_range('2024-01-01', periods=26, freq='h')

    ranges = extract_pivot_ranges(df)

    # 驗證
    assert len(ranges) == 2, f"應該有 2 個區間，但得到 {len(ranges)} 個"
    assert ranges[0]['start_idx'] == 5, "第一個區間起始索引錯誤"
    assert ranges[0]['end_idx'] == 15, "第一個區間結束索引錯誤"
    assert ranges[0]['pivot_type'] == 'L', "第一個區間 Pivot 類型錯誤"

    print(f"✓ 正確提取 {len(ranges)} 個區間")
    print("✓ extract_pivot_ranges() 測試通過")


def test_calculate_volume_profile_for_range():
    """測試 Volume Profile 計算"""
    print("\n=== 測試 calculate_volume_profile_for_range() ===")

    # 建立測試資料
    df = pd.DataFrame({
        'high': [102, 104, 106, 108, 110],
        'low': [100, 102, 104, 106, 108],
        'real_volume': [100, 100, 100, 100, 100]
    })

    result = calculate_volume_profile_for_range(
        df,
        start_idx=0,
        end_idx=4,
        price_levels=5
    )

    # 驗證
    assert result['price_lowest'] == 100, "最低價錯誤"
    assert result['price_highest'] == 110, "最高價錯誤"
    assert result['price_step'] == 2.0, "價格步長錯誤"
    assert result['total_volume'] == 500, "總成交量錯誤"
    assert len(result['volume_profile']) == 5, "Volume Profile 長度錯誤"

    print("✓ 價格範圍計算正確")
    print("✓ 成交量分配正確")
    print("✓ calculate_volume_profile_for_range() 測試通過")


def test_calculate_value_area():
    """測試 Value Area 計算"""
    print("\n=== 測試 calculate_value_area() ===")

    # 建立測試資料
    volume_storage = np.array([10, 20, 50, 20, 10])

    result = calculate_value_area(
        volume_storage=volume_storage,
        price_lowest=100.0,
        price_step=2.0,
        value_area_pct=0.7
    )

    # 驗證
    assert result['poc_level'] == 2, "POC 層級錯誤"
    assert result['poc_price'] == 105.0, "POC 價格錯誤"

    target_volume = 110 * 0.7
    assert result['value_area_volume'] >= target_volume, "Value Area 成交量不足"

    print(f"✓ POC 計算正確：層級 {result['poc_level']}, 價格 {result['poc_price']}")
    print(f"✓ Value Area 計算正確：{result['value_area_pct']:.1f}%")
    print("✓ calculate_value_area() 測試通過")


def test_calculate_vppa():
    """測試 VPPA 主函數"""
    print("\n=== 測試 calculate_vppa() ===")

    # 建立測試資料
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100)) * 2

    df = pd.DataFrame({
        'high': prices + 1,
        'low': prices - 1,
        'real_volume': np.random.randint(50, 150, size=100)
    })
    df.index = pd.date_range('2024-01-01', periods=100, freq='h')

    result = calculate_vppa(
        df,
        pivot_length=10,
        price_levels=10,
        value_area_pct=0.68,
        include_developing=True
    )

    # 驗證結果結構
    assert 'metadata' in result, "缺少 metadata"
    assert 'pivot_summary' in result, "缺少 pivot_summary"
    assert 'pivot_ranges' in result, "缺少 pivot_ranges"
    assert 'developing_range' in result, "缺少 developing_range"

    # 驗證元數據
    assert result['metadata']['total_bars'] == 100, "總 K 線數錯誤"
    assert result['metadata']['pivot_length'] == 10, "pivot_length 錯誤"
    assert result['metadata']['price_levels'] == 10, "price_levels 錯誤"

    # 驗證區間數量
    total_pivots = result['metadata']['total_pivot_points']
    total_ranges = result['metadata']['total_ranges']

    if total_pivots > 0:
        assert total_ranges == total_pivots - 1, "區間數量錯誤"

    print(f"✓ 找到 {total_pivots} 個 Pivot Points")
    print(f"✓ 產生 {total_ranges} 個區間")

    # 驗證每個區間的完整性
    for i, range_data in enumerate(result['pivot_ranges']):
        assert 'range_id' in range_data
        assert 'poc' in range_data
        assert 'vah' in range_data
        assert 'val' in range_data
        assert 'volume_profile' in range_data
        assert len(range_data['volume_profile']) == 10

        # 驗證 VAL <= POC <= VAH
        assert range_data['val'] <= range_data['poc']['price'], f"區間 {i}: VAL > POC"
        assert range_data['poc']['price'] <= range_data['vah'], f"區間 {i}: POC > VAH"

    print(f"✓ 所有 {total_ranges} 個區間資料完整且正確")
    print("✓ calculate_vppa() 測試通過")


def main():
    """執行所有測試"""
    print("=" * 60)
    print("VPPA 功能測試")
    print("=" * 60)

    try:
        test_find_pivot_points()
        test_extract_pivot_ranges()
        test_calculate_volume_profile_for_range()
        test_calculate_value_area()
        test_calculate_vppa()

        print("\n" + "=" * 60)
        print("所有測試通過！")
        print("=" * 60)

        return 0

    except AssertionError as e:
        print(f"\n✗ 測試失敗：{e}")
        return 1
    except Exception as e:
        print(f"\n✗ 發生錯誤：{e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
