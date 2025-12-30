#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Volume Profile 資料分析範例

此範例展示如何取得 K 線資料並進行 Volume Profile 分析。
包含 POC (Point of Control) 和 Value Area 計算。

使用方式：
    python examples/demo_volume_profile_data.py

注意事項：
    1. 執行前請先設定 .env 檔案（複製 .env.example 並填入您的 MT5 帳號資訊）
    2. 確保 MT5 終端機已安裝並可正常連線

輸出：
    - 在 output/ 目錄下產生分析結果檔案
    - 包含 POC、Value Area High、Value Area Low 等關鍵價位
"""

import sys
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from loguru import logger
from core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher


def setup_logger():
    """設定日誌系統"""
    logger.remove()

    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / 'volume_profile.log',
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB"
    )


def calculate_volume_profile(
    df: pd.DataFrame,
    price_bins: int = 100
) -> Tuple[pd.DataFrame, Dict]:
    """
    計算 Volume Profile

    參數：
        df: K 線資料 DataFrame
        price_bins: 價格區間數量

    回傳：
        (profile_df, metrics) 元組
        - profile_df: Volume Profile DataFrame
        - metrics: 包含 POC、VAH、VAL 的字典
    """
    logger.info(f"開始計算 Volume Profile（價格區間數：{price_bins}）")

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
    profile_df = profile_df.sort_values('volume', ascending=False)

    # 5. 計算 POC (Point of Control) - 成交量最大的價位
    poc_price = profile_df.iloc[0]['price']
    poc_volume = profile_df.iloc[0]['volume']

    logger.info(f"POC (Point of Control)：{poc_price:.2f}，成交量：{poc_volume:.0f}")

    # 6. 計算 Value Area (70% 成交量區間)
    total_volume = volumes.sum()
    target_volume = total_volume * 0.70

    # 從 POC 開始向兩側擴展，直到達到 70% 成交量
    profile_df_sorted = profile_df.sort_values('price')
    poc_idx = profile_df_sorted[profile_df_sorted['price'] == poc_price].index[0]

    # 初始化 Value Area
    value_area_volume = poc_volume
    lower_idx = poc_idx
    upper_idx = poc_idx

    # 向兩側擴展
    while value_area_volume < target_volume:
        # 檢查是否還有空間擴展
        can_expand_lower = lower_idx > 0
        can_expand_upper = upper_idx < len(profile_df_sorted) - 1

        if not can_expand_lower and not can_expand_upper:
            break

        # 選擇成交量較大的一側擴展
        lower_volume = profile_df_sorted.iloc[lower_idx - 1]['volume'] if can_expand_lower else 0
        upper_volume = profile_df_sorted.iloc[upper_idx + 1]['volume'] if can_expand_upper else 0

        if lower_volume > upper_volume and can_expand_lower:
            lower_idx -= 1
            value_area_volume += lower_volume
        elif can_expand_upper:
            upper_idx += 1
            value_area_volume += upper_volume

    # Value Area High (VAH) 和 Low (VAL)
    vah = profile_df_sorted.iloc[upper_idx]['price']
    val = profile_df_sorted.iloc[lower_idx]['price']

    logger.info(f"Value Area High (VAH)：{vah:.2f}")
    logger.info(f"Value Area Low (VAL)：{val:.2f}")
    logger.info(f"Value Area 成交量：{value_area_volume:.0f} ({value_area_volume/total_volume*100:.1f}%)")

    # 7. 整理結果
    metrics = {
        'poc_price': poc_price,
        'poc_volume': poc_volume,
        'vah': vah,
        'val': val,
        'value_area_volume': value_area_volume,
        'total_volume': total_volume,
        'value_area_percentage': value_area_volume / total_volume * 100
    }

    return profile_df, metrics


def main():
    """主函式"""
    setup_logger()

    logger.info("=" * 60)
    logger.info("Chip Whisperer - Volume Profile 資料分析範例")
    logger.info("=" * 60)

    try:
        # 1. 載入設定並連線
        logger.info("步驟 1：載入設定並連線到 MT5")
        config = MT5Config()

        with ChipWhispererMT5Client(config) as client:
            logger.info(f"客戶端狀態：{client}")

            # 2. 建立資料取得器
            fetcher = HistoricalDataFetcher(client)

            # 3. 取得 GOLD 最近一週的 H1 資料
            logger.info("\n" + "=" * 60)
            logger.info("步驟 2：取得 GOLD 最近一週的 H1 K 線資料")
            logger.info("=" * 60)

            df = fetcher.get_candles_by_date(
                symbol='GOLD',
                timeframe='H1',
                from_date='2024-12-23',  # 最近一週
                default_count=200
            )

            logger.info(f"取得資料筆數：{len(df)}")
            logger.info(f"日期範圍：{df['time'].min()} ~ {df['time'].max()}")

            # 4. 計算 Volume Profile
            logger.info("\n" + "=" * 60)
            logger.info("步驟 3：計算 Volume Profile")
            logger.info("=" * 60)

            profile_df, metrics = calculate_volume_profile(df, price_bins=50)

            # 5. 顯示分析結果
            logger.info("\n" + "=" * 60)
            logger.info("Volume Profile 分析結果")
            logger.info("=" * 60)

            logger.info(f"\n關鍵價位：")
            logger.info(f"  POC (Point of Control):  {metrics['poc_price']:.2f}")
            logger.info(f"  VAH (Value Area High):   {metrics['vah']:.2f}")
            logger.info(f"  VAL (Value Area Low):    {metrics['val']:.2f}")
            logger.info(f"  Value Area 範圍:          {metrics['vah'] - metrics['val']:.2f} 點")

            logger.info(f"\n成交量統計：")
            logger.info(f"  總成交量:                 {metrics['total_volume']:.0f}")
            logger.info(f"  POC 成交量:              {metrics['poc_volume']:.0f}")
            logger.info(f"  Value Area 成交量:       {metrics['value_area_volume']:.0f}")
            logger.info(f"  Value Area 佔比:         {metrics['value_area_percentage']:.1f}%")

            # 6. 儲存結果
            logger.info("\n" + "=" * 60)
            logger.info("步驟 4：儲存分析結果")
            logger.info("=" * 60)

            # 建立輸出目錄
            output_dir = project_root / 'output'
            output_dir.mkdir(exist_ok=True)

            # 儲存原始 K 線資料
            candles_file = output_dir / 'GOLD_h1_candles.csv'
            df.to_csv(candles_file, index=False, encoding='utf-8-sig')
            logger.info(f"K 線資料已儲存：{candles_file}")

            # 儲存 Volume Profile
            profile_file = output_dir / 'GOLD_h1_volume_profile.csv'
            profile_df.to_csv(profile_file, index=False, encoding='utf-8-sig')
            logger.info(f"Volume Profile 已儲存：{profile_file}")

            # 儲存分析指標
            metrics_df = pd.DataFrame([metrics])
            metrics_file = output_dir / 'GOLD_h1_metrics.csv'
            metrics_df.to_csv(metrics_file, index=False, encoding='utf-8-sig')
            logger.info(f"分析指標已儲存：{metrics_file}")

            # 7. 額外分析：顯示成交量前 10 的價位
            logger.info("\n" + "=" * 60)
            logger.info("成交量前 10 的價位區間")
            logger.info("=" * 60)

            top_10 = profile_df.head(10).reset_index(drop=True)
            for idx, row in top_10.iterrows():
                is_poc = '← POC' if row['price'] == metrics['poc_price'] else ''
                in_va = '✓' if metrics['val'] <= row['price'] <= metrics['vah'] else ''
                logger.info(
                    f"  {idx + 1:2d}. 價位 {row['price']:8.2f}，"
                    f"成交量 {row['volume']:12.0f} {is_poc} {in_va}"
                )

        logger.info("\n" + "=" * 60)
        logger.info("範例執行完成")
        logger.info("=" * 60)

    except ValueError as e:
        logger.error(f"設定錯誤：{e}")
        sys.exit(1)

    except RuntimeError as e:
        logger.error(f"執行錯誤：{e}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("使用者中斷執行")
        sys.exit(0)

    except Exception as e:
        logger.exception(f"未預期的錯誤：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
