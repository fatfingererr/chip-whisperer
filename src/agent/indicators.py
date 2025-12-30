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
    計算整個資料集的 Volume Profile

    注意：此函數計算整個 DataFrame 的 Volume Profile。
    如果需要計算特定區間的 Volume Profile（例如 Pivot Point 之間的區間），
    請使用 calculate_volume_profile_for_range() 函數。

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


def find_pivot_points(
    df: pd.DataFrame,
    length: int = 20
) -> pd.DataFrame:
    """
    偵測 Pivot High 和 Pivot Low

    Pivot High：中心點的 high 價格高於左右各 length 根 K 線
    Pivot Low：中心點的 low 價格低於左右各 length 根 K 線

    參數：
        df: K 線資料 DataFrame（必須包含 'high' 和 'low' 欄位）
        length: 左右觀察窗口大小（預設 20）

    回傳：
        添加 'pivot_high' 和 'pivot_low' 欄位的 DataFrame 副本
        - pivot_high: Pivot High 的價格，非 Pivot High 位置為 NaN
        - pivot_low: Pivot Low 的價格，非 Pivot Low 位置為 NaN

    例外：
        ValueError: 輸入資料格式錯誤或資料量不足時

    注意：
        - Pivot Point 的確認需要右側 length 根 K 線，因此最後 length 根 K 線無法確認
        - 這是符合交易實務的延遲特性
    """
    logger.info(f"開始偵測 Pivot Points（左右窗口：{length}）")

    # 驗證輸入
    required_columns = ['high', 'low']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    if len(df) < length * 2 + 1:
        raise ValueError(
            f"資料筆數（{len(df)}）不足以偵測 Pivot Points"
            f"（需要至少 {length * 2 + 1} 筆）"
        )

    # 建立副本以避免修改原始資料
    df_result = df.copy()
    df_result['pivot_high'] = np.nan
    df_result['pivot_low'] = np.nan

    # 遍歷可能的 Pivot Point 位置（排除前後各 length 根）
    for i in range(length, len(df) - length):
        # 檢查 Pivot High
        center_high = df['high'].iloc[i]
        left_window = df['high'].iloc[i-length:i]
        right_window = df['high'].iloc[i+1:i+length+1]

        # 中心點必須嚴格大於左右兩側的所有點
        if (center_high > left_window.max() and
            center_high > right_window.max()):
            df_result.loc[df_result.index[i], 'pivot_high'] = center_high
            logger.debug(
                f"偵測到 Pivot High：索引 {i}，價格 {center_high:.2f}"
            )

        # 檢查 Pivot Low
        center_low = df['low'].iloc[i]
        left_window_low = df['low'].iloc[i-length:i]
        right_window_low = df['low'].iloc[i+1:i+length+1]

        # 中心點必須嚴格小於左右兩側的所有點
        if (center_low < left_window_low.min() and
            center_low < right_window_low.min()):
            df_result.loc[df_result.index[i], 'pivot_low'] = center_low
            logger.debug(
                f"偵測到 Pivot Low：索引 {i}，價格 {center_low:.2f}"
            )

    # 統計結果
    pivot_high_count = df_result['pivot_high'].notna().sum()
    pivot_low_count = df_result['pivot_low'].notna().sum()
    logger.info(
        f"偵測完成：找到 {pivot_high_count} 個 Pivot High，"
        f"{pivot_low_count} 個 Pivot Low"
    )

    return df_result


def extract_pivot_ranges(df: pd.DataFrame) -> list:
    """
    從 DataFrame 中提取 Pivot Point 區間配對

    相鄰的兩個 Pivot Point（無論是 High 還是 Low）形成一個區間，
    用於計算該區間的 Volume Profile。

    參數：
        df: 包含 'pivot_high' 和 'pivot_low' 欄位的 DataFrame
            （通常是 find_pivot_points() 的輸出）

    回傳：
        區間列表，每個元素是一個字典：
        {
            'start_idx': int,        # 起始位置（整數索引）
            'end_idx': int,          # 結束位置（整數索引）
            'start_time': Timestamp, # 起始時間
            'end_time': Timestamp,   # 結束時間
            'pivot_type': str,       # 結束位置的 Pivot 類型（'H' 或 'L'）
            'pivot_price': float     # 結束位置的 Pivot 價格
        }

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    logger.info("開始提取 Pivot Point 區間")

    # 驗證輸入
    required_columns = ['pivot_high', 'pivot_low']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    # 找出所有 Pivot Point 的位置
    pivot_points = []

    for i in range(len(df)):
        if not pd.isna(df['pivot_high'].iloc[i]):
            pivot_points.append({
                'idx': i,
                'type': 'H',
                'price': df['pivot_high'].iloc[i],
                'time': df.index[i]
            })
        elif not pd.isna(df['pivot_low'].iloc[i]):
            pivot_points.append({
                'idx': i,
                'type': 'L',
                'price': df['pivot_low'].iloc[i],
                'time': df.index[i]
            })

    if len(pivot_points) < 2:
        logger.warning(f"Pivot Point 數量不足（僅 {len(pivot_points)} 個），無法形成區間")
        return []

    # 配對相鄰的 Pivot Points 形成區間
    ranges = []
    for i in range(len(pivot_points) - 1):
        start_pivot = pivot_points[i]
        end_pivot = pivot_points[i + 1]

        range_info = {
            'start_idx': start_pivot['idx'],
            'end_idx': end_pivot['idx'],
            'start_time': start_pivot['time'],
            'end_time': end_pivot['time'],
            'pivot_type': end_pivot['type'],
            'pivot_price': end_pivot['price'],
            'bar_count': end_pivot['idx'] - start_pivot['idx']
        }

        ranges.append(range_info)

        logger.debug(
            f"區間 {i+1}：索引 {range_info['start_idx']} -> {range_info['end_idx']}，"
            f"類型 {range_info['pivot_type']}，K 線數 {range_info['bar_count']}"
        )

    logger.info(f"提取完成：共 {len(ranges)} 個區間")

    return ranges


def calculate_volume_profile_for_range(
    df: pd.DataFrame,
    start_idx: int,
    end_idx: int,
    price_levels: int = 25
) -> dict:
    """
    計算指定區間的 Volume Profile

    此函數實作與 PineScript VPPA 相同的成交量分配演算法：
    - 價格範圍平均分為 price_levels 層
    - 每根 K 線的成交量按其覆蓋的價格層級比例分配

    參數：
        df: K 線資料 DataFrame（必須包含 'high', 'low', 'real_volume'）
        start_idx: 起始索引（包含，整數位置）
        end_idx: 結束索引（包含，整數位置）
        price_levels: 價格分層數量（預設 25）

    回傳：
        字典，包含：
        {
            'volume_profile': np.ndarray,   # 每層的成交量（長度 = price_levels）
            'price_lowest': float,          # 區間最低價
            'price_highest': float,         # 區間最高價
            'price_step': float,            # 每層的價格高度
            'price_centers': np.ndarray,    # 每層的中心價格
            'total_volume': float,          # 區間總成交量
            'bar_count': int                # K 線數量
        }

    例外：
        ValueError: 輸入資料格式錯誤或索引超出範圍時
    """
    logger.debug(
        f"計算 Volume Profile：索引 {start_idx} -> {end_idx}，"
        f"價格層級 {price_levels}"
    )

    # 驗證輸入
    required_columns = ['high', 'low', 'real_volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    if start_idx < 0 or end_idx >= len(df) or start_idx >= end_idx:
        raise ValueError(
            f"無效的索引範圍：start_idx={start_idx}, end_idx={end_idx}, "
            f"資料長度={len(df)}"
        )

    # 取得區間資料（包含 end_idx）
    range_df = df.iloc[start_idx:end_idx+1]
    bar_count = len(range_df)

    # 計算價格範圍
    price_highest = range_df['high'].max()
    price_lowest = range_df['low'].min()
    price_range = price_highest - price_lowest

    if price_range == 0:
        logger.warning(
            f"區間價格無變化（{price_lowest:.2f}），"
            "無法計算 Volume Profile"
        )
        # 回傳空的 Profile
        return {
            'volume_profile': np.zeros(price_levels),
            'price_lowest': price_lowest,
            'price_highest': price_highest,
            'price_step': 0,
            'price_centers': np.full(price_levels, price_lowest),
            'total_volume': range_df['real_volume'].sum(),
            'bar_count': bar_count
        }

    price_step = price_range / price_levels

    # 初始化成交量儲存陣列
    volume_storage = np.zeros(price_levels)

    # 遍歷每根 K 線，分配成交量到價格層級
    for idx in range(len(range_df)):
        row = range_df.iloc[idx]
        bar_high = row['high']
        bar_low = row['low']
        bar_volume = row['real_volume']
        bar_range = bar_high - bar_low

        # 遍歷每個價格層級
        for level in range(price_levels):
            level_low = price_lowest + level * price_step
            level_high = price_lowest + (level + 1) * price_step

            # 檢查 K 線是否覆蓋此價格層級
            # 條件：K 線的 high >= 層級下界 AND K 線的 low < 層級上界
            if bar_high >= level_low and bar_low < level_high:
                # 按比例分配成交量
                if bar_range == 0:
                    # K 線是一條線（開盤價 = 收盤價），全部分配給此層級
                    volume_storage[level] += bar_volume
                else:
                    # 按 price_step / bar_range 比例分配
                    # 這是 PineScript VPPA 的核心公式
                    ratio = price_step / bar_range
                    volume_storage[level] += bar_volume * ratio

    # 計算每層的中心價格
    price_centers = np.array([
        price_lowest + (level + 0.5) * price_step
        for level in range(price_levels)
    ])

    total_volume = volume_storage.sum()

    logger.debug(
        f"Volume Profile 計算完成：總成交量 {total_volume:.0f}，"
        f"價格範圍 {price_lowest:.2f} - {price_highest:.2f}"
    )

    return {
        'volume_profile': volume_storage,
        'price_lowest': price_lowest,
        'price_highest': price_highest,
        'price_step': price_step,
        'price_centers': price_centers,
        'total_volume': total_volume,
        'bar_count': bar_count
    }


def calculate_value_area(
    volume_storage: np.ndarray,
    price_lowest: float,
    price_step: float,
    value_area_pct: float = 0.68
) -> dict:
    """
    計算 Value Area（價值區域）

    Value Area 是包含指定百分比總成交量的價格區間，
    從 POC（成交量最大的價格層級）開始向兩側擴展。

    演算法：
    1. 找出 POC（Point of Control）- 成交量最大的層級
    2. 從 POC 開始，累積成交量
    3. 向兩側擴展，每次選擇成交量較大的一側
    4. 直到累積成交量達到目標百分比（預設 68%）

    參數：
        volume_storage: 每個價格層級的成交量陣列
        price_lowest: 區間最低價
        price_step: 每層的價格高度
        value_area_pct: Value Area 包含的成交量百分比（預設 0.68 即 68%）

    回傳：
        字典，包含：
        {
            'poc_level': int,           # POC 所在層級索引
            'poc_price': float,         # POC 價格（層級中心）
            'poc_volume': float,        # POC 的成交量
            'poc_volume_pct': float,    # POC 佔總成交量的百分比
            'vah': float,               # Value Area High
            'val': float,               # Value Area Low
            'value_area_volume': float, # Value Area 內的成交量
            'total_volume': float,      # 總成交量
            'value_area_pct': float,    # Value Area 實際達到的百分比
            'value_area_width': float,  # Value Area 價格寬度（vah - val）
            'level_above_poc': int,     # VAH 所在層級
            'level_below_poc': int      # VAL 所在層級
        }

    例外：
        ValueError: 輸入參數無效時
    """
    logger.debug(
        f"計算 Value Area：目標百分比 {value_area_pct*100:.1f}%"
    )

    # 驗證輸入
    if len(volume_storage) == 0:
        raise ValueError("volume_storage 不能為空")

    if value_area_pct <= 0 or value_area_pct > 1:
        raise ValueError(
            f"value_area_pct 必須在 0 到 1 之間，得到：{value_area_pct}"
        )

    if price_step < 0:
        raise ValueError(f"price_step 必須為正數，得到：{price_step}")

    # 計算 POC (Point of Control)
    poc_level = int(np.argmax(volume_storage))
    poc_volume = volume_storage[poc_level]
    poc_price = price_lowest + (poc_level + 0.5) * price_step

    total_volume = volume_storage.sum()

    if total_volume == 0:
        logger.warning("總成交量為 0，無法計算 Value Area")
        return {
            'poc_level': poc_level,
            'poc_price': poc_price,
            'poc_volume': 0,
            'poc_volume_pct': 0,
            'vah': price_lowest + (poc_level + 1.0) * price_step,
            'val': price_lowest + (poc_level + 0.0) * price_step,
            'value_area_volume': 0,
            'total_volume': 0,
            'value_area_pct': 0,
            'value_area_width': 0,
            'level_above_poc': poc_level,
            'level_below_poc': poc_level
        }

    poc_volume_pct = (poc_volume / total_volume * 100) if total_volume > 0 else 0

    logger.debug(
        f"POC：層級 {poc_level}，價格 {poc_price:.2f}，"
        f"成交量 {poc_volume:.0f} ({poc_volume_pct:.1f}%)"
    )

    # 計算目標成交量
    target_volume = total_volume * value_area_pct

    # 從 POC 開始向兩側擴展
    value_area_volume = poc_volume
    level_above_poc = poc_level
    level_below_poc = poc_level

    while value_area_volume < target_volume:
        # 檢查是否已經到達邊界
        if level_below_poc == 0 and level_above_poc == len(volume_storage) - 1:
            logger.debug("已擴展到價格範圍邊界，停止擴展")
            break

        # 取得上下相鄰層級的成交量
        volume_above = (
            volume_storage[level_above_poc + 1]
            if level_above_poc < len(volume_storage) - 1
            else 0
        )
        volume_below = (
            volume_storage[level_below_poc - 1]
            if level_below_poc > 0
            else 0
        )

        # 如果兩側都沒有成交量，停止擴展
        if volume_above == 0 and volume_below == 0:
            logger.debug("兩側都無成交量，停止擴展")
            break

        # 選擇成交量較大的一側擴展
        # 如果成交量相等，優先向上擴展（與 PineScript 行為一致）
        if volume_above >= volume_below:
            value_area_volume += volume_above
            level_above_poc += 1
            logger.debug(
                f"向上擴展到層級 {level_above_poc}，"
                f"增加成交量 {volume_above:.0f}"
            )
        else:
            value_area_volume += volume_below
            level_below_poc -= 1
            logger.debug(
                f"向下擴展到層級 {level_below_poc}，"
                f"增加成交量 {volume_below:.0f}"
            )

    # 計算 VAH 和 VAL
    # VAH = 上邊界層級的上界
    vah = price_lowest + (level_above_poc + 1.0) * price_step
    # VAL = 下邊界層級的下界
    val = price_lowest + (level_below_poc + 0.0) * price_step

    value_area_width = vah - val
    actual_value_area_pct = (
        (value_area_volume / total_volume * 100) if total_volume > 0 else 0
    )

    logger.debug(
        f"Value Area 計算完成：VAH {vah:.2f}，VAL {val:.2f}，"
        f"寬度 {value_area_width:.2f}，"
        f"成交量 {value_area_volume:.0f} ({actual_value_area_pct:.1f}%)"
    )

    return {
        'poc_level': int(poc_level),
        'poc_price': float(poc_price),
        'poc_volume': float(poc_volume),
        'poc_volume_pct': float(poc_volume_pct),
        'vah': float(vah),
        'val': float(val),
        'value_area_volume': float(value_area_volume),
        'total_volume': float(total_volume),
        'value_area_pct': float(actual_value_area_pct),
        'value_area_width': float(value_area_width),
        'level_above_poc': int(level_above_poc),
        'level_below_poc': int(level_below_poc)
    }


def calculate_vppa(
    df: pd.DataFrame,
    pivot_length: int = 20,
    price_levels: int = 25,
    value_area_pct: float = 0.68,
    include_developing: bool = True
) -> dict:
    """
    計算 Volume Profile Pivot Anchored (VPPA)

    此函數是 VPPA 指標的主要入口，整合以下功能：
    1. 偵測所有 Pivot Points（高點和低點）
    2. 提取相鄰 Pivot Points 之間的區間
    3. 為每個區間計算 Volume Profile
    4. 計算每個區間的 Value Area（POC、VAH、VAL）
    5. 計算即時發展中的區間（從最後一個 Pivot Point 到現在）

    參數：
        df: K 線資料 DataFrame（必須包含 'high', 'low', 'real_volume' 欄位）
        pivot_length: Pivot Point 左右觀察窗口大小（預設 20）
        price_levels: Volume Profile 價格分層數量（預設 25）
        value_area_pct: Value Area 包含的成交量百分比（預設 0.68 即 68%）
        include_developing: 是否包含即時發展中的區間（預設 True）

    回傳：
        字典，包含：
        {
            # 元數據
            'metadata': {
                'total_bars': int,              # 總 K 線數
                'pivot_length': int,
                'price_levels': int,
                'value_area_pct': float,
                'total_pivot_points': int,      # Pivot Points 總數
                'total_ranges': int,            # 區間總數
                'pivot_high_count': int,        # Pivot High 數量
                'pivot_low_count': int          # Pivot Low 數量
            },

            # Pivot Points 摘要
            'pivot_summary': [
                {
                    'idx': int,                 # K 線索引
                    'type': str,                # 'H' 或 'L'
                    'price': float,             # Pivot 價格
                    'time': Timestamp           # 時間戳
                },
                ...
            ],

            # 已確認的 Pivot Point 區間（歷史區間）
            'pivot_ranges': [
                {
                    # 區間資訊
                    'range_id': int,            # 區間編號（從 0 開始）
                    'start_idx': int,
                    'end_idx': int,
                    'start_time': Timestamp,
                    'end_time': Timestamp,
                    'bar_count': int,

                    # Pivot Point 資訊
                    'pivot_type': str,          # 'H' 或 'L'
                    'pivot_price': float,

                    # 價格範圍
                    'price_highest': float,
                    'price_lowest': float,
                    'price_range': float,
                    'price_step': float,

                    # Volume Profile 資料
                    'volume_profile': list,     # 每層成交量（轉為 list 方便序列化）
                    'price_centers': list,      # 每層中心價格

                    # POC 資訊
                    'poc': {
                        'level': int,
                        'price': float,
                        'volume': float,
                        'volume_pct': float
                    },

                    # Value Area 資訊
                    'vah': float,
                    'val': float,
                    'value_area_width': float,
                    'value_area_volume': float,
                    'value_area_pct': float,

                    # 統計資訊
                    'total_volume': float,
                    'avg_volume_per_bar': float
                },
                ...
            ],

            # 即時發展中的區間（可選）
            'developing_range': {
                # 結構同 pivot_ranges，但標記為 is_developing = True
                'is_developing': True,
                ...
            } 或 None（如果 include_developing=False 或無法計算）
        }

    例外：
        ValueError: 輸入資料格式錯誤或資料量不足時
    """
    logger.info("=" * 60)
    logger.info("開始計算 VPPA (Volume Profile Pivot Anchored)")
    logger.info("=" * 60)
    logger.info(
        f"參數：pivot_length={pivot_length}, price_levels={price_levels}, "
        f"value_area_pct={value_area_pct*100:.1f}%"
    )
    logger.info(f"資料筆數：{len(df)} 根 K 線")

    # 驗證輸入
    required_columns = ['high', 'low', 'real_volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    if len(df) < pivot_length * 2 + 1:
        raise ValueError(
            f"資料筆數（{len(df)}）不足以計算 VPPA"
            f"（需要至少 {pivot_length * 2 + 1} 筆）"
        )

    # Step 1: 偵測 Pivot Points
    logger.info("Step 1/5: 偵測 Pivot Points")
    df_with_pivots = find_pivot_points(df, length=pivot_length)

    pivot_high_count = df_with_pivots['pivot_high'].notna().sum()
    pivot_low_count = df_with_pivots['pivot_low'].notna().sum()
    total_pivot_points = pivot_high_count + pivot_low_count

    # Step 2: 提取區間
    logger.info("Step 2/5: 提取 Pivot Point 區間")
    ranges = extract_pivot_ranges(df_with_pivots)

    if len(ranges) == 0:
        logger.warning("未找到任何 Pivot Point 區間，回傳空結果")
        return {
            'metadata': {
                'total_bars': len(df),
                'pivot_length': pivot_length,
                'price_levels': price_levels,
                'value_area_pct': value_area_pct,
                'total_pivot_points': total_pivot_points,
                'total_ranges': 0,
                'pivot_high_count': pivot_high_count,
                'pivot_low_count': pivot_low_count
            },
            'pivot_summary': [],
            'pivot_ranges': [],
            'developing_range': None
        }

    # Step 3: 計算每個區間的 Volume Profile
    logger.info(f"Step 3/5: 計算 {len(ranges)} 個區間的 Volume Profile")

    pivot_ranges_data = []

    for i, range_info in enumerate(ranges):
        logger.info(f"處理區間 {i+1}/{len(ranges)}：索引 {range_info['start_idx']} -> {range_info['end_idx']}")

        # 計算 Volume Profile
        vp_result = calculate_volume_profile_for_range(
            df,
            start_idx=range_info['start_idx'],
            end_idx=range_info['end_idx'],
            price_levels=price_levels
        )

        # 計算 Value Area
        va_result = calculate_value_area(
            volume_storage=vp_result['volume_profile'],
            price_lowest=vp_result['price_lowest'],
            price_step=vp_result['price_step'],
            value_area_pct=value_area_pct
        )

        # 整合所有資料
        range_data = {
            # 區間資訊
            'range_id': i,
            'start_idx': range_info['start_idx'],
            'end_idx': range_info['end_idx'],
            'start_time': range_info['start_time'],
            'end_time': range_info['end_time'],
            'bar_count': range_info['bar_count'],

            # Pivot Point 資訊
            'pivot_type': range_info['pivot_type'],
            'pivot_price': range_info['pivot_price'],

            # 價格範圍
            'price_highest': vp_result['price_highest'],
            'price_lowest': vp_result['price_lowest'],
            'price_range': vp_result['price_highest'] - vp_result['price_lowest'],
            'price_step': vp_result['price_step'],

            # Volume Profile（轉為 list 以便序列化）
            'volume_profile': vp_result['volume_profile'].tolist(),
            'price_centers': vp_result['price_centers'].tolist(),

            # POC
            'poc': {
                'level': va_result['poc_level'],
                'price': va_result['poc_price'],
                'volume': va_result['poc_volume'],
                'volume_pct': va_result['poc_volume_pct']
            },

            # Value Area
            'vah': va_result['vah'],
            'val': va_result['val'],
            'value_area_width': va_result['value_area_width'],
            'value_area_volume': va_result['value_area_volume'],
            'value_area_pct': va_result['value_area_pct'],

            # 統計
            'total_volume': vp_result['total_volume'],
            'avg_volume_per_bar': (
                vp_result['total_volume'] / vp_result['bar_count']
                if vp_result['bar_count'] > 0 else 0
            )
        }

        pivot_ranges_data.append(range_data)

        logger.debug(
            f"區間 {i+1} 完成：POC={va_result['poc_price']:.2f}, "
            f"VAH={va_result['vah']:.2f}, VAL={va_result['val']:.2f}"
        )

    # Step 4: 建立 Pivot Points 摘要
    logger.info("Step 4/5: 建立 Pivot Points 摘要")

    pivot_summary = []
    for i in range(len(df_with_pivots)):
        if not pd.isna(df_with_pivots['pivot_high'].iloc[i]):
            pivot_summary.append({
                'idx': i,
                'type': 'H',
                'price': df_with_pivots['pivot_high'].iloc[i],
                'time': df_with_pivots.index[i]
            })
        elif not pd.isna(df_with_pivots['pivot_low'].iloc[i]):
            pivot_summary.append({
                'idx': i,
                'type': 'L',
                'price': df_with_pivots['pivot_low'].iloc[i],
                'time': df_with_pivots.index[i]
            })

    # Step 5: 計算即時發展中的區間（可選）
    logger.info("Step 5/5: 計算即時發展中的區間")

    developing_range = None

    if include_developing and len(pivot_summary) > 0:
        # 最後一個 Pivot Point
        last_pivot = pivot_summary[-1]
        last_pivot_idx = last_pivot['idx']
        current_idx = len(df) - 1

        # 確保有足夠的 K 線形成區間
        if current_idx > last_pivot_idx:
            logger.info(
                f"計算發展中區間：索引 {last_pivot_idx} -> {current_idx} "
                f"({current_idx - last_pivot_idx} 根 K 線)"
            )

            try:
                # 計算 Volume Profile
                vp_dev = calculate_volume_profile_for_range(
                    df,
                    start_idx=last_pivot_idx,
                    end_idx=current_idx,
                    price_levels=price_levels
                )

                # 計算 Value Area
                va_dev = calculate_value_area(
                    volume_storage=vp_dev['volume_profile'],
                    price_lowest=vp_dev['price_lowest'],
                    price_step=vp_dev['price_step'],
                    value_area_pct=value_area_pct
                )

                developing_range = {
                    'is_developing': True,
                    'range_id': len(ranges),  # 接續最後一個歷史區間的 ID
                    'start_idx': last_pivot_idx,
                    'end_idx': current_idx,
                    'start_time': df.index[last_pivot_idx],
                    'end_time': df.index[current_idx],
                    'bar_count': current_idx - last_pivot_idx + 1,

                    # Pivot Point 資訊（發展中，使用最後一個 Pivot）
                    'pivot_type': last_pivot['type'],
                    'pivot_price': last_pivot['price'],

                    # 價格範圍
                    'price_highest': vp_dev['price_highest'],
                    'price_lowest': vp_dev['price_lowest'],
                    'price_range': vp_dev['price_highest'] - vp_dev['price_lowest'],
                    'price_step': vp_dev['price_step'],

                    # Volume Profile
                    'volume_profile': vp_dev['volume_profile'].tolist(),
                    'price_centers': vp_dev['price_centers'].tolist(),

                    # POC
                    'poc': {
                        'level': va_dev['poc_level'],
                        'price': va_dev['poc_price'],
                        'volume': va_dev['poc_volume'],
                        'volume_pct': va_dev['poc_volume_pct']
                    },

                    # Value Area
                    'vah': va_dev['vah'],
                    'val': va_dev['val'],
                    'value_area_width': va_dev['value_area_width'],
                    'value_area_volume': va_dev['value_area_volume'],
                    'value_area_pct': va_dev['value_area_pct'],

                    # 統計
                    'total_volume': vp_dev['total_volume'],
                    'avg_volume_per_bar': (
                        vp_dev['total_volume'] / vp_dev['bar_count']
                        if vp_dev['bar_count'] > 0 else 0
                    )
                }

                logger.info(
                    f"發展中區間完成：POC={va_dev['poc_price']:.2f}, "
                    f"VAH={va_dev['vah']:.2f}, VAL={va_dev['val']:.2f}"
                )

            except Exception as e:
                logger.warning(f"計算發展中區間時發生錯誤：{e}")
                developing_range = None
        else:
            logger.info("最後一個 Pivot Point 後沒有足夠的 K 線，跳過發展中區間")

    # 組裝最終結果
    result = {
        'metadata': {
            'total_bars': len(df),
            'pivot_length': pivot_length,
            'price_levels': price_levels,
            'value_area_pct': value_area_pct,
            'total_pivot_points': total_pivot_points,
            'total_ranges': len(ranges),
            'pivot_high_count': pivot_high_count,
            'pivot_low_count': pivot_low_count
        },
        'pivot_summary': pivot_summary,
        'pivot_ranges': pivot_ranges_data,
        'developing_range': developing_range
    }

    logger.info("=" * 60)
    logger.info("VPPA 計算完成")
    logger.info(f"找到 {total_pivot_points} 個 Pivot Points（{pivot_high_count} High, {pivot_low_count} Low）")
    logger.info(f"產生 {len(ranges)} 個歷史區間")
    logger.info(f"發展中區間：{'是' if developing_range else '否'}")
    logger.info("=" * 60)

    return result
