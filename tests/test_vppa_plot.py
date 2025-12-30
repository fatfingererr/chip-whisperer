"""
VPPA 視覺化模組測試
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

from src.visualization.plotly_utils import (
    map_idx_to_time,
    validate_vppa_json,
    validate_candles_df,
    normalize_volume_width,
    get_volume_colors
)
from src.visualization import plot_vppa_chart


@pytest.fixture
def sample_candles_df():
    """建立範例 K 線 DataFrame"""
    n = 100
    times = [datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=i) for i in range(n)]

    df = pd.DataFrame({
        'time': times,
        'open': np.random.uniform(2600, 2650, n),
        'high': np.random.uniform(2650, 2700, n),
        'low': np.random.uniform(2550, 2600, n),
        'close': np.random.uniform(2600, 2650, n),
        'real_volume': np.random.randint(1000, 5000, n)
    })

    return df


@pytest.fixture
def sample_vppa_json():
    """建立範例 VPPA JSON"""
    return {
        'symbol': 'GOLD',
        'timeframe': 'M1',
        'pivot_points': [
            {'idx': 10, 'type': 'H', 'price': 2680.0},
            {'idx': 30, 'type': 'L', 'price': 2570.0},
            {'idx': 50, 'type': 'H', 'price': 2690.0},
        ],
        'pivot_ranges': [
            {
                'range_id': 0,
                'start_idx': 10,
                'end_idx': 30,
                'price_info': {
                    'highest': 2680.0,
                    'lowest': 2570.0,
                    'range': 110.0,
                    'step': 2.24
                },
                'poc': {
                    'level': 24,
                    'price': 2625.0,
                    'volume': 50000.0,
                    'volume_pct': 15.0
                },
                'value_area': {
                    'vah': 2650.0,
                    'val': 2600.0,
                    'width': 50.0,
                    'volume': 200000.0,
                    'pct': 0.68
                },
                'volume_profile': {
                    'levels': 49,
                    'price_centers': [2571.0 + i * 2.24 for i in range(49)],
                    'volumes': [1000.0 + i * 100 for i in range(49)]
                }
            }
        ]
    }


class TestPlotlyUtils:
    """測試 plotly_utils 輔助函數"""

    def test_map_idx_to_time(self, sample_candles_df):
        """測試索引到時間的映射"""
        result = map_idx_to_time(0, sample_candles_df)
        assert isinstance(result, pd.Timestamp)
        assert result == sample_candles_df.iloc[0]['time']

        result = map_idx_to_time(50, sample_candles_df)
        assert result == sample_candles_df.iloc[50]['time']

    def test_map_idx_to_time_out_of_range(self, sample_candles_df):
        """測試索引超出範圍時的錯誤處理"""
        with pytest.raises(IndexError):
            map_idx_to_time(1000, sample_candles_df)

        with pytest.raises(IndexError):
            map_idx_to_time(-1, sample_candles_df)

    def test_validate_vppa_json_valid(self, sample_vppa_json):
        """測試有效的 VPPA JSON 驗證"""
        # 不應該拋出異常
        validate_vppa_json(sample_vppa_json)

    def test_validate_vppa_json_missing_key(self):
        """測試缺少必要欄位的 VPPA JSON"""
        invalid_json = {
            'symbol': 'GOLD',
            'timeframe': 'M1'
            # 缺少 pivot_ranges 和 pivot_points
        }

        with pytest.raises(ValueError, match="缺少必要欄位"):
            validate_vppa_json(invalid_json)

    def test_validate_candles_df_valid(self, sample_candles_df):
        """測試有效的 K 線 DataFrame 驗證"""
        # 不應該拋出異常
        validate_candles_df(sample_candles_df)

    def test_validate_candles_df_missing_column(self):
        """測試缺少必要欄位的 K 線 DataFrame"""
        invalid_df = pd.DataFrame({
            'time': [datetime.now(timezone.utc)],
            'open': [2600.0]
            # 缺少 high, low, close
        })

        with pytest.raises(ValueError, match="缺少必要欄位"):
            validate_candles_df(invalid_df)

    def test_validate_candles_df_empty(self):
        """測試空的 K 線 DataFrame"""
        empty_df = pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close'])

        with pytest.raises(ValueError, match="不能為空"):
            validate_candles_df(empty_df)

    def test_normalize_volume_width(self):
        """測試成交量寬度正規化"""
        volumes = np.array([100, 200, 300, 400, 500])
        result = normalize_volume_width(volumes, max_width_bars=10, timeframe='M1')

        # 最大值應該被映射到 10 分鐘
        assert result.max() == 10.0

        # 其他值應該按比例縮放
        assert result[0] == 2.0  # 100/500 * 10 = 2.0
        assert result[2] == 6.0  # 300/500 * 10 = 6.0

    def test_normalize_volume_width_zero(self):
        """測試成交量全為零的情況"""
        volumes = np.array([0, 0, 0])
        result = normalize_volume_width(volumes, max_width_bars=10, timeframe='M1')

        assert np.all(result == 0)

    def test_get_volume_colors(self):
        """測試 Volume Profile 顏色分配"""
        price_centers = np.array([2600.0, 2610.0, 2620.0, 2630.0, 2640.0])
        vah = 2630.0
        val = 2610.0

        colors = get_volume_colors(price_centers, vah, val)

        # 應該返回正確數量的顏色
        assert len(colors) == len(price_centers)

        # 檢查顏色邏輯（簡化檢查）
        # Value Area 內的價格應該有一種顏色，外面的應該有另一種顏色
        assert isinstance(colors[0], str)
        assert isinstance(colors[2], str)


class TestPlotVPPAChart:
    """測試 plot_vppa_chart 主函數"""

    def test_plot_vppa_chart_basic(self, sample_vppa_json, sample_candles_df, tmp_path):
        """測試基本繪圖功能"""
        output_path = tmp_path / "test_chart.png"

        fig = plot_vppa_chart(
            vppa_json=sample_vppa_json,
            candles_df=sample_candles_df,
            output_path=str(output_path),
            show_pivot_points=True,
            show_developing=True,
            width=800,
            height=600
        )

        # 檢查圖表物件
        assert fig is not None
        assert hasattr(fig, 'data')

        # 檢查輸出檔案
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_plot_vppa_chart_no_output(self, sample_vppa_json, sample_candles_df):
        """測試不輸出檔案的情況"""
        fig = plot_vppa_chart(
            vppa_json=sample_vppa_json,
            candles_df=sample_candles_df,
            output_path=None,
            show_pivot_points=False,
            show_developing=True,
            width=800,
            height=600
        )

        # 應該返回 Figure 物件
        assert fig is not None
        assert hasattr(fig, 'data')

    def test_plot_vppa_chart_invalid_json(self, sample_candles_df):
        """測試無效的 VPPA JSON"""
        invalid_json = {'symbol': 'GOLD'}

        with pytest.raises(ValueError):
            plot_vppa_chart(
                vppa_json=invalid_json,
                candles_df=sample_candles_df
            )

    def test_plot_vppa_chart_invalid_df(self, sample_vppa_json):
        """測試無效的 K 線 DataFrame"""
        invalid_df = pd.DataFrame({'time': []})

        with pytest.raises(ValueError):
            plot_vppa_chart(
                vppa_json=sample_vppa_json,
                candles_df=invalid_df
            )
