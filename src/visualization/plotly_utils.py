"""
Plotly 輔助工具函數
"""

import pandas as pd
import numpy as np
from loguru import logger

from .chart_config import COLORS


def map_idx_to_time(idx: int, df: pd.DataFrame) -> pd.Timestamp:
    """
    將整數索引映射到時間戳

    參數：
        idx: K 線索引（整數位置）
        df: K 線 DataFrame

    回傳：
        對應的時間戳

    例外：
        IndexError: 索引超出範圍時
    """
    if idx < 0 or idx >= len(df):
        raise IndexError(f"索引 {idx} 超出範圍（0-{len(df)-1}）")

    return df.iloc[idx]['time']


def validate_vppa_json(vppa_json: dict) -> None:
    """
    驗證 VPPA JSON 資料格式

    參數：
        vppa_json: VPPA 分析結果的 JSON 字典

    例外：
        ValueError: 缺少必要欄位時
    """
    required_keys = ['symbol', 'timeframe', 'pivot_ranges', 'pivot_points']
    for key in required_keys:
        if key not in vppa_json:
            raise ValueError(f"VPPA JSON 缺少必要欄位：{key}")

    logger.info(f"VPPA JSON 驗證通過：{vppa_json['symbol']} {vppa_json['timeframe']}")


def validate_candles_df(df: pd.DataFrame) -> None:
    """
    驗證 K 線 DataFrame 格式

    參數：
        df: K 線 DataFrame

    例外：
        ValueError: 缺少必要欄位或資料為空時
    """
    required_columns = ['time', 'open', 'high', 'low', 'close']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"K 線 DataFrame 缺少必要欄位：{missing}")

    if len(df) == 0:
        raise ValueError("K 線 DataFrame 不能為空")

    logger.info(f"K 線 DataFrame 驗證通過：{len(df)} 筆資料")


def normalize_volume_width(
    volumes: np.ndarray,
    max_width_bars: int = 10,
    timeframe: str = 'M1'
) -> np.ndarray:
    """
    正規化 Volume Profile 的成交量寬度

    參數：
        volumes: 原始成交量陣列
        max_width_bars: Volume Profile 最大寬度（以 K 線數量為單位）
        timeframe: 時間週期（用於計算時間差）

    回傳：
        正規化後的寬度陣列（單位：分鐘）
    """
    max_volume = volumes.max()
    if max_volume == 0:
        logger.warning("成交量最大值為 0，無法正規化")
        return np.zeros_like(volumes)

    # 將最大成交量映射到 max_width_bars 根 K 線的寬度
    # M1 = 1 分鐘一根
    timeframe_minutes = {
        'M1': 1,
        'M5': 5,
        'M15': 15,
        'M30': 30,
        'H1': 60,
        'H4': 240,
        'D1': 1440
    }

    minutes_per_bar = timeframe_minutes.get(timeframe, 1)
    max_width_minutes = max_width_bars * minutes_per_bar

    normalized = (volumes / max_volume) * max_width_minutes

    logger.debug(
        f"成交量正規化完成：最大值 {max_volume:.0f} -> {max_width_minutes} 分鐘"
    )

    return normalized


def get_volume_colors(
    price_centers: np.ndarray,
    vah: float,
    val: float
) -> list:
    """
    根據價格是否在 Value Area 內，回傳對應的顏色陣列

    參數：
        price_centers: 每層的中心價格
        vah: Value Area High
        val: Value Area Low

    回傳：
        顏色字串列表
    """
    colors = []
    for price in price_centers:
        if val <= price <= vah:
            colors.append(COLORS['volume_in_va'])   # Value Area 內：藍色
        else:
            colors.append(COLORS['volume_out_va'])  # Value Area 外：灰色

    return colors
