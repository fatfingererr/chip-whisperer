"""
歷史資料取得模組

此模組提供從 MT5 取得歷史 K 線資料的功能，支援多種查詢模式和資料快取。
"""

from typing import Optional, Dict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import MetaTrader5 as mt5
import pandas as pd
from loguru import logger

from .mt5_client import ChipWhispererMT5Client


class HistoricalDataFetcher:
    """
    歷史 K 線資料取得器

    提供多種方式取得和管理歷史 K 線資料，包括快取功能。
    """

    # MT5 時間週期對應表
    TIMEFRAME_MAP = {
        'M1': mt5.TIMEFRAME_M1,      # 1 分鐘
        'M2': mt5.TIMEFRAME_M2,      # 2 分鐘
        'M3': mt5.TIMEFRAME_M3,      # 3 分鐘
        'M4': mt5.TIMEFRAME_M4,      # 4 分鐘
        'M5': mt5.TIMEFRAME_M5,      # 5 分鐘
        'M6': mt5.TIMEFRAME_M6,      # 6 分鐘
        'M10': mt5.TIMEFRAME_M10,    # 10 分鐘
        'M12': mt5.TIMEFRAME_M12,    # 12 分鐘
        'M15': mt5.TIMEFRAME_M15,    # 15 分鐘
        'M20': mt5.TIMEFRAME_M20,    # 20 分鐘
        'M30': mt5.TIMEFRAME_M30,    # 30 分鐘
        'H1': mt5.TIMEFRAME_H1,      # 1 小時
        'H2': mt5.TIMEFRAME_H2,      # 2 小時
        'H3': mt5.TIMEFRAME_H3,      # 3 小時
        'H4': mt5.TIMEFRAME_H4,      # 4 小時
        'H6': mt5.TIMEFRAME_H6,      # 6 小時
        'H8': mt5.TIMEFRAME_H8,      # 8 小時
        'H12': mt5.TIMEFRAME_H12,    # 12 小時
        'D1': mt5.TIMEFRAME_D1,      # 日線
        'W1': mt5.TIMEFRAME_W1,      # 週線
        'MN1': mt5.TIMEFRAME_MN1,    # 月線
    }

    def __init__(self, client: ChipWhispererMT5Client, cache_dir: Optional[str] = None):
        """
        初始化資料取得器

        參數：
            client: MT5 客戶端實例
            cache_dir: 快取目錄路徑（可選）
        """
        self.client = client
        self.cache_dir = Path(cache_dir) if cache_dir else Path('data/cache')

        # 建立快取目錄
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"資料快取目錄：{self.cache_dir}")

    def _get_timeframe_constant(self, timeframe: str) -> int:
        """
        取得 MT5 時間週期常數

        參數：
            timeframe: 時間週期字串（例如 'H1', 'D1'）

        回傳：
            MT5 時間週期常數

        例外：
            ValueError: 時間週期無效時
        """
        tf_upper = timeframe.upper()
        if tf_upper not in self.TIMEFRAME_MAP:
            raise ValueError(
                f"無效的時間週期：{timeframe}，"
                f"支援的時間週期：{', '.join(self.TIMEFRAME_MAP.keys())}"
            )
        return self.TIMEFRAME_MAP[tf_upper]

    def _parse_date(self, date_str: str, is_end_date: bool = False) -> datetime:
        """
        解析日期字串

        參數：
            date_str: 日期字串（格式：'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'）
            is_end_date: 是否為結束日期（會自動補齊為當天 23:59:59）

        回傳：
            datetime 物件（UTC 時區）

        例外：
            ValueError: 日期格式錯誤時
        """
        # 支援的日期格式
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d'
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)

                # 如果只有日期部分，補齊時間
                if fmt == '%Y-%m-%d':
                    if is_end_date:
                        dt = dt.replace(hour=23, minute=59, second=59)
                    else:
                        dt = dt.replace(hour=0, minute=0, second=0)

                # 設定為 UTC 時區
                return dt.replace(tzinfo=timezone.utc)

            except ValueError:
                continue

        raise ValueError(f"無效的日期格式：{date_str}，支援格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")

    def _verify_symbol(self, symbol: str) -> bool:
        """
        驗證商品是否存在

        參數：
            symbol: 商品代碼

        回傳：
            True 如果商品存在

        例外：
            ValueError: 商品不存在時
        """
        self.client.ensure_connected()

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise ValueError(f"商品不存在：{symbol}")

        # 確保商品可見
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                raise ValueError(f"無法啟用商品：{symbol}")
            logger.debug(f"已啟用商品：{symbol}")

        return True

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

        # 驗證參數
        self._verify_symbol(symbol)
        tf_constant = self._get_timeframe_constant(timeframe)

        # 確保已連線
        self.client.ensure_connected()

        # 從 MT5 取得資料
        rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, count)

        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            raise RuntimeError(f"取得 K 線資料失敗：{error}")

        # 轉換為 DataFrame
        df = pd.DataFrame(rates)

        # 處理時間欄位（轉換為 datetime，UTC 時區）
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

        # 按時間排序（最新的在前）
        df = df.sort_values('time', ascending=False).reset_index(drop=True)

        logger.info(f"成功取得 {len(df)} 根 K 線")
        return df

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

        # 驗證參數
        self._verify_symbol(symbol)
        tf_constant = self._get_timeframe_constant(timeframe)

        # 確保已連線
        self.client.ensure_connected()

        # 解析日期
        from_datetime = None
        to_datetime = None

        if from_date:
            from_datetime = self._parse_date(from_date, is_end_date=False)

        if to_date:
            to_datetime = self._parse_date(to_date, is_end_date=True)

        # 確保日期順序正確
        if from_datetime and to_datetime and from_datetime > to_datetime:
            logger.warning("起始日期晚於結束日期，已自動交換")
            from_datetime, to_datetime = to_datetime, from_datetime

        # 根據參數選擇適當的 MT5 API
        rates = None

        if from_datetime and to_datetime:
            # 兩個日期都提供：使用範圍查詢
            logger.debug(f"使用範圍查詢：{from_datetime} ~ {to_datetime}")
            rates = mt5.copy_rates_range(symbol, tf_constant, from_datetime, to_datetime)

        elif from_datetime:
            # 只有起始日期：從該日期開始取得指定數量
            logger.debug(f"從 {from_datetime} 開始取得 {default_count} 根")
            rates = mt5.copy_rates_from(symbol, tf_constant, from_datetime, default_count)

        elif to_datetime:
            # 只有結束日期：往前推 30 天
            lookback_days = 30
            start_date = to_datetime - timedelta(days=lookback_days)
            logger.debug(f"使用範圍查詢（往前推 {lookback_days} 天）：{start_date} ~ {to_datetime}")
            rates = mt5.copy_rates_range(symbol, tf_constant, start_date, to_datetime)

        else:
            # 沒有日期：取得最新資料
            logger.debug(f"取得最新 {default_count} 根")
            rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, default_count)

        # 驗證資料
        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            raise RuntimeError(f"取得 K 線資料失敗：{error}")

        # 轉換為 DataFrame
        df = pd.DataFrame(rates)

        # 處理時間欄位
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

        # 按時間排序（最新的在前）
        df = df.sort_values('time', ascending=False).reset_index(drop=True)

        logger.info(f"成功取得 {len(df)} 根 K 線")
        return df

    def save_to_cache(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        file_format: str = 'csv'
    ) -> Path:
        """
        將資料儲存到快取

        參數：
            df: K 線資料 DataFrame
            symbol: 商品代碼
            timeframe: 時間週期
            file_format: 檔案格式（'csv' 或 'parquet'）

        回傳：
            儲存的檔案路徑

        例外：
            ValueError: 不支援的檔案格式
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{symbol}_{timeframe}_{timestamp}.{file_format}"
        filepath = self.cache_dir / filename

        if file_format == 'csv':
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
        elif file_format == 'parquet':
            df.to_parquet(filepath, index=False)
        else:
            raise ValueError(f"不支援的檔案格式：{file_format}，請使用 'csv' 或 'parquet'")

        logger.info(f"資料已儲存到快取：{filepath}")
        return filepath

    def load_from_cache(self, filepath: str) -> pd.DataFrame:
        """
        從快取載入資料

        參數：
            filepath: 快取檔案路徑

        回傳：
            K 線資料 DataFrame

        例外：
            FileNotFoundError: 檔案不存在時
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"快取檔案不存在：{filepath}")

        if filepath.suffix == '.csv':
            df = pd.read_csv(filepath)
            # 確保時間欄位為 datetime
            df['time'] = pd.to_datetime(df['time'], utc=True)
        elif filepath.suffix == '.parquet':
            df = pd.read_parquet(filepath)
        else:
            raise ValueError(f"不支援的檔案格式：{filepath.suffix}")

        logger.info(f"已從快取載入 {len(df)} 根 K 線：{filepath}")
        return df
