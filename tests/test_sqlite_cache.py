"""
SQLite 快取管理器單元測試
"""

import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import os

from src.core.sqlite_cache import SQLiteCacheManager


@pytest.fixture
def temp_db():
    """建立臨時資料庫"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    yield db_path

    # 清理
    if os.path.exists(db_path):
        os.remove(db_path)
    # 清理 WAL 檔案
    wal_path = db_path + '-wal'
    if os.path.exists(wal_path):
        os.remove(wal_path)
    shm_path = db_path + '-shm'
    if os.path.exists(shm_path):
        os.remove(shm_path)


@pytest.fixture
def cache_manager(temp_db):
    """建立快取管理器實例"""
    return SQLiteCacheManager(db_path=temp_db)


@pytest.fixture
def sample_candles():
    """建立樣本 K 線數據"""
    data = {
        'time': pd.date_range('2024-01-01', periods=100, freq='h', tz='UTC'),
        'open': [100.0 + i * 0.1 for i in range(100)],
        'high': [101.0 + i * 0.1 for i in range(100)],
        'low': [99.0 + i * 0.1 for i in range(100)],
        'close': [100.5 + i * 0.1 for i in range(100)],
        'tick_volume': [1000 + i * 10 for i in range(100)],
        'spread': [2] * 100,
        'real_volume': [5000 + i * 50 for i in range(100)]
    }
    return pd.DataFrame(data)


class TestSQLiteCacheManager:
    """SQLiteCacheManager 測試類別"""

    def test_initialization(self, temp_db):
        """測試：初始化"""
        manager = SQLiteCacheManager(db_path=temp_db)

        # 驗證資料庫檔案存在
        assert Path(temp_db).exists()

        # 驗證資料表已建立
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert 'candles' in tables
        assert 'cache_metadata' in tables
        assert 'data_gaps' in tables
        assert 'indicator_cache' in tables

        conn.close()

    def test_insert_candles(self, cache_manager, sample_candles):
        """測試：插入 K 線數據"""
        symbol = 'GOLD'
        timeframe = 'H1'

        count = cache_manager.insert_candles(
            sample_candles, symbol, timeframe
        )

        assert count == 100

        # 驗證數據可被查詢
        df = cache_manager.query_candles(symbol, timeframe)
        assert len(df) == 100

    def test_query_candles_with_date_range(
        self, cache_manager, sample_candles
    ):
        """測試：使用日期範圍查詢 K 線數據"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 插入數據
        cache_manager.insert_candles(sample_candles, symbol, timeframe)

        # 查詢特定範圍
        from_date = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2024, 1, 1, 20, 0, 0, tzinfo=timezone.utc)

        df = cache_manager.query_candles(
            symbol, timeframe, from_date, to_date
        )

        # 驗證數據範圍
        assert len(df) > 0
        assert all(df['time'] >= from_date)
        assert all(df['time'] <= to_date)

    def test_get_cache_info(self, cache_manager, sample_candles):
        """測試：取得快取資訊"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 插入數據
        cache_manager.insert_candles(sample_candles, symbol, timeframe)

        # 取得快取資訊
        info = cache_manager.get_cache_info(symbol, timeframe)

        assert info is not None
        assert info['symbol'] == symbol
        assert info['timeframe'] == timeframe
        assert info['total_records'] == 100
        assert info['first_time'] is not None
        assert info['last_time'] is not None

    def test_clear_cache(self, cache_manager, sample_candles):
        """測試：清除快取"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 插入數據
        cache_manager.insert_candles(sample_candles, symbol, timeframe)

        # 清除快取
        deleted_count = cache_manager.clear_cache(symbol, timeframe)

        assert deleted_count == 100

        # 驗證數據已清除
        df = cache_manager.query_candles(symbol, timeframe)
        assert len(df) == 0

    def test_upsert_candles(self, cache_manager, sample_candles):
        """測試：更新（UPSERT）K 線數據"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 第一次插入
        cache_manager.insert_candles(sample_candles, symbol, timeframe)

        # 修改部分數據並重新插入
        modified_candles = sample_candles.copy()
        modified_candles.loc[0, 'close'] = 999.9

        cache_manager.insert_candles(modified_candles, symbol, timeframe)

        # 驗證數據被更新
        df = cache_manager.query_candles(symbol, timeframe)
        assert len(df) == 100  # 記錄數不變

        # 驗證特定記錄已更新
        first_record = df.iloc[-1]  # 最早的記錄（DESC 排序）
        assert first_record['close'] == 999.9


class TestSmartQueryFunctions:
    """智能查詢功能測試"""

    def test_is_cache_sufficient_full_coverage(
        self, cache_manager, sample_candles
    ):
        """測試：快取完全涵蓋"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 插入數據（2024-01-01 00:00 ~ 2024-01-05 03:00）
        cache_manager.insert_candles(sample_candles, symbol, timeframe)

        # 查詢範圍在快取內
        from_date = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)

        result = cache_manager.is_cache_sufficient(
            symbol, timeframe, from_date, to_date
        )

        assert result is True

    def test_is_cache_sufficient_no_cache(self, cache_manager):
        """測試：無快取"""
        symbol = 'SILVER'
        timeframe = 'H1'

        from_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        result = cache_manager.is_cache_sufficient(
            symbol, timeframe, from_date, to_date
        )

        assert result is False

    def test_identify_missing_ranges_no_cache(self, cache_manager):
        """測試：無快取時識別缺失範圍"""
        symbol = 'GOLD'
        timeframe = 'H1'

        from_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        ranges = cache_manager.identify_missing_ranges(
            symbol, timeframe, from_date, to_date
        )

        assert len(ranges) == 1
        assert ranges[0] == (from_date, to_date)

    def test_identify_missing_ranges_partial_cache(
        self, cache_manager, sample_candles
    ):
        """測試：部分快取時識別缺失範圍"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 插入數據（2024-01-01 00:00 ~ 2024-01-05 03:00）
        cache_manager.insert_candles(sample_candles, symbol, timeframe)

        # 查詢範圍超出快取
        from_date = datetime(2023, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2024, 1, 10, 0, 0, 0, tzinfo=timezone.utc)

        ranges = cache_manager.identify_missing_ranges(
            symbol, timeframe, from_date, to_date
        )

        # 應該有兩個缺失範圍（前端和後端）
        assert len(ranges) == 2

    def test_fetch_candles_smart_with_callback(
        self, cache_manager, sample_candles
    ):
        """測試：智能數據獲取（使用回調）"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 建立模擬回調函數
        def mock_fetcher(sym, tf, start, end):
            # 返回樣本數據的子集
            return sample_candles[
                (sample_candles['time'] >= start) &
                (sample_candles['time'] <= end)
            ]

        # 第一次查詢（無快取）
        from_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        df = cache_manager.fetch_candles_smart(
            symbol, timeframe, from_date, to_date, mock_fetcher
        )

        assert len(df) > 0

        # 驗證數據已存入快取
        cache_info = cache_manager.get_cache_info(symbol, timeframe)
        assert cache_info is not None


class TestGapDetectionAndFilling:
    """缺口檢測與填補測試"""

    def test_detect_gaps_with_missing_data(self, cache_manager):
        """測試：檢測數據缺口"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 建立有缺口的數據
        data1 = {
            'time': pd.date_range(
                '2024-01-01 00:00', periods=10, freq='h', tz='UTC'
            ),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
            'spread': [2] * 10,
            'real_volume': [5000] * 10
        }
        df1 = pd.DataFrame(data1)

        # 缺口：10小時後繼續
        data2 = {
            'time': pd.date_range(
                '2024-01-01 20:00', periods=10, freq='h', tz='UTC'
            ),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
            'spread': [2] * 10,
            'real_volume': [5000] * 10
        }
        df2 = pd.DataFrame(data2)

        # 插入數據
        cache_manager.insert_candles(df1, symbol, timeframe)
        cache_manager.insert_candles(df2, symbol, timeframe)

        # 檢測缺口
        gaps = cache_manager.detect_data_gaps(symbol, timeframe)

        # 應該檢測到一個缺口
        assert len(gaps) > 0

    def test_get_gaps(self, cache_manager):
        """測試：查詢缺口"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 建立有缺口的數據並檢測
        data1 = {
            'time': pd.date_range(
                '2024-01-01 00:00', periods=10, freq='h', tz='UTC'
            ),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
            'spread': [2] * 10,
            'real_volume': [5000] * 10
        }
        df1 = pd.DataFrame(data1)

        data2 = {
            'time': pd.date_range(
                '2024-01-01 20:00', periods=10, freq='h', tz='UTC'
            ),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
            'spread': [2] * 10,
            'real_volume': [5000] * 10
        }
        df2 = pd.DataFrame(data2)

        cache_manager.insert_candles(df1, symbol, timeframe)
        cache_manager.insert_candles(df2, symbol, timeframe)
        cache_manager.detect_data_gaps(symbol, timeframe)

        # 查詢缺口
        gaps_df = cache_manager.get_gaps(symbol, timeframe)

        assert len(gaps_df) > 0
        assert 'gap_start' in gaps_df.columns
        assert 'gap_end' in gaps_df.columns

    def test_fill_data_gaps(self, cache_manager):
        """測試：填補缺口"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 建立有缺口的數據
        data1 = {
            'time': pd.date_range(
                '2024-01-01 00:00', periods=10, freq='h', tz='UTC'
            ),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
            'spread': [2] * 10,
            'real_volume': [5000] * 10
        }
        df1 = pd.DataFrame(data1)

        data2 = {
            'time': pd.date_range(
                '2024-01-01 20:00', periods=10, freq='h', tz='UTC'
            ),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
            'spread': [2] * 10,
            'real_volume': [5000] * 10
        }
        df2 = pd.DataFrame(data2)

        cache_manager.insert_candles(df1, symbol, timeframe)
        cache_manager.insert_candles(df2, symbol, timeframe)
        cache_manager.detect_data_gaps(symbol, timeframe)

        # 建立模擬填補回調
        def mock_fill_callback(sym, tf, start, end):
            # 返回缺口範圍的數據
            return pd.DataFrame({
                'time': pd.date_range(start, end, freq='h', tz='UTC'),
                'open': [100.0] * 10,
                'high': [101.0] * 10,
                'low': [99.0] * 10,
                'close': [100.5] * 10,
                'tick_volume': [1000] * 10,
                'spread': [2] * 10,
                'real_volume': [5000] * 10
            })

        # 執行填補
        filled_count = cache_manager.fill_data_gaps(
            symbol, timeframe, mock_fill_callback
        )

        # 驗證填補成功
        assert filled_count > 0

    def test_ignore_gap(self, cache_manager):
        """測試：忽略缺口"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 建立有缺口的數據
        data1 = {
            'time': pd.date_range(
                '2024-01-01 00:00', periods=10, freq='h', tz='UTC'
            ),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
            'spread': [2] * 10,
            'real_volume': [5000] * 10
        }
        df1 = pd.DataFrame(data1)

        data2 = {
            'time': pd.date_range(
                '2024-01-01 20:00', periods=10, freq='h', tz='UTC'
            ),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
            'spread': [2] * 10,
            'real_volume': [5000] * 10
        }
        df2 = pd.DataFrame(data2)

        cache_manager.insert_candles(df1, symbol, timeframe)
        cache_manager.insert_candles(df2, symbol, timeframe)
        cache_manager.detect_data_gaps(symbol, timeframe)

        # 取得缺口 ID
        gaps_df = cache_manager.get_gaps(symbol, timeframe)
        gap_id = gaps_df.iloc[0]['id']

        # 忽略缺口
        cache_manager.ignore_gap(gap_id, notes='測試忽略')

        # 驗證狀態已更新
        gaps_df = cache_manager.get_gaps(symbol, timeframe, status='ignored')
        assert len(gaps_df) == 1
