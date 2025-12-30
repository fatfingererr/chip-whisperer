"""
技術指標計算模組

此模組提供各種技術指標的計算功能，可被 Agent 工具調用。
"""

from typing import Dict, Tuple
import numpy as np
import pandas as pd
from loguru import logger


def calculate_volume_profile(
    df: pd.DataFrame,
    price_bins: int = 100
) -> Tuple[pd.DataFrame, Dict]:
    """
    計算 Volume Profile

    參數：
        df: K 線資料 DataFrame（必須包含 'high', 'low', 'real_volume' 欄位）
        price_bins: 價格區間數量（預設 100）

    回傳：
        (profile_df, metrics) 元組
        - profile_df: Volume Profile DataFrame，包含 'price' 和 'volume' 欄位
        - metrics: 包含 POC、VAH、VAL 的字典

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    logger.info(f"開始計算 Volume Profile（價格區間數：{price_bins}）")

    # 驗證輸入資料
    required_columns = ['high', 'low', 'real_volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    if len(df) == 0:
        raise ValueError("輸入資料為空")

    # 1. 確定價格範圍
    price_min = df['low'].min()
    price_max = df['high'].max()
    logger.debug(f"價格範圍：{price_min:.2f} ~ {price_max:.2f}")

    # 2. 建立價格區間
    price_edges = np.linspace(price_min, price_max, price_bins + 1)
    price_centers = (price_edges[:-1] + price_edges[1:]) / 2

    # 3. 計算每個價格區間的成交量
    volumes = np.zeros(price_bins)

    for _, row in df.iterrows():
        # 找出此 K 線涵蓋的價格區間
        low_idx = np.searchsorted(price_edges, row['low'], side='left')
        high_idx = np.searchsorted(price_edges, row['high'], side='right') - 1

        # 確保索引在有效範圍內
        low_idx = max(0, min(low_idx, price_bins - 1))
        high_idx = max(0, min(high_idx, price_bins - 1))

        # 將成交量分配到涵蓋的價格區間
        span = high_idx - low_idx + 1
        if span > 0:
            volume_per_bin = row['real_volume'] / span
            volumes[low_idx:high_idx + 1] += volume_per_bin

    # 4. 建立 Volume Profile DataFrame
    profile_df = pd.DataFrame({
        'price': price_centers,
        'volume': volumes
    })

    # 按成交量排序
    profile_df_sorted_by_volume = profile_df.sort_values('volume', ascending=False)

    # 5. 計算 POC (Point of Control) - 成交量最大的價位
    poc_price = profile_df_sorted_by_volume.iloc[0]['price']
    poc_volume = profile_df_sorted_by_volume.iloc[0]['volume']

    logger.info(f"POC (Point of Control)：{poc_price:.2f}，成交量：{poc_volume:.0f}")

    # 6. 計算 Value Area (70% 成交量區間)
    total_volume = volumes.sum()
    target_volume = total_volume * 0.70

    # 從 POC 開始向兩側擴展，直到達到 70% 成交量
    profile_df_sorted_by_price = profile_df.sort_values('price')
    poc_idx = profile_df_sorted_by_price[
        profile_df_sorted_by_price['price'] == poc_price
    ].index[0]

    # 初始化 Value Area
    value_area_volume = poc_volume
    lower_idx = poc_idx
    upper_idx = poc_idx

    # 向兩側擴展
    while value_area_volume < target_volume:
        # 檢查是否還有空間擴展
        can_expand_lower = lower_idx > 0
        can_expand_upper = upper_idx < len(profile_df_sorted_by_price) - 1

        if not can_expand_lower and not can_expand_upper:
            break

        # 選擇成交量較大的一側擴展
        lower_volume = (
            profile_df_sorted_by_price.iloc[lower_idx - 1]['volume']
            if can_expand_lower else 0
        )
        upper_volume = (
            profile_df_sorted_by_price.iloc[upper_idx + 1]['volume']
            if can_expand_upper else 0
        )

        if lower_volume > upper_volume and can_expand_lower:
            lower_idx -= 1
            value_area_volume += lower_volume
        elif can_expand_upper:
            upper_idx += 1
            value_area_volume += upper_volume

    # Value Area High (VAH) 和 Low (VAL)
    vah = profile_df_sorted_by_price.iloc[upper_idx]['price']
    val = profile_df_sorted_by_price.iloc[lower_idx]['price']

    logger.info(f"Value Area High (VAH)：{vah:.2f}")
    logger.info(f"Value Area Low (VAL)：{val:.2f}")
    logger.info(
        f"Value Area 成交量：{value_area_volume:.0f} "
        f"({value_area_volume/total_volume*100:.1f}%)"
    )

    # 7. 整理結果
    metrics = {
        'poc_price': float(poc_price),
        'poc_volume': float(poc_volume),
        'vah': float(vah),
        'val': float(val),
        'value_area_volume': float(value_area_volume),
        'total_volume': float(total_volume),
        'value_area_percentage': float(value_area_volume / total_volume * 100)
    }

    return profile_df, metrics


def calculate_sma(df: pd.DataFrame, window: int = 20, column: str = 'close') -> pd.Series:
    """
    計算簡單移動平均線 (Simple Moving Average)

    參數：
        df: K 線資料 DataFrame
        window: 移動平均視窗大小（預設 20）
        column: 用於計算的欄位名稱（預設 'close'）

    回傳：
        包含 SMA 值的 Series

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    if column not in df.columns:
        raise ValueError(f"DataFrame 中缺少欄位：{column}")

    if len(df) < window:
        raise ValueError(f"資料筆數（{len(df)}）少於視窗大小（{window}）")

    logger.info(f"計算 SMA（視窗大小：{window}）")
    sma = df[column].rolling(window=window).mean()

    return sma


def calculate_rsi(df: pd.DataFrame, window: int = 14, column: str = 'close') -> pd.Series:
    """
    計算相對強弱指標 (Relative Strength Index)

    參數：
        df: K 線資料 DataFrame
        window: RSI 視窗大小（預設 14）
        column: 用於計算的欄位名稱（預設 'close'）

    回傳：
        包含 RSI 值的 Series（範圍 0-100）

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    if column not in df.columns:
        raise ValueError(f"DataFrame 中缺少欄位：{column}")

    if len(df) < window + 1:
        raise ValueError(f"資料筆數（{len(df)}）不足以計算 RSI（需要至少 {window + 1} 筆）")

    logger.info(f"計算 RSI（視窗大小：{window}）")

    # 計算價格變動
    delta = df[column].diff()

    # 分離漲跌
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # 計算平均漲跌
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    # 計算 RS 和 RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_bollinger_bands(
    df: pd.DataFrame,
    window: int = 20,
    num_std: float = 2.0,
    column: str = 'close'
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    計算布林通道 (Bollinger Bands)

    參數：
        df: K 線資料 DataFrame
        window: 移動平均視窗大小（預設 20）
        num_std: 標準差倍數（預設 2.0）
        column: 用於計算的欄位名稱（預設 'close'）

    回傳：
        (upper_band, middle_band, lower_band) 元組

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    if column not in df.columns:
        raise ValueError(f"DataFrame 中缺少欄位：{column}")

    if len(df) < window:
        raise ValueError(f"資料筆數（{len(df)}）少於視窗大小（{window}）")

    logger.info(f"計算布林通道（視窗：{window}，標準差倍數：{num_std}）")

    # 中軌 = SMA
    middle_band = df[column].rolling(window=window).mean()

    # 計算標準差
    std = df[column].rolling(window=window).std()

    # 上軌和下軌
    upper_band = middle_band + (std * num_std)
    lower_band = middle_band - (std * num_std)

    return upper_band, middle_band, lower_band
