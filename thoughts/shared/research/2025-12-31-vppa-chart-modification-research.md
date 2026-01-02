---
title: "VPPA 圖表修改需求分析研究"
date: 2025-12-31
author: Claude Code (Codebase Researcher)
tags: [vppa, visualization, plotly, chart-modification, research]
status: completed
related_files:
  - scripts/analyze_vppa.py
  - src/visualization/vppa_plot.py
  - src/visualization/chart_config.py
  - src/visualization/plotly_utils.py
  - src/agent/indicators.py
last_updated: 2025-12-31
last_updated_by: Claude Code
---

# VPPA 圖表修改需求分析研究

## 研究問題

分析 VPPA (Volume Profile Pivot Anchored) 視覺化系統的完整程式碼結構，以支援以下修改需求：

1. **移除功能**：
   - 區間內最高最低的紅色與綠色箭頭
   - Volume Profile 的區間的綠色虛線

2. **改顏色和樣式**：
   - 區間範圍的背景顏色改成透明度 50%
   - Volume Profile 中間區間的顏色改成 #D5A634
   - Volume Profile 的 POC 改成紅色實線

3. **加上網格**：
   - Y 軸間隔為整數關卡，根據目前價位的位數（例如 4000 為四位數）的最小值的 1/20
   - X 軸間隔：M1/M5/M15 為小時，M30/H1/H4 為 4 小時，更大時間尺度為日

4. **POC 延伸**：
   - 把每個區間的 POC 都延伸到最右邊
   - 在線條的最右邊上方標註價位
   - 標註與目前最新價格的落差（+ 或 - 多少 %，四捨五入到小數第一位）

5. **最後區間處理**：
   - 把最後一個沒有形成完整 Pivot Range 的部分，也做一個 Volume Profile

6. **標題格式**：
   - 只需顯示 `<Symbol>, <Timeframe> - Volume Profile, Pivot Anchored`

## 摘要

本次研究全面掃描了 VPPA 視覺化系統的程式碼架構，確認了所有需要修改的程式碼位置。系統採用 Plotly 圖表庫，具備清晰的模組化設計，主要程式碼集中在 `src/visualization/` 目錄下。研究發現：

- **Pivot Points 箭頭標記**由 `vppa_plot.py` 的 `_add_pivot_markers()` 函數繪製
- **VAH/VAL 綠色虛線**由 `_add_value_area_lines()` 函數繪製
- **顏色配置**集中在 `chart_config.py` 的 `COLORS` 字典
- **POC 線條**由 `_add_poc_lines()` 函數繪製，目前為虛線且僅延伸到區間終點
- **網格系統**尚未實作，需要透過 Plotly 的 `xaxis` 和 `yaxis` 配置添加
- **developing_range**（即時發展中區間）已經在 `calculate_vppa()` 中計算，但目前不會繪製 Volume Profile

## 詳細研究發現

### 1. 程式碼架構總覽

VPPA 視覺化系統採用三層架構：

```
scripts/analyze_vppa.py          # 入口腳本，負責數據獲取和分析調用
    ↓
src/agent/indicators.py          # 核心計算邏輯（VPPA 演算法）
    ↓
src/visualization/               # Plotly 圖表繪製模組
    ├── vppa_plot.py            # 主繪圖函數
    ├── chart_config.py         # 顏色和樣式配置
    └── plotly_utils.py         # 輔助工具函數
```

### 2. 主要檔案分析

#### 2.1 `scripts/analyze_vppa.py`（入口腳本）

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\scripts\analyze_vppa.py`

**核心功能**：
- 連接 MT5 並獲取 M1 K 線資料
- 調用 `calculate_vppa()` 計算 VPPA 指標
- 調用 `plot_vppa_chart()` 繪製圖表

**關鍵程式碼段（第 534-555 行）**：
```python
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
        show_pivot_points=True,      # ← 控制是否顯示 Pivot Points 箭頭標記
        show_developing=True,
        width=1920,
        height=1080
    )

    print(f"✅ 圖表已儲存到：{plot_output_path}")
```

**修改點**：
- 需求 1(a)：將 `show_pivot_points=True` 改為 `False` 即可移除箭頭標記（但建議在 `vppa_plot.py` 中完全移除相關程式碼）

---

#### 2.2 `src/visualization/vppa_plot.py`（主繪圖模組）

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\src\visualization\vppa_plot.py`

**核心函數列表**：
- `_add_candlestick()` - 繪製 K 線圖（第 24-48 行）
- `_add_range_boxes()` - 建立 Pivot Range 方塊（第 51-94 行）
- `_add_volume_profiles()` - 繪製 Volume Profile 矩形（第 97-180 行）
- `_add_poc_lines()` - 繪製 POC 線（第 183-222 行）
- `_add_value_area_lines()` - 繪製 VAH/VAL 線（第 225-288 行）
- `_add_pivot_markers()` - 繪製 Pivot Points 箭頭標記（第 291-348 行）
- `plot_vppa_chart()` - 主函數，整合所有圖層（第 351-456 行）

---

##### 2.2.1 **需求 1(a)：移除 Pivot Points 箭頭標記**

**程式碼位置**：第 291-348 行

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

    # 分離 Pivot High 和 Pivot Low
    high_points = [p for p in pivot_points if p['type'] == 'H']
    low_points = [p for p in pivot_points if p['type'] == 'L']

    # Pivot High 標記（紅色向下三角）
    if high_points:
        high_times = [map_idx_to_time(p['idx'], df) for p in high_points]
        high_prices = [p['price'] for p in high_points]

        fig.add_trace(go.Scatter(
            x=high_times,
            y=high_prices,
            mode='markers',
            marker=dict(
                symbol='triangle-down',    # 紅色向下三角
                size=10,
                color=COLORS['pivot_high']  # 'red'
            ),
            name='Pivot High',
            showlegend=True,
            hovertemplate='Pivot High: %{y:.2f}<extra></extra>'
        ))

    # Pivot Low 標記（綠色向上三角）
    if low_points:
        low_times = [map_idx_to_time(p['idx'], df) for p in low_points]
        low_prices = [p['price'] for p in low_points]

        fig.add_trace(go.Scatter(
            x=low_times,
            y=low_prices,
            mode='markers',
            marker=dict(
                symbol='triangle-up',       # 綠色向上三角
                size=10,
                color=COLORS['pivot_low']   # 'green'
            ),
            name='Pivot Low',
            showlegend=True,
            hovertemplate='Pivot Low: %{y:.2f}<extra></extra>'
        ))

    logger.debug(f"Pivot Points 標記完成：{len(high_points)} High, {len(low_points)} Low")
```

**修改方案**：
- 在主函數 `plot_vppa_chart()` 中移除對此函數的調用（第 418-419 行）
- 或直接刪除整個 `_add_pivot_markers()` 函數

---

##### 2.2.2 **需求 1(b)：移除 VAH/VAL 綠色虛線**

**程式碼位置**：第 225-288 行

```python
def _add_value_area_lines(fig: go.Figure, ranges: list) -> None:
    """
    添加 VAH（Value Area High）和 VAL（Value Area Low）線

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
    """
    logger.debug(f"添加 {len(ranges)} 組 Value Area 線")

    # VAH 線（合併）
    vah_x = []
    vah_y = []

    # VAL 線（合併）
    val_x = []
    val_y = []

    for range_data in ranges:
        # 直接使用 JSON 中的時間欄位
        x0 = pd.Timestamp(range_data['start_time'])
        x1 = pd.Timestamp(range_data['end_time'])
        vah = range_data['value_area']['vah']
        val = range_data['value_area']['val']

        # VAH 線段
        vah_x.extend([x0, x1, None])
        vah_y.extend([vah, vah, None])

        # VAL 線段
        val_x.extend([x0, x1, None])
        val_y.extend([val, val, None])

    # 繪製 VAH 線（綠色點線）
    fig.add_trace(go.Scatter(
        x=vah_x,
        y=vah_y,
        mode='lines',
        line=dict(
            color=COLORS['va_line'],    # 'rgb(0, 128, 0)' 綠色
            width=1.5,
            dash=LINE_STYLES['va']      # 'dot' 點線
        ),
        name='VAH',
        showlegend=True,
        hovertemplate='VAH: %{y:.2f}<extra></extra>'
    ))

    # 繪製 VAL 線（綠色點線）
    fig.add_trace(go.Scatter(
        x=val_x,
        y=val_y,
        mode='lines',
        line=dict(
            color=COLORS['va_line'],    # 'rgb(0, 128, 0)' 綠色
            width=1.5,
            dash=LINE_STYLES['va']      # 'dot' 點線
        ),
        name='VAL',
        showlegend=True,
        hovertemplate='VAL: %{y:.2f}<extra></extra>'
    ))

    logger.debug(f"Value Area 線繪製完成：{len(ranges)} 組")
```

**修改方案**：
- 在主函數 `plot_vppa_chart()` 中移除對此函數的調用（第 415 行）
- 或直接刪除整個 `_add_value_area_lines()` 函數

---

##### 2.2.3 **需求 2(a)：區間範圍背景顏色透明度改為 50%**

**程式碼位置**：第 51-94 行的 `_add_range_boxes()` 函數

目前的填充顏色在 `chart_config.py` 中定義：
```python
'range_fill': 'rgba(255, 255, 153, 0.3)',    # 淺黃色填充，透明度 30%
```

**修改位置**：第 85 行
```python
fillcolor=COLORS['range_fill'],  # 需要在 chart_config.py 中修改透明度為 0.5
```

---

##### 2.2.4 **需求 2(b)：Volume Profile 中間區間顏色改為 #D5A634**

**程式碼位置**：第 97-180 行的 `_add_volume_profiles()` 函數

目前的 Value Area 內外顏色在 `chart_config.py` 中定義：
```python
# Volume Profile（提高不透明度使其更明顯）
'volume_in_va': 'rgba(65, 105, 225, 0.85)',   # Value Area 內（皇家藍）
'volume_out_va': 'rgba(128, 128, 128, 0.65)', # Value Area 外（灰色）
```

**繪製邏輯**（第 162-165 行）：
```python
# 選擇顏色（Value Area 內外不同）
if val <= price <= vah:
    fill_color = COLORS['volume_in_va']  # Value Area 內：藍色
else:
    fill_color = COLORS['volume_out_va']  # Value Area 外：灰色
```

**疑問**：需求中的「中間區間」指的是 Value Area 內的顏色，還是整個 Volume Profile？
- 如果是 Value Area 內：修改 `volume_in_va` 為 `'rgba(213, 166, 52, 0.85)'` (#D5A634 + alpha)
- 如果是所有 Volume Profile：統一顏色，移除 Value Area 內外顏色分層

---

##### 2.2.5 **需求 2(c)：POC 改為紅色實線**

**程式碼位置**：第 183-222 行的 `_add_poc_lines()` 函數

目前的 POC 線樣式（第 212-216 行）：
```python
line=dict(
    color=COLORS['poc_line'],    # 'rgb(255, 0, 0)' 紅色（已經是紅色）
    width=2,
    dash=LINE_STYLES['poc']      # 'dash' 虛線 ← 需要改為實線
),
```

**修改方案**：
- 移除 `dash=LINE_STYLES['poc']` 或改為 `dash='solid'`（實線）

---

##### 2.2.6 **需求 4：POC 延伸到最右邊並標註價位和漲跌幅**

**目前實作**（第 198-205 行）：
```python
for range_data in ranges:
    # 直接使用 JSON 中的時間欄位
    x0 = pd.Timestamp(range_data['start_time'])
    x1 = pd.Timestamp(range_data['end_time'])    # ← 目前僅延伸到區間終點
    poc_price = range_data['poc']['price']

    # 添加線段（使用 None 分隔不同線段）
    all_x.extend([x0, x1, None])
    all_y.extend([poc_price, poc_price, None])
```

**修改方案**：
1. 將 `x1` 改為圖表的最右邊時間（最新 K 線的時間）
2. 在每條 POC 線的最右邊添加價格標註（使用 `go.Scatter` 的 `text` 參數或 `annotations`）
3. 計算與最新價格的漲跌幅並標註

**需要的數據**：
- 最新 K 線的時間和收盤價（來自 `candles_df`）
- 每個區間的 POC 價格（已有）

---

##### 2.2.7 **需求 3：添加網格系統**

**目前的軸配置**（第 432-440 行）：
```python
xaxis={
    'title': '時間',
    'type': 'date',
    'rangeslider': {'visible': False}
},
yaxis={
    'title': '價格',
    'fixedrange': False
},
```

**修改方案**：
1. **Y 軸網格**：根據價格位數動態計算間隔
   ```python
   # 計算價格位數
   latest_price = candles_df['close'].iloc[-1]
   price_digits = len(str(int(latest_price)))  # 例如 4000 → 4 位數
   min_unit = 10 ** (price_digits - 1)         # 4 位數 → 1000
   y_interval = min_unit / 20                  # 1000 / 20 = 50

   yaxis={
       'title': '價格',
       'fixedrange': False,
       'showgrid': True,
       'dtick': y_interval,  # 設定 Y 軸間隔
       'gridcolor': 'lightgray'
   }
   ```

2. **X 軸網格**：根據時間週期設定間隔
   ```python
   # 根據時間週期決定 X 軸間隔
   timeframe_grid_intervals = {
       'M1': 3600000,      # 1 小時 (毫秒)
       'M5': 3600000,      # 1 小時
       'M15': 3600000,     # 1 小時
       'M30': 14400000,    # 4 小時
       'H1': 14400000,     # 4 小時
       'H4': 14400000,     # 4 小時
       'D1': 86400000      # 1 日
   }

   x_interval = timeframe_grid_intervals.get(timeframe, 3600000)

   xaxis={
       'title': '時間',
       'type': 'date',
       'rangeslider': {'visible': False},
       'showgrid': True,
       'dtick': x_interval,
       'gridcolor': 'lightgray'
   }
   ```

---

##### 2.2.8 **需求 6：修改標題格式**

**目前的標題設定**（第 426-431 行）：
```python
title={
    'text': f'{symbol} {timeframe} - Volume Profile Pivot Anchored',
    'x': 0.5,
    'xanchor': 'center',
    'font': {'size': 18}
},
```

**修改方案**：
- 將 `'text'` 改為逗號分隔格式：
  ```python
  'text': f'{symbol}, {timeframe} - Volume Profile, Pivot Anchored',
  ```

---

##### 2.2.9 **需求 5：繪製 developing_range 的 Volume Profile**

**目前狀況**：
- `developing_range` 已在 `calculate_vppa()` 中計算（`src/agent/indicators.py` 第 993-1084 行）
- 但在繪圖時並未使用，`plot_vppa_chart()` 僅處理 `pivot_ranges`

**主函數中的處理邏輯**（第 392-405 行）：
```python
# 1. 先收集所有 shapes（方塊 + Volume Profile）
all_shapes = []

# 建立 Pivot Range 方塊
range_shapes = _add_range_boxes(
    vppa_json['pivot_ranges'], show_developing  # ← 這裡的 show_developing 目前未使用
)
all_shapes.extend(range_shapes)

# 建立 Volume Profile shapes（最大寬度 = Range 寬度的 2/3）
vp_shapes = _add_volume_profiles(
    vppa_json['pivot_ranges'], timeframe=timeframe  # ← 僅處理 pivot_ranges
)
all_shapes.extend(vp_shapes)
```

**修改方案**：
1. 檢查 `vppa_json['developing_range']` 是否存在
2. 如果存在，將其也傳入 `_add_range_boxes()` 和 `_add_volume_profiles()`
3. 需要修改這兩個函數以支援單一區間物件（目前僅接受列表）

**developing_range 資料結構**（來自 `indicators.py` 第 1028-1072 行）：
```python
developing_range = {
    'is_developing': True,
    'range_id': len(ranges),
    'start_idx': last_pivot_idx,
    'end_idx': current_idx,
    'start_time': df.index[last_pivot_idx],
    'end_time': df.index[current_idx],
    'bar_count': current_idx - last_pivot_idx + 1,
    'pivot_type': last_pivot['type'],
    'pivot_price': last_pivot['price'],
    'price_highest': vp_dev['price_highest'],
    'price_lowest': vp_dev['price_lowest'],
    'price_range': vp_dev['price_highest'] - vp_dev['price_lowest'],
    'price_step': vp_dev['price_step'],
    'volume_profile': vp_dev['volume_profile'].tolist(),
    'price_centers': vp_dev['price_centers'].tolist(),
    'poc': { ... },
    'vah': ...,
    'val': ...,
    # ... 其他欄位與 pivot_ranges 相同
}
```

---

#### 2.3 `src/visualization/chart_config.py`（顏色和樣式配置）

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\src\visualization\chart_config.py`

**完整內容**（第 1-48 行）：
```python
"""
圖表配置常數
"""

# 顏色配置
COLORS = {
    # K 線顏色
    'candle_up': '#26a69a',      # 上漲（綠色）
    'candle_down': '#ef5350',    # 下跌（紅色）

    # Pivot Range 方塊
    'range_fill': 'rgba(255, 255, 153, 0.3)',    # 淺黃色填充，透明度 30%
    'range_border': 'rgba(204, 153, 0, 1.0)',    # 深黃色邊框

    # Volume Profile（提高不透明度使其更明顯）
    'volume_in_va': 'rgba(65, 105, 225, 0.85)',   # Value Area 內（皇家藍）
    'volume_out_va': 'rgba(128, 128, 128, 0.65)', # Value Area 外（灰色）

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

**需要修改的項目**：

1. **需求 2(a)**：`range_fill` 透明度從 0.3 改為 0.5
   ```python
   'range_fill': 'rgba(255, 255, 153, 0.5)',  # 透明度改為 50%
   ```

2. **需求 2(b)**：`volume_in_va` 顏色改為 #D5A634（金黃色）
   ```python
   'volume_in_va': 'rgba(213, 166, 52, 0.85)',  # #D5A634 轉為 RGBA
   ```

3. **需求 2(c)**：`LINE_STYLES['poc']` 從 'dash' 改為 'solid'
   ```python
   LINE_STYLES = {
       'poc': 'solid',    # 實線
       'va': 'dot'        # 點線（但此項將被移除）
   }
   ```

---

#### 2.4 `src/visualization/plotly_utils.py`（輔助工具函數）

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\src\visualization\plotly_utils.py`

**核心函數**：
- `map_idx_to_time()` - 將整數索引映射到時間戳（第 12-29 行）
- `validate_vppa_json()` - 驗證 VPPA JSON 資料格式（第 32-47 行）
- `validate_candles_df()` - 驗證 K 線 DataFrame 格式（第 50-68 行）
- `normalize_volume_width()` - 正規化 Volume Profile 的成交量寬度（第 71-113 行）
- `get_volume_colors()` - 根據 Value Area 分配顏色（第 116-139 行）

**與修改需求相關的函數**：

1. **`map_idx_to_time()`**：在 POC 延伸時會用到，將索引轉為時間戳
2. **`get_volume_colors()`**：決定 Volume Profile 的顏色分層，可能需要修改或移除

---

#### 2.5 `src/agent/indicators.py`（VPPA 核心計算邏輯）

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\src\agent\indicators.py`

**核心函數**：
- `find_pivot_points()` - 偵測 Pivot High 和 Pivot Low（第 265-346 行）
- `extract_pivot_ranges()` - 提取 Pivot Point 區間配對（第 349-430 行）
- `calculate_volume_profile_for_range()` - 計算指定區間的 Volume Profile（第 433-561 行）
- `calculate_value_area()` - 計算 Value Area（POC、VAH、VAL）（第 564-733 行）
- `calculate_vppa()` - VPPA 主函數，整合所有計算（第 736-1109 行）

**developing_range 計算邏輯**（第 993-1084 行）：
```python
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
                'range_id': len(ranges),
                'start_idx': last_pivot_idx,
                'end_idx': current_idx,
                'start_time': df.index[last_pivot_idx],
                'end_time': df.index[current_idx],
                'bar_count': current_idx - last_pivot_idx + 1,
                # ... 其他欄位與 pivot_ranges 相同
            }
        except Exception as e:
            logger.warning(f"計算發展中區間時發生錯誤：{e}")
            developing_range = None
```

**關鍵發現**：
- `developing_range` 已經在 VPPA 計算中包含完整的 Volume Profile 資料
- 資料結構與 `pivot_ranges` 完全相同，只是多了 `'is_developing': True` 標記
- 繪圖模組只需要將此資料也傳入 `_add_range_boxes()` 和 `_add_volume_profiles()` 即可

---

### 3. 前一輪修改的參考資訊

根據 `thoughts/shared/coding/2024-12-30-plotly-vppa-visualization-summary.md` 的記錄，前一輪實作完成了以下功能：

**已完成的功能**：
- ✅ K 線圖繪製（綠色上漲、紅色下跌）
- ✅ Pivot Range 方塊（淺黃色填充 + 深黃色邊框）
- ✅ 橫向 Volume Profile（靠左繪製，最大寬度 = Range 寬度的 2/3）
- ✅ Volume Profile 顏色分層（Value Area 內藍色、外灰色）
- ✅ POC 線（紅色虛線）
- ✅ VAH/VAL 線（綠色點線）
- ✅ Pivot Points 標記（High 紅色向下三角、Low 綠色向上三角）

**技術亮點**：
- 使用 `None` 分隔技巧合併多條線段為單一 Trace（效能優化）
- 透過 `timedelta` 精確控制 Volume Profile 的橫向寬度
- 自動根據 VAH/VAL 分配顏色，視覺化 Value Area
- 批量添加 shapes，避免多次更新布局

**效能表現**：
- 2000 根 K 線 + 60 個 Pivot Ranges：繪製時間約 2-3 秒
- PNG 輸出（1920x1080, scale=2）：約 1-2 秒
- 記憶體使用：穩定在 200-300 MB

---

### 4. 程式碼修改位置總結表

| 需求編號 | 功能描述 | 檔案位置 | 函數/行數 | 修改方式 |
|---------|---------|---------|----------|---------|
| 1(a) | 移除 Pivot Points 箭頭標記 | `vppa_plot.py` | `_add_pivot_markers()` 第 291-348 行 | 移除函數調用（第 418-419 行）或刪除函數 |
| 1(b) | 移除 VAH/VAL 綠色虛線 | `vppa_plot.py` | `_add_value_area_lines()` 第 225-288 行 | 移除函數調用（第 415 行）或刪除函數 |
| 2(a) | 區間背景透明度改為 50% | `chart_config.py` | `COLORS['range_fill']` 第 12 行 | 將 `0.3` 改為 `0.5` |
| 2(b) | Volume Profile 顏色改為 #D5A634 | `chart_config.py` | `COLORS['volume_in_va']` 第 16 行 | 改為 `'rgba(213, 166, 52, 0.85)'` |
| 2(c) | POC 改為紅色實線 | `chart_config.py` | `LINE_STYLES['poc']` 第 30 行 | 將 `'dash'` 改為 `'solid'` |
| 3(Y軸) | 添加 Y 軸網格（動態間隔） | `vppa_plot.py` | `plot_vppa_chart()` 第 437-440 行 | 在 `yaxis` 配置中添加 `showgrid`、`dtick`、`gridcolor` |
| 3(X軸) | 添加 X 軸網格（時間週期間隔） | `vppa_plot.py` | `plot_vppa_chart()` 第 432-436 行 | 在 `xaxis` 配置中添加 `showgrid`、`dtick`、`gridcolor` |
| 4 | POC 延伸到最右邊並標註 | `vppa_plot.py` | `_add_poc_lines()` 第 183-222 行 | 修改 `x1` 為最新時間，添加價格和漲跌幅標註 |
| 5 | 繪製 developing_range | `vppa_plot.py` | `plot_vppa_chart()` 第 392-405 行 | 檢查並處理 `vppa_json['developing_range']` |
| 6 | 修改標題格式 | `vppa_plot.py` | `plot_vppa_chart()` 第 427 行 | 改為逗號分隔格式 |

---

### 5. 資料結構分析

#### 5.1 `vppa_json` 結構（VPPA 分析結果）

```python
{
    'symbol': 'GOLD',
    'timeframe': 'M1',
    'analysis_time': '2025-12-31T...',
    'parameters': {
        'count': 2160,
        'pivot_length': 73,
        'price_levels': 49,
        'value_area_pct': 0.68,
        'volume_ma_length': 14
    },
    'data_range': {
        'start_time': '...',
        'end_time': '...',
        'total_bars': 2160
    },
    'summary': {
        'total_pivot_points': 30,
        'total_ranges': 29,
        'avg_range_bars': 74,
        'has_developing_range': True,
        'volume_stats': { ... }
    },
    'pivot_points': [
        {
            'idx': 73,
            'type': 'H',  # 'H' 或 'L'
            'price': 2650.50,
            'time': '2025-12-30T10:15:00Z'
        },
        ...
    ],
    'pivot_ranges': [
        {
            'range_id': 0,
            'start_idx': 73,
            'end_idx': 150,
            'start_time': '2025-12-30T10:15:00Z',
            'end_time': '2025-12-30T11:32:00Z',
            'bar_count': 77,
            'pivot_type': 'L',
            'pivot_price': 2645.20,
            'price_info': {
                'highest': 2650.50,
                'lowest': 2645.20,
                'range': 5.30,
                'step': 0.108  # price_range / price_levels
            },
            'poc': {
                'level': 25,
                'price': 2647.85,
                'volume': 12500.0,
                'volume_pct': 15.2
            },
            'value_area': {
                'vah': 2649.00,
                'val': 2646.70,
                'width': 2.30,
                'volume': 55000.0,
                'pct': 68.0
            },
            'volume_info': {
                'total': 80000.0,
                'avg_per_bar': 1038.96
            },
            'volume_profile': {
                'levels': 49,
                'price_centers': [2645.25, 2645.36, ..., 2650.45],
                'volumes': [1200.0, 1500.0, ..., 800.0]
            }
        },
        ...
    ],
    'developing_range': {
        'is_developing': True,
        'range_id': 29,
        'start_idx': 2100,
        'end_idx': 2159,
        'start_time': '2025-12-31T09:00:00Z',
        'end_time': '2025-12-31T09:59:00Z',
        'bar_count': 60,
        # ... 其他欄位與 pivot_ranges 相同
    }
}
```

#### 5.2 `candles_df` 結構（K 線資料）

```python
# DataFrame 欄位
columns = [
    'time',        # pd.Timestamp，K 線時間
    'open',        # float，開盤價
    'high',        # float，最高價
    'low',         # float，最低價
    'close',       # float，收盤價
    'real_volume', # float，真實成交量
    'tick_volume', # int，tick 成交量
    'spread',      # int，點差
    'volume_ma'    # float，成交量移動平均（在 analyze_vppa.py 中計算）
]

# 範例資料
#   time                    open     high     low      close    real_volume
# 0 2025-12-30 08:00:00+00  2645.20  2645.80  2645.10  2645.50  1500.0
# 1 2025-12-30 08:01:00+00  2645.50  2646.00  2645.40  2645.90  1800.0
# ...
```

---

### 6. 技術決策建議

#### 6.1 需求 2(b) 的澄清

**問題**：「Volume Profile 中間區間的顏色改成 #D5A634」指的是什麼？

**可能的解釋**：
1. **解釋 A**：Value Area 內的顏色（目前是藍色）
   - 修改 `COLORS['volume_in_va']` 為金黃色
   - Value Area 外維持灰色

2. **解釋 B**：所有 Volume Profile 統一顏色
   - 移除 Value Area 內外顏色分層
   - 所有 Volume Profile 矩形都使用金黃色

**建議**：根據 VPPA 指標的慣例，「中間區間」通常指 Value Area（POC 上下 68% 成交量範圍），因此建議採用**解釋 A**。

#### 6.2 POC 延伸的實作方式

**需求**：
- POC 延伸到最右邊
- 標註價位
- 標註與最新價格的漲跌幅

**實作方案**：

**方案 A：使用 Plotly Annotations**
```python
# 在每條 POC 線的最右邊添加標註
for range_data in ranges:
    poc_price = range_data['poc']['price']
    latest_price = candles_df['close'].iloc[-1]
    price_diff_pct = ((latest_price - poc_price) / poc_price) * 100

    fig.add_annotation(
        x=candles_df['time'].iloc[-1],
        y=poc_price,
        text=f"{poc_price:.2f} ({price_diff_pct:+.1f}%)",
        showarrow=False,
        xanchor='left',
        yanchor='bottom',
        font=dict(size=10, color='red')
    )
```

**方案 B：使用 Scatter Text Mode**
```python
# 建立單獨的 Scatter Trace 用於標註
annotation_x = []
annotation_y = []
annotation_text = []

latest_price = candles_df['close'].iloc[-1]
latest_time = candles_df['time'].iloc[-1]

for range_data in ranges:
    poc_price = range_data['poc']['price']
    price_diff_pct = ((latest_price - poc_price) / poc_price) * 100

    annotation_x.append(latest_time)
    annotation_y.append(poc_price)
    annotation_text.append(f"{poc_price:.2f} ({price_diff_pct:+.1f}%)")

fig.add_trace(go.Scatter(
    x=annotation_x,
    y=annotation_y,
    mode='text',
    text=annotation_text,
    textposition='top right',
    showlegend=False
))
```

**建議**：採用**方案 B**，因為 Annotations 數量過多時會影響效能和可讀性，使用 Scatter Text Mode 可以更靈活地控制標註位置和樣式。

#### 6.3 網格間隔的計算邏輯

**Y 軸網格間隔計算**：
```python
def calculate_y_grid_interval(latest_price: float) -> float:
    """
    根據價格位數計算 Y 軸網格間隔

    規則：最小值的 1/20
    - 例如 4000 (4位數) → 最小值 1000 → 間隔 50
    - 例如 25000 (5位數) → 最小值 10000 → 間隔 500
    """
    price_int = int(latest_price)
    price_digits = len(str(price_int))
    min_unit = 10 ** (price_digits - 1)
    interval = min_unit / 20
    return interval

# 範例：
# latest_price = 2650.50 → price_digits = 4 → min_unit = 1000 → interval = 50
# latest_price = 25000.00 → price_digits = 5 → min_unit = 10000 → interval = 500
```

**X 軸網格間隔對照表**：
```python
TIMEFRAME_GRID_INTERVALS = {
    'M1': 3600000,       # 1 小時 (毫秒)
    'M5': 3600000,       # 1 小時
    'M15': 3600000,      # 1 小時
    'M30': 14400000,     # 4 小時
    'H1': 14400000,      # 4 小時
    'H4': 14400000,      # 4 小時
    'D1': 86400000,      # 1 日
    'W1': 604800000,     # 1 週（7 日）
    'MN1': 2592000000    # 1 月（30 日）
}
```

---

### 7. 修改實作順序建議

**階段 1：簡單修改（顏色和樣式）**
1. 修改 `chart_config.py`：
   - 區間背景透明度改為 50%
   - Volume Profile 顏色改為 #D5A634
   - POC 線條改為實線
2. 修改 `vppa_plot.py`：
   - 移除 `_add_pivot_markers()` 函數調用
   - 移除 `_add_value_area_lines()` 函數調用
   - 修改標題格式

**階段 2：網格系統**
1. 在 `vppa_plot.py` 中實作 Y 軸間隔計算函數
2. 在 `plot_vppa_chart()` 中添加網格配置

**階段 3：POC 延伸和標註**
1. 修改 `_add_poc_lines()` 函數：
   - 將所有 POC 線延伸到最右邊
   - 添加價格和漲跌幅標註

**階段 4：developing_range 繪製**
1. 修改 `_add_range_boxes()` 和 `_add_volume_profiles()` 以支援單一區間物件
2. 在 `plot_vppa_chart()` 中添加 developing_range 處理邏輯

---

### 8. 程式碼範例（關鍵修改）

#### 8.1 修改後的 `chart_config.py`

```python
# 顏色配置
COLORS = {
    # K 線顏色
    'candle_up': '#26a69a',
    'candle_down': '#ef5350',

    # Pivot Range 方塊
    'range_fill': 'rgba(255, 255, 153, 0.5)',    # ← 透明度改為 50%
    'range_border': 'rgba(204, 153, 0, 1.0)',

    # Volume Profile
    'volume_in_va': 'rgba(213, 166, 52, 0.85)',  # ← #D5A634 金黃色
    'volume_out_va': 'rgba(128, 128, 128, 0.65)',

    # 輔助線
    'poc_line': 'rgb(255, 0, 0)',        # POC（紅色）
    # va_line 可以移除，因為不再使用

    # Pivot Points 標記（可以移除）
    # 'pivot_high': 'red',
    # 'pivot_low': 'green'
}

# 線條樣式
LINE_STYLES = {
    'poc': 'solid',    # ← 實線
    # 'va': 'dot'      # 移除，因為不再繪製 VAH/VAL
}
```

#### 8.2 修改後的 `plot_vppa_chart()` 主函數

```python
def plot_vppa_chart(
    vppa_json: dict,
    candles_df: pd.DataFrame,
    output_path: Optional[str] = None,
    show_pivot_points: bool = False,  # ← 預設改為 False
    show_developing: bool = True,
    width: int = 1600,
    height: int = 900
) -> go.Figure:
    # ... 驗證輸入 ...

    # 取得時間週期和最新價格（用於網格計算）
    timeframe = vppa_json.get('timeframe', 'M1')
    latest_price = candles_df['close'].iloc[-1]
    latest_time = candles_df['time'].iloc[-1]

    # 建立 Figure
    fig = go.Figure()

    # 1. 收集所有 shapes（方塊 + Volume Profile）
    all_shapes = []
    all_ranges = vppa_json['pivot_ranges'].copy()

    # 如果存在 developing_range，也加入繪製
    if show_developing and vppa_json.get('developing_range'):
        all_ranges.append(vppa_json['developing_range'])

    range_shapes = _add_range_boxes(all_ranges, show_developing)
    all_shapes.extend(range_shapes)

    vp_shapes = _add_volume_profiles(all_ranges, timeframe=timeframe)
    all_shapes.extend(vp_shapes)

    fig.update_layout(shapes=all_shapes)

    # 2. 添加 K 線圖
    _add_candlestick(fig, candles_df)

    # 3. 添加 POC 線（延伸到最右邊，附帶標註）
    _add_poc_lines_extended(fig, vppa_json['pivot_ranges'], latest_time, latest_price)

    # 4. 不再添加 VAH/VAL 線（已移除）
    # _add_value_area_lines(fig, vppa_json['pivot_ranges'])

    # 5. 不再添加 Pivot Points 標記（已移除）
    # if show_pivot_points:
    #     _add_pivot_markers(fig, vppa_json['pivot_points'], candles_df)

    # 計算網格間隔
    y_grid_interval = calculate_y_grid_interval(latest_price)
    x_grid_interval = get_x_grid_interval(timeframe)

    # 設定布局
    symbol = vppa_json['symbol']

    fig.update_layout(
        title={
            'text': f'{symbol}, {timeframe} - Volume Profile, Pivot Anchored',  # ← 修改標題格式
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis={
            'title': '時間',
            'type': 'date',
            'rangeslider': {'visible': False},
            'showgrid': True,            # ← 顯示網格
            'dtick': x_grid_interval,    # ← X 軸間隔
            'gridcolor': 'lightgray',
            'gridwidth': 0.5
        },
        yaxis={
            'title': '價格',
            'fixedrange': False,
            'showgrid': True,            # ← 顯示網格
            'dtick': y_grid_interval,    # ← Y 軸間隔
            'gridcolor': 'lightgray',
            'gridwidth': 0.5
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

    return fig
```

#### 8.3 新增的輔助函數

```python
def calculate_y_grid_interval(latest_price: float) -> float:
    """
    根據價格位數計算 Y 軸網格間隔

    規則：最小值的 1/20
    例如 4000 (4位數) → 最小值 1000 → 間隔 50
    """
    price_int = int(latest_price)
    price_digits = len(str(price_int))
    min_unit = 10 ** (price_digits - 1)
    interval = min_unit / 20
    return interval


def get_x_grid_interval(timeframe: str) -> int:
    """
    根據時間週期取得 X 軸網格間隔（毫秒）

    規則：
    - M1/M5/M15: 1 小時
    - M30/H1/H4: 4 小時
    - D1 以上: 1 日
    """
    intervals = {
        'M1': 3600000,       # 1 小時
        'M5': 3600000,
        'M15': 3600000,
        'M30': 14400000,     # 4 小時
        'H1': 14400000,
        'H4': 14400000,
        'D1': 86400000,      # 1 日
        'W1': 604800000,     # 1 週
        'MN1': 2592000000    # 1 月
    }
    return intervals.get(timeframe, 3600000)


def _add_poc_lines_extended(
    fig: go.Figure,
    ranges: list,
    latest_time: pd.Timestamp,
    latest_price: float
) -> None:
    """
    添加延伸到最右邊的 POC 線，並附帶價格和漲跌幅標註

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
        latest_time: 最新 K 線的時間
        latest_price: 最新收盤價
    """
    logger.debug(f"添加 {len(ranges)} 條延伸 POC 線")

    # 合併所有 POC 線
    all_x = []
    all_y = []

    # 標註資料
    annotation_x = []
    annotation_y = []
    annotation_text = []

    for range_data in ranges:
        x0 = pd.Timestamp(range_data['start_time'])
        x1 = latest_time  # ← 延伸到最右邊
        poc_price = range_data['poc']['price']

        # 添加線段
        all_x.extend([x0, x1, None])
        all_y.extend([poc_price, poc_price, None])

        # 計算漲跌幅
        price_diff_pct = ((latest_price - poc_price) / poc_price) * 100

        # 添加標註
        annotation_x.append(x1)
        annotation_y.append(poc_price)
        annotation_text.append(f"{poc_price:.2f} ({price_diff_pct:+.1f}%)")

    # 繪製所有 POC 線
    fig.add_trace(go.Scatter(
        x=all_x,
        y=all_y,
        mode='lines',
        line=dict(
            color=COLORS['poc_line'],
            width=2,
            dash=LINE_STYLES['poc']  # 'solid' 實線
        ),
        name='POC',
        showlegend=True,
        hovertemplate='POC: %{y:.2f}<extra></extra>'
    ))

    # 添加價格和漲跌幅標註
    fig.add_trace(go.Scatter(
        x=annotation_x,
        y=annotation_y,
        mode='text',
        text=annotation_text,
        textposition='top right',
        textfont=dict(size=9, color='red'),
        showlegend=False,
        hoverinfo='skip'
    ))

    logger.debug(f"POC 線繪製完成：{len(ranges)} 條")
```

---

## 程式碼引用

### 關鍵檔案位置

1. **入口腳本**：`C:\Users\fatfi\works\chip-whisperer\scripts\analyze_vppa.py`
   - 第 534-555 行：繪圖功能調用

2. **主繪圖模組**：`C:\Users\fatfi\works\chip-whisperer\src\visualization\vppa_plot.py`
   - 第 24-48 行：`_add_candlestick()` - K 線圖
   - 第 51-94 行：`_add_range_boxes()` - Pivot Range 方塊
   - 第 97-180 行：`_add_volume_profiles()` - Volume Profile
   - 第 183-222 行：`_add_poc_lines()` - POC 線
   - 第 225-288 行：`_add_value_area_lines()` - VAH/VAL 線（待移除）
   - 第 291-348 行：`_add_pivot_markers()` - Pivot Points 標記（待移除）
   - 第 351-456 行：`plot_vppa_chart()` - 主函數

3. **配置檔案**：`C:\Users\fatfi\works\chip-whisperer\src\visualization\chart_config.py`
   - 第 6-26 行：`COLORS` 字典
   - 第 29-32 行：`LINE_STYLES` 字典

4. **輔助工具**：`C:\Users\fatfi\works\chip-whisperer\src\visualization\plotly_utils.py`
   - 第 12-29 行：`map_idx_to_time()`
   - 第 116-139 行：`get_volume_colors()`

5. **VPPA 計算**：`C:\Users\fatfi\works\chip-whisperer\src\agent\indicators.py`
   - 第 736-1109 行：`calculate_vppa()` - VPPA 主函數
   - 第 993-1084 行：developing_range 計算邏輯

---

## 架構圖

### VPPA 視覺化系統資料流程

```
┌─────────────────────────────────────────────────────────────────┐
│ scripts/analyze_vppa.py (入口腳本)                              │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 1. MT5 連線並獲取 M1 K 線資料                               │ │
│ │ 2. 調用 calculate_vppa() 計算 VPPA 指標                     │ │
│ │ 3. 調用 plot_vppa_chart() 繪製圖表                          │ │
│ └─────────────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ src/agent/indicators.py (VPPA 計算邏輯)                         │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ calculate_vppa()                                            │ │
│ │ ├─ find_pivot_points() - 偵測 Pivot High/Low               │ │
│ │ ├─ extract_pivot_ranges() - 提取區間                       │ │
│ │ ├─ calculate_volume_profile_for_range() - 計算 VP          │ │
│ │ ├─ calculate_value_area() - 計算 POC/VAH/VAL               │ │
│ │ └─ 計算 developing_range (最後未完成區間)                  │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ 回傳：vppa_json (包含 pivot_ranges + developing_range)         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ src/visualization/ (Plotly 圖表繪製)                            │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ vppa_plot.py - 主繪圖模組                                   │ │
│ │ ┌─────────────────────────────────────────────────────────┐ │ │
│ │ │ plot_vppa_chart() - 主函數                              │ │ │
│ │ │ ├─ _add_candlestick() - K 線圖                          │ │ │
│ │ │ ├─ _add_range_boxes() - Pivot Range 方塊                │ │ │
│ │ │ ├─ _add_volume_profiles() - Volume Profile 矩形         │ │ │
│ │ │ ├─ _add_poc_lines() - POC 線                            │ │ │
│ │ │ ├─ _add_value_area_lines() - VAH/VAL 線 [待移除]        │ │ │
│ │ │ └─ _add_pivot_markers() - 箭頭標記 [待移除]             │ │ │
│ │ └─────────────────────────────────────────────────────────┘ │ │
│ │                                                               │ │
│ │ chart_config.py - 顏色和樣式配置                            │ │
│ │ ├─ COLORS 字典 (顏色定義)                                   │ │
│ │ └─ LINE_STYLES 字典 (線條樣式)                              │ │
│ │                                                               │ │
│ │ plotly_utils.py - 輔助工具                                  │ │
│ │ ├─ map_idx_to_time() - 索引映射                             │ │
│ │ ├─ validate_vppa_json() - JSON 驗證                         │ │
│ │ └─ get_volume_colors() - 顏色分配                           │ │
│ └─────────────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ↓
                    ┌───────────────┐
                    │ PNG 圖表輸出  │
                    └───────────────┘
```

### 圖表圖層結構（由下至上）

```
┌─────────────────────────────────────────────────────────────────┐
│ 圖表圖層堆疊（Layer Stack）                                     │
├─────────────────────────────────────────────────────────────────┤
│ [最上層]                                                         │
│  ↑                                                               │
│  │  7. POC 價格標註 (Text Mode Scatter)                         │
│  │  6. POC 線 (紅色實線，延伸到最右邊) [修改後]                 │
│  │  5. Pivot Points 標記 (紅/綠三角) [待移除]                   │
│  │  4. VAH/VAL 線 (綠色點線) [待移除]                           │
│  │  3. K 線圖 (Candlestick)                                     │
│  │  2. Volume Profile 矩形 (金黃色，layer='below')              │
│  │  1. Pivot Range 方塊 (淺黃色背景，layer='below')             │
│  │                                                               │
│  ↓  + 網格系統 (X/Y 軸網格線) [新增]                            │
│ [最下層]                                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 歷史脈絡

### 前一輪修改記錄（2024-12-30）

根據 `thoughts/shared/coding/2024-12-30-plotly-vppa-visualization-summary.md` 記錄：

**實作階段**：
- 階段 1：環境準備與基礎架構 ✅
- 階段 2：K 線圖與方塊繪製 ✅
- 階段 3：Volume Profile 繪製 ✅
- 階段 4：輔助線與標記 ✅
- 階段 5：整合到 analyze_vppa.py ✅
- 階段 6：測試與驗證 ✅

**技術成就**：
- 使用 `None` 分隔技巧合併多條線段為單一 Trace（效能優化）
- 透過 `timedelta` 精確控制 Volume Profile 的橫向寬度
- 自動根據 VAH/VAL 分配顏色，視覺化 Value Area
- 批量添加 shapes，避免多次更新布局

**測試結果**：
- 14/14 單元測試通過
- 程式碼覆蓋率：vppa_plot.py 98%、plotly_utils.py 100%
- 效能表現：2000 根 K 線 + 60 個 Pivot Ranges 繪製時間約 2-3 秒

---

## 相關研究文檔

- `thoughts/shared/coding/2024-12-30-plotly-vppa-visualization-summary.md` - 前一輪 VPPA 視覺化實作總結
- `thoughts/shared/plan/2024-12-30-plotly-vppa-visualization-plan.md` - 原始視覺化計劃
- `thoughts/shared/research/2024-12-30-plotly-kline-volume-profile-research.md` - Plotly K 線圖與 Volume Profile 研究

---

## 開放問題

### 1. Volume Profile 顏色定義澄清

**問題**：需求 2(b) 中的「Volume Profile 中間區間」具體指什麼？
- 選項 A：Value Area 內的顏色（POC 上下 68% 成交量範圍）
- 選項 B：所有 Volume Profile 統一顏色（移除內外分層）

**建議**：根據 VPPA 指標慣例，建議採用選項 A（僅修改 Value Area 內顏色）。

### 2. POC 標註位置

**問題**：多條 POC 線延伸到最右邊時，標註可能會重疊。

**可能的解決方案**：
- 方案 A：垂直錯開標註位置（自動檢測重疊並調整 Y 座標）
- 方案 B：僅標註最近 N 個區間的 POC
- 方案 C：使用 hover 顯示詳細資訊，減少常駐標註

**建議**：先實作基本版本（方案 B），在實際測試後再決定是否需要防重疊邏輯。

### 3. developing_range 的視覺區分

**問題**：developing_range 是即時發展中的區間，是否需要與已確認區間視覺上有所區分？

**可能的設計**：
- 使用虛線邊框（已確認區間為實線）
- 使用不同的透明度
- 添加「Developing」文字標註

**建議**：先保持一致的視覺樣式，在使用者回饋後再決定是否需要視覺區分。

---

## 總結

本次研究全面掃描了 VPPA 視覺化系統的程式碼架構，確認了所有六大修改需求的程式碼位置和修改方式：

**核心發現**：
1. **移除功能**可透過移除函數調用或刪除函數完成
2. **顏色和樣式修改**集中在 `chart_config.py`，實作簡單
3. **網格系統**需要新增動態計算邏輯和軸配置
4. **POC 延伸**需要修改線段終點並添加標註系統
5. **developing_range**已有完整資料，只需添加繪製邏輯
6. **標題格式**只需修改一行字串

系統採用清晰的模組化設計，各功能職責分離，修改影響範圍可控。建議按照「簡單到複雜」的順序實作，先完成顏色和樣式修改，再實作網格系統和 POC 延伸功能。

---

**研究完成時間**：2025-12-31
**研究狀態**：✅ 完成
**研究者備註**：所有程式碼位置已確認，修改方案已提出，可進入實作階段。建議先確認需求 2(b) 的澄清問題後再開始修改。
