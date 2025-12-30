"""
HistoricalDataFetcher 類別的單元測試
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.data_fetcher import HistoricalDataFetcher


class TestHistoricalDataFetcher:
    """HistoricalDataFetcher 測試類別"""

    def test_get_timeframe_constant_valid(self, fetcher_with_mock_client):
        """測試有效的時間週期轉換"""
        fetcher = fetcher_with_mock_client

        # 測試各種時間週期
        assert fetcher._get_timeframe_constant('H1') is not None
        assert fetcher._get_timeframe_constant('D1') is not None
        assert fetcher._get_timeframe_constant('M5') is not None
        assert fetcher._get_timeframe_constant('h1') is not None  # 測試大小寫不敏感

    def test_get_timeframe_constant_invalid(self, fetcher_with_mock_client):
        """測試無效的時間週期"""
        fetcher = fetcher_with_mock_client

        with pytest.raises(ValueError) as exc_info:
            fetcher._get_timeframe_constant('INVALID')

        assert '無效的時間週期' in str(exc_info.value)

    def test_parse_date_full_datetime(self, fetcher_with_mock_client):
        """測試解析完整日期時間"""
        fetcher = fetcher_with_mock_client

        dt = fetcher._parse_date('2024-01-15 14:30:00')

        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 14
        assert dt.minute == 30

    def test_parse_date_date_only(self, fetcher_with_mock_client):
        """測試解析僅日期"""
        fetcher = fetcher_with_mock_client

        # 起始日期（應該是 00:00:00）
        dt_start = fetcher._parse_date('2024-01-15', is_end_date=False)
        assert dt_start.hour == 0
        assert dt_start.minute == 0

        # 結束日期（應該是 23:59:59）
        dt_end = fetcher._parse_date('2024-01-15', is_end_date=True)
        assert dt_end.hour == 23
        assert dt_end.minute == 59

    def test_parse_date_invalid_format(self, fetcher_with_mock_client):
        """測試無效的日期格式"""
        fetcher = fetcher_with_mock_client

        with pytest.raises(ValueError) as exc_info:
            fetcher._parse_date('2024/01/15')  # 錯誤的分隔符號

        assert '無效的日期格式' in str(exc_info.value)

    def test_cache_dir_creation(self, tmp_path):
        """測試快取目錄建立"""
        from unittest.mock import Mock

        cache_dir = tmp_path / 'test_cache'
        mock_client = Mock()

        fetcher = HistoricalDataFetcher(mock_client, cache_dir=str(cache_dir))

        # 目錄應該被建立
        assert cache_dir.exists()
        assert cache_dir.is_dir()


# Fixtures

@pytest.fixture
def fetcher_with_mock_client():
    """建立帶有 mock 客戶端的 fetcher"""
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.ensure_connected = Mock()

    return HistoricalDataFetcher(mock_client)
