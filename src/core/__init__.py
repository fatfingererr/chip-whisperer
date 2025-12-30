"""
Chip Whisperer 核心模組

此套件包含 MT5 整合的核心功能：
- MT5Config: 設定管理
- ChipWhispererMT5Client: MT5 客戶端封裝
- HistoricalDataFetcher: 歷史資料取得器
"""

from .mt5_config import MT5Config
from .mt5_client import ChipWhispererMT5Client
from .data_fetcher import HistoricalDataFetcher

__all__ = [
    'MT5Config',
    'ChipWhispererMT5Client',
    'HistoricalDataFetcher',
]

__version__ = '0.1.0'
