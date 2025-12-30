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

    def get_oldest_time(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[datetime]:
        """
        取得指定商品和週期的最早數據時間

        參數：
            symbol: 商品代碼
            timeframe: 時間週期

        回傳：
            最早的時間戳，若無數據則回傳 None
        """
        conn = self._get_connection()

        try:
            query = """
                SELECT MIN(time) as oldest_time
                FROM candles
                WHERE symbol = ? AND timeframe = ?
            """

            cursor = conn.cursor()
            cursor.execute(query, (symbol, timeframe))
            row = cursor.fetchone()

            if row and row['oldest_time']:
                # 轉換為 datetime（UTC）
                oldest_str = row['oldest_time']
                if isinstance(oldest_str, str):
                    return datetime.fromisoformat(oldest_str.replace('Z', '+00:00'))
                elif isinstance(oldest_str, datetime):
                    return oldest_str.replace(tzinfo=timezone.utc)
                else:
                    return None
            else:
                return None

        finally:
            conn.close()

    def get_newest_time(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[datetime]:
        """
        取得指定商品和週期的最新數據時間

        參數：
            symbol: 商品代碼
            timeframe: 時間週期

        回傳：
            最新的時間戳，若無數據則回傳 None
        """
        conn = self._get_connection()

        try:
            query = """
                SELECT MAX(time) as newest_time
                FROM candles
                WHERE symbol = ? AND timeframe = ?
            """

            cursor = conn.cursor()
            cursor.execute(query, (symbol, timeframe))
            row = cursor.fetchone()

            if row and row['newest_time']:
                # 轉換為 datetime（UTC）
                newest_str = row['newest_time']
                if isinstance(newest_str, str):
                    return datetime.fromisoformat(newest_str.replace('Z', '+00:00'))
                elif isinstance(newest_str, datetime):
                    return newest_str.replace(tzinfo=timezone.utc)
                else:
                    return None
            else:
                return None

        finally:
            conn.close()

    def get_record_count(
        self,
        symbol: str,
        timeframe: str
    ) -> int:
        """
        取得指定商品和週期的數據筆數

        參數：
            symbol: 商品代碼
            timeframe: 時間週期

        回傳：
            數據筆數
        """
        conn = self._get_connection()

        try:
            query = """
                SELECT COUNT(*) as count
                FROM candles
                WHERE symbol = ? AND timeframe = ?
            """

            cursor = conn.cursor()
            cursor.execute(query, (symbol, timeframe))
            row = cursor.fetchone()

            return row['count'] if row else 0

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

    # ========================================================================
    # Phase 2: Smart Query Functions
    # ========================================================================

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

    # ========================================================================
    # Phase 3: Gap Detection and Filling
    # ========================================================================

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
