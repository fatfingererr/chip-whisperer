"""
VPPA (Volume Profile Pivot Anchored) 功能的單元測試與整合測試
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from agent.indicators import (
    find_pivot_points,
    extract_pivot_ranges,
    calculate_volume_profile_for_range,
    calculate_value_area,
    calculate_vppa
)


class TestFindPivotPoints:
    """測試 find_pivot_points() 函數"""

    def test_basic_pivot_detection(self):
        """測試基本的 Pivot Point 偵測"""
        # 建立測試資料：明顯的高低點
        highs = [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1]
        lows = [0.5, 1.5, 2.5, 3.5, 4.5, 3.5, 2.5, 1.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 4.5, 3.5, 2.5, 1.5, 0.5]

        df = pd.DataFrame({
            'high': highs,
            'low': lows
        })

        # 使用小窗口（length=3）以便測試
        result = find_pivot_points(df, length=3)

        # 應該偵測到 Pivot High 和 Pivot Low
        assert result['pivot_high'].notna().sum() > 0
        assert result['pivot_low'].notna().sum() > 0

    def test_pivot_high_position(self):
        """測試 Pivot High 的位置正確性"""
        # 建立清晰的高點：索引 10 應該是 Pivot High
        highs = [1] * 8 + [2, 3, 10, 3, 2] + [1] * 8
        lows = [h - 0.5 for h in highs]

        df = pd.DataFrame({
            'high': highs,
            'low': lows
        })

        result = find_pivot_points(df, length=3)

        # 索引 10 應該被偵測為 Pivot High
        assert not pd.isna(result['pivot_high'].iloc[10])
        assert result['pivot_high'].iloc[10] == 10

    def test_pivot_low_position(self):
        """測試 Pivot Low 的位置正確性"""
        # 建立清晰的低點：索引 10 應該是 Pivot Low
        lows = [10] * 8 + [9, 8, 1, 8, 9] + [10] * 8
        highs = [l + 0.5 for l in lows]

        df = pd.DataFrame({
            'high': highs,
            'low': lows
        })

        result = find_pivot_points(df, length=3)

        # 索引 10 應該被偵測為 Pivot Low
        assert not pd.isna(result['pivot_low'].iloc[10])
        assert result['pivot_low'].iloc[10] == 1

    def test_insufficient_data(self):
        """測試資料量不足的情況"""
        df = pd.DataFrame({
            'high': [1, 2, 3],
            'low': [0.5, 1.5, 2.5]
        })

        with pytest.raises(ValueError) as exc_info:
            find_pivot_points(df, length=20)

        assert "資料筆數" in str(exc_info.value)

    def test_missing_columns(self):
        """測試缺少必要欄位"""
        df = pd.DataFrame({
            'high': [1, 2, 3]
        })

        with pytest.raises(ValueError) as exc_info:
            find_pivot_points(df, length=1)

        assert "缺少必要欄位" in str(exc_info.value)


class TestExtractPivotRanges:
    """測試 extract_pivot_ranges() 函數"""

    def test_basic_range_extraction(self):
        """測試基本的區間提取"""
        # 建立有兩個 Pivot Points 的資料
        df = pd.DataFrame({
            'pivot_high': [np.nan] * 10 + [100.0] + [np.nan] * 10 + [110.0] + [np.nan] * 10,
            'pivot_low': [np.nan] * 30
        })
        df.index = pd.date_range('2024-01-01', periods=30, freq='h')

        ranges = extract_pivot_ranges(df)

        # 應該有一個區間（從第一個 Pivot 到第二個）
        assert len(ranges) == 1
        assert ranges[0]['start_idx'] == 10
        assert ranges[0]['end_idx'] == 21
        assert ranges[0]['pivot_type'] == 'H'

    def test_alternating_pivots(self):
        """測試交替的高低點"""
        pivot_highs = [np.nan] * 5 + [100.0] + [np.nan] * 10 + [110.0] + [np.nan] * 10
        pivot_lows = [np.nan] * 15 + [90.0] + [np.nan] * 10

        df = pd.DataFrame({
            'pivot_high': pivot_highs,
            'pivot_low': pivot_lows
        })
        df.index = pd.date_range('2024-01-01', periods=26, freq='h')

        ranges = extract_pivot_ranges(df)

        # 應該有兩個區間
        assert len(ranges) == 2
        # 第一個區間：從 Pivot High (5) 到 Pivot Low (15)
        assert ranges[0]['start_idx'] == 5
        assert ranges[0]['end_idx'] == 15
        assert ranges[0]['pivot_type'] == 'L'
        # 第二個區間：從 Pivot Low (15) 到 Pivot High (21)
        assert ranges[1]['start_idx'] == 15
        assert ranges[1]['end_idx'] == 21
        assert ranges[1]['pivot_type'] == 'H'

    def test_insufficient_pivots(self):
        """測試 Pivot Points 不足的情況"""
        df = pd.DataFrame({
            'pivot_high': [100.0] + [np.nan] * 10,
            'pivot_low': [np.nan] * 11
        })
        df.index = pd.date_range('2024-01-01', periods=11, freq='h')

        ranges = extract_pivot_ranges(df)

        # 只有一個 Pivot，無法形成區間
        assert len(ranges) == 0


class TestCalculateVolumeProfileForRange:
    """測試 calculate_volume_profile_for_range() 函數"""

    def test_basic_volume_distribution(self):
        """測試基本的成交量分配"""
        # 建立簡單的測試資料：5 根 K 線，價格從 100 到 110
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

        # 驗證基本屬性
        assert result['price_lowest'] == 100
        assert result['price_highest'] == 110
        assert result['price_step'] == 2.0  # (110 - 100) / 5
        assert result['total_volume'] == 500
        assert len(result['volume_profile']) == 5

    def test_single_bar_range(self):
        """測試單根 K 線的區間"""
        df = pd.DataFrame({
            'high': [105],
            'low': [100],
            'real_volume': [100]
        })

        result = calculate_volume_profile_for_range(
            df,
            start_idx=0,
            end_idx=0,
            price_levels=5
        )

        assert result['bar_count'] == 1
        assert result['total_volume'] == 100

    def test_flat_price_range(self):
        """測試價格無變化的情況"""
        df = pd.DataFrame({
            'high': [100, 100, 100],
            'low': [100, 100, 100],
            'real_volume': [50, 50, 50]
        })

        result = calculate_volume_profile_for_range(
            df,
            start_idx=0,
            end_idx=2,
            price_levels=5
        )

        # 價格無變化，price_step 應該為 0
        assert result['price_step'] == 0
        assert result['total_volume'] == 150

    def test_invalid_index_range(self):
        """測試無效的索引範圍"""
        df = pd.DataFrame({
            'high': [100, 105, 110],
            'low': [95, 100, 105],
            'real_volume': [100, 100, 100]
        })

        with pytest.raises(ValueError):
            calculate_volume_profile_for_range(df, start_idx=2, end_idx=1, price_levels=5)


class TestCalculateValueArea:
    """測試 calculate_value_area() 函數"""

    def test_simple_value_area(self):
        """測試簡單的 Value Area 計算"""
        # 建立簡單的成交量分佈：中間層級成交量最大
        volume_storage = np.array([10, 20, 50, 20, 10])  # POC 在索引 2

        result = calculate_value_area(
            volume_storage=volume_storage,
            price_lowest=100.0,
            price_step=2.0,
            value_area_pct=0.7
        )

        # POC 應該在索引 2
        assert result['poc_level'] == 2
        assert result['poc_price'] == 100.0 + (2 + 0.5) * 2.0  # 105.0

        # Value Area 應該包含 70% 的成交量
        target_volume = 110 * 0.7  # 總成交量 110
        assert result['value_area_volume'] >= target_volume

    def test_poc_at_edge(self):
        """測試 POC 在邊界的情況"""
        # POC 在最上層
        volume_storage = np.array([10, 20, 30, 40, 100])

        result = calculate_value_area(
            volume_storage=volume_storage,
            price_lowest=100.0,
            price_step=2.0,
            value_area_pct=0.68
        )

        assert result['poc_level'] == 4
        # VAH 不能超出範圍
        assert result['vah'] <= 100.0 + 5 * 2.0

    def test_zero_total_volume(self):
        """測試總成交量為 0 的情況"""
        volume_storage = np.zeros(5)

        result = calculate_value_area(
            volume_storage=volume_storage,
            price_lowest=100.0,
            price_step=2.0,
            value_area_pct=0.68
        )

        # 應該回傳有效的結果（雖然成交量為 0）
        assert result['total_volume'] == 0
        assert result['value_area_volume'] == 0


class TestCalculateVPPA:
    """測試 calculate_vppa() 主函數（整合測試）"""

    def test_basic_vppa_calculation(self):
        """測試基本的 VPPA 計算"""
        # 建立足夠的測試資料
        np.random.seed(42)

        # 建立一個有趨勢的價格序列
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
        assert 'metadata' in result
        assert 'pivot_summary' in result
        assert 'pivot_ranges' in result
        assert 'developing_range' in result

        # 驗證元數據
        assert result['metadata']['total_bars'] == 100
        assert result['metadata']['pivot_length'] == 10
        assert result['metadata']['price_levels'] == 10

    def test_vppa_range_count(self):
        """測試區間數量正確性"""
        # 建立測試資料
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(200)) * 2

        df = pd.DataFrame({
            'high': prices + 1,
            'low': prices - 1,
            'real_volume': np.random.randint(50, 150, size=200)
        })
        df.index = pd.date_range('2024-01-01', periods=200, freq='h')

        result = calculate_vppa(df, pivot_length=15, price_levels=20)

        # 區間數量應該 = Pivot Points 總數 - 1
        total_pivots = result['metadata']['total_pivot_points']
        total_ranges = result['metadata']['total_ranges']

        if total_pivots > 0:
            assert total_ranges == total_pivots - 1

    def test_vppa_each_range_complete(self):
        """測試每個區間的資料完整性"""
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(150)) * 2

        df = pd.DataFrame({
            'high': prices + 1,
            'low': prices - 1,
            'real_volume': np.random.randint(50, 150, size=150)
        })
        df.index = pd.date_range('2024-01-01', periods=150, freq='h')

        result = calculate_vppa(df, pivot_length=10, price_levels=15)

        # 檢查每個區間
        for range_data in result['pivot_ranges']:
            # 必要欄位存在
            assert 'range_id' in range_data
            assert 'start_idx' in range_data
            assert 'end_idx' in range_data
            assert 'poc' in range_data
            assert 'vah' in range_data
            assert 'val' in range_data
            assert 'volume_profile' in range_data

            # volume_profile 長度正確
            assert len(range_data['volume_profile']) == 15

            # VAL <= POC <= VAH
            assert range_data['val'] <= range_data['poc']['price']
            assert range_data['poc']['price'] <= range_data['vah']

    def test_vppa_with_insufficient_data(self):
        """測試資料不足的情況"""
        df = pd.DataFrame({
            'high': [100, 101, 102],
            'low': [99, 100, 101],
            'real_volume': [50, 50, 50]
        })
        df.index = pd.date_range('2024-01-01', periods=3, freq='h')

        with pytest.raises(ValueError) as exc_info:
            calculate_vppa(df, pivot_length=20)

        assert "資料筆數" in str(exc_info.value)


# Fixtures

@pytest.fixture
def sample_ohlcv_data():
    """建立範例 OHLCV 資料"""
    np.random.seed(42)

    prices = 100 + np.cumsum(np.random.randn(200)) * 2

    df = pd.DataFrame({
        'high': prices + 1,
        'low': prices - 1,
        'close': prices,
        'real_volume': np.random.randint(50, 150, size=200)
    })
    df.index = pd.date_range('2024-01-01', periods=200, freq='h')

    return df


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
