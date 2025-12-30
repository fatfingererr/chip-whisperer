#!/usr/bin/env python3
"""
VPPA 分析腳本

此腳本會：
1. 補充 DB 數據（從最後一筆到目前為止的 M1）
2. 往回取 2000 根 M1 數據
3. 計算 Pivot Point 和 Volume Profile
4. 輸出 JSON 格式的分析結果

使用方式：
    python scripts/analyze_vppa.py GOLD
    python scripts/analyze_vppa.py GOLD --count 3000
    python scripts/analyze_vppa.py GOLD --output results/gold_vppa.json
    python scripts/analyze_vppa.py GOLD --pivot-length 15 --price-levels 30
    python scripts/analyze_vppa.py GOLD --plot
    python scripts/analyze_vppa.py GOLD --plot --plot-output output/gold_vppa.png
"""

import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from loguru import logger

from src.core.mt5_config import MT5Config
from src.core.mt5_client import ChipWhispererMT5Client
from src.core.sqlite_cache import SQLiteCacheManager
from src.agent.indicators import calculate_vppa


class NumpyEncoder(json.JSONEncoder):
    """自訂 JSON 編碼器，處理 NumPy 類型"""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def update_db_to_now(
    symbol: str,
    cache: SQLiteCacheManager,
    client: ChipWhispererMT5Client
) -> int:
    """
    補充 DB 數據到目前為止

    參數：
        symbol: 商品代碼
        cache: SQLite 快取管理器
        client: MT5 客戶端

    回傳：
        新增的數據筆數
    """
    timeframe = 'M1'
    tf_constant = mt5.TIMEFRAME_M1

    # 取得 DB 中最新的時間
    newest_time = cache.get_newest_time(symbol, timeframe)

    if newest_time:
        logger.info(f"DB 最新數據時間：{newest_time}")
        # 從最新時間的下一分鐘開始取
        from_time = newest_time + timedelta(minutes=1)
    else:
        logger.info("DB 中無數據，從現在往回取 2000 根")
        from_time = datetime.now(timezone.utc) - timedelta(minutes=2000)

    # 取得到目前為止的數據
    to_time = datetime.now(timezone.utc)

    logger.info(f"補充數據：{from_time} ~ {to_time}")

    # 從 MT5 取得數據
    rates = mt5.copy_rates_range(
        symbol,
        tf_constant,
        from_time,
        to_time
    )

    if rates is None or len(rates) == 0:
        logger.info("無新數據需要補充")
        return 0

    # 轉換為 DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

    logger.info(f"從 MT5 取得 {len(df)} 筆新數據")

    # 保存到 DB
    inserted = cache.insert_candles(df, symbol, timeframe)
    logger.info(f"已保存 {inserted} 筆數據到 DB")

    return inserted


def fetch_m1_data(
    symbol: str,
    count: int,
    cache: SQLiteCacheManager,
    client: ChipWhispererMT5Client
) -> pd.DataFrame:
    """
    取得 M1 數據（優先從 DB，不足則從 MT5 補充）

    參數：
        symbol: 商品代碼
        count: 需要的 K 線數量
        cache: SQLite 快取管理器
        client: MT5 客戶端

    回傳：
        K 線 DataFrame
    """
    timeframe = 'M1'
    tf_constant = mt5.TIMEFRAME_M1

    # 先從 DB 取得數據
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=count * 2)  # 多取一些以確保足夠

    df = cache.query_candles(symbol, timeframe, start_time, end_time)

    if df is not None and len(df) >= count:
        logger.info(f"從 DB 取得 {len(df)} 筆數據")
        # 取最新的 count 筆
        df = df.sort_values('time', ascending=True).tail(count).reset_index(drop=True)
        return df

    # DB 數據不足，從 MT5 取得
    logger.info(f"DB 數據不足（{len(df) if df is not None else 0} 筆），從 MT5 補充")

    rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, count)

    if rates is None or len(rates) == 0:
        raise RuntimeError(f"無法從 MT5 取得 {symbol} M1 數據")

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

    # 保存到 DB
    cache.insert_candles(df, symbol, timeframe)

    # 按時間排序（舊到新）
    df = df.sort_values('time', ascending=True).reset_index(drop=True)

    logger.info(f"從 MT5 取得並保存 {len(df)} 筆數據")
    return df


def analyze_vppa(
    symbol: str = "GOLD",
    count: int = 2160,
    pivot_length: int = 73,
    price_levels: int = 49,
    value_area_pct: float = 0.68,
    volume_ma_length: int = 14,
    db_path: str = "data/candles.db",
    return_dataframe: bool = False
) -> dict:
    """
    執行 VPPA 分析

    參數：
        symbol: 商品代碼
        count: K 線數量
        pivot_length: Pivot Point 左右觀察窗口（預設 20）
        price_levels: 價格分層數量/Number of Rows（預設 49）
        value_area_pct: Value Area 百分比
        volume_ma_length: 成交量移動平均長度（預設 14）
        db_path: 資料庫路徑

    回傳：
        VPPA 分析結果（JSON 可序列化格式）
    """
    logger.info(f"=" * 60)
    logger.info(f"開始 VPPA 分析：{symbol}")
    logger.info(f"參數：count={count}, pivot_length={pivot_length}, price_levels={price_levels}, volume_ma_length={volume_ma_length}")
    logger.info(f"=" * 60)

    # 初始化 MT5 連線
    config = MT5Config()
    client = ChipWhispererMT5Client(config)

    try:
        client.connect()
        logger.info("MT5 連線成功")

        # 驗證商品
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise ValueError(f"商品不存在：{symbol}")

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                raise ValueError(f"無法啟用商品：{symbol}")

        # 初始化 SQLite 快取
        cache = SQLiteCacheManager(db_path)

        # 步驟 1：補充 DB 到最新
        logger.info("-" * 40)
        logger.info("步驟 1：補充 DB 數據到目前為止")
        new_count = update_db_to_now(symbol, cache, client)
        logger.info(f"新增 {new_count} 筆數據")

        # 步驟 2：取得 M1 數據
        logger.info("-" * 40)
        logger.info(f"步驟 2：取得 {count} 根 M1 數據")
        df = fetch_m1_data(symbol, count, cache, client)
        logger.info(f"取得 {len(df)} 筆數據")
        logger.info(f"時間範圍：{df['time'].min()} ~ {df['time'].max()}")

        # 步驟 3：計算成交量移動平均
        logger.info("-" * 40)
        logger.info(f"步驟 3：計算成交量移動平均（長度：{volume_ma_length}）")
        df['volume_ma'] = df['real_volume'].rolling(window=volume_ma_length).mean()

        # 步驟 4：計算 VPPA
        logger.info("-" * 40)
        logger.info("步驟 4：計算 VPPA")

        # 設定時間索引
        df_indexed = df.set_index('time')

        vppa_result = calculate_vppa(
            df_indexed,
            pivot_length=pivot_length,
            price_levels=price_levels,
            value_area_pct=value_area_pct
        )

        logger.info(f"找到 {vppa_result['metadata']['total_pivot_points']} 個 Pivot Points")
        logger.info(f"產生 {vppa_result['metadata']['total_ranges']} 個區間")

        # 步驟 5：整理輸出
        logger.info("-" * 40)
        logger.info("步驟 5：整理輸出結果")

        # 計算最新的成交量 MA 值
        latest_volume_ma = df['volume_ma'].iloc[-1] if not pd.isna(df['volume_ma'].iloc[-1]) else None
        avg_volume = df['real_volume'].mean()

        output = {
            'symbol': symbol,
            'timeframe': 'M1',
            'analysis_time': datetime.now(timezone.utc).isoformat(),
            'parameters': {
                'count': count,
                'pivot_length': pivot_length,
                'price_levels': price_levels,
                'value_area_pct': value_area_pct,
                'volume_ma_length': volume_ma_length
            },
            'data_range': {
                'start_time': df['time'].min().isoformat(),
                'end_time': df['time'].max().isoformat(),
                'total_bars': len(df)
            },
            'summary': {
                'total_pivot_points': vppa_result['metadata']['total_pivot_points'],
                'total_ranges': vppa_result['metadata']['total_ranges'],
                'avg_range_bars': vppa_result['metadata'].get('avg_range_bars', 0),
                'has_developing_range': vppa_result['developing_range'] is not None,
                'volume_stats': {
                    'latest_volume_ma': float(latest_volume_ma) if latest_volume_ma else None,
                    'avg_volume': float(avg_volume),
                    'total_volume': float(df['real_volume'].sum())
                }
            },
            'pivot_points': vppa_result['pivot_summary'],
            'pivot_ranges': [],
            'developing_range': None
        }

        # 整理每個區間的數據
        for i, range_data in enumerate(vppa_result['pivot_ranges']):
            range_output = {
                'range_id': i,
                'start_idx': range_data['start_idx'],
                'end_idx': range_data['end_idx'],
                'start_time': range_data['start_time'],
                'end_time': range_data['end_time'],
                'bar_count': range_data['bar_count'],
                'pivot_type': range_data['pivot_type'],
                'pivot_price': range_data['pivot_price'],
                'price_info': {
                    'highest': range_data['price_highest'],
                    'lowest': range_data['price_lowest'],
                    'range': range_data['price_range'],
                    'step': range_data['price_step']
                },
                'poc': {
                    'level': range_data['poc']['level'],
                    'price': range_data['poc']['price'],
                    'volume': range_data['poc']['volume'],
                    'volume_pct': range_data['poc']['volume_pct']
                },
                'value_area': {
                    'vah': range_data['vah'],
                    'val': range_data['val'],
                    'width': range_data['value_area_width'],
                    'volume': range_data['value_area_volume'],
                    'pct': range_data['value_area_pct']
                },
                'volume_info': {
                    'total': range_data['total_volume'],
                    'avg_per_bar': range_data['avg_volume_per_bar']
                },
                'volume_profile': {
                    'levels': len(range_data['volume_profile']),
                    'price_centers': range_data['price_centers'],
                    'volumes': range_data['volume_profile']
                }
            }
            output['pivot_ranges'].append(range_output)

        # 處理發展中的區間
        if vppa_result['developing_range']:
            dev = vppa_result['developing_range']
            output['developing_range'] = {
                'start_idx': dev['start_idx'],
                'end_idx': dev['end_idx'],
                'start_time': dev['start_time'],
                'end_time': dev['end_time'],
                'bar_count': dev['bar_count'],
                'is_developing': True,
                'price_info': {
                    'highest': dev['price_highest'],
                    'lowest': dev['price_lowest'],
                    'range': dev['price_range'],
                    'step': dev['price_step']
                },
                'poc': {
                    'level': dev['poc']['level'],
                    'price': dev['poc']['price'],
                    'volume': dev['poc']['volume'],
                    'volume_pct': dev['poc']['volume_pct']
                },
                'value_area': {
                    'vah': dev['vah'],
                    'val': dev['val'],
                    'width': dev['value_area_width'],
                    'volume': dev['value_area_volume'],
                    'pct': dev['value_area_pct']
                },
                'volume_info': {
                    'total': dev['total_volume'],
                    'avg_per_bar': dev['avg_volume_per_bar']
                },
                'volume_profile': {
                    'levels': len(dev['volume_profile']),
                    'price_centers': dev['price_centers'],
                    'volumes': dev['volume_profile']
                }
            }

        logger.info(f"=" * 60)
        logger.info("VPPA 分析完成！")
        logger.info(f"=" * 60)

        if return_dataframe:
            return output, df
        else:
            return output

    finally:
        client.disconnect()
        logger.info("MT5 連線已關閉")


def main():
    parser = argparse.ArgumentParser(
        description='VPPA 分析腳本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
    python scripts/analyze_vppa.py GOLD
    python scripts/analyze_vppa.py EURUSD --count 3000
    python scripts/analyze_vppa.py GOLD --output results/gold_vppa.json
    python scripts/analyze_vppa.py GOLD --pivot-length 15 --price-levels 30
    python scripts/analyze_vppa.py GOLD --plot
    python scripts/analyze_vppa.py GOLD --plot --plot-output output/gold_vppa.png
        """
    )

    parser.add_argument(
        'symbol',
        type=str,
        default='GOLD',
        help='商品代碼（例如：GOLD, EURUSD）'
    )

    parser.add_argument(
        '--count',
        type=int,
        default=2160,
        help='K 線數量（預設：2160）'
    )

    parser.add_argument(
        '--pivot-length',
        type=int,
        default=73,
        help='Pivot Point 觀察窗口（預設：73）'
    )

    parser.add_argument(
        '--price-levels',
        type=int,
        default=49,
        help='價格分層數量/Number of Rows（預設：49）'
    )

    parser.add_argument(
        '--value-area-pct',
        type=float,
        default=0.68,
        help='Value Area 百分比（預設：0.68）'
    )

    parser.add_argument(
        '--volume-ma-length',
        type=int,
        default=14,
        help='成交量移動平均長度（預設：14）'
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default='data/candles.db',
        help='資料庫路徑（預設：data/candles.db）'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='輸出 JSON 檔案路徑（預設：輸出到 stdout）'
    )

    parser.add_argument(
        '--pretty',
        action='store_true',
        help='美化 JSON 輸出'
    )

    parser.add_argument(
        '--plot',
        action='store_true',
        help='繪製 VPPA 圖表（需要 plotly 和 kaleido）'
    )

    parser.add_argument(
        '--plot-output',
        type=str,
        default=None,
        help='圖表輸出路徑（預設：output/vppa_chart.png）'
    )

    args = parser.parse_args()

    # 確保資料庫目錄存在
    db_dir = Path(args.db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 執行分析
        if args.plot:
            # 如果需要繪圖，同時取得 DataFrame
            result, df = analyze_vppa(
                symbol=args.symbol.upper(),
                count=args.count,
                pivot_length=args.pivot_length,
                price_levels=args.price_levels,
                value_area_pct=args.value_area_pct,
                volume_ma_length=args.volume_ma_length,
                db_path=args.db_path,
                return_dataframe=True
            )
        else:
            result = analyze_vppa(
                symbol=args.symbol.upper(),
                count=args.count,
                pivot_length=args.pivot_length,
                price_levels=args.price_levels,
                value_area_pct=args.value_area_pct,
                volume_ma_length=args.volume_ma_length,
                db_path=args.db_path,
                return_dataframe=False
            )

        # 輸出 JSON
        indent = 2 if args.pretty else None

        if args.output:
            # 輸出到檔案
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, cls=NumpyEncoder, indent=indent, ensure_ascii=False)

            print(f"\n✅ 分析結果已輸出到：{output_path}")
            print(f"   Pivot Points: {result['summary']['total_pivot_points']}")
            print(f"   區間數量: {result['summary']['total_ranges']}")

        else:
            # 輸出到 stdout
            print(json.dumps(result, cls=NumpyEncoder, indent=indent, ensure_ascii=False))

        # 繪製圖表
        if args.plot:
            from src.visualization import plot_vppa_chart

            # 設定輸出路徑
            if args.plot_output:
                plot_output_path = Path(args.plot_output)
            else:
                plot_output_path = Path('output/vppa_chart.png')

            plot_output_path.parent.mkdir(parents=True, exist_ok=True)

            print(f"\n繪製圖表中...")

            fig = plot_vppa_chart(
                vppa_json=result,
                candles_df=df,
                output_path=str(plot_output_path),
                show_pivot_points=True,
                show_developing=True,
                width=1920,
                height=1080
            )

            print(f"✅ 圖表已儲存到：{plot_output_path}")

    except KeyboardInterrupt:
        print("\n\n⚠️ 使用者中斷")
        sys.exit(130)

    except Exception as e:
        logger.error(f"分析失敗：{e}")
        print(f"\n❌ 錯誤：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
