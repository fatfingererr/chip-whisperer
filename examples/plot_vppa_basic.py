#!/usr/bin/env python3
"""
VPPA 視覺化基本測試

此腳本測試 K 線圖、Pivot Range 方塊、Volume Profile、POC 線和 VAH/VAL 線的繪製功能。
"""

import json
import sys
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.core.sqlite_cache import SQLiteCacheManager
from src.visualization import plot_vppa_chart

def main():
    # 1. 載入 VPPA 分析結果
    vppa_json_path = Path('data/vppa_full_output.json')

    if not vppa_json_path.exists():
        print(f"❌ 找不到 VPPA 資料檔案：{vppa_json_path}")
        print("請先執行：python scripts/analyze_vppa.py GOLD --output data/vppa_full_output.json")
        sys.exit(1)

    with open(vppa_json_path, 'r', encoding='utf-8') as f:
        vppa_data = json.load(f)

    print(f"✅ 載入 VPPA 資料：{vppa_data['symbol']} {vppa_data['timeframe']}")
    print(f"   Pivot Points: {vppa_data['summary']['total_pivot_points']}")
    print(f"   區間數量: {vppa_data['summary']['total_ranges']}")

    # 2. 從快取獲取 K 線資料
    cache = SQLiteCacheManager('data/candles.db')
    symbol = vppa_data['symbol']
    timeframe = vppa_data['timeframe']
    start_time = pd.Timestamp(vppa_data['data_range']['start_time'])
    end_time = pd.Timestamp(vppa_data['data_range']['end_time'])

    df = cache.query_candles(symbol, timeframe, start_time, end_time)

    if df is None or len(df) == 0:
        print("❌ 無法從快取取得 K 線資料")
        sys.exit(1)

    print(f"✅ 取得 K 線資料：{len(df)} 筆")

    # 3. 繪製圖表
    output_path = Path('output/vppa_chart_test.png')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n繪製圖表中...")

    fig = plot_vppa_chart(
        vppa_json=vppa_data,
        candles_df=df,
        output_path=str(output_path),
        show_pivot_points=True,
        show_developing=True,
        width=1920,
        height=1080
    )

    print(f"\n✅ 圖表已儲存到：{output_path}")
    print("\n測試完成！")
    print("請檢查以下項目：")
    print("  [ ] K 線圖正確顯示（上漲綠色、下跌紅色）")
    print("  [ ] Pivot Range 方塊位置正確（淺黃色填充 + 深黃色邊框）")
    print("  [ ] Volume Profile 位置在區間左側")
    print("  [ ] Volume Profile 高度對應價格層級")
    print("  [ ] Value Area 內為藍色，外為灰色")
    print("  [ ] POC 線（紅色虛線）在成交量最大的價格")
    print("  [ ] VAH/VAL 線（綠色點線）正確標示 Value Area 範圍")
    print("  [ ] Pivot Points 標記（紅色向下三角、綠色向上三角）位置正確")

if __name__ == '__main__':
    main()
