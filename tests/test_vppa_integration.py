"""
VPPA 整合測試

測試 VPPA 圖表產生和 Telegram 整合功能。
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 測試環境設定
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
os.environ['TELEGRAM_GROUP_IDS'] = '123456'
os.environ['ANTHROPIC_API_KEY'] = 'test_key'

from src.agent.tools import execute_tool, _generate_vppa_chart, _get_candles


class TestVPPAChartGeneration:
    """測試 VPPA 圖表產生功能"""

    @pytest.fixture
    def mock_mt5_client(self):
        """模擬 MT5 客戶端"""
        with patch('src.agent.tools.get_mt5_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def mock_cache_manager(self):
        """模擬快取管理器"""
        with patch('src.agent.tools._get_cache_manager') as mock:
            cache = MagicMock()
            mock.return_value = cache
            yield cache

    def test_tool_definition_exists(self):
        """測試工具定義存在"""
        from src.agent.tools import TOOLS

        tool_names = [tool['name'] for tool in TOOLS]
        assert 'generate_vppa_chart' in tool_names

    def test_tool_definition_schema(self):
        """測試工具定義符合規範"""
        from src.agent.tools import TOOLS

        vppa_tool = next(t for t in TOOLS if t['name'] == 'generate_vppa_chart')

        assert 'description' in vppa_tool
        assert 'input_schema' in vppa_tool
        assert vppa_tool['input_schema']['type'] == 'object'
        assert 'properties' in vppa_tool['input_schema']
        assert 'required' in vppa_tool['input_schema']

        # 檢查必要參數
        required = vppa_tool['input_schema']['required']
        assert 'symbol' in required
        assert 'timeframe' in required

    @patch('src.agent.tools.plot_vppa_chart')
    @patch('src.agent.tools.calculate_vppa')
    @patch('scripts.analyze_vppa.fetch_data')
    @patch('scripts.analyze_vppa.update_db_to_now')
    def test_generate_vppa_chart_success(
        self,
        mock_update_db,
        mock_fetch_data,
        mock_calculate_vppa,
        mock_plot_chart,
        mock_mt5_client,
        mock_cache_manager
    ):
        """測試成功產生 VPPA 圖表"""
        import pandas as pd

        # 模擬資料
        mock_update_db.return_value = 10

        # 模擬 K 線資料
        df = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=100, freq='1H'),
            'open': [2000 + i for i in range(100)],
            'high': [2005 + i for i in range(100)],
            'low': [1995 + i for i in range(100)],
            'close': [2000 + i for i in range(100)],
            'real_volume': [1000] * 100
        })
        mock_fetch_data.return_value = df

        # 模擬 VPPA 結果
        mock_calculate_vppa.return_value = {
            'metadata': {
                'total_pivot_points': 10,
                'total_ranges': 9
            },
            'pivot_summary': [],
            'pivot_ranges': [],
            'developing_range': None
        }

        # 模擬圖表產生
        mock_plot_chart.return_value = MagicMock()

        # 執行測試
        result = _generate_vppa_chart({
            'symbol': 'GOLD',
            'timeframe': 'M1',
            'count': 100
        })

        # 驗證結果
        assert result['success'] is True
        assert 'image_path' in result['data']
        assert result['data']['image_type'] == 'vppa_chart'
        assert 'summary' in result['data']
        assert result['data']['summary']['symbol'] == 'GOLD'
        assert result['data']['summary']['timeframe'] == 'M1'

        # 驗證函數被調用
        mock_update_db.assert_called_once()
        mock_fetch_data.assert_called_once()
        mock_calculate_vppa.assert_called_once()
        mock_plot_chart.assert_called_once()

    def test_generate_vppa_chart_invalid_timeframe(self, mock_mt5_client, mock_cache_manager):
        """測試無效時間週期"""
        result = _generate_vppa_chart({
            'symbol': 'GOLD',
            'timeframe': 'INVALID',
            'count': 100
        })

        assert result['success'] is False
        assert '無效的時間週期' in result['error']

    @patch('src.agent.tools.plot_vppa_chart')
    @patch('src.agent.tools.calculate_vppa')
    @patch('scripts.analyze_vppa.fetch_data')
    @patch('scripts.analyze_vppa.update_db_to_now')
    def test_generate_vppa_chart_file_too_large(
        self,
        mock_update_db,
        mock_fetch_data,
        mock_calculate_vppa,
        mock_plot_chart,
        mock_mt5_client,
        mock_cache_manager
    ):
        """測試檔案過大處理"""
        import pandas as pd

        # 模擬資料
        mock_update_db.return_value = 0
        df = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=100, freq='1H'),
            'open': [2000] * 100,
            'high': [2005] * 100,
            'low': [1995] * 100,
            'close': [2000] * 100,
            'real_volume': [1000] * 100
        })
        mock_fetch_data.return_value = df

        mock_calculate_vppa.return_value = {
            'metadata': {'total_pivot_points': 10, 'total_ranges': 9},
            'pivot_summary': [],
            'pivot_ranges': [],
            'developing_range': None
        }

        # 模擬產生超大檔案
        with patch('os.path.getsize', return_value=15 * 1024 * 1024):  # 15MB
            result = _generate_vppa_chart({
                'symbol': 'GOLD',
                'timeframe': 'M1',
                'count': 100
            })

        assert result['success'] is False
        assert '檔案過大' in result['error']


class TestGetCandlesWithBackfill:
    """測試 get_candles 自動回補功能"""

    @pytest.fixture
    def mock_mt5_client(self):
        """模擬 MT5 客戶端"""
        with patch('src.agent.tools.get_mt5_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def mock_cache_manager(self):
        """模擬快取管理器"""
        with patch('src.agent.tools._get_cache_manager') as mock:
            cache = MagicMock()
            mock.return_value = cache
            yield cache

    @patch('scripts.analyze_vppa.update_db_to_now')
    def test_get_candles_sufficient_data(self, mock_update_db, mock_mt5_client, mock_cache_manager):
        """測試 DB 資料充足時不觸發回補"""
        import pandas as pd

        # 模擬 DB 有足夠資料
        df = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=150, freq='1H'),
            'open': [2000] * 150,
            'high': [2005] * 150,
            'low': [1995] * 150,
            'close': [2000] * 150,
            'real_volume': [1000] * 150
        })
        mock_cache_manager.query_candles.return_value = df

        result = _get_candles({
            'symbol': 'GOLD',
            'timeframe': 'H1',
            'count': 100
        })

        assert result['success'] is True
        assert result['data']['summary']['total_candles'] == 100
        assert result['data']['summary']['backfilled'] is False

        # 驗證未調用回補
        mock_update_db.assert_not_called()

    @patch('scripts.analyze_vppa.update_db_to_now')
    def test_get_candles_triggers_backfill(self, mock_update_db, mock_mt5_client, mock_cache_manager):
        """測試 DB 資料不足時觸發回補"""
        import pandas as pd

        # 第一次查詢：資料不足
        df_insufficient = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=50, freq='1H'),
            'open': [2000] * 50,
            'high': [2005] * 50,
            'low': [1995] * 50,
            'close': [2000] * 50,
            'real_volume': [1000] * 50
        })

        # 第二次查詢：回補後資料充足
        df_sufficient = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=150, freq='1H'),
            'open': [2000] * 150,
            'high': [2005] * 150,
            'low': [1995] * 150,
            'close': [2000] * 150,
            'real_volume': [1000] * 150
        })

        mock_cache_manager.query_candles.side_effect = [df_insufficient, df_sufficient]
        mock_update_db.return_value = 100

        result = _get_candles({
            'symbol': 'GOLD',
            'timeframe': 'H1',
            'count': 100
        })

        assert result['success'] is True
        assert result['data']['summary']['total_candles'] == 100
        assert result['data']['summary']['backfilled'] is True
        assert result['data']['summary']['backfill_count'] == 100

        # 驗證調用了回補
        mock_update_db.assert_called_once()

    def test_get_candles_invalid_timeframe(self, mock_mt5_client, mock_cache_manager):
        """測試無效時間週期"""
        result = _get_candles({
            'symbol': 'GOLD',
            'timeframe': 'INVALID',
            'count': 100
        })

        assert result['success'] is False
        assert '無效的時間週期' in result['error']


class TestExecuteTool:
    """測試工具執行器"""

    def test_execute_vppa_chart_tool(self):
        """測試執行 VPPA 圖表工具"""
        with patch('src.agent.tools._generate_vppa_chart') as mock_func:
            mock_func.return_value = {'success': True}

            result = execute_tool('generate_vppa_chart', {'symbol': 'GOLD', 'timeframe': 'M1'})

            assert result['success'] is True
            mock_func.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
