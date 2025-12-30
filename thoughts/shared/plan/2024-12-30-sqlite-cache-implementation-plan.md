# SQLite3 快取功能實作計劃

## 計劃概覽

### 目標

為 Chip Whisperer 專案建立基於 SQLite3 的數據快取系統，取代現有的檔案快取機制，提供更高效的數據管理、查詢優化、缺口檢測和自動填補功能。

### 範圍

**包含：**
1. 設計和建立 SQLite3 資料庫結構（4 張核心資料表）
2. 實作 `SQLiteCacheManager` 核心快取管理類別
3. 整合 `SQLiteCacheManager` 到現有 `HistoricalDataFetcher`
4. 實作智能數據獲取流程（優先從快取讀取，必要時從 MT5 補充）
5. 實作數據缺口檢測演算法
6. 實作數據缺口填補機制
7. 建立命令列快取管理工具
8. 撰寫完整的單元測試

**不包含：**
- 修改現有 MT5 連線和數據獲取的核心邏輯
- 技術指標計算結果的快取（保留為未來階段）
- 假日日曆整合（保留為未來階段）
- 多資料庫檔案支援（保留為未來階段）
- 刪除現有的檔案快取功能（保持向下相容）

### 時程估算

- **階段一（資料庫設計與核心類別）**：2-3 天
- **階段二（整合與數據流程）**：2-3 天
- **階段三（缺口檢測與填補）**：2-3 天
- **階段四（管理工具與測試）**：1-2 天
- **總計**：約 7-11 個工作天

---

## 當前狀態分析

### 現有快取機制

**位置**：`src/core/data_fetcher.py`

**功能**：
- `save_to_cache()` (行 292-326)：儲存 DataFrame 到 CSV/Parquet 檔案
- `load_from_cache()` (行 328-356)：從檔案載入 DataFrame

**限制**：
- ❌ 無法高效查詢特定時間範圍的數據
- ❌ 缺乏數據版本控制機制
- ❌ 檔案名稱衝突會導致數據覆蓋
- ❌ 無法偵測數據缺口
- ❌ 無並發控制
- ❌ 無數據更新追蹤

### 關鍵發現

根據研究報告 `thoughts/shared/research/2024-12-30-fetch-data-sqlite-cache-analysis.md`：

1. **數據獲取集中於 `HistoricalDataFetcher`**
   - 提供 `get_candles_latest()` 和 `get_candles_by_date()` 兩種查詢模式
   - 支援 20 種時間週期（M1 到 MN1）
   - 數據格式統一為 pandas DataFrame

2. **數據欄位完整**
   - 必要欄位：time, open, high, low, close, tick_volume, spread, real_volume
   - 時間採用 UTC 時區

3. **系統架構適合引入 SQLite3**
   - 單檔案資料庫符合現有檔案快取理念
   - Python 標準庫內建支援
   - 無需額外資料庫服務

---

## 階段一：資料庫設計與核心類別

### 概覽

建立 SQLite3 資料庫結構和 `SQLiteCacheManager` 核心類別，提供基本的數據插入和查詢功能。

### 1.1 建立資料庫結構

#### 目標

設計並建立 4 張核心資料表：candles（K 線數據）、cache_metadata（快取元數據）、data_gaps（數據缺口記錄）、indicator_cache（指標快取，預留）。

#### 新增檔案：`src/core/schema.sql`

**變更內容**：

```sql
-- ============================================================================
-- K 線數據表
-- ============================================================================
CREATE TABLE IF NOT EXISTS candles (
    -- 主鍵與基本識別
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,                    -- 商品代碼（例如：GOLD, SILVER）
    timeframe TEXT NOT NULL,                 -- 時間週期（例如：H1, D1）
    time TIMESTAMP NOT NULL,                 -- K 線時間（UTC）

    -- K 線 OHLC 數據
    open REAL NOT NULL,                      -- 開盤價
    high REAL NOT NULL,                      -- 最高價
    low REAL NOT NULL,                       -- 最低價
    close REAL NOT NULL,                     -- 收盤價

    -- 成交量數據
    tick_volume INTEGER NOT NULL,            -- Tick 成交量
    spread INTEGER NOT NULL,                 -- 點差
    real_volume INTEGER NOT NULL,            -- 真實成交量

    -- 元數據
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 建立時間
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 更新時間
    source TEXT DEFAULT 'MT5',               -- 數據來源

    -- 唯一約束：同一商品、同一週期、同一時間只能有一筆記錄
    UNIQUE(symbol, timeframe, time)
);

-- 索引：優化查詢效能
CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe ON candles(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_candles_time ON candles(time);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe_time ON candles(symbol, timeframe, time);

-- ============================================================================
-- 快取元數據表
-- ============================================================================
CREATE TABLE IF NOT EXISTS cache_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,

    -- 數據範圍
    first_time TIMESTAMP,                    -- 最早數據時間
    last_time TIMESTAMP,                     -- 最新數據時間
    total_records INTEGER DEFAULT 0,         -- 總記錄數

    -- 快取狀態
    last_fetch_time TIMESTAMP,               -- 最後取得時間
    last_update_time TIMESTAMP,              -- 最後更新時間
    fetch_count INTEGER DEFAULT 0,           -- 取得次數

    -- 數據品質
    has_gaps BOOLEAN DEFAULT 0,              -- 是否有數據缺口
    gap_count INTEGER DEFAULT 0,             -- 缺口數量
    last_gap_check TIMESTAMP,                -- 最後缺口檢查時間

    UNIQUE(symbol, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_metadata_symbol_timeframe ON cache_metadata(symbol, timeframe);

-- ============================================================================
-- 數據缺口表
-- ============================================================================
CREATE TABLE IF NOT EXISTS data_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,

    -- 缺口範圍
    gap_start TIMESTAMP NOT NULL,            -- 缺口開始時間
    gap_end TIMESTAMP NOT NULL,              -- 缺口結束時間

    -- 缺口資訊
    expected_records INTEGER,                -- 預期應有的記錄數
    gap_duration_minutes INTEGER,            -- 缺口時長（分鐘）

    -- 處理狀態
    status TEXT DEFAULT 'detected',          -- 狀態：detected, filling, filled, ignored
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP,

    -- 備註
    notes TEXT,

    UNIQUE(symbol, timeframe, gap_start)
);

CREATE INDEX IF NOT EXISTS idx_gaps_symbol_timeframe ON data_gaps(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_gaps_status ON data_gaps(status);

-- ============================================================================
-- 指標計算結果快取表（預留未來使用）
-- ============================================================================
CREATE TABLE IF NOT EXISTS indicator_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    indicator_name TEXT NOT NULL,            -- 指標名稱（例如：sma_20, rsi_14）

    -- 計算參數（JSON 格式）
    parameters TEXT,                         -- 例如：{"window": 20, "column": "close"}

    -- 計算結果
    time TIMESTAMP NOT NULL,                 -- K 線時間
    value REAL,                              -- 指標值

    -- 元數據
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(symbol, timeframe, indicator_name, parameters, time)
);

CREATE INDEX IF NOT EXISTS idx_indicator_cache_lookup ON indicator_cache(symbol, timeframe, indicator_name, parameters, time);
```

#### 成功標準

**自動驗證：**
- [ ] schema.sql 檔案建立成功
- [ ] SQL 語法無錯誤（可透過 sqlite3 命令驗證）

**手動驗證：**
- [ ] 資料表結構符合設計需求
- [ ] 索引設置正確
- [ ] 唯一約束設置正確

---

### 1.2 實作 SQLiteCacheManager 核心類別

#### 目標

建立 `SQLiteCacheManager` 類別，提供資料庫初始化、基本 CRUD 操作和連線管理功能。

#### 新增檔案：`src/core/sqlite_cache.py`

**變更內容**：

```python
"""
SQLite3 快取管理模組

此模組提供基於 SQLite3 的數據快取功能，支援高效查詢、缺口檢測和數據管理。
"""

import sqlite3
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
from loguru import logger


class SQLiteCacheManager:
    """
    SQLite3 快取管理器

    提供 K 線數據的快取管理功能，包括儲存、查詢、缺口檢測和填補。
    """

    # 時間週期對應分鐘數
    TIMEFRAME_MINUTES = {
        'M1': 1, 'M2': 2, 'M3': 3, 'M4': 4, 'M5': 5, 'M6': 6,
        'M10': 10, 'M12': 12, 'M15': 15, 'M20': 20, 'M30': 30,
        'H1': 60, 'H2': 120, 'H3': 180, 'H4': 240, 'H6': 360,
        'H8': 480, 'H12': 720,
        'D1': 1440, 'W1': 10080, 'MN1': 43200  # 約略值
    }

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化快取管理器

        參數：
            db_path: 資料庫檔案路徑（預設：data/cache/mt5_cache.db）
        """
        if db_path is None:
            db_path = Path('data/cache/mt5_cache.db')
        else:
            db_path = Path(db_path)

        # 確保目錄存在
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(db_path)
        self._init_database()

        logger.info(f"SQLite 快取管理器初始化完成：{self.db_path}")

    def _init_database(self) -> None:
        """
        初始化資料庫結構

        讀取 schema.sql 並執行，建立所有必要的資料表和索引。
        """
        schema_path = Path(__file__).parent / 'schema.sql'

        if not schema_path.exists():
            logger.error(f"找不到 schema.sql：{schema_path}")
            raise FileNotFoundError(f"Schema 檔案不存在：{schema_path}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 讀取並執行 schema.sql
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            cursor.executescript(schema_sql)

            # 啟用 WAL 模式（提升並發效能）
            cursor.execute("PRAGMA journal_mode=WAL")

            # 啟用外鍵約束
            cursor.execute("PRAGMA foreign_keys=ON")

            conn.commit()
            logger.debug("資料庫結構初始化完成")

        except Exception as e:
            logger.error(f"資料庫初始化失敗：{e}")
            raise
        finally:
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """
        取得資料庫連線

        回傳：
            SQLite 連線物件
        """
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        # 設定 Row Factory 以便使用欄位名稱存取
        conn.row_factory = sqlite3.Row
        return conn

    def _get_timeframe_interval(self, timeframe: str) -> timedelta:
        """
        取得時間週期的時間間隔

        參數：
            timeframe: 時間週期代碼（例如 'H1', 'D1'）

        回傳：
            timedelta 物件

        例外：
            ValueError: 時間週期無效時
        """
        tf_upper = timeframe.upper()
        if tf_upper not in self.TIMEFRAME_MINUTES:
            raise ValueError(f"無效的時間週期：{timeframe}")

        minutes = self.TIMEFRAME_MINUTES[tf_upper]
        return timedelta(minutes=minutes)

    def insert_candles(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> int:
        """
        批次插入 K 線數據（使用 UPSERT 策略）

        參數：
            df: K 線數據 DataFrame
            symbol: 商品代碼
            timeframe: 時間週期

        回傳：
            插入的記錄數
        """
        if df.empty:
            logger.warning("DataFrame 為空，略過插入")
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # 準備數據
            df_copy = df.copy()

            # 確保時間欄位為字串格式（ISO 8601）
            if 'time' in df_copy.columns:
                df_copy['time'] = pd.to_datetime(df_copy['time']).dt.strftime('%Y-%m-%d %H:%M:%S')

            # 新增 symbol 和 timeframe 欄位
            df_copy['symbol'] = symbol
            df_copy['timeframe'] = timeframe

            # 批次插入（使用 INSERT OR REPLACE）
            insert_query = """
                INSERT OR REPLACE INTO candles (
                    symbol, timeframe, time,
                    open, high, low, close,
                    tick_volume, spread, real_volume,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """

            records = []
            for _, row in df_copy.iterrows():
                records.append((
                    row['symbol'], row['timeframe'], row['time'],
                    row['open'], row['high'], row['low'], row['close'],
                    row['tick_volume'], row['spread'], row['real_volume']
                ))

            cursor.executemany(insert_query, records)
            inserted_count = cursor.rowcount

            # 更新快取元數據
            self._update_metadata(cursor, symbol, timeframe, df)

            conn.commit()
            logger.info(f"成功插入 {inserted_count} 筆 K 線數據：{symbol} {timeframe}")

            return inserted_count

        except Exception as e:
            conn.rollback()
            logger.error(f"插入 K 線數據失敗：{e}")
            raise
        finally:
            conn.close()

    def _update_metadata(
        self,
        cursor: sqlite3.Cursor,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame
    ) -> None:
        """
        更新快取元數據

        參數：
            cursor: 資料庫游標
            symbol: 商品代碼
            timeframe: 時間週期
            df: 新插入的 K 線數據
        """
        # 查詢當前快取狀態
        query = """
            SELECT
                MIN(time) as first_time,
                MAX(time) as last_time,
                COUNT(*) as total_records
            FROM candles
            WHERE symbol = ? AND timeframe = ?
        """

        cursor.execute(query, (symbol, timeframe))
        row = cursor.fetchone()

        if row:
            first_time = row['first_time']
            last_time = row['last_time']
            total_records = row['total_records']

            # 更新或插入元數據
            upsert_query = """
                INSERT INTO cache_metadata (
                    symbol, timeframe, first_time, last_time,
                    total_records, last_update_time, fetch_count
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
                ON CONFLICT(symbol, timeframe) DO UPDATE SET
                    first_time = excluded.first_time,
                    last_time = excluded.last_time,
                    total_records = excluded.total_records,
                    last_update_time = CURRENT_TIMESTAMP,
                    fetch_count = fetch_count + 1
            """

            cursor.execute(
                upsert_query,
                (symbol, timeframe, first_time, last_time, total_records)
            )

    def query_candles(
        self,
        symbol: str,
        timeframe: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        查詢 K 線數據

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            from_date: 起始日期（UTC）
            to_date: 結束日期（UTC）

        回傳：
            K 線數據 DataFrame
        """
        conn = self._get_connection()

        try:
            # 建立查詢
            query = """
                SELECT
                    time, open, high, low, close,
                    tick_volume, spread, real_volume
                FROM candles
                WHERE symbol = ? AND timeframe = ?
            """

            params = [symbol, timeframe]

            if from_date:
                query += " AND time >= ?"
                params.append(from_date.strftime('%Y-%m-%d %H:%M:%S'))

            if to_date:
                query += " AND time <= ?"
                params.append(to_date.strftime('%Y-%m-%d %H:%M:%S'))

            query += " ORDER BY time DESC"

            # 執行查詢
            df = pd.read_sql_query(query, conn, params=params)

            # 轉換時間欄位為 datetime（UTC）
            if not df.empty and 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], utc=True)

            logger.info(f"從快取查詢到 {len(df)} 筆 K 線數據：{symbol} {timeframe}")

            return df

        except Exception as e:
            logger.error(f"查詢 K 線數據失敗：{e}")
            raise
        finally:
            conn.close()

    def get_cache_info(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Dict]:
        """
        取得快取資訊

        參數：
            symbol: 商品代碼
            timeframe: 時間週期

        回傳：
            快取資訊字典，若無快取則回傳 None
        """
        conn = self._get_connection()

        try:
            query = """
                SELECT * FROM cache_metadata
                WHERE symbol = ? AND timeframe = ?
            """

            cursor = conn.cursor()
            cursor.execute(query, (symbol, timeframe))
            row = cursor.fetchone()

            if row:
                return dict(row)
            else:
                return None

        finally:
            conn.close()

    def clear_cache(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None
    ) -> int:
        """
        清除快取數據

        參數：
            symbol: 商品代碼（若為 None 則清除所有商品）
            timeframe: 時間週期（若為 None 則清除所有週期）

        回傳：
            刪除的記錄數
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = "DELETE FROM candles WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)

            if timeframe:
                query += " AND timeframe = ?"
                params.append(timeframe)

            cursor.execute(query, params)
            deleted_count = cursor.rowcount

            # 同步刪除元數據
            meta_query = "DELETE FROM cache_metadata WHERE 1=1"
            meta_params = []

            if symbol:
                meta_query += " AND symbol = ?"
                meta_params.append(symbol)

            if timeframe:
                meta_query += " AND timeframe = ?"
                meta_params.append(timeframe)

            cursor.execute(meta_query, meta_params)

            conn.commit()
            logger.info(f"已清除 {deleted_count} 筆快取數據")

            return deleted_count

        except Exception as e:
            conn.rollback()
            logger.error(f"清除快取失敗：{e}")
            raise
        finally:
            conn.close()
```

#### 成功標準

**自動驗證：**
- [ ] `SQLiteCacheManager` 類別可成功初始化
- [ ] 資料庫檔案成功建立於 `data/cache/mt5_cache.db`
- [ ] 所有資料表和索引正確建立
- [ ] WAL 模式成功啟用

**手動驗證：**
- [ ] 程式碼符合 PEP 8 風格
- [ ] 包含完整的 docstring
- [ ] 錯誤處理完善

---

### 1.3 基本功能單元測試

#### 目標

撰寫 `SQLiteCacheManager` 的基本功能單元測試，確保核心功能正常運作。

#### 新增檔案：`tests/test_sqlite_cache.py`

**變更內容**：

```python
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
```

#### 執行步驟

```bash
# 1. 確保測試環境設定正確
cd C:\Users\fatfi\works\chip-whisperer

# 2. 執行單元測試
pytest tests/test_sqlite_cache.py -v

# 3. 檢查測試覆蓋率
pytest tests/test_sqlite_cache.py --cov=src.core.sqlite_cache --cov-report=html
```

#### 成功標準

**自動驗證：**
- [ ] 所有測試案例通過
- [ ] 測試覆蓋率 >= 80%
- [ ] 無警告或錯誤訊息

**手動驗證：**
- [ ] 測試案例涵蓋主要功能
- [ ] 測試數據合理且完整

---

## 階段二：整合與智能數據流程

### 概覽

將 `SQLiteCacheManager` 整合到 `HistoricalDataFetcher`，實作智能數據獲取流程（優先從快取讀取，必要時從 MT5 補充）。

### 2.1 擴展 SQLiteCacheManager 智能查詢功能

#### 目標

在 `SQLiteCacheManager` 中新增智能數據獲取方法，能夠判斷快取覆蓋情況並自動補充缺失數據。

#### 修改檔案：`src/core/sqlite_cache.py`

**變更內容**：

在 `SQLiteCacheManager` 類別中新增以下方法：

```python
    def is_cache_sufficient(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> bool:
        """
        檢查快取是否足夠涵蓋請求的時間範圍

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            from_date: 起始日期
            to_date: 結束日期

        回傳：
            True 如果快取完全涵蓋請求範圍
        """
        cache_info = self.get_cache_info(symbol, timeframe)

        if cache_info is None:
            return False

        # 解析快取時間範圍
        cache_first = pd.to_datetime(cache_info['first_time'], utc=True)
        cache_last = pd.to_datetime(cache_info['last_time'], utc=True)

        # 檢查是否涵蓋
        return cache_first <= from_date and cache_last >= to_date

    def identify_missing_ranges(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Tuple[datetime, datetime]]:
        """
        識別需要從 MT5 取得的缺失時間範圍

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            from_date: 請求的起始日期
            to_date: 請求的結束日期

        回傳：
            缺失範圍列表 [(start1, end1), (start2, end2), ...]
        """
        cache_info = self.get_cache_info(symbol, timeframe)

        if cache_info is None:
            # 完全沒有快取
            return [(from_date, to_date)]

        cache_first = pd.to_datetime(cache_info['first_time'], utc=True)
        cache_last = pd.to_datetime(cache_info['last_time'], utc=True)

        missing_ranges = []

        # 檢查前端缺口
        if from_date < cache_first:
            missing_ranges.append((from_date, cache_first))

        # 檢查後端缺口
        if to_date > cache_last:
            missing_ranges.append((cache_last, to_date))

        return missing_ranges

    def fetch_candles_smart(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime,
        fetcher_callback
    ) -> pd.DataFrame:
        """
        智能數據獲取：優先從快取取得，必要時從 MT5 補充

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            from_date: 起始日期
            to_date: 結束日期
            fetcher_callback: MT5 數據獲取回調函數
                簽名：fetcher_callback(symbol, timeframe, from_date, to_date) -> DataFrame

        回傳：
            完整的 K 線數據 DataFrame
        """
        logger.info(
            f"智能數據獲取：{symbol} {timeframe} "
            f"{from_date.strftime('%Y-%m-%d')} ~ {to_date.strftime('%Y-%m-%d')}"
        )

        # 1. 檢查快取是否充足
        if self.is_cache_sufficient(symbol, timeframe, from_date, to_date):
            logger.info("快取完全命中，直接從資料庫查詢")
            return self.query_candles(symbol, timeframe, from_date, to_date)

        # 2. 識別缺失範圍
        missing_ranges = self.identify_missing_ranges(
            symbol, timeframe, from_date, to_date
        )

        if missing_ranges:
            logger.info(f"發現 {len(missing_ranges)} 個缺失範圍，從 MT5 補充")

            # 3. 從 MT5 取得缺失數據
            for start, end in missing_ranges:
                try:
                    df_new = fetcher_callback(symbol, timeframe, start, end)

                    if not df_new.empty:
                        # 插入新數據到快取
                        self.insert_candles(df_new, symbol, timeframe)
                        logger.info(
                            f"已補充 {len(df_new)} 筆數據：{start} ~ {end}"
                        )
                except Exception as e:
                    logger.error(f"補充數據失敗：{e}")
                    # 繼續處理其他範圍

        # 4. 從快取查詢完整數據
        return self.query_candles(symbol, timeframe, from_date, to_date)
```

#### 成功標準

**自動驗證：**
- [ ] 新增方法可成功編譯
- [ ] 無語法錯誤

**手動驗證：**
- [ ] 邏輯正確
- [ ] Docstring 完整

---

### 2.2 整合到 HistoricalDataFetcher

#### 目標

修改 `HistoricalDataFetcher` 類別，整合 `SQLiteCacheManager`，提供使用 SQLite 快取的選項。

#### 修改檔案：`src/core/data_fetcher.py`

**變更內容**：

```python
# 在檔案頂部新增 import
from .sqlite_cache import SQLiteCacheManager

# 修改 __init__ 方法
class HistoricalDataFetcher:
    """
    歷史 K 線資料取得器

    提供多種方式取得和管理歷史 K 線資料，包括快取功能。
    """

    # ... (TIMEFRAME_MAP 保持不變)

    def __init__(
        self,
        client: ChipWhispererMT5Client,
        cache_dir: Optional[str] = None,
        use_sqlite: bool = True  # 新增參數
    ):
        """
        初始化資料取得器

        參數：
            client: MT5 客戶端實例
            cache_dir: 快取目錄路徑（可選）
            use_sqlite: 是否使用 SQLite 快取（預設 True）
        """
        self.client = client
        self.cache_dir = Path(cache_dir) if cache_dir else Path('data/cache')
        self.use_sqlite = use_sqlite

        # 建立快取目錄
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 SQLite 快取管理器
        if self.use_sqlite:
            db_path = self.cache_dir / 'mt5_cache.db'
            self.sqlite_cache = SQLiteCacheManager(str(db_path))
            logger.info("SQLite 快取已啟用")
        else:
            self.sqlite_cache = None
            logger.info("SQLite 快取已停用，使用檔案快取")

        logger.debug(f"資料快取目錄：{self.cache_dir}")

# 新增輔助方法
    def _fetch_from_mt5_by_date(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> pd.DataFrame:
        """
        從 MT5 取得指定日期範圍的數據（內部輔助方法）

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            from_date: 起始日期（UTC）
            to_date: 結束日期（UTC）

        回傳：
            K 線數據 DataFrame
        """
        self._verify_symbol(symbol)
        tf_constant = self._get_timeframe_constant(timeframe)
        self.client.ensure_connected()

        # 從 MT5 取得數據
        rates = mt5.copy_rates_range(symbol, tf_constant, from_date, to_date)

        if rates is None or len(rates) == 0:
            logger.warning(f"MT5 未返回數據：{symbol} {timeframe} {from_date} ~ {to_date}")
            return pd.DataFrame()

        # 轉換為 DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.sort_values('time', ascending=False).reset_index(drop=True)

        return df

# 修改 get_candles_latest 方法
    def get_candles_latest(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100
    ) -> pd.DataFrame:
        """
        取得最新的 N 根 K 線

        參數：
            symbol: 商品代碼（例如 'GOLD', 'SILVER'）
            timeframe: 時間週期（例如 'H1', 'D1'）
            count: 要取得的 K 線數量（預設 100）

        回傳：
            包含 K 線資料的 DataFrame

        例外：
            ValueError: 參數無效時
            RuntimeError: 資料取得失敗時
        """
        logger.info(f"取得 {symbol} {timeframe} 最新 {count} 根 K 線")

        # 如果啟用 SQLite 快取
        if self.use_sqlite and self.sqlite_cache:
            # 計算時間範圍
            end_time = datetime.now(timezone.utc)

            # 根據時間週期計算起始時間
            interval_minutes = self.sqlite_cache.TIMEFRAME_MINUTES.get(
                timeframe.upper(), 60
            )
            start_time = end_time - timedelta(minutes=interval_minutes * count * 1.5)

            # 使用智能查詢
            df = self.sqlite_cache.fetch_candles_smart(
                symbol=symbol,
                timeframe=timeframe,
                from_date=start_time,
                to_date=end_time,
                fetcher_callback=self._fetch_from_mt5_by_date
            )

            # 限制返回數量
            return df.head(count)

        # 原有邏輯：直接從 MT5 取得
        self._verify_symbol(symbol)
        tf_constant = self._get_timeframe_constant(timeframe)
        self.client.ensure_connected()

        rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, count)

        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            raise RuntimeError(f"取得 K 線資料失敗：{error}")

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.sort_values('time', ascending=False).reset_index(drop=True)

        logger.info(f"成功取得 {len(df)} 根 K 線")
        return df

# 修改 get_candles_by_date 方法
    def get_candles_by_date(
        self,
        symbol: str,
        timeframe: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        default_count: int = 1000
    ) -> pd.DataFrame:
        """
        取得指定日期範圍的 K 線資料

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            from_date: 起始日期（格式：'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'）
            to_date: 結束日期（格式：'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'）
            default_count: 未指定日期時的預設數量

        回傳：
            包含 K 線資料的 DataFrame

        例外：
            ValueError: 參數無效時
            RuntimeError: 資料取得失敗時
        """
        logger.info(f"取得 {symbol} {timeframe} K 線資料：{from_date} ~ {to_date}")

        # 解析日期
        from_datetime = None
        to_datetime = None

        if from_date:
            from_datetime = self._parse_date(from_date, is_end_date=False)

        if to_date:
            to_datetime = self._parse_date(to_date, is_end_date=True)

        # 如果啟用 SQLite 快取且有明確的日期範圍
        if self.use_sqlite and self.sqlite_cache and from_datetime and to_datetime:
            # 確保日期順序正確
            if from_datetime > to_datetime:
                logger.warning("起始日期晚於結束日期，已自動交換")
                from_datetime, to_datetime = to_datetime, from_datetime

            # 使用智能查詢
            return self.sqlite_cache.fetch_candles_smart(
                symbol=symbol,
                timeframe=timeframe,
                from_date=from_datetime,
                to_date=to_datetime,
                fetcher_callback=self._fetch_from_mt5_by_date
            )

        # 原有邏輯（未啟用 SQLite 或參數不完整時）
        self._verify_symbol(symbol)
        tf_constant = self._get_timeframe_constant(timeframe)
        self.client.ensure_connected()

        # 確保日期順序正確
        if from_datetime and to_datetime and from_datetime > to_datetime:
            logger.warning("起始日期晚於結束日期，已自動交換")
            from_datetime, to_datetime = to_datetime, from_datetime

        # 根據參數選擇適當的 MT5 API
        rates = None

        if from_datetime and to_datetime:
            logger.debug(f"使用範圍查詢：{from_datetime} ~ {to_datetime}")
            rates = mt5.copy_rates_range(symbol, tf_constant, from_datetime, to_datetime)

        elif from_datetime:
            logger.debug(f"從 {from_datetime} 開始取得 {default_count} 根")
            rates = mt5.copy_rates_from(symbol, tf_constant, from_datetime, default_count)

        elif to_datetime:
            lookback_days = 30
            start_date = to_datetime - timedelta(days=lookback_days)
            logger.debug(f"使用範圍查詢（往前推 {lookback_days} 天）：{start_date} ~ {to_datetime}")
            rates = mt5.copy_rates_range(symbol, tf_constant, start_date, to_datetime)

        else:
            logger.debug(f"取得最新 {default_count} 根")
            rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, default_count)

        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            raise RuntimeError(f"取得 K 線資料失敗：{error}")

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.sort_values('time', ascending=False).reset_index(drop=True)

        logger.info(f"成功取得 {len(df)} 根 K 線")
        return df
```

#### 成功標準

**自動驗證：**
- [ ] 程式碼可成功編譯
- [ ] 向下相容（`use_sqlite=False` 時使用原有邏輯）
- [ ] 無語法錯誤

**手動驗證：**
- [ ] 整合邏輯正確
- [ ] 保持現有 API 不變

---

### 2.3 整合測試

#### 目標

撰寫整合測試，驗證 `HistoricalDataFetcher` 與 `SQLiteCacheManager` 的協同運作。

#### 新增檔案：`tests/test_data_fetcher_sqlite.py`

**變更內容**：

```python
"""
HistoricalDataFetcher 與 SQLite 快取整合測試
"""

import pytest
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import tempfile
import os

from src.core.data_fetcher import HistoricalDataFetcher
from src.core.mt5_client import ChipWhispererMT5Client
from src.core.mt5_config import MT5Config


@pytest.fixture
def temp_cache_dir():
    """建立臨時快取目錄"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_mt5_client():
    """建立模擬 MT5 客戶端"""
    mock_client = Mock(spec=ChipWhispererMT5Client)
    mock_client.is_connected.return_value = True
    return mock_client


@pytest.fixture
def sample_rates():
    """建立樣本 K 線數據（模擬 MT5 格式）"""
    import numpy as np

    # 模擬 MT5 返回的 structured array
    data = []
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()

    for i in range(100):
        data.append((
            int(base_time + i * 3600),  # time (timestamp)
            100.0 + i * 0.1,            # open
            101.0 + i * 0.1,            # high
            99.0 + i * 0.1,             # low
            100.5 + i * 0.1,            # close
            1000 + i * 10,              # tick_volume
            2,                          # spread
            5000 + i * 50               # real_volume
        ))

    dtype = [
        ('time', 'i8'), ('open', 'f8'), ('high', 'f8'), ('low', 'f8'),
        ('close', 'f8'), ('tick_volume', 'i8'), ('spread', 'i4'),
        ('real_volume', 'i8')
    ]

    return np.array(data, dtype=dtype)


class TestDataFetcherSQLiteIntegration:
    """HistoricalDataFetcher 與 SQLite 整合測試"""

    @patch('MetaTrader5.copy_rates_range')
    @patch('MetaTrader5.symbol_info')
    def test_get_candles_with_sqlite_cache_miss(
        self,
        mock_symbol_info,
        mock_copy_rates,
        mock_mt5_client,
        temp_cache_dir,
        sample_rates
    ):
        """測試：快取未命中，從 MT5 取得並儲存"""
        # 設定 mock
        mock_symbol_info.return_value = Mock(visible=True)
        mock_copy_rates.return_value = sample_rates

        # 建立 fetcher（啟用 SQLite）
        fetcher = HistoricalDataFetcher(
            client=mock_mt5_client,
            cache_dir=temp_cache_dir,
            use_sqlite=True
        )

        # 第一次查詢（快取未命中）
        df = fetcher.get_candles_by_date(
            symbol='GOLD',
            timeframe='H1',
            from_date='2024-01-01',
            to_date='2024-01-05'
        )

        # 驗證數據正確
        assert len(df) > 0
        assert 'time' in df.columns

        # 驗證 MT5 API 被調用
        assert mock_copy_rates.called

    @patch('MetaTrader5.copy_rates_range')
    @patch('MetaTrader5.symbol_info')
    def test_get_candles_with_sqlite_cache_hit(
        self,
        mock_symbol_info,
        mock_copy_rates,
        mock_mt5_client,
        temp_cache_dir,
        sample_rates
    ):
        """測試：快取命中，直接從資料庫查詢"""
        # 設定 mock
        mock_symbol_info.return_value = Mock(visible=True)
        mock_copy_rates.return_value = sample_rates

        # 建立 fetcher
        fetcher = HistoricalDataFetcher(
            client=mock_mt5_client,
            cache_dir=temp_cache_dir,
            use_sqlite=True
        )

        # 第一次查詢（快取未命中）
        df1 = fetcher.get_candles_by_date(
            symbol='GOLD',
            timeframe='H1',
            from_date='2024-01-01',
            to_date='2024-01-05'
        )

        # 重置 mock 計數
        mock_copy_rates.reset_mock()

        # 第二次查詢（快取命中）
        df2 = fetcher.get_candles_by_date(
            symbol='GOLD',
            timeframe='H1',
            from_date='2024-01-01',
            to_date='2024-01-05'
        )

        # 驗證數據一致
        assert len(df2) == len(df1)

        # 驗證 MT5 API 未被調用（快取命中）
        assert not mock_copy_rates.called

    def test_fallback_to_file_cache(
        self,
        mock_mt5_client,
        temp_cache_dir
    ):
        """測試：停用 SQLite 時使用檔案快取"""
        fetcher = HistoricalDataFetcher(
            client=mock_mt5_client,
            cache_dir=temp_cache_dir,
            use_sqlite=False
        )

        # 驗證 SQLite 快取未初始化
        assert fetcher.sqlite_cache is None
        assert fetcher.use_sqlite is False
```

#### 執行步驟

```bash
# 執行整合測試
pytest tests/test_data_fetcher_sqlite.py -v

# 檢查覆蓋率
pytest tests/test_data_fetcher_sqlite.py --cov=src.core.data_fetcher --cov-report=html
```

#### 成功標準

**自動驗證：**
- [ ] 所有測試案例通過
- [ ] 快取命中/未命中邏輯正確
- [ ] 向下相容性正常

**手動驗證：**
- [ ] 測試涵蓋主要場景
- [ ] Mock 設定合理

---

## 階段三：數據缺口檢測與填補

### 概覽

實作數據缺口檢測演算法和自動填補機制，提供缺口警告和管理功能。

### 3.1 實作缺口檢測演算法

#### 目標

在 `SQLiteCacheManager` 中實作缺口檢測邏輯，能夠識別異常的時間間隔並記錄到 `data_gaps` 表。

#### 修改檔案：`src/core/sqlite_cache.py`

**變更內容**：

在 `SQLiteCacheManager` 類別中新增以下方法：

```python
    def detect_data_gaps(
        self,
        symbol: str,
        timeframe: str,
        min_gap_threshold: float = 1.5
    ) -> List[Dict]:
        """
        檢測數據缺口

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            min_gap_threshold: 最小缺口閾值（相對於正常間隔的倍數）

        回傳：
            缺口清單
        """
        logger.info(f"開始檢測數據缺口：{symbol} {timeframe}")

        conn = self._get_connection()

        try:
            # 1. 查詢所有時間戳（升序）
            query = """
                SELECT time
                FROM candles
                WHERE symbol = ? AND timeframe = ?
                ORDER BY time ASC
            """

            df = pd.read_sql_query(query, conn, params=(symbol, timeframe))

            if len(df) < 2:
                logger.info("數據筆數不足，無法檢測缺口")
                return []

            df['time'] = pd.to_datetime(df['time'], utc=True)

            # 2. 計算預期間隔
            expected_interval = self._get_timeframe_interval(timeframe)

            # 3. 計算實際間隔
            df['time_diff'] = df['time'].diff()

            # 4. 識別異常間隔
            threshold = expected_interval * min_gap_threshold
            gaps_df = df[df['time_diff'] > threshold].copy()

            # 5. 過濾合理的缺口（週末、假日等）
            filtered_gaps = []

            for idx, row in gaps_df.iterrows():
                gap_start = df.loc[idx - 1, 'time']
                gap_end = row['time']

                if not self._is_expected_gap(gap_start, gap_end, timeframe):
                    gap_duration_minutes = int(
                        row['time_diff'].total_seconds() / 60
                    )
                    expected_records = self._calculate_expected_records(
                        gap_start, gap_end, timeframe
                    )

                    gap_info = {
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'gap_start': gap_start,
                        'gap_end': gap_end,
                        'gap_duration_minutes': gap_duration_minutes,
                        'expected_records': expected_records
                    }

                    filtered_gaps.append(gap_info)

            # 6. 儲存缺口記錄
            if filtered_gaps:
                self._save_gaps(filtered_gaps)
                logger.info(f"檢測到 {len(filtered_gaps)} 個數據缺口")
            else:
                logger.info("未檢測到數據缺口")

            # 7. 更新元數據
            self._update_gap_metadata(symbol, timeframe, len(filtered_gaps))

            return filtered_gaps

        except Exception as e:
            logger.error(f"檢測數據缺口失敗：{e}")
            raise
        finally:
            conn.close()

    def _is_expected_gap(
        self,
        start: datetime,
        end: datetime,
        timeframe: str
    ) -> bool:
        """
        判斷缺口是否為預期的（週末、假日等）

        參數：
            start: 缺口開始時間
            end: 缺口結束時間
            timeframe: 時間週期

        回傳：
            True 如果是預期的缺口
        """
        # 檢查是否跨越週末（週五收盤到週一開盤）
        # 外匯市場：週五 21:00 UTC ~ 週日 21:00 UTC
        if start.weekday() == 4:  # 週五
            # 如果是週五晚上到週一早上，視為正常
            if end.weekday() == 0 and (end - start).days <= 3:
                return True

        # TODO: 整合假日日曆
        # 目前僅檢查週末

        return False

    def _calculate_expected_records(
        self,
        start: datetime,
        end: datetime,
        timeframe: str
    ) -> int:
        """
        計算預期應有的記錄數

        參數：
            start: 開始時間
            end: 結束時間
            timeframe: 時間週期

        回傳：
            預期記錄數
        """
        interval = self._get_timeframe_interval(timeframe)
        duration = end - start

        # 計算理論記錄數
        expected = int(duration / interval)

        return max(expected, 1)

    def _save_gaps(self, gaps: List[Dict]) -> None:
        """
        儲存缺口記錄到資料庫

        參數：
            gaps: 缺口資訊列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            insert_query = """
                INSERT OR IGNORE INTO data_gaps (
                    symbol, timeframe, gap_start, gap_end,
                    gap_duration_minutes, expected_records, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'detected')
            """

            for gap in gaps:
                cursor.execute(insert_query, (
                    gap['symbol'],
                    gap['timeframe'],
                    gap['gap_start'].strftime('%Y-%m-%d %H:%M:%S'),
                    gap['gap_end'].strftime('%Y-%m-%d %H:%M:%S'),
                    gap['gap_duration_minutes'],
                    gap['expected_records']
                ))

            conn.commit()

        except Exception as e:
            conn.rollback()
            logger.error(f"儲存缺口記錄失敗：{e}")
            raise
        finally:
            conn.close()

    def _update_gap_metadata(
        self,
        symbol: str,
        timeframe: str,
        gap_count: int
    ) -> None:
        """
        更新快取元數據的缺口統計

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            gap_count: 缺口數量
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            update_query = """
                UPDATE cache_metadata
                SET
                    has_gaps = ?,
                    gap_count = ?,
                    last_gap_check = CURRENT_TIMESTAMP
                WHERE symbol = ? AND timeframe = ?
            """

            cursor.execute(
                update_query,
                (1 if gap_count > 0 else 0, gap_count, symbol, timeframe)
            )

            conn.commit()

        except Exception as e:
            logger.error(f"更新缺口元數據失敗：{e}")
        finally:
            conn.close()

    def get_gaps(
        self,
        symbol: str,
        timeframe: str,
        status: Optional[str] = None
    ) -> pd.DataFrame:
        """
        查詢數據缺口

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            status: 缺口狀態篩選（detected, filling, filled, ignored）

        回傳：
            缺口資訊 DataFrame
        """
        conn = self._get_connection()

        try:
            query = """
                SELECT * FROM data_gaps
                WHERE symbol = ? AND timeframe = ?
            """

            params = [symbol, timeframe]

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY gap_start ASC"

            df = pd.read_sql_query(query, conn, params=params)

            # 轉換時間欄位
            if not df.empty:
                for col in ['gap_start', 'gap_end', 'detected_at', 'filled_at']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], utc=True)

            return df

        finally:
            conn.close()
```

#### 成功標準

**自動驗證：**
- [ ] 缺口檢測邏輯正確
- [ ] 週末過濾功能正常
- [ ] 缺口記錄成功儲存到資料庫

**手動驗證：**
- [ ] 演算法合理
- [ ] 閾值設定適當

---

### 3.2 實作缺口填補機制

#### 目標

實作自動填補缺口的功能，能夠從 MT5 取得缺口範圍的數據並更新資料庫。

#### 修改檔案：`src/core/sqlite_cache.py`

**變更內容**：

在 `SQLiteCacheManager` 類別中新增以下方法：

```python
    def fill_data_gaps(
        self,
        symbol: str,
        timeframe: str,
        fetcher_callback,
        status_filter: str = 'detected'
    ) -> int:
        """
        填補數據缺口

        參數：
            symbol: 商品代碼
            timeframe: 時間週期
            fetcher_callback: MT5 數據獲取回調函數
            status_filter: 要填補的缺口狀態

        回傳：
            成功填補的缺口數量
        """
        logger.info(f"開始填補數據缺口：{symbol} {timeframe}")

        # 查詢未填補的缺口
        gaps_df = self.get_gaps(symbol, timeframe, status=status_filter)

        if gaps_df.empty:
            logger.info("沒有需要填補的缺口")
            return 0

        filled_count = 0

        for _, gap in gaps_df.iterrows():
            gap_id = gap['id']
            gap_start = gap['gap_start']
            gap_end = gap['gap_end']

            try:
                logger.info(f"填補缺口 #{gap_id}：{gap_start} ~ {gap_end}")

                # 從 MT5 取得缺口範圍的數據
                df_new = fetcher_callback(
                    symbol, timeframe, gap_start, gap_end
                )

                if not df_new.empty:
                    # 插入數據
                    inserted_count = self.insert_candles(
                        df_new, symbol, timeframe
                    )

                    # 更新缺口狀態為 'filled'
                    self._update_gap_status(gap_id, 'filled')

                    filled_count += 1
                    logger.info(
                        f"缺口 #{gap_id} 填補完成，插入 {inserted_count} 筆數據"
                    )
                else:
                    logger.warning(f"缺口 #{gap_id} 無法取得數據")
                    self._update_gap_status(
                        gap_id, 'filling',
                        notes='MT5 未返回數據'
                    )

            except Exception as e:
                logger.error(f"填補缺口 #{gap_id} 失敗：{e}")
                self._update_gap_status(
                    gap_id, 'filling',
                    notes=str(e)
                )

        logger.info(f"缺口填補完成：成功 {filled_count}/{len(gaps_df)}")

        return filled_count

    def _update_gap_status(
        self,
        gap_id: int,
        status: str,
        notes: Optional[str] = None
    ) -> None:
        """
        更新缺口狀態

        參數：
            gap_id: 缺口 ID
            status: 新狀態
            notes: 備註
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if status == 'filled':
                update_query = """
                    UPDATE data_gaps
                    SET status = ?, filled_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """
                cursor.execute(update_query, (status, gap_id))
            else:
                update_query = """
                    UPDATE data_gaps
                    SET status = ?, notes = ?
                    WHERE id = ?
                """
                cursor.execute(update_query, (status, notes, gap_id))

            conn.commit()

        except Exception as e:
            logger.error(f"更新缺口狀態失敗：{e}")
        finally:
            conn.close()

    def ignore_gap(self, gap_id: int, notes: Optional[str] = None) -> None:
        """
        手動忽略特定缺口

        參數：
            gap_id: 缺口 ID
            notes: 忽略原因
        """
        self._update_gap_status(gap_id, 'ignored', notes)
        logger.info(f"缺口 #{gap_id} 已標記為忽略")
```

#### 成功標準

**自動驗證：**
- [ ] 缺口填補邏輯正確
- [ ] 狀態更新正常
- [ ] 錯誤處理完善

**手動驗證：**
- [ ] 填補流程合理
- [ ] 日誌記錄完整

---

### 3.3 缺口檢測與填補測試

#### 目標

撰寫缺口檢測和填補功能的單元測試。

#### 修改檔案：`tests/test_sqlite_cache.py`

**變更內容**：

在測試檔案中新增以下測試案例：

```python
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

        # 驗證檢測到缺口
        assert len(gaps) > 0
        assert gaps[0]['symbol'] == symbol
        assert gaps[0]['timeframe'] == timeframe

    def test_fill_gaps(self, cache_manager):
        """測試：填補缺口"""
        symbol = 'GOLD'
        timeframe = 'H1'

        # 建立有缺口的數據
        data1 = {
            'time': pd.date_range(
                '2024-01-01 00:00', periods=5, freq='h', tz='UTC'
            ),
            'open': [100.0] * 5,
            'high': [101.0] * 5,
            'low': [99.0] * 5,
            'close': [100.5] * 5,
            'tick_volume': [1000] * 5,
            'spread': [2] * 5,
            'real_volume': [5000] * 5
        }
        df1 = pd.DataFrame(data1)

        data2 = {
            'time': pd.date_range(
                '2024-01-01 10:00', periods=5, freq='h', tz='UTC'
            ),
            'open': [100.0] * 5,
            'high': [101.0] * 5,
            'low': [99.0] * 5,
            'close': [100.5] * 5,
            'tick_volume': [1000] * 5,
            'spread': [2] * 5,
            'real_volume': [5000] * 5
        }
        df2 = pd.DataFrame(data2)

        # 插入數據
        cache_manager.insert_candles(df1, symbol, timeframe)
        cache_manager.insert_candles(df2, symbol, timeframe)

        # 檢測缺口
        cache_manager.detect_data_gaps(symbol, timeframe)

        # 模擬填補回調函數
        def mock_fetcher(sym, tf, start, end):
            # 返回缺口範圍的數據
            gap_data = {
                'time': pd.date_range(
                    start, end, freq='h', tz='UTC'
                ),
                'open': [100.0] * 5,
                'high': [101.0] * 5,
                'low': [99.0] * 5,
                'close': [100.5] * 5,
                'tick_volume': [1000] * 5,
                'spread': [2] * 5,
                'real_volume': [5000] * 5
            }
            return pd.DataFrame(gap_data)

        # 填補缺口
        filled_count = cache_manager.fill_data_gaps(
            symbol, timeframe, mock_fetcher
        )

        # 驗證缺口已填補
        assert filled_count > 0

        # 驗證數據連續
        df_complete = cache_manager.query_candles(symbol, timeframe)
        assert len(df_complete) >= 15  # 原有 10 筆 + 填補 5 筆
```

#### 執行步驟

```bash
# 執行測試
pytest tests/test_sqlite_cache.py::TestGapDetectionAndFilling -v
```

#### 成功標準

**自動驗證：**
- [ ] 所有測試通過
- [ ] 缺口檢測正確
- [ ] 缺口填補正確

**手動驗證：**
- [ ] 測試邏輯合理

---

## 階段四：管理工具與文件

### 概覽

建立命令列快取管理工具，提供快取狀態查詢、缺口檢測和維護功能，並撰寫完整的使用文件。

### 4.1 建立命令列管理工具

#### 目標

建立 `manage_cache.py` 腳本，提供快取管理的命令列介面。

#### 新增檔案：`scripts/manage_cache.py`

**變更內容**：

```python
#!/usr/bin/env python3
"""
SQLite 快取管理命令列工具

使用方式：
    python scripts/manage_cache.py status
    python scripts/manage_cache.py check-gaps --symbol GOLD --timeframe H1
    python scripts/manage_cache.py fill-gaps --symbol GOLD --timeframe H1
    python scripts/manage_cache.py clear --symbol GOLD --timeframe H1
    python scripts/manage_cache.py optimize
"""

import sys
from pathlib import Path

# 新增專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from loguru import logger
from tabulate import tabulate

from src.core.sqlite_cache import SQLiteCacheManager
from src.core.mt5_client import ChipWhispererMT5Client
from src.core.mt5_config import MT5Config
from src.core.data_fetcher import HistoricalDataFetcher


@click.group()
@click.option(
    '--db-path',
    default='data/cache/mt5_cache.db',
    help='SQLite 資料庫路徑'
)
@click.pass_context
def cli(ctx, db_path):
    """SQLite 快取管理工具"""
    ctx.ensure_object(dict)
    ctx.obj['db_path'] = db_path
    ctx.obj['cache_manager'] = SQLiteCacheManager(db_path)


@cli.command()
@click.pass_context
def status(ctx):
    """顯示快取狀態"""
    manager = ctx.obj['cache_manager']

    # 查詢所有快取元數據
    conn = manager._get_connection()

    try:
        import pandas as pd

        query = "SELECT * FROM cache_metadata ORDER BY symbol, timeframe"
        df = pd.read_sql_query(query, conn)

        if df.empty:
            click.echo("快取為空")
            return

        # 格式化顯示
        df['first_time'] = pd.to_datetime(df['first_time']).dt.strftime('%Y-%m-%d')
        df['last_time'] = pd.to_datetime(df['last_time']).dt.strftime('%Y-%m-%d')
        df['last_update_time'] = pd.to_datetime(
            df['last_update_time']
        ).dt.strftime('%Y-%m-%d %H:%M')

        # 選擇要顯示的欄位
        display_df = df[[
            'symbol', 'timeframe', 'total_records',
            'first_time', 'last_time', 'has_gaps', 'gap_count'
        ]]

        click.echo("\n快取狀態摘要：\n")
        click.echo(tabulate(
            display_df.values,
            headers=display_df.columns,
            tablefmt='grid'
        ))

        # 統計資訊
        click.echo(f"\n總商品-週期組合數：{len(df)}")
        click.echo(f"總記錄數：{df['total_records'].sum()}")
        click.echo(f"有缺口的組合數：{df['has_gaps'].sum()}")

    finally:
        conn.close()


@cli.command()
@click.option('--symbol', required=True, help='商品代碼')
@click.option('--timeframe', required=True, help='時間週期')
@click.pass_context
def check_gaps(ctx, symbol, timeframe):
    """檢查數據缺口"""
    manager = ctx.obj['cache_manager']

    click.echo(f"\n檢查 {symbol} {timeframe} 的數據缺口...\n")

    # 執行缺口檢測
    gaps = manager.detect_data_gaps(symbol, timeframe)

    if not gaps:
        click.echo("未發現數據缺口")
        return

    click.echo(f"發現 {len(gaps)} 個數據缺口：\n")

    # 格式化顯示
    for i, gap in enumerate(gaps, 1):
        click.echo(f"{i}. {gap['gap_start']} ~ {gap['gap_end']}")
        click.echo(f"   時長：{gap['gap_duration_minutes']} 分鐘")
        click.echo(f"   預期記錄數：{gap['expected_records']}")
        click.echo()


@cli.command()
@click.option('--symbol', required=True, help='商品代碼')
@click.option('--timeframe', required=True, help='時間週期')
@click.option('--auto', is_flag=True, help='自動填補（不詢問）')
@click.pass_context
def fill_gaps(ctx, symbol, timeframe, auto):
    """填補數據缺口"""
    manager = ctx.obj['cache_manager']

    # 查詢未填補的缺口
    gaps_df = manager.get_gaps(symbol, timeframe, status='detected')

    if gaps_df.empty:
        click.echo("沒有需要填補的缺口")
        return

    click.echo(f"\n發現 {len(gaps_df)} 個未填補的缺口")

    # 顯示缺口清單
    for _, gap in gaps_df.iterrows():
        click.echo(
            f"  - {gap['gap_start']} ~ {gap['gap_end']} "
            f"(預期 {gap['expected_records']} 筆)"
        )

    # 確認是否填補
    if not auto:
        if not click.confirm('\n是否開始填補？'):
            click.echo("已取消")
            return

    # 建立 MT5 連線和 Fetcher
    try:
        config = MT5Config()
        client = ChipWhispererMT5Client(config)
        client.connect()

        fetcher = HistoricalDataFetcher(client, use_sqlite=False)

        # 定義回調函數
        def fetch_callback(sym, tf, start, end):
            return fetcher._fetch_from_mt5_by_date(sym, tf, start, end)

        # 執行填補
        click.echo("\n開始填補缺口...\n")
        filled_count = manager.fill_data_gaps(
            symbol, timeframe, fetch_callback
        )

        click.echo(f"\n填補完成：成功填補 {filled_count} 個缺口")

    except Exception as e:
        click.echo(f"\n錯誤：{e}", err=True)
    finally:
        if client.is_connected():
            client.disconnect()


@cli.command()
@click.option('--symbol', help='商品代碼（可選）')
@click.option('--timeframe', help='時間週期（可選）')
@click.option('--force', is_flag=True, help='強制清除（不詢問）')
@click.pass_context
def clear(ctx, symbol, timeframe, force):
    """清除快取數據"""
    manager = ctx.obj['cache_manager']

    # 確認訊息
    if symbol and timeframe:
        msg = f"清除 {symbol} {timeframe} 的所有快取數據"
    elif symbol:
        msg = f"清除 {symbol} 的所有快取數據"
    else:
        msg = "清除所有快取數據"

    click.echo(f"\n{msg}")

    if not force:
        if not click.confirm('確定要繼續嗎？'):
            click.echo("已取消")
            return

    # 執行清除
    deleted_count = manager.clear_cache(symbol, timeframe)
    click.echo(f"\n已刪除 {deleted_count} 筆記錄")


@cli.command()
@click.pass_context
def optimize(ctx):
    """優化資料庫"""
    db_path = ctx.obj['db_path']

    click.echo("\n開始資料庫優化...\n")

    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # ANALYZE
        click.echo("1/3 分析查詢計劃...")
        cursor.execute("ANALYZE")

        # REINDEX
        click.echo("2/3 重建索引...")
        cursor.execute("REINDEX")

        # VACUUM
        click.echo("3/3 清理碎片...")
        cursor.execute("VACUUM")

        conn.commit()
        click.echo("\n資料庫優化完成")

    except Exception as e:
        click.echo(f"\n優化失敗：{e}", err=True)
    finally:
        conn.close()


if __name__ == '__main__':
    cli()
```

#### 安裝依賴

```bash
# 安裝 click 和 tabulate
pip install click tabulate
```

#### 成功標準

**自動驗證：**
- [ ] 腳本可成功執行
- [ ] 所有命令正常運作

**手動驗證：**
- [ ] 命令列介面友好
- [ ] 輸出格式清晰

---

### 4.2 更新 requirements.txt

#### 目標

新增 SQLite 快取相關的依賴套件到 `requirements.txt`。

#### 修改檔案：`requirements.txt`

**變更內容**：

在現有內容後新增：

```txt
# SQLite 快取管理
click>=8.1.0
tabulate>=0.9.0
```

#### 執行步驟

```bash
# 安裝新增依賴
pip install -r requirements.txt
```

#### 成功標準

**自動驗證：**
- [ ] 所有套件安裝成功

---

### 4.3 撰寫使用文件

#### 目標

建立 SQLite 快取功能的使用文件。

#### 新增檔案：`docs/sqlite-cache-usage.md`

**變更內容**：

```markdown
# SQLite3 快取功能使用指南

## 概述

Chip Whisperer 提供基於 SQLite3 的數據快取系統，能夠：

- 高效儲存和查詢歷史 K 線數據
- 自動檢測並填補數據缺口
- 減少對 MT5 伺服器的請求次數
- 提供完整的快取管理工具

## 快速開始

### 啟用 SQLite 快取

在建立 `HistoricalDataFetcher` 時，設定 `use_sqlite=True`（預設已啟用）：

```python
from src.core.mt5_client import ChipWhispererMT5Client
from src.core.mt5_config import MT5Config
from src.core.data_fetcher import HistoricalDataFetcher

# 建立 MT5 客戶端
config = MT5Config()
client = ChipWhispererMT5Client(config)
client.connect()

# 建立資料取得器（啟用 SQLite 快取）
fetcher = HistoricalDataFetcher(client, use_sqlite=True)

# 第一次查詢：從 MT5 取得並儲存到快取
df = fetcher.get_candles_by_date(
    symbol='GOLD',
    timeframe='H1',
    from_date='2024-01-01',
    to_date='2024-01-31'
)

# 第二次查詢：直接從快取取得（快速）
df = fetcher.get_candles_by_date(
    symbol='GOLD',
    timeframe='H1',
    from_date='2024-01-01',
    to_date='2024-01-31'
)
```

### 停用 SQLite 快取

如需使用原有的檔案快取：

```python
fetcher = HistoricalDataFetcher(client, use_sqlite=False)
```

## 快取管理工具

### 查看快取狀態

```bash
python scripts/manage_cache.py status
```

輸出範例：

```
快取狀態摘要：

+--------+-----------+----------------+-------------+-------------+-----------+-----------+
| symbol | timeframe | total_records  | first_time  | last_time   | has_gaps  | gap_count |
+========+===========+================+=============+=============+===========+===========+
| GOLD   | H1        | 2400           | 2024-01-01  | 2024-03-31  | 1         | 3         |
| SILVER | H1        | 1800           | 2024-01-15  | 2024-03-31  | 0         | 0         |
+--------+-----------+----------------+-------------+-------------+-----------+-----------+

總商品-週期組合數：2
總記錄數：4200
有缺口的組合數：1
```

### 檢查數據缺口

```bash
python scripts/manage_cache.py check-gaps --symbol GOLD --timeframe H1
```

輸出範例：

```
檢查 GOLD H1 的數據缺口...

發現 3 個數據缺口：

1. 2024-01-15 10:00:00 ~ 2024-01-15 14:00:00
   時長：240 分鐘
   預期記錄數：4

2. 2024-02-10 08:00:00 ~ 2024-02-10 12:00:00
   時長：240 分鐘
   預期記錄數：4

3. 2024-03-05 16:00:00 ~ 2024-03-05 20:00:00
   時長：240 分鐘
   預期記錄數：4
```

### 填補數據缺口

```bash
# 互動式填補（會詢問確認）
python scripts/manage_cache.py fill-gaps --symbol GOLD --timeframe H1

# 自動填補（不詢問）
python scripts/manage_cache.py fill-gaps --symbol GOLD --timeframe H1 --auto
```

### 清除快取

```bash
# 清除特定商品和週期
python scripts/manage_cache.py clear --symbol GOLD --timeframe H1

# 清除特定商品的所有週期
python scripts/manage_cache.py clear --symbol GOLD

# 清除所有快取（危險！）
python scripts/manage_cache.py clear --force
```

### 優化資料庫

定期執行以維護效能：

```bash
python scripts/manage_cache.py optimize
```

## 進階使用

### 直接使用 SQLiteCacheManager

如需更細緻的控制，可直接使用 `SQLiteCacheManager`：

```python
from src.core.sqlite_cache import SQLiteCacheManager

# 初始化
cache = SQLiteCacheManager('data/cache/mt5_cache.db')

# 插入數據
cache.insert_candles(df, symbol='GOLD', timeframe='H1')

# 查詢數據
from datetime import datetime, timezone

df = cache.query_candles(
    symbol='GOLD',
    timeframe='H1',
    from_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    to_date=datetime(2024, 1, 31, tzinfo=timezone.utc)
)

# 檢測缺口
gaps = cache.detect_data_gaps('GOLD', 'H1')

# 填補缺口
def my_fetcher(symbol, timeframe, start, end):
    # 自定義數據獲取邏輯
    pass

filled_count = cache.fill_data_gaps('GOLD', 'H1', my_fetcher)
```

### 快取資訊查詢

```python
# 取得快取資訊
info = cache.get_cache_info('GOLD', 'H1')

if info:
    print(f"數據範圍：{info['first_time']} ~ {info['last_time']}")
    print(f"總記錄數：{info['total_records']}")
    print(f"有缺口：{info['has_gaps']}")
    print(f"缺口數量：{info['gap_count']}")
```

### 缺口管理

```python
# 查詢缺口
gaps_df = cache.get_gaps('GOLD', 'H1', status='detected')

# 手動忽略某個缺口
cache.ignore_gap(gap_id=1, notes='週末市場休市')
```

## 資料庫結構

SQLite 快取使用以下資料表：

### 1. candles（K 線數據表）

儲存所有 K 線數據。

**主要欄位**：
- `symbol`: 商品代碼
- `timeframe`: 時間週期
- `time`: K 線時間（UTC）
- `open`, `high`, `low`, `close`: OHLC 價格
- `tick_volume`, `spread`, `real_volume`: 成交量資訊

### 2. cache_metadata（快取元數據表）

記錄每個商品-週期組合的快取狀態。

**主要欄位**：
- `symbol`, `timeframe`: 識別鍵
- `first_time`, `last_time`: 數據時間範圍
- `total_records`: 記錄數
- `has_gaps`: 是否有缺口
- `gap_count`: 缺口數量

### 3. data_gaps（數據缺口表）

記錄檢測到的所有數據缺口。

**主要欄位**：
- `symbol`, `timeframe`: 識別鍵
- `gap_start`, `gap_end`: 缺口時間範圍
- `status`: 狀態（detected, filling, filled, ignored）
- `expected_records`: 預期記錄數

### 4. indicator_cache（指標快取表）

預留未來使用，目前未啟用。

## 效能建議

### 定期維護

建議每週執行一次資料庫優化：

```bash
python scripts/manage_cache.py optimize
```

### 清理舊數據

如需釋放磁碟空間，可清理過舊的數據：

```python
# 僅保留最近 1 年的數據（範例）
from datetime import datetime, timedelta

cutoff_date = datetime.now() - timedelta(days=365)

# 手動刪除（需自行實作）
```

### 批次插入

插入大量數據時，SQLite 會自動使用批次處理，無需額外設定。

## 故障排除

### 問題：資料庫鎖定錯誤

**原因**：多個程序同時寫入資料庫。

**解決**：
- SQLite 已啟用 WAL 模式，支援並發讀取
- 避免多個程序同時寫入
- 確保程序正確關閉連線

### 問題：缺口檢測過於敏感

**原因**：閾值設定過小。

**解決**：

```python
# 調整缺口檢測閾值（預設 1.5）
gaps = cache.detect_data_gaps(
    'GOLD', 'H1',
    min_gap_threshold=2.0  # 增加閾值
)
```

### 問題：填補缺口失敗

**原因**：MT5 無法提供缺口範圍的數據。

**解決**：
- 檢查 MT5 連線狀態
- 確認商品和時間範圍有效
- 手動標記為忽略：

```python
cache.ignore_gap(gap_id=1, notes='MT5 無數據')
```

## 參考資料

- [SQLite3 官方文件](https://www.sqlite.org/docs.html)
- [研究報告](../thoughts/shared/research/2024-12-30-fetch-data-sqlite-cache-analysis.md)
- [實作計劃](../thoughts/shared/plan/2024-12-30-sqlite-cache-implementation-plan.md)
```

#### 成功標準

**手動驗證：**
- [ ] 文件內容完整
- [ ] 範例程式碼正確
- [ ] 格式清晰易讀

---

## 總結與下一步

### 實作摘要

本計劃詳細規劃了 SQLite3 快取功能的完整實作，包括：

1. **階段一**：資料庫設計與核心類別
   - 4 張資料表結構
   - `SQLiteCacheManager` 核心功能
   - 基本 CRUD 操作

2. **階段二**：整合與智能數據流程
   - 智能查詢（快取命中/未命中處理）
   - 整合到 `HistoricalDataFetcher`
   - 向下相容性保證

3. **階段三**：數據缺口檢測與填補
   - 缺口檢測演算法
   - 自動填補機制
   - 週末過濾功能

4. **階段四**：管理工具與文件
   - 命令列管理工具
   - 完整使用文件

### 技術亮點

1. **智能快取策略**
   - 優先從快取讀取
   - 自動識別缺失範圍
   - 按需從 MT5 補充

2. **數據品質保證**
   - 自動缺口檢測
   - 一鍵填補功能
   - 週末/假日過濾

3. **效能優化**
   - WAL 模式支援並發
   - 批次插入提升寫入效能
   - 索引優化查詢速度

4. **易用性**
   - 向下相容
   - 命令列工具
   - 完整文件

### 實作檢查清單

#### 階段一檢查點
- [ ] schema.sql 建立完成
- [ ] SQLiteCacheManager 實作完成
- [ ] 基本單元測試通過

#### 階段二檢查點
- [ ] 智能查詢功能實作完成
- [ ] HistoricalDataFetcher 整合完成
- [ ] 整合測試通過

#### 階段三檢查點
- [ ] 缺口檢測功能完成
- [ ] 缺口填補功能完成
- [ ] 相關測試通過

#### 階段四檢查點
- [ ] 命令列工具建立完成
- [ ] requirements.txt 更新完成
- [ ] 使用文件撰寫完成

### 後續優化方向

#### 第二階段功能（未來）

1. **指標計算結果快取**
   - 啟用 `indicator_cache` 表
   - 快取常用指標計算結果
   - 減少重複計算

2. **假日日曆整合**
   - 建立 `market_holidays` 表
   - 整合第三方假日 API
   - 更精確的缺口過濾

3. **多資料庫檔案支援**
   - 按年份分檔
   - 自動歸檔舊數據
   - 管理磁碟空間

4. **數據匯入/匯出工具**
   - 從 CSV 匯入歷史數據
   - 匯出為標準格式
   - 資料庫遷移工具

#### 效能監控

建議新增效能監控指標：

- 快取命中率
- 平均查詢時間
- 資料庫檔案大小
- 缺口檢測耗時

### 風險與注意事項

1. **資料庫大小管理**
   - 定期檢查檔案大小
   - 必要時清理舊數據
   - 執行 VACUUM 壓縮

2. **並發控制**
   - WAL 模式已啟用
   - 避免多程序同時寫入
   - 正確關閉連線

3. **數據一致性**
   - 使用交易確保原子性
   - 完整的錯誤處理
   - 定期備份資料庫

4. **測試覆蓋**
   - 單元測試覆蓋率 >= 80%
   - 整合測試涵蓋主要場景
   - 邊界情況測試

---

## 附錄

### A. 資料表 DDL

完整的資料表定義請參考：`src/core/schema.sql`

### B. API 參考

#### SQLiteCacheManager 主要方法

| 方法 | 說明 |
|------|------|
| `__init__(db_path)` | 初始化快取管理器 |
| `insert_candles(df, symbol, timeframe)` | 插入 K 線數據 |
| `query_candles(symbol, timeframe, from_date, to_date)` | 查詢 K 線數據 |
| `get_cache_info(symbol, timeframe)` | 取得快取資訊 |
| `detect_data_gaps(symbol, timeframe)` | 檢測數據缺口 |
| `fill_data_gaps(symbol, timeframe, fetcher_callback)` | 填補數據缺口 |
| `get_gaps(symbol, timeframe, status)` | 查詢缺口記錄 |
| `clear_cache(symbol, timeframe)` | 清除快取 |

### C. 時間週期對應表

| 週期代碼 | 分鐘數 | 說明 |
|---------|-------|------|
| M1 | 1 | 1 分鐘 |
| M5 | 5 | 5 分鐘 |
| M15 | 15 | 15 分鐘 |
| M30 | 30 | 30 分鐘 |
| H1 | 60 | 1 小時 |
| H4 | 240 | 4 小時 |
| D1 | 1440 | 日線 |
| W1 | 10080 | 週線 |
| MN1 | 43200 | 月線 |

### D. 缺口狀態說明

| 狀態 | 說明 |
|-----|------|
| detected | 已檢測到，待處理 |
| filling | 填補中或部分失敗 |
| filled | 已成功填補 |
| ignored | 手動標記忽略 |

---

**計劃完成日期**：2024-12-30
**計劃制定者**：Claude (Sonnet 4.5)
**基於研究**：`thoughts/shared/research/2024-12-30-fetch-data-sqlite-cache-analysis.md`
**目標版本**：Chip Whisperer v1.1.0

本實作計劃提供了完整的技術規格、實作步驟和驗證標準，可直接作為開發參考使用。
