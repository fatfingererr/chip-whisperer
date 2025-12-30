---
title: "Plotly K線圖與成交量分佈視覺化功能實作計劃"
date: 2024-12-30
author: Claude Code (Implementation Planner)
tags: [plotly, visualization, vppa, implementation-plan, candlestick, volume-profile]
status: ready-for-implementation
related_research: thoughts/shared/research/2024-12-30-plotly-kline-volume-profile-research.md
priority: high
estimated_days: 7-10
---

# Plotly K線圖與成交量分佈視覺化功能實作計劃

## 計劃總覽

基於 `analyze_vppa.py` 的輸出資料，建立一個可復用的 Plotly 視覺化函式庫，用於繪製 K 線圖、Pivot Range 方塊和橫向成交量分佈圖（Volume Profile），並支援 PNG 圖片輸出。

**核心目標**：
1. 在 K 線圖上繪製 Pivot Point 切分的價格區間方塊（淺黃色填充 + 深黃色邊框）
2. 在每個區間左側繪製橫向 Volume Profile 直方圖
3. 標示 POC（Point of Control）、VAH（Value Area High）、VAL（Value Area Low）線
4. 支援 PNG 檔案輸出
5. 建立可復用的視覺化模組

## 目前狀態分析

### 現有資源

**資料來源**：
- ✅ `analyze_vppa.py`：完整的 VPPA 分析腳本，輸出 JSON 格式資料
- ✅ `src/agent/indicators.py`：VPPA 計算核心（`calculate_vppa()` 函數）
- ✅ `src/core/data_fetcher.py`：MT5 資料獲取模組
- ✅ `src/core/sqlite_cache.py`：SQLite 快取管理
- ✅ `data/vppa_full_output.json`：範例輸出資料（60 個 Pivot Range）

**JSON 資料結構**（`analyze_vppa.py` 輸出）：
```json
{
  "symbol": "GOLD",
  "timeframe": "M1",
  "parameters": { ... },
  "data_range": { ... },
  "pivot_points": [
    {"idx": 22, "type": "H", "price": 4518.78, "time": "..."},
    ...
  ],
  "pivot_ranges": [
    {
      "range_id": 0,
      "start_idx": 22,
      "end_idx": 41,
      "price_info": {"highest": 4518.78, "lowest": 4512.13, ...},
      "poc": {"price": 4516.405, "volume": 51295.02, ...},
      "value_area": {"vah": 4517.15, "val": 4514.84, ...},
      "volume_profile": {
        "price_centers": [4512.19, 4512.33, ...],
        "volumes": [50123.45, 48932.12, ...]
      }
    },
    ...
  ],
  "developing_range": { ... }
}
```

**K 線資料**（來自 `data_fetcher.py` 或 SQLite 快取）：
```python
df = pd.DataFrame({
    'time': pd.DatetimeIndex,  # UTC 時間戳
    'open': float64,
    'high': float64,
    'low': float64,
    'close': float64,
    'real_volume': int64       # 用於 Volume Profile
})
```

### 缺少的元件

- ❌ **Plotly 和 Kaleido 依賴**：需要新增到 `requirements.txt`
- ❌ **視覺化模組**：`src/visualization/` 目錄和相關檔案
- ❌ **繪圖函數**：K 線圖、方塊、Volume Profile、輔助線等
- ❌ **整合到 analyze_vppa.py**：`--plot` 選項
- ❌ **測試檔案**：單元測試和視覺化驗證腳本
- ❌ **範例腳本**：展示如何使用繪圖功能

## 期望的最終狀態

### 功能規格

**1. 主要繪圖函數**：
```python
from src.visualization.vppa_plot import plot_vppa_chart

fig = plot_vppa_chart(
    vppa_json=vppa_data,           # analyze_vppa.py 的 JSON 輸出
    candles_df=df,                 # K 線 DataFrame
    output_path='output/chart.png', # PNG 輸出路徑（可選）
    show_pivot_points=True,        # 是否顯示 Pivot Points 標記
    show_developing=True,          # 是否顯示發展中區間
    width=1920,                    # 圖表寬度
    height=1080                    # 圖表高度
)
```

**2. 圖表元素**：
- ✅ K 線圖（Candlestick）：上漲綠色、下跌紅色
- ✅ Pivot Range 方塊：淺黃色填充（`rgba(255, 255, 153, 0.3)`）+ 深黃色邊框（`rgba(204, 153, 0, 1.0)`）
- ✅ 橫向 Volume Profile：靠左繪製，Value Area 內藍色、外灰色
- ✅ POC 線：紅色虛線
- ✅ VAH/VAL 線：綠色點線
- ⭕ Pivot Points 標記（可選）：High 紅色向下三角、Low 綠色向上三角

**3. 整合到分析流程**：
```bash
python scripts/analyze_vppa.py GOLD --count 2000 --plot --plot-output output/gold_vppa.png
```

### 驗證標準

#### 自動化驗證
- [ ] 所有函數都有完整的 docstring（Google 風格）
- [ ] 程式碼通過 Black 格式化（行長度 100）
- [ ] 單元測試通過（`pytest tests/test_vppa_plot.py`）
- [ ] 能成功產生 PNG 檔案

#### 手動驗證
- [ ] K 線圖正確顯示（顏色、時間軸、價格軸）
- [ ] Pivot Range 方塊位置正確（對齊 Pivot Points）
- [ ] Volume Profile 位置在區間左側，高度對應價格層級
- [ ] POC 線在成交量最大的價格
- [ ] VAH/VAL 線包含 68% 成交量
- [ ] PNG 圖片解析度足夠（文字清晰可讀）
- [ ] 互動式 HTML 圖表可正常縮放和 hover

## 不在本次實作範圍內的功能

為避免範圍膨脹，以下功能明確排除：

1. ❌ **多時間週期支援**：目前僅支援 M1，其他週期留待未來擴展
2. ❌ **圖表動畫效果**：靜態圖表為主，不實作動態更新
3. ❌ **自訂配色主題**：使用預設配色，主題功能延後
4. ❌ **匯出其他格式**：僅支援 PNG，SVG/PDF/HTML 延後
5. ❌ **互動式註解編輯**：僅顯示資訊，不支援使用者編輯
6. ❌ **效能優化（超大資料集）**：針對 2000-5000 根 K 線優化，更大資料集延後處理

## 實作方法

### 技術堆疊

**繪圖核心**：
- `plotly>=5.18.0`：互動式圖表繪製
- `kaleido>=0.2.1`：PNG 靜態圖片輸出

**資料處理**（已存在）：
- `pandas>=2.0.0`
- `numpy>=1.24.0`

**工具**（已存在）：
- `loguru>=0.7.0`：日誌記錄

### 模組架構

```
src/visualization/
├── __init__.py              # 匯出主要函數
├── vppa_plot.py             # VPPA 專用繪圖函數
├── plotly_utils.py          # Plotly 輔助工具（正規化、顏色等）
└── chart_config.py          # 圖表配置（顏色、字體、布局）
```

**核心函數設計**：

```python
# src/visualization/vppa_plot.py

def plot_vppa_chart(
    vppa_json: dict,
    candles_df: pd.DataFrame,
    output_path: str = None,
    show_pivot_points: bool = True,
    show_developing: bool = True,
    width: int = 1600,
    height: int = 900
) -> go.Figure:
    """
    繪製 VPPA 圖表（K 線圖 + Volume Profile）

    參數：
        vppa_json: analyze_vppa.py 的 JSON 輸出
        candles_df: K 線 DataFrame（需包含 'time', 'open', 'high', 'low', 'close'）
        output_path: PNG 輸出路徑（若為 None 則不儲存）
        show_pivot_points: 是否顯示 Pivot Points 標記
        show_developing: 是否顯示發展中區間
        width: 圖表寬度（像素）
        height: 圖表高度（像素）

    回傳：
        Plotly Figure 物件

    例外：
        ValueError: 資料格式錯誤或不一致時
    """
    pass

# 子函數
def _add_candlestick(fig: go.Figure, df: pd.DataFrame) -> None:
    """添加 K 線圖層"""
    pass

def _add_range_boxes(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """添加 Pivot Range 方塊"""
    pass

def _add_volume_profiles(fig: go.Figure, ranges: list, df: pd.DataFrame,
                         max_width_bars: int = 10) -> None:
    """添加 Volume Profile 長條圖"""
    pass

def _add_poc_lines(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """添加 POC 線"""
    pass

def _add_value_area_lines(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """添加 VAH/VAL 線"""
    pass

def _add_pivot_markers(fig: go.Figure, pivot_points: list, df: pd.DataFrame) -> None:
    """添加 Pivot Points 標記（可選）"""
    pass
```

```python
# src/visualization/plotly_utils.py

def map_idx_to_time(idx: int, df: pd.DataFrame) -> pd.Timestamp:
    """將整數索引映射到時間戳"""
    return df.iloc[idx]['time']

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
        return np.zeros_like(volumes)

    # 將最大成交量映射到 max_width_bars 根 K 線的寬度
    # M1 = 1 分鐘一根
    normalized = (volumes / max_volume) * max_width_bars
    return normalized

def validate_vppa_json(vppa_json: dict) -> None:
    """驗證 VPPA JSON 資料格式"""
    required_keys = ['symbol', 'timeframe', 'pivot_ranges', 'pivot_points']
    for key in required_keys:
        if key not in vppa_json:
            raise ValueError(f"VPPA JSON 缺少必要欄位：{key}")

def validate_candles_df(df: pd.DataFrame) -> None:
    """驗證 K 線 DataFrame 格式"""
    required_columns = ['time', 'open', 'high', 'low', 'close']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"K 線 DataFrame 缺少必要欄位：{missing}")
```

```python
# src/visualization/chart_config.py

"""
圖表配置常數
"""

# 顏色配置
COLORS = {
    # K 線顏色
    'candle_up': '#26a69a',      # 上漲（綠色）
    'candle_down': '#ef5350',    # 下跌（紅色）

    # Pivot Range 方塊
    'range_fill': 'rgba(255, 255, 153, 0.3)',    # 淺黃色填充
    'range_border': 'rgba(204, 153, 0, 1.0)',    # 深黃色邊框

    # Volume Profile
    'volume_in_va': 'rgba(100, 149, 237, 0.6)',   # Value Area 內（藍色）
    'volume_out_va': 'rgba(169, 169, 169, 0.4)',  # Value Area 外（灰色）

    # 輔助線
    'poc_line': 'rgb(255, 0, 0)',        # POC（紅色）
    'va_line': 'rgb(0, 128, 0)',         # VAH/VAL（綠色）

    # Pivot Points 標記
    'pivot_high': 'red',
    'pivot_low': 'green'
}

# 線條樣式
LINE_STYLES = {
    'poc': 'dash',     # 虛線
    'va': 'dot'        # 點線
}

# 圖表布局
DEFAULT_LAYOUT = {
    'plot_bgcolor': 'white',
    'paper_bgcolor': 'white',
    'font': {'family': 'Arial, sans-serif', 'size': 12},
    'hovermode': 'x unified',
    'showlegend': True,
    'legend': {
        'orientation': 'v',
        'yanchor': 'top',
        'y': 1,
        'xanchor': 'left',
        'x': 1.01
    }
}
```

### 實作流程圖

```
使用者執行 analyze_vppa.py GOLD --plot
    ↓
1. 分析 VPPA（已完成）
    ↓
2. 輸出 JSON 到 data/vppa_full_output.json
    ↓
3. 從 SQLite 快取取得 K 線資料
    ↓
4. 調用 plot_vppa_chart()
    ├── 驗證輸入資料
    ├── 建立 Plotly Figure
    ├── _add_candlestick() → K 線圖
    ├── _add_range_boxes() → 方塊
    ├── _add_volume_profiles() → Volume Profile
    ├── _add_poc_lines() → POC 線
    ├── _add_value_area_lines() → VAH/VAL 線
    └── _add_pivot_markers() → Pivot Points 標記（可選）
    ↓
5. 輸出 PNG 到 output/vppa_chart.png
    ↓
6. 完成
```

## 階段 1：環境準備與基礎架構（第 1 天）

### 目標
建立視覺化模組的基礎架構和開發環境。

### 任務清單

#### 1.1 更新專案依賴

**檔案**：`requirements.txt`

新增以下依賴：
```
# 視覺化
plotly>=5.18.0
kaleido>=0.2.1
```

**執行**：
```bash
pip install plotly kaleido
```

#### 1.2 建立視覺化模組結構

**建立目錄和檔案**：
```bash
mkdir -p src/visualization
touch src/visualization/__init__.py
touch src/visualization/vppa_plot.py
touch src/visualization/plotly_utils.py
touch src/visualization/chart_config.py
```

**檔案內容**：

**`src/visualization/__init__.py`**：
```python
"""
視覺化模組

提供 Plotly 圖表繪製功能，專注於 VPPA 分析結果的視覺化。
"""

from .vppa_plot import plot_vppa_chart

__all__ = ['plot_vppa_chart']
```

**`src/visualization/chart_config.py`**：
（完整內容如「實作方法」章節所示）

**`src/visualization/plotly_utils.py`**：
（框架，實作輔助函數的空框架）

**`src/visualization/vppa_plot.py`**：
（框架，實作主函數和子函數的空框架）

#### 1.3 建立輸出目錄

```bash
mkdir -p output
```

### 成功標準

#### 自動化驗證
- [ ] `pip list | grep plotly` 顯示 plotly >= 5.18.0
- [ ] `pip list | grep kaleido` 顯示 kaleido >= 0.2.1
- [ ] `ls src/visualization` 顯示所有檔案都已建立
- [ ] `python -c "from src.visualization import plot_vppa_chart"` 不報錯

#### 手動驗證
- [ ] 確認 `output/` 目錄已建立
- [ ] 確認所有 `.py` 檔案都有基本的 docstring

**實作注意事項**：完成此階段後，暫停並確認環境設定正確，再繼續下一階段。

---

## 階段 2：K 線圖與方塊繪製（第 2-3 天）

### 目標
實作 K 線圖和 Pivot Range 方塊的繪製功能。

### 任務清單

#### 2.1 實作輔助函數

**檔案**：`src/visualization/plotly_utils.py`

```python
import pandas as pd
import numpy as np
from loguru import logger

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
    """驗證 VPPA JSON 資料格式"""
    required_keys = ['symbol', 'timeframe', 'pivot_ranges', 'pivot_points']
    for key in required_keys:
        if key not in vppa_json:
            raise ValueError(f"VPPA JSON 缺少必要欄位：{key}")

    logger.info(f"VPPA JSON 驗證通過：{vppa_json['symbol']} {vppa_json['timeframe']}")

def validate_candles_df(df: pd.DataFrame) -> None:
    """驗證 K 線 DataFrame 格式"""
    required_columns = ['time', 'open', 'high', 'low', 'close']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"K 線 DataFrame 缺少必要欄位：{missing}")

    if len(df) == 0:
        raise ValueError("K 線 DataFrame 不能為空")

    logger.info(f"K 線 DataFrame 驗證通過：{len(df)} 筆資料")
```

#### 2.2 實作 K 線圖繪製

**檔案**：`src/visualization/vppa_plot.py`

```python
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from loguru import logger
from typing import Optional

from .chart_config import COLORS, DEFAULT_LAYOUT
from .plotly_utils import validate_vppa_json, validate_candles_df, map_idx_to_time

def _add_candlestick(fig: go.Figure, df: pd.DataFrame) -> None:
    """
    添加 K 線圖層

    參數：
        fig: Plotly Figure 物件
        df: K 線 DataFrame
    """
    logger.debug("添加 K 線圖層")

    candlestick = go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='K線',
        increasing_line_color=COLORS['candle_up'],
        decreasing_line_color=COLORS['candle_down'],
        increasing_fillcolor=COLORS['candle_up'],
        decreasing_fillcolor=COLORS['candle_down']
    )

    fig.add_trace(candlestick)
    logger.debug(f"K 線圖層添加完成：{len(df)} 根 K 線")
```

#### 2.3 實作 Pivot Range 方塊繪製

**檔案**：`src/visualization/vppa_plot.py`（續）

```python
def _add_range_boxes(
    fig: go.Figure,
    ranges: list,
    df: pd.DataFrame,
    show_developing: bool = True
) -> None:
    """
    添加 Pivot Range 方塊

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
        df: K 線 DataFrame
        show_developing: 是否顯示發展中區間
    """
    logger.debug(f"添加 {len(ranges)} 個 Pivot Range 方塊")

    shapes = []

    for range_data in ranges:
        # 映射索引到時間
        start_time = map_idx_to_time(range_data['start_idx'], df)
        end_time = map_idx_to_time(range_data['end_idx'], df)

        # 價格範圍
        lowest_price = range_data['price_info']['lowest']
        highest_price = range_data['price_info']['highest']

        # 建立矩形
        shapes.append(dict(
            type='rect',
            x0=start_time,
            x1=end_time,
            y0=lowest_price,
            y1=highest_price,
            fillcolor=COLORS['range_fill'],
            line=dict(
                color=COLORS['range_border'],
                width=2
            ),
            layer='below'  # 放在 K 線圖下層
        ))

    # 批量添加所有 shapes（效能優化）
    fig.update_layout(shapes=shapes)
    logger.debug(f"方塊繪製完成：{len(shapes)} 個")
```

#### 2.4 實作主函數框架

**檔案**：`src/visualization/vppa_plot.py`（續）

```python
def plot_vppa_chart(
    vppa_json: dict,
    candles_df: pd.DataFrame,
    output_path: Optional[str] = None,
    show_pivot_points: bool = False,  # 階段 2 先不實作
    show_developing: bool = True,
    width: int = 1600,
    height: int = 900
) -> go.Figure:
    """
    繪製 VPPA 圖表（K 線圖 + Volume Profile）

    參數：
        vppa_json: analyze_vppa.py 的 JSON 輸出
        candles_df: K 線 DataFrame（需包含 'time', 'open', 'high', 'low', 'close'）
        output_path: PNG 輸出路徑（若為 None 則不儲存）
        show_pivot_points: 是否顯示 Pivot Points 標記（階段 2 暫不支援）
        show_developing: 是否顯示發展中區間
        width: 圖表寬度（像素）
        height: 圖表高度（像素）

    回傳：
        Plotly Figure 物件

    例外：
        ValueError: 資料格式錯誤或不一致時
    """
    logger.info("=" * 60)
    logger.info("開始繪製 VPPA 圖表")
    logger.info("=" * 60)

    # 驗證輸入
    validate_vppa_json(vppa_json)
    validate_candles_df(candles_df)

    # 建立 Figure
    fig = go.Figure()

    # 階段 2：添加 K 線圖和方塊
    _add_candlestick(fig, candles_df)
    _add_range_boxes(fig, vppa_json['pivot_ranges'], candles_df, show_developing)

    # 階段 3：添加 Volume Profile（暫時跳過）
    # _add_volume_profiles(fig, vppa_json['pivot_ranges'], candles_df)

    # 階段 4：添加輔助線（暫時跳過）
    # _add_poc_lines(fig, vppa_json['pivot_ranges'], candles_df)
    # _add_value_area_lines(fig, vppa_json['pivot_ranges'], candles_df)

    # 設定布局
    symbol = vppa_json['symbol']
    timeframe = vppa_json['timeframe']

    fig.update_layout(
        title={
            'text': f'{symbol} {timeframe} - Volume Profile Pivot Anchored',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis={
            'title': '時間',
            'type': 'date',
            'rangeslider': {'visible': False}
        },
        yaxis={
            'title': '價格',
            'fixedrange': False
        },
        width=width,
        height=height,
        **DEFAULT_LAYOUT
    )

    # 輸出 PNG
    if output_path:
        logger.info(f"輸出 PNG 到：{output_path}")
        fig.write_image(output_path, width=width, height=height, scale=2)
        logger.info("PNG 輸出完成")

    logger.info("=" * 60)
    logger.info("VPPA 圖表繪製完成")
    logger.info("=" * 60)

    return fig
```

#### 2.5 建立測試腳本

**檔案**：`examples/plot_vppa_basic.py`

```python
#!/usr/bin/env python3
"""
VPPA 視覺化基本測試（階段 2）

此腳本測試 K 線圖和 Pivot Range 方塊的繪製功能。
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

    # 3. 繪製圖表（階段 2：僅 K 線圖 + 方塊）
    output_path = Path('output/vppa_chart_stage2.png')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n繪製圖表中...")

    fig = plot_vppa_chart(
        vppa_json=vppa_data,
        candles_df=df,
        output_path=str(output_path),
        show_pivot_points=False,  # 階段 2 不支援
        show_developing=True,
        width=1920,
        height=1080
    )

    print(f"\n✅ 圖表已儲存到：{output_path}")
    print("\n階段 2 測試完成！")
    print("請檢查以下項目：")
    print("  [ ] K 線圖正確顯示")
    print("  [ ] Pivot Range 方塊位置正確")
    print("  [ ] 方塊顏色為淺黃色填充 + 深黃色邊框")
    print("  [ ] 方塊在 K 線圖下層")

if __name__ == '__main__':
    main()
```

**執行**：
```bash
python examples/plot_vppa_basic.py
```

### 成功標準

#### 自動化驗證
- [ ] `python examples/plot_vppa_basic.py` 執行成功
- [ ] `output/vppa_chart_stage2.png` 檔案已產生
- [ ] 檔案大小 > 100 KB（確認有內容）
- [ ] 日誌顯示「VPPA 圖表繪製完成」

#### 手動驗證
- [ ] 開啟 `output/vppa_chart_stage2.png`
- [ ] K 線圖正確顯示（上漲綠色、下跌紅色）
- [ ] Pivot Range 方塊位置正確（對應 Pivot Points）
- [ ] 方塊顏色為淺黃色填充 + 深黃色邊框
- [ ] 方塊在 K 線圖下層（不遮蓋 K 線）
- [ ] 時間軸和價格軸標籤清晰可讀

**實作注意事項**：完成此階段後，暫停並進行人工視覺化驗證，確認方塊位置和顏色正確，再繼續下一階段。

---

## 階段 3：Volume Profile 繪製（第 4-5 天）

### 目標
實作橫向 Volume Profile 直方圖的繪製功能。

### 任務清單

#### 3.1 實作成交量正規化函數

**檔案**：`src/visualization/plotly_utils.py`（續）

```python
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
```

**注意**：需要在 `plotly_utils.py` 開頭添加 `from .chart_config import COLORS`

#### 3.2 實作 Volume Profile 繪製

**檔案**：`src/visualization/vppa_plot.py`（續）

```python
from datetime import timedelta

def _add_volume_profiles(
    fig: go.Figure,
    ranges: list,
    df: pd.DataFrame,
    max_width_bars: int = 10
) -> None:
    """
    添加 Volume Profile 長條圖

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
        df: K 線 DataFrame
        max_width_bars: Volume Profile 最大寬度（以 K 線數量為單位）
    """
    logger.debug(f"添加 {len(ranges)} 個 Volume Profile")

    from .plotly_utils import normalize_volume_width, get_volume_colors, map_idx_to_time

    for i, range_data in enumerate(ranges):
        # 取得資料
        price_centers = np.array(range_data['volume_profile']['price_centers'])
        volumes = np.array(range_data['volume_profile']['volumes'])

        # 正規化成交量寬度（轉換為分鐘）
        normalized_widths = normalize_volume_width(volumes, max_width_bars, 'M1')

        # 映射起始時間
        start_time = map_idx_to_time(range_data['start_idx'], df)

        # 計算每個長條的 X 座標（終點）
        x_values = []
        for width_minutes in normalized_widths:
            x_values.append(start_time + timedelta(minutes=width_minutes))

        # 取得顏色（Value Area 內外不同顏色）
        vah = range_data['value_area']['vah']
        val = range_data['value_area']['val']
        colors = get_volume_colors(price_centers, vah, val)

        # 計算長條高度（價格方向）
        price_step = range_data['price_info']['step']

        # 建立自訂資料（用於 hover 顯示原始成交量）
        customdata = volumes

        # 繪製橫向長條圖
        fig.add_trace(go.Bar(
            x=x_values,
            y=price_centers,
            orientation='h',
            marker=dict(
                color=colors,
                line=dict(width=0)
            ),
            width=price_step,  # 長條高度 = 價格步長
            name=f'VP {range_data["range_id"]}',
            showlegend=False,
            hovertemplate=(
                '價格: %{y:.2f}<br>'
                '成交量: %{customdata:.0f}<br>'
                '<extra></extra>'
            ),
            customdata=customdata,
            base=start_time  # 設定長條起點
        ))

    logger.debug(f"Volume Profile 繪製完成：{len(ranges)} 個")
```

#### 3.3 更新主函數

**檔案**：`src/visualization/vppa_plot.py`（修改 `plot_vppa_chart()`）

在階段 2 的基礎上，取消註解以下行：
```python
# 階段 3：添加 Volume Profile
_add_volume_profiles(fig, vppa_json['pivot_ranges'], candles_df)
```

#### 3.4 更新測試腳本

**檔案**：`examples/plot_vppa_basic.py`（修改輸出路徑）

```python
output_path = Path('output/vppa_chart_stage3.png')
```

並更新檢查清單：
```python
print("  [ ] K 線圖正確顯示")
print("  [ ] Pivot Range 方塊位置正確")
print("  [ ] Volume Profile 位置在區間左側")
print("  [ ] Volume Profile 高度對應價格層級")
print("  [ ] Value Area 內為藍色，外為灰色")
print("  [ ] Volume Profile 未遮蓋 K 線圖")
```

**執行**：
```bash
python examples/plot_vppa_basic.py
```

### 成功標準

#### 自動化驗證
- [ ] `python examples/plot_vppa_basic.py` 執行成功
- [ ] `output/vppa_chart_stage3.png` 檔案已產生
- [ ] 日誌顯示「Volume Profile 繪製完成」

#### 手動驗證
- [ ] 開啟 `output/vppa_chart_stage3.png`
- [ ] Volume Profile 位置在每個區間的左側
- [ ] Volume Profile 高度對應價格層級（與方塊高度一致）
- [ ] Value Area 內的長條為藍色
- [ ] Value Area 外的長條為灰色
- [ ] Volume Profile 寬度適中（未遮蓋 K 線）
- [ ] 滑鼠 hover 可顯示原始成交量值

**實作注意事項**：
1. 如果 Volume Profile 過大（遮蓋 K 線），調整 `max_width_bars` 參數（預設 10，可改為 8 或 6）
2. 如果顏色對比不夠，可調整 `chart_config.py` 中的 `COLORS` 配置
3. 完成此階段後，暫停並進行人工視覺化驗證，確認 Volume Profile 位置和顏色正確

---

## 階段 4：輔助線與標記（第 6 天）

### 目標
添加 POC 線、VAH/VAL 線和 Pivot Points 標記。

### 任務清單

#### 4.1 實作 POC 線繪製

**檔案**：`src/visualization/vppa_plot.py`（續）

```python
def _add_poc_lines(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """
    添加 POC（Point of Control）線

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
        df: K 線 DataFrame
    """
    logger.debug(f"添加 {len(ranges)} 條 POC 線")

    from .chart_config import COLORS, LINE_STYLES
    from .plotly_utils import map_idx_to_time

    # 合併所有 POC 線為單一 Trace（效能優化）
    all_x = []
    all_y = []

    for range_data in ranges:
        start_time = map_idx_to_time(range_data['start_idx'], df)
        end_time = map_idx_to_time(range_data['end_idx'], df)
        poc_price = range_data['poc']['price']

        # 添加線段（使用 None 分隔不同線段）
        all_x.extend([start_time, end_time, None])
        all_y.extend([poc_price, poc_price, None])

    # 繪製所有 POC 線
    fig.add_trace(go.Scatter(
        x=all_x,
        y=all_y,
        mode='lines',
        line=dict(
            color=COLORS['poc_line'],
            width=2,
            dash=LINE_STYLES['poc']
        ),
        name='POC',
        showlegend=True,
        hovertemplate='POC: %{y:.2f}<extra></extra>'
    ))

    logger.debug(f"POC 線繪製完成：{len(ranges)} 條")
```

#### 4.2 實作 VAH/VAL 線繪製

**檔案**：`src/visualization/vppa_plot.py`（續）

```python
def _add_value_area_lines(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """
    添加 VAH（Value Area High）和 VAL（Value Area Low）線

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
        df: K 線 DataFrame
    """
    logger.debug(f"添加 {len(ranges)} 組 Value Area 線")

    from .chart_config import COLORS, LINE_STYLES
    from .plotly_utils import map_idx_to_time

    # VAH 線（合併）
    vah_x = []
    vah_y = []

    # VAL 線（合併）
    val_x = []
    val_y = []

    for range_data in ranges:
        start_time = map_idx_to_time(range_data['start_idx'], df)
        end_time = map_idx_to_time(range_data['end_idx'], df)
        vah = range_data['value_area']['vah']
        val = range_data['value_area']['val']

        # VAH 線段
        vah_x.extend([start_time, end_time, None])
        vah_y.extend([vah, vah, None])

        # VAL 線段
        val_x.extend([start_time, end_time, None])
        val_y.extend([val, val, None])

    # 繪製 VAH 線
    fig.add_trace(go.Scatter(
        x=vah_x,
        y=vah_y,
        mode='lines',
        line=dict(
            color=COLORS['va_line'],
            width=1.5,
            dash=LINE_STYLES['va']
        ),
        name='VAH',
        showlegend=True,
        hovertemplate='VAH: %{y:.2f}<extra></extra>'
    ))

    # 繪製 VAL 線
    fig.add_trace(go.Scatter(
        x=val_x,
        y=val_y,
        mode='lines',
        line=dict(
            color=COLORS['va_line'],
            width=1.5,
            dash=LINE_STYLES['va']
        ),
        name='VAL',
        showlegend=True,
        hovertemplate='VAL: %{y:.2f}<extra></extra>'
    ))

    logger.debug(f"Value Area 線繪製完成：{len(ranges)} 組")
```

#### 4.3 實作 Pivot Points 標記（可選）

**檔案**：`src/visualization/vppa_plot.py`（續）

```python
def _add_pivot_markers(fig: go.Figure, pivot_points: list, df: pd.DataFrame) -> None:
    """
    添加 Pivot Points 標記（可選）

    參數：
        fig: Plotly Figure 物件
        pivot_points: pivot_points 列表
        df: K 線 DataFrame
    """
    if not pivot_points:
        logger.debug("無 Pivot Points 需要標記")
        return

    logger.debug(f"添加 {len(pivot_points)} 個 Pivot Points 標記")

    from .chart_config import COLORS
    from .plotly_utils import map_idx_to_time

    # 分離 Pivot High 和 Pivot Low
    high_points = [p for p in pivot_points if p['type'] == 'H']
    low_points = [p for p in pivot_points if p['type'] == 'L']

    # Pivot High 標記
    if high_points:
        high_times = [map_idx_to_time(p['idx'], df) for p in high_points]
        high_prices = [p['price'] for p in high_points]

        fig.add_trace(go.Scatter(
            x=high_times,
            y=high_prices,
            mode='markers',
            marker=dict(
                symbol='triangle-down',
                size=10,
                color=COLORS['pivot_high']
            ),
            name='Pivot High',
            showlegend=True,
            hovertemplate='Pivot High: %{y:.2f}<extra></extra>'
        ))

    # Pivot Low 標記
    if low_points:
        low_times = [map_idx_to_time(p['idx'], df) for p in low_points]
        low_prices = [p['price'] for p in low_points]

        fig.add_trace(go.Scatter(
            x=low_times,
            y=low_prices,
            mode='markers',
            marker=dict(
                symbol='triangle-up',
                size=10,
                color=COLORS['pivot_low']
            ),
            name='Pivot Low',
            showlegend=True,
            hovertemplate='Pivot Low: %{y:.2f}<extra></extra>'
        ))

    logger.debug(f"Pivot Points 標記完成：{len(high_points)} High, {len(low_points)} Low")
```

#### 4.4 更新主函數

**檔案**：`src/visualization/vppa_plot.py`（修改 `plot_vppa_chart()`）

取消註解以下行：
```python
# 階段 4：添加輔助線
_add_poc_lines(fig, vppa_json['pivot_ranges'], candles_df)
_add_value_area_lines(fig, vppa_json['pivot_ranges'], candles_df)

# 可選：Pivot Points 標記
if show_pivot_points:
    _add_pivot_markers(fig, vppa_json['pivot_points'], candles_df)
```

並修改函數簽名：
```python
def plot_vppa_chart(
    vppa_json: dict,
    candles_df: pd.DataFrame,
    output_path: Optional[str] = None,
    show_pivot_points: bool = True,  # 修改為 True
    show_developing: bool = True,
    width: int = 1600,
    height: int = 900
) -> go.Figure:
```

#### 4.5 更新測試腳本

**檔案**：`examples/plot_vppa_basic.py`（修改）

```python
output_path = Path('output/vppa_chart_stage4.png')

fig = plot_vppa_chart(
    vppa_json=vppa_data,
    candles_df=df,
    output_path=str(output_path),
    show_pivot_points=True,  # 啟用 Pivot Points 標記
    show_developing=True,
    width=1920,
    height=1080
)
```

並更新檢查清單：
```python
print("  [ ] POC 線在成交量最大的價格")
print("  [ ] VAH/VAL 線包含約 68% 成交量")
print("  [ ] Pivot High 標記（紅色向下三角）位置正確")
print("  [ ] Pivot Low 標記（綠色向上三角）位置正確")
```

### 成功標準

#### 自動化驗證
- [ ] `python examples/plot_vppa_basic.py` 執行成功
- [ ] `output/vppa_chart_stage4.png` 檔案已產生
- [ ] 日誌顯示「POC 線繪製完成」
- [ ] 日誌顯示「Value Area 線繪製完成」
- [ ] 日誌顯示「Pivot Points 標記完成」

#### 手動驗證
- [ ] POC 線（紅色虛線）在每個區間成交量最大的價格
- [ ] VAH/VAL 線（綠色點線）正確標示 Value Area 範圍
- [ ] Pivot High 標記（紅色向下三角）在高點位置
- [ ] Pivot Low 標記（綠色向上三角）在低點位置
- [ ] 所有線條和標記未過度遮蓋 K 線圖
- [ ] 圖例清晰可讀

**實作注意事項**：
1. 如果標記過多導致圖表擁擠，可調整 `marker.size` 參數（預設 10，可改為 8）
2. 如果線條顏色對比不夠，可調整 `chart_config.py` 中的配色
3. 完成此階段後，已具備完整的 VPPA 視覺化功能

---

## 階段 5：整合到 analyze_vppa.py（第 7 天）

### 目標
將繪圖功能整合到 VPPA 分析流程中，支援 `--plot` 選項。

### 任務清單

#### 5.1 修改 analyze_vppa.py

**檔案**：`scripts/analyze_vppa.py`

在 `argparse` 部分添加 `--plot` 相關參數：

```python
# 在 parser.add_argument('--pretty', ...) 之後添加：

parser.add_argument(
    '--plot',
    action='store_true',
    help='分析完成後自動繪製圖表'
)

parser.add_argument(
    '--plot-output',
    type=str,
    default=None,
    help='圖表輸出路徑（預設：output/{SYMBOL}_vppa_{YYYYMMDD}.png）'
)

parser.add_argument(
    '--plot-width',
    type=int,
    default=1920,
    help='圖表寬度（預設：1920）'
)

parser.add_argument(
    '--plot-height',
    type=int,
    default=1080,
    help='圖表高度（預設：1080）'
)

parser.add_argument(
    '--no-pivot-markers',
    action='store_true',
    help='不顯示 Pivot Points 標記'
)
```

在 `main()` 函數的最後（輸出 JSON 之後）添加繪圖邏輯：

```python
# 在 print(json.dumps(...)) 或檔案輸出之後添加：

# 繪製圖表（如果指定了 --plot）
if args.plot:
    logger.info("=" * 60)
    logger.info("開始繪製 VPPA 圖表")
    logger.info("=" * 60)

    try:
        from src.visualization import plot_vppa_chart

        # 確定輸出路徑
        if args.plot_output:
            plot_output_path = Path(args.plot_output)
        else:
            # 預設路徑：output/{SYMBOL}_vppa_{YYYYMMDD}.png
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            plot_output_path = Path(f'output/{args.symbol.upper()}_vppa_{date_str}.png')

        # 確保輸出目錄存在
        plot_output_path.parent.mkdir(parents=True, exist_ok=True)

        # 繪製圖表
        fig = plot_vppa_chart(
            vppa_json=result,
            candles_df=df,
            output_path=str(plot_output_path),
            show_pivot_points=not args.no_pivot_markers,
            show_developing=True,
            width=args.plot_width,
            height=args.plot_height
        )

        print(f"\n✅ 圖表已輸出到：{plot_output_path}")

    except ImportError as e:
        logger.error(f"無法匯入視覺化模組：{e}")
        print(f"\n❌ 繪圖失敗：缺少視覺化模組")
        print("   請確認已安裝 plotly 和 kaleido：pip install plotly kaleido")

    except Exception as e:
        logger.error(f"繪圖失敗：{e}")
        print(f"\n❌ 繪圖失敗：{e}")
```

#### 5.2 測試整合功能

**執行完整流程**：

```bash
# 測試 1：基本繪圖
python scripts/analyze_vppa.py GOLD --count 2000 --plot

# 測試 2：指定輸出路徑
python scripts/analyze_vppa.py GOLD --count 2000 --plot --plot-output output/test_gold.png

# 測試 3：不顯示 Pivot Points 標記
python scripts/analyze_vppa.py GOLD --count 2000 --plot --no-pivot-markers

# 測試 4：自訂圖表大小
python scripts/analyze_vppa.py GOLD --count 2000 --plot --plot-width 2560 --plot-height 1440
```

#### 5.3 更新 README.md

**檔案**：`README.md`

在使用說明部分添加視覺化功能說明：

```markdown
### VPPA 視覺化

分析完成後可自動產生 VPPA 圖表：

```bash
# 基本用法：分析並繪製圖表
python scripts/analyze_vppa.py GOLD --count 2000 --plot

# 指定輸出路徑
python scripts/analyze_vppa.py GOLD --plot --plot-output output/my_chart.png

# 自訂圖表大小
python scripts/analyze_vppa.py GOLD --plot --plot-width 2560 --plot-height 1440

# 不顯示 Pivot Points 標記（簡化圖表）
python scripts/analyze_vppa.py GOLD --plot --no-pivot-markers
```

圖表包含：
- K 線圖（上漲綠色、下跌紅色）
- Pivot Range 方塊（淺黃色填充 + 深黃色邊框）
- 橫向 Volume Profile（Value Area 內藍色、外灰色）
- POC 線（紅色虛線）
- VAH/VAL 線（綠色點線）
- Pivot Points 標記（可選）
```

### 成功標準

#### 自動化驗證
- [ ] `python scripts/analyze_vppa.py GOLD --count 500 --plot` 執行成功
- [ ] 圖表檔案產生在預設路徑（`output/GOLD_vppa_YYYYMMDD.png`）
- [ ] `python scripts/analyze_vppa.py GOLD --plot --plot-output output/test.png` 產生 `output/test.png`
- [ ] `--no-pivot-markers` 選項有效（圖表無 Pivot Points 標記）

#### 手動驗證
- [ ] 圖表包含所有視覺化元素（K 線、方塊、Volume Profile、輔助線）
- [ ] 圖表解析度符合設定（預設 1920x1080）
- [ ] 日誌清晰記錄每個步驟
- [ ] 錯誤處理正常（例如：缺少 plotly 時顯示友善錯誤訊息）

**實作注意事項**：
1. 確保 `df` 在繪圖時仍可用（不要提前刪除）
2. 錯誤處理要完善，避免繪圖失敗導致整個分析流程中斷
3. 輸出路徑要處理特殊字元和空格

---

## 階段 6：測試與文檔（第 8 天）

### 目標
建立完整的單元測試和使用文檔。

### 任務清單

#### 6.1 建立單元測試

**檔案**：`tests/test_vppa_plot.py`

```python
"""
VPPA 視覺化模組單元測試
"""

import pytest
import json
import pandas as pd
import numpy as np
from pathlib import Path
import plotly.graph_objects as go

from src.visualization import plot_vppa_chart
from src.visualization.plotly_utils import (
    map_idx_to_time,
    normalize_volume_width,
    validate_vppa_json,
    validate_candles_df
)

# 測試資料目錄
FIXTURES_DIR = Path(__file__).parent / 'fixtures'

@pytest.fixture
def sample_candles_df():
    """建立範例 K 線 DataFrame"""
    return pd.DataFrame({
        'time': pd.date_range('2025-01-01', periods=100, freq='1min'),
        'open': np.random.uniform(4500, 4520, 100),
        'high': np.random.uniform(4510, 4530, 100),
        'low': np.random.uniform(4490, 4510, 100),
        'close': np.random.uniform(4500, 4520, 100),
        'real_volume': np.random.randint(50000, 100000, 100)
    })

@pytest.fixture
def sample_vppa_json():
    """建立範例 VPPA JSON 資料"""
    return {
        'symbol': 'GOLD',
        'timeframe': 'M1',
        'pivot_points': [
            {'idx': 20, 'type': 'H', 'price': 4520.0, 'time': '2025-01-01T00:20:00'},
            {'idx': 40, 'type': 'L', 'price': 4500.0, 'time': '2025-01-01T00:40:00'}
        ],
        'pivot_ranges': [
            {
                'range_id': 0,
                'start_idx': 20,
                'end_idx': 40,
                'price_info': {'highest': 4520.0, 'lowest': 4500.0, 'step': 1.0},
                'poc': {'price': 4510.0, 'volume': 100000.0},
                'value_area': {'vah': 4515.0, 'val': 4505.0},
                'volume_profile': {
                    'price_centers': [4500.0 + i for i in range(20)],
                    'volumes': [50000.0 + i * 1000 for i in range(20)]
                }
            }
        ]
    }

class TestPlotlyUtils:
    """測試 plotly_utils 模組"""

    def test_map_idx_to_time(self, sample_candles_df):
        """測試索引到時間的映射"""
        result = map_idx_to_time(0, sample_candles_df)
        assert result == pd.Timestamp('2025-01-01 00:00:00')

        result = map_idx_to_time(50, sample_candles_df)
        assert result == pd.Timestamp('2025-01-01 00:50:00')

    def test_map_idx_to_time_out_of_range(self, sample_candles_df):
        """測試索引超出範圍"""
        with pytest.raises(IndexError):
            map_idx_to_time(1000, sample_candles_df)

    def test_normalize_volume_width(self):
        """測試成交量正規化"""
        volumes = np.array([100000, 200000, 50000])
        result = normalize_volume_width(volumes, max_width_bars=10, timeframe='M1')

        # 最大值應該對應到 10 分鐘
        assert result.max() == 10

        # 比例應該正確
        assert result[0] == 5  # 100000 / 200000 * 10
        assert result[2] == 2.5  # 50000 / 200000 * 10

    def test_validate_vppa_json_success(self, sample_vppa_json):
        """測試 VPPA JSON 驗證（成功）"""
        validate_vppa_json(sample_vppa_json)  # 不應拋出例外

    def test_validate_vppa_json_missing_key(self):
        """測試 VPPA JSON 驗證（缺少欄位）"""
        invalid_json = {'symbol': 'GOLD'}  # 缺少其他必要欄位

        with pytest.raises(ValueError, match='缺少必要欄位'):
            validate_vppa_json(invalid_json)

    def test_validate_candles_df_success(self, sample_candles_df):
        """測試 K 線 DataFrame 驗證（成功）"""
        validate_candles_df(sample_candles_df)  # 不應拋出例外

    def test_validate_candles_df_missing_column(self):
        """測試 K 線 DataFrame 驗證（缺少欄位）"""
        invalid_df = pd.DataFrame({'time': [1, 2, 3]})

        with pytest.raises(ValueError, match='缺少必要欄位'):
            validate_candles_df(invalid_df)

class TestVPPAPlot:
    """測試 VPPA 繪圖功能"""

    def test_plot_vppa_chart_basic(self, sample_vppa_json, sample_candles_df, tmp_path):
        """測試基本繪圖功能"""
        output_path = tmp_path / 'test_chart.png'

        fig = plot_vppa_chart(
            vppa_json=sample_vppa_json,
            candles_df=sample_candles_df,
            output_path=str(output_path),
            show_pivot_points=False
        )

        # 驗證回傳的是 Plotly Figure
        assert isinstance(fig, go.Figure)

        # 驗證圖表有資料
        assert len(fig.data) > 0

        # 驗證 PNG 檔案已建立
        assert output_path.exists()
        assert output_path.stat().st_size > 1000  # 至少 1KB

    def test_plot_vppa_chart_with_pivot_markers(self, sample_vppa_json, sample_candles_df):
        """測試包含 Pivot Points 標記的繪圖"""
        fig = plot_vppa_chart(
            vppa_json=sample_vppa_json,
            candles_df=sample_candles_df,
            output_path=None,
            show_pivot_points=True
        )

        assert isinstance(fig, go.Figure)
        # Pivot Points 標記會增加 trace 數量
        assert len(fig.data) >= 2  # 至少有 K 線圖 + Pivot High 或 Pivot Low

    def test_plot_vppa_chart_invalid_json(self, sample_candles_df):
        """測試無效的 VPPA JSON"""
        invalid_json = {'symbol': 'GOLD'}  # 缺少必要欄位

        with pytest.raises(ValueError):
            plot_vppa_chart(
                vppa_json=invalid_json,
                candles_df=sample_candles_df
            )

    def test_plot_vppa_chart_invalid_df(self, sample_vppa_json):
        """測試無效的 K 線 DataFrame"""
        invalid_df = pd.DataFrame({'time': [1, 2, 3]})

        with pytest.raises(ValueError):
            plot_vppa_chart(
                vppa_json=sample_vppa_json,
                candles_df=invalid_df
            )

# 執行測試
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

**執行測試**：
```bash
pytest tests/test_vppa_plot.py -v
```

#### 6.2 建立視覺化驗證腳本

**檔案**：`scripts/visual_verification.py`

```python
#!/usr/bin/env python3
"""
VPPA 視覺化驗證腳本

此腳本產生 VPPA 圖表並輸出驗證 Checklist，
幫助人工檢查視覺化結果是否正確。
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.core.sqlite_cache import SQLiteCacheManager
from src.visualization import plot_vppa_chart

def main():
    print("=" * 70)
    print("VPPA 視覺化驗證腳本")
    print("=" * 70)

    # 1. 載入 VPPA 資料
    vppa_json_path = Path('data/vppa_full_output.json')

    if not vppa_json_path.exists():
        print(f"\n❌ 找不到 VPPA 資料檔案：{vppa_json_path}")
        print("請先執行：python scripts/analyze_vppa.py GOLD --output data/vppa_full_output.json")
        sys.exit(1)

    with open(vppa_json_path, 'r', encoding='utf-8') as f:
        vppa_data = json.load(f)

    print(f"\n✅ 載入 VPPA 資料")
    print(f"   商品: {vppa_data['symbol']}")
    print(f"   時間週期: {vppa_data['timeframe']}")
    print(f"   Pivot Points: {vppa_data['summary']['total_pivot_points']}")
    print(f"   區間數量: {vppa_data['summary']['total_ranges']}")

    # 2. 載入 K 線資料
    cache = SQLiteCacheManager('data/candles.db')
    symbol = vppa_data['symbol']
    timeframe = vppa_data['timeframe']
    start_time = pd.Timestamp(vppa_data['data_range']['start_time'])
    end_time = pd.Timestamp(vppa_data['data_range']['end_time'])

    df = cache.query_candles(symbol, timeframe, start_time, end_time)

    if df is None or len(df) == 0:
        print("\n❌ 無法從快取取得 K 線資料")
        sys.exit(1)

    print(f"\n✅ 取得 K 線資料：{len(df)} 筆")

    # 3. 產生圖表
    output_path = Path('output/vppa_verification.png')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n繪製圖表中...")

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

    # 4. 輸出驗證 Checklist
    print("\n" + "=" * 70)
    print("視覺化驗證 Checklist")
    print("=" * 70)
    print(f"\n圖表資訊：")
    print(f"  K 線數量：{len(df)}")
    print(f"  Pivot Points 數量：{len(vppa_data['pivot_points'])}")
    print(f"  Pivot Ranges 數量：{len(vppa_data['pivot_ranges'])}")
    print(f"  圖表檔案：{output_path}")

    print(f"\n請開啟圖表並檢查以下項目：")
    print(f"\n【基本元素】")
    print(f"  [ ] K 線圖正確顯示（上漲綠色、下跌紅色）")
    print(f"  [ ] 時間軸標籤清晰可讀")
    print(f"  [ ] 價格軸標籤清晰可讀")
    print(f"  [ ] 圖表標題顯示正確（{symbol} {timeframe}）")

    print(f"\n【Pivot Range 方塊】")
    print(f"  [ ] 方塊數量正確（{len(vppa_data['pivot_ranges'])} 個）")
    print(f"  [ ] 方塊顏色為淺黃色填充 + 深黃色邊框")
    print(f"  [ ] 方塊位置對應 Pivot Points")
    print(f"  [ ] 方塊在 K 線圖下層（不遮蓋 K 線）")

    print(f"\n【Volume Profile】")
    print(f"  [ ] Volume Profile 位置在區間左側")
    print(f"  [ ] Volume Profile 高度對應價格層級")
    print(f"  [ ] Value Area 內的長條為藍色")
    print(f"  [ ] Value Area 外的長條為灰色")
    print(f"  [ ] Volume Profile 未過度遮蓋 K 線")

    print(f"\n【輔助線】")
    print(f"  [ ] POC 線（紅色虛線）在成交量最大的價格")
    print(f"  [ ] VAH 線（綠色點線）在 Value Area 上界")
    print(f"  [ ] VAL 線（綠色點線）在 Value Area 下界")
    print(f"  [ ] VAH 和 VAL 之間包含約 68% 成交量")

    print(f"\n【Pivot Points 標記】")
    pivot_high_count = len([p for p in vppa_data['pivot_points'] if p['type'] == 'H'])
    pivot_low_count = len([p for p in vppa_data['pivot_points'] if p['type'] == 'L'])
    print(f"  [ ] Pivot High 標記數量正確（{pivot_high_count} 個紅色向下三角）")
    print(f"  [ ] Pivot Low 標記數量正確（{pivot_low_count} 個綠色向上三角）")
    print(f"  [ ] 標記位置在對應的高點/低點")

    print(f"\n【圖表品質】")
    print(f"  [ ] PNG 圖片解析度足夠（文字清晰）")
    print(f"  [ ] 圖例清晰可讀")
    print(f"  [ ] 整體配色協調")
    print(f"  [ ] 無視覺元素過度重疊")

    print(f"\n" + "=" * 70)
    print("驗證完成！")
    print("=" * 70)

if __name__ == '__main__':
    main()
```

**執行驗證**：
```bash
python scripts/visual_verification.py
```

#### 6.3 建立完整使用範例

**檔案**：`examples/plot_vppa_complete.py`

```python
#!/usr/bin/env python3
"""
VPPA 視覺化完整範例

此範例展示如何使用 plot_vppa_chart 函數的所有功能：
1. 從 JSON 和 SQLite 載入資料
2. 繪製完整的 VPPA 圖表
3. 自訂圖表參數
4. 輸出 PNG 檔案
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.core.sqlite_cache import SQLiteCacheManager
from src.visualization import plot_vppa_chart

def main():
    print("VPPA 視覺化完整範例")
    print("=" * 60)

    # 1. 載入 VPPA 分析結果
    print("\n步驟 1：載入 VPPA 分析結果")
    vppa_json_path = Path('data/vppa_full_output.json')

    if not vppa_json_path.exists():
        print(f"❌ 找不到 VPPA 資料檔案：{vppa_json_path}")
        print("請先執行：python scripts/analyze_vppa.py GOLD --output data/vppa_full_output.json")
        sys.exit(1)

    with open(vppa_json_path, 'r', encoding='utf-8') as f:
        vppa_data = json.load(f)

    print(f"✅ 載入完成")
    print(f"   商品: {vppa_data['symbol']}")
    print(f"   Pivot Ranges: {vppa_data['summary']['total_ranges']}")

    # 2. 從 SQLite 快取獲取 K 線資料
    print("\n步驟 2：從 SQLite 快取獲取 K 線資料")
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

    # 3. 繪製圖表（包含所有功能）
    print("\n步驟 3：繪製完整的 VPPA 圖表")
    output_path = Path('output/vppa_chart_complete.png')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig = plot_vppa_chart(
        vppa_json=vppa_data,
        candles_df=df,
        output_path=str(output_path),
        show_pivot_points=True,     # 顯示 Pivot Points 標記
        show_developing=True,       # 顯示發展中區間
        width=1920,                 # 圖表寬度
        height=1080                 # 圖表高度
    )

    print(f"✅ 圖表已儲存到：{output_path}")

    # 4. 也可以產生不同配置的圖表
    print("\n步驟 4：產生簡化版圖表（無 Pivot Points 標記）")
    simple_output = Path('output/vppa_chart_simple.png')

    fig_simple = plot_vppa_chart(
        vppa_json=vppa_data,
        candles_df=df,
        output_path=str(simple_output),
        show_pivot_points=False,    # 不顯示 Pivot Points 標記
        show_developing=True,
        width=1600,
        height=900
    )

    print(f"✅ 簡化版圖表已儲存到：{simple_output}")

    # 5. 產生高解析度版本（適合印刷）
    print("\n步驟 5：產生高解析度版本")
    hires_output = Path('output/vppa_chart_hires.png')

    fig_hires = plot_vppa_chart(
        vppa_json=vppa_data,
        candles_df=df,
        output_path=str(hires_output),
        show_pivot_points=True,
        show_developing=True,
        width=2560,                 # 更高解析度
        height=1440
    )

    print(f"✅ 高解析度圖表已儲存到：{hires_output}")

    print("\n" + "=" * 60)
    print("範例執行完成！")
    print("\n已產生以下圖表：")
    print(f"  1. 完整版：{output_path}")
    print(f"  2. 簡化版：{simple_output}")
    print(f"  3. 高解析度版：{hires_output}")
    print("\n你也可以在 Jupyter Notebook 中使用 fig.show() 顯示互動式圖表")

if __name__ == '__main__':
    main()
```

**執行範例**：
```bash
python examples/plot_vppa_complete.py
```

### 成功標準

#### 自動化驗證
- [ ] `pytest tests/test_vppa_plot.py -v` 所有測試通過
- [ ] `python scripts/visual_verification.py` 執行成功並產生圖表
- [ ] `python examples/plot_vppa_complete.py` 執行成功並產生 3 個圖表

#### 手動驗證
- [ ] 所有測試案例通過（包含正常和異常情況）
- [ ] 視覺化驗證腳本的 Checklist 項目全部確認
- [ ] README.md 文檔清楚易懂
- [ ] 範例腳本可正常執行

**實作注意事項**：
1. 單元測試要涵蓋正常和異常情況
2. 視覺化驗證腳本的 Checklist 要全面且具體
3. 文檔要包含實際的執行範例

---

## 階段 7：效能優化與最終驗證（第 9-10 天，可選）

### 目標
優化繪圖效能，確保在處理大量資料時仍能流暢運行。

### 任務清單

#### 7.1 效能基準測試

**建立基準測試腳本**：

**檔案**：`scripts/benchmark_vppa_plot.py`

```python
#!/usr/bin/env python3
"""
VPPA 視覺化效能基準測試

測試不同資料量下的繪圖效能。
"""

import time
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.core.sqlite_cache import SQLiteCacheManager
from src.visualization import plot_vppa_chart

def benchmark(count: int, symbol: str = 'GOLD'):
    """
    執行效能測試

    參數：
        count: K 線數量
        symbol: 商品代碼
    """
    print(f"\n測試 {count} 根 K 線的繪圖效能...")

    # 1. 載入資料（不計時）
    vppa_json_path = Path('data/vppa_full_output.json')
    with open(vppa_json_path, 'r', encoding='utf-8') as f:
        vppa_data = json.load(f)

    cache = SQLiteCacheManager('data/candles.db')
    start_time_str = pd.Timestamp(vppa_data['data_range']['start_time'])
    end_time_str = pd.Timestamp(vppa_data['data_range']['end_time'])

    df = cache.query_candles(symbol, 'M1', start_time_str, end_time_str)

    # 取指定數量的 K 線
    if len(df) > count:
        df = df.tail(count)

    # 2. 繪製圖表（計時）
    start_time = time.time()

    fig = plot_vppa_chart(
        vppa_json=vppa_data,
        candles_df=df,
        output_path=None,  # 不輸出 PNG（加快速度）
        show_pivot_points=True,
        show_developing=True,
        width=1920,
        height=1080
    )

    elapsed = time.time() - start_time

    print(f"  ✅ 完成：{elapsed:.2f} 秒")

    return elapsed

def main():
    print("=" * 60)
    print("VPPA 視覺化效能基準測試")
    print("=" * 60)

    # 測試不同的資料量
    test_counts = [500, 1000, 2000, 3000, 5000]

    results = {}

    for count in test_counts:
        try:
            elapsed = benchmark(count)
            results[count] = elapsed
        except Exception as e:
            print(f"  ❌ 測試失敗：{e}")
            results[count] = None

    # 輸出結果摘要
    print("\n" + "=" * 60)
    print("效能測試結果摘要")
    print("=" * 60)
    print(f"\n{'K 線數量':<10} {'時間 (秒)':<15} {'FPS':<10}")
    print("-" * 40)

    for count, elapsed in results.items():
        if elapsed:
            fps = count / elapsed
            print(f"{count:<10} {elapsed:<15.2f} {fps:<10.1f}")
        else:
            print(f"{count:<10} {'失敗':<15} {'-':<10}")

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)

if __name__ == '__main__':
    main()
```

**執行基準測試**：
```bash
python scripts/benchmark_vppa_plot.py
```

**預期效能目標**：
- 500 根 K 線：< 2 秒
- 1000 根 K 線：< 3 秒
- 2000 根 K 線：< 5 秒
- 5000 根 K 線：< 10 秒

#### 7.2 效能優化（如果需要）

如果效能測試未達標，考慮以下優化策略：

**1. 減少 Trace 數量**（已在階段 4 實作）：
- 合併所有 POC 線為單一 Trace
- 合併所有 VAH/VAL 線

**2. 批量添加 Shapes**（已在階段 2 實作）：
- 使用 `fig.update_layout(shapes=shapes)` 而非 `fig.add_shape()`

**3. 資料精簡**：
```python
# 在 _add_volume_profiles 中，過濾成交量接近 0 的層級
filtered_indices = np.where(volumes > volumes.max() * 0.01)[0]
price_centers_filtered = price_centers[filtered_indices]
volumes_filtered = volumes[filtered_indices]
```

**4. 使用 Scattergl**（適用於超大資料集）：
```python
# 如果 K 線數量 > 5000，使用 WebGL 渲染
if len(df) > 5000:
    fig.add_trace(go.Scattergl(...))  # 而非 go.Scatter
```

#### 7.3 記憶體使用優化

**監控記憶體使用**：

```python
import tracemalloc

tracemalloc.start()

fig = plot_vppa_chart(...)

current, peak = tracemalloc.get_traced_memory()
print(f"目前記憶體使用：{current / 1024 / 1024:.1f} MB")
print(f"峰值記憶體使用：{peak / 1024 / 1024:.1f} MB")

tracemalloc.stop()
```

**優化策略**：
- 避免不必要的資料複製（使用 `.values` 而非 `.copy()`）
- 及時釋放不需要的大型陣列

### 成功標準

#### 自動化驗證
- [ ] 基準測試腳本執行成功
- [ ] 2000 根 K 線的繪圖時間 < 5 秒
- [ ] 5000 根 K 線的繪圖時間 < 10 秒
- [ ] 峰值記憶體使用 < 500 MB

#### 手動驗證
- [ ] 大資料集（5000 根 K 線）的圖表品質仍然良好
- [ ] PNG 輸出速度可接受（< 10 秒）
- [ ] 互動式圖表縮放和 hover 流暢

**實作注意事項**：
1. 此階段為可選，如果基本效能已滿足需求，可跳過
2. 過度優化可能犧牲程式碼可讀性，需權衡
3. 記錄優化前後的效能數據，確保改進有效

---

## 風險評估與緩解策略

### 技術風險

#### 風險 1：成交量正規化參數調整困難

**風險等級**：中

**描述**：Volume Profile 可能過大（遮蓋 K 線）或過小（看不清楚），需要多次調整 `max_width_bars` 參數才能找到最佳值。

**緩解策略**：
1. 提供可調整的 `max_width_bars` 參數（預設 10）
2. 在測試腳本中嘗試不同的值（6, 8, 10, 12）
3. 根據實際效果確定最佳預設值
4. 在文檔中說明如何調整此參數

**應變計畫**：
- 如果無法找到通用的最佳值，提供自動計算邏輯（根據區間 K 線數量動態調整）

#### 風險 2：效能問題（大量 Pivot Ranges）

**風險等級**：中

**描述**：60+ 個區間可能導致繪圖緩慢或瀏覽器卡頓。

**緩解策略**：
1. 使用批量添加 shapes（`fig.update_layout(shapes=shapes)`）
2. 合併 POC/VAH/VAL 線為單一 Trace
3. 進行效能基準測試（階段 7）
4. 提供 `max_ranges` 參數限制顯示的區間數（如果需要）

**應變計畫**：
- 如果效能仍不足，考慮僅繪製最新的 N 個區間
- 提供「簡化模式」，減少視覺元素

#### 風險 3：時間軸映射錯誤

**風險等級**：低

**描述**：索引映射不正確導致方塊或 Volume Profile 位置錯誤。

**緩解策略**：
1. 嚴格驗證 DataFrame 排序順序（必須時間升序）
2. 添加索引範圍檢查（`map_idx_to_time()` 函數）
3. 撰寫單元測試驗證映射邏輯
4. 在視覺化驗證腳本中明確檢查位置正確性

**應變計畫**：
- 提供 debug 模式，輸出映射關係到日誌
- 添加警告訊息，提示可能的時間軸不一致

### 可用性風險

#### 風險 4：圖表過於複雜

**風險等級**：低

**描述**：過多元素導致圖表難以閱讀。

**緩解策略**：
1. 提供開關選項（`show_pivot_points`, `show_developing`）
2. 使用適當的透明度和顏色
3. 支援圖例篩選（Plotly 內建功能）
4. 提供「簡化模式」範例

**應變計畫**：
- 調整預設配色和透明度
- 減少預設啟用的視覺元素

#### 風險 5：PNG 解析度不足

**風險等級**：低

**描述**：輸出的 PNG 圖片模糊或文字太小。

**緩解策略**：
1. 預設使用 `scale=2` 提高解析度
2. 提供可調整的 `width` 和 `height` 參數
3. 建議最小尺寸（1600x900）
4. 在文檔中說明解析度設定

**應變計畫**：
- 提供「高解析度模式」（`scale=3`）
- 調整字體大小和線條寬度

### 維護風險

#### 風險 6：Plotly API 變更

**風險等級**：低

**描述**：未來 Plotly 版本可能不相容。

**緩解策略**：
1. 在 `requirements.txt` 中固定版本範圍（`plotly>=5.18.0,<6.0.0`）
2. 撰寫單元測試確保相容性
3. 定期檢查 Plotly 更新日誌

**應變計畫**：
- 如果發現不相容，固定到已知可用版本
- 提供升級指南

#### 風險 7：資料格式變更

**風險等級**：低

**描述**：`analyze_vppa.py` 的 JSON 格式變更導致繪圖失敗。

**緩解策略**：
1. 添加版本檢查（JSON 中包含 `version` 欄位，未來實作）
2. 撰寫資料驗證函數（`validate_vppa_json()`）
3. 提供清楚的錯誤訊息

**應變計畫**：
- 提供資料格式轉換工具
- 支援多版本資料格式

---

## 測試策略

### 單元測試（Unit Tests）

**覆蓋範圍**：
- `plotly_utils.py` 的所有函數
- `vppa_plot.py` 的主函數和子函數
- 異常處理和錯誤情況

**測試檔案**：`tests/test_vppa_plot.py`

**執行方式**：
```bash
pytest tests/test_vppa_plot.py -v --cov=src.visualization
```

**目標覆蓋率**：> 80%

### 整合測試（Integration Tests）

**測試腳本**：
- `examples/plot_vppa_basic.py`：階段性測試
- `examples/plot_vppa_complete.py`：完整功能測試
- `scripts/visual_verification.py`：視覺化驗證

**執行方式**：
```bash
python examples/plot_vppa_complete.py
python scripts/visual_verification.py
```

### 效能測試（Performance Tests）

**測試腳本**：`scripts/benchmark_vppa_plot.py`

**執行方式**：
```bash
python scripts/benchmark_vppa_plot.py
```

**效能目標**：
- 2000 根 K 線：< 5 秒
- 記憶體使用：< 500 MB

### 視覺化驗證（Visual Verification）

**方法**：人工檢查圖表品質

**檢查清單**：
- [ ] K 線圖正確顯示
- [ ] Pivot Range 方塊位置和顏色正確
- [ ] Volume Profile 位置和顏色正確
- [ ] POC、VAH、VAL 線位置正確
- [ ] Pivot Points 標記位置正確
- [ ] 圖表整體品質良好

**工具**：`scripts/visual_verification.py` 自動產生檢查清單

---

## 交付清單

### 程式碼檔案

- [ ] `src/visualization/__init__.py`
- [ ] `src/visualization/vppa_plot.py`
- [ ] `src/visualization/plotly_utils.py`
- [ ] `src/visualization/chart_config.py`

### 測試檔案

- [ ] `tests/test_vppa_plot.py`
- [ ] `scripts/visual_verification.py`
- [ ] `scripts/benchmark_vppa_plot.py`

### 範例腳本

- [ ] `examples/plot_vppa_basic.py`
- [ ] `examples/plot_vppa_complete.py`

### 文檔

- [ ] `README.md`（更新視覺化功能說明）
- [ ] 此實作計劃文檔

### 配置檔案

- [ ] `requirements.txt`（更新，添加 plotly 和 kaleido）

### 輸出檔案（範例）

- [ ] `output/vppa_chart_stage2.png`（階段 2 測試）
- [ ] `output/vppa_chart_stage3.png`（階段 3 測試）
- [ ] `output/vppa_chart_stage4.png`（階段 4 測試）
- [ ] `output/vppa_chart_complete.png`（完整版）
- [ ] `output/vppa_verification.png`（驗證版）

---

## 實作時程

| 階段 | 任務 | 預估時間 | 累計時間 |
|------|------|----------|----------|
| 階段 1 | 環境準備與基礎架構 | 1 天 | 1 天 |
| 階段 2 | K 線圖與方塊繪製 | 2 天 | 3 天 |
| 階段 3 | Volume Profile 繪製 | 2 天 | 5 天 |
| 階段 4 | 輔助線與標記 | 1 天 | 6 天 |
| 階段 5 | 整合到 analyze_vppa.py | 1 天 | 7 天 |
| 階段 6 | 測試與文檔 | 1 天 | 8 天 |
| 階段 7 | 效能優化（可選） | 2 天 | 10 天 |

**總計**：7-10 天

**關鍵里程碑**：
- 第 3 天：K 線圖和方塊繪製完成（階段 2）
- 第 5 天：Volume Profile 繪製完成（階段 3）
- 第 6 天：輔助線和標記完成（階段 4）
- 第 7 天：整合到分析流程（階段 5）
- 第 8 天：測試和文檔完成（階段 6）

---

## 後續優化建議

完成基本實作後，以下功能可作為未來擴展：

### 短期（1-2 週）

1. **互動式圖表改進**
   - 支援圖表縮放同步
   - 添加自訂註解功能
   - 改進 hover 顯示資訊

2. **配色主題**
   - 提供亮色/暗色主題切換
   - 支援自訂配色方案
   - 預設多種主題選項

3. **多時間週期支援**
   - 支援 M5、M15、M30、H1、H4、D1
   - 自動調整 Volume Profile 寬度

### 中期（1-2 個月）

1. **匯出格式擴展**
   - 支援 SVG（向量圖形，適合編輯）
   - 支援 PDF（適合報告）
   - 支援互動式 HTML

2. **效能優化**
   - 支援超大資料集（10000+ K 線）
   - 實作快取機制（避免重複計算）
   - WebGL 渲染支援

3. **統計資訊面板**
   - 在圖表上顯示關鍵統計資料
   - POC、VAH、VAL 數值標註
   - 成交量統計摘要

### 長期（3-6 個月）

1. **Web 介面**
   - 建立 Web 應用（使用 Dash 或 Streamlit）
   - 支援即時資料更新
   - 互動式參數調整

2. **批量處理**
   - 支援多商品批量繪圖
   - 自動產生報告（含多個圖表）
   - 排程自動更新

3. **進階視覺化**
   - 3D Volume Profile
   - 多時間週期對比圖
   - 成交量熱力圖

---

## 結論

本實作計劃提供了一個完整、結構化的路徑，用於建立 Plotly K 線圖與成交量分佈視覺化功能。計劃分為 7 個階段，從環境準備到效能優化，每個階段都有明確的目標、任務清單和成功標準。

**關鍵成功因素**：
1. **分階段實作**：每個階段完成後進行驗證，確保品質
2. **完整測試**：單元測試、整合測試、視覺化驗證三管齊下
3. **效能優化**：批量處理、合併 Trace、適當的資料結構
4. **良好文檔**：清晰的範例、完整的說明、詳細的 Checklist

**預期成果**：
- 一個可復用的 VPPA 視覺化模組
- 完整的測試覆蓋和文檔
- 整合到現有的分析流程
- 良好的效能和使用者體驗

**下一步行動**：
1. 確認計劃內容和時程安排
2. 開始階段 1 實作（環境準備）
3. 按照計劃逐步推進

---

**計劃制定時間**：2024-12-30
**計劃制定者**：Claude Code (Implementation Planner)
**相關研究文檔**：`thoughts/shared/research/2024-12-30-plotly-kline-volume-profile-research.md`

---

## 附錄 A：程式碼風格指南

遵循專案現有的程式碼風格：

**命名慣例**：
- 函數：`snake_case`（例：`plot_vppa_chart`）
- 類別：`PascalCase`（例：`VPPAPlotter`）
- 常數：`UPPER_CASE`（例：`DEFAULT_LAYOUT`）
- 私有函數：`_leading_underscore`（例：`_add_candlestick`）

**文檔字串**：
- 使用 Google 風格
- 包含參數說明、回傳值、例外
- 提供使用範例（如果適用）

**格式化**：
- 使用 Black（行長度 100）
- 遵循 PEP 8

**日誌記錄**：
- 使用 loguru
- 適當的日誌等級（`debug`, `info`, `warning`, `error`）
- 包含關鍵步驟和錯誤訊息

**錯誤處理**：
- 明確的 `ValueError` 和 `RuntimeError`
- 提供有意義的錯誤訊息
- 適當的例外傳播

## 附錄 B：關鍵技術細節

### Plotly Candlestick 圖表

```python
candlestick = go.Candlestick(
    x=df['time'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name='K線',
    increasing_line_color='#26a69a',  # 上漲（綠色）
    decreasing_line_color='#ef5350'   # 下跌（紅色）
)
```

### 橫向長條圖（Volume Profile）

```python
fig.add_trace(go.Bar(
    x=x_values,           # 長條終點（起點為 base）
    y=price_centers,      # 價格中心
    orientation='h',      # 橫向
    marker=dict(color=colors),
    width=price_step,     # 長條高度（價格方向）
    base=start_time       # 長條起點
))
```

### 矩形方塊（Shapes）

```python
fig.add_shape(
    type='rect',
    x0=start_time,
    x1=end_time,
    y0=lowest_price,
    y1=highest_price,
    fillcolor='rgba(255, 255, 153, 0.3)',
    line=dict(color='rgba(204, 153, 0, 1.0)', width=2),
    layer='below'  # 放在下層
)
```

### PNG 輸出

```python
fig.write_image(
    output_path,
    width=1920,
    height=1080,
    scale=2  # 提高解析度
)
```

## 附錄 C：常見問題排解

### 問題 1：Kaleido 安裝失敗

**症狀**：`pip install kaleido` 失敗或 `fig.write_image()` 報錯

**解決方案**：
```bash
pip uninstall kaleido
pip install kaleido --no-cache-dir
```

### 問題 2：PNG 圖片為空白

**症狀**：產生的 PNG 檔案大小正常，但開啟後為空白

**解決方案**：
1. 確認 Kaleido 版本正確（`>= 0.2.1`）
2. 檢查圖表是否有資料（`len(fig.data) > 0`）
3. 嘗試先 `fig.show()` 查看互動式圖表

### 問題 3：Volume Profile 遮蓋 K 線

**症狀**：Volume Profile 過寬，遮蓋 K 線圖

**解決方案**：
調整 `max_width_bars` 參數（預設 10，改為 6 或 8）

### 問題 4：時間軸顯示錯誤

**症狀**：方塊或 Volume Profile 位置與 Pivot Points 不一致

**解決方案**：
1. 確認 DataFrame 按時間升序排列
2. 檢查 `map_idx_to_time()` 的索引範圍
3. 驗證 JSON 中的 `start_idx` 和 `end_idx` 正確

### 問題 5：記憶體不足

**症狀**：處理大量資料時記憶體溢出

**解決方案**：
1. 減少一次處理的 K 線數量
2. 啟用垃圾回收（`import gc; gc.collect()`）
3. 使用資料串流處理（分批繪製）

---

**實作計劃完成**
