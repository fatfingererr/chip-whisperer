---
title: "VPPA 圖表修改實作總結"
date: 2025-12-31
author: Claude Code (Implementation Specialist)
tags: [vppa, visualization, plotly, chart-modification, implementation]
status: completed
related_files:
  - src/visualization/vppa_plot.py
  - src/visualization/chart_config.py
  - thoughts/shared/research/2025-12-31-vppa-chart-modification-research.md
last_updated: 2025-12-31
last_updated_by: Claude Code
---

# VPPA 圖表修改實作總結

## 實作概述

本次實作根據研究文件 `thoughts/shared/research/2025-12-31-vppa-chart-modification-research.md` 中的開發計畫，對 VPPA (Volume Profile Pivot Anchored) 視覺化系統進行了全面的功能增強和樣式調整。所有四個階段的修改均已成功完成並通過測試驗證。

## 實作時間

- **開始時間**：2025-12-31
- **完成時間**：2025-12-31
- **總耗時**：約 1 小時
- **實作狀態**：✅ 完成

## 實作階段摘要

### 階段 1：顏色和樣式修改（簡單）✅

**目標**：移除不需要的視覺元素並調整配色方案

**修改檔案**：
- `src/visualization/chart_config.py`（配置檔案）
- `src/visualization/vppa_plot.py`（繪圖模組）

**具體修改**：

1. **需求 1(a)：移除 Pivot Points 箭頭標記**
   - 位置：`vppa_plot.py` 第 418-420 行
   - 修改：註解掉 `_add_pivot_markers()` 函數調用
   ```python
   # 5. 移除 Pivot Points 標記（需求 1(a)）
   # if show_pivot_points:
   #     _add_pivot_markers(fig, vppa_json['pivot_points'], candles_df)
   ```

2. **需求 1(b)：移除 VAH/VAL 綠色虛線**
   - 位置：`vppa_plot.py` 第 415-416 行
   - 修改：註解掉 `_add_value_area_lines()` 函數調用
   ```python
   # 移除 VAH/VAL 線（需求 1(b)）
   # _add_value_area_lines(fig, vppa_json['pivot_ranges'])
   ```

3. **需求 2(a)：區間背景透明度改為 50%**
   - 位置：`chart_config.py` 第 12 行
   - 修改前：`'range_fill': 'rgba(255, 255, 153, 0.3)'`
   - 修改後：`'range_fill': 'rgba(255, 255, 153, 0.5)'`

4. **需求 2(b)：Volume Profile 中間區間顏色改為 #D5A634**
   - 位置：`chart_config.py` 第 16 行
   - 修改前：`'volume_in_va': 'rgba(65, 105, 225, 0.85)'`（藍色）
   - 修改後：`'volume_in_va': 'rgba(213, 166, 52, 0.85)'`（金黃色）

5. **需求 2(c)：POC 改為紅色實線**
   - 位置：`chart_config.py` 第 30 行
   - 修改前：`'poc': 'dash'`（虛線）
   - 修改後：`'poc': 'solid'`（實線）

6. **需求 6：修改標題格式**
   - 位置：`vppa_plot.py` 第 428 行
   - 修改前：`'{symbol} {timeframe} - Volume Profile Pivot Anchored'`
   - 修改後：`'{symbol}, {timeframe} - Volume Profile, Pivot Anchored'`

**成果**：
- 視覺簡化，移除了干擾元素（箭頭標記和 VAH/VAL 線）
- 配色更加和諧，金黃色 Volume Profile 更加醒目
- POC 實線更清晰易讀
- 標題格式更符合業界規範

---

### 階段 2：網格系統實作 ✅

**目標**：添加 X 軸和 Y 軸網格以提升圖表可讀性

**修改檔案**：
- `src/visualization/vppa_plot.py`

**新增函數**：

1. **`calculate_y_grid_interval(latest_price: float) -> float`**（第 24-42 行）
   - 功能：根據價格位數動態計算 Y 軸網格間隔
   - 邏輯：最小值的 1/20
   - 範例：
     - 4000（4 位數）→ 最小值 1000 → 間隔 50
     - 25000（5 位數）→ 最小值 10000 → 間隔 500

2. **`get_x_grid_interval(timeframe: str) -> int`**（第 45-71 行）
   - 功能：根據時間週期取得 X 軸網格間隔（毫秒）
   - 規則：
     - M1/M5/M15：1 小時（3600000 毫秒）
     - M30/H1/H4：4 小時（14400000 毫秒）
     - D1 以上：1 日（86400000 毫秒）

**主函數修改**：

1. **獲取最新價格和時間**（第 463-466 行）
   ```python
   # 取得時間週期和最新價格（用於網格計算和 POC 延伸）
   timeframe = vppa_json.get('timeframe', 'M1')
   latest_price = candles_df['close'].iloc[-1]
   latest_time = candles_df['time'].iloc[-1]
   ```

2. **計算網格間隔**（第 473-475 行）
   ```python
   # 計算網格間隔
   y_grid_interval = calculate_y_grid_interval(latest_price)
   x_grid_interval = get_x_grid_interval(timeframe)
   ```

3. **應用網格配置**（第 488-503 行）
   ```python
   xaxis={
       'title': '時間',
       'type': 'date',
       'rangeslider': {'visible': False},
       'showgrid': True,            # 顯示網格
       'dtick': x_grid_interval,    # X 軸間隔
       'gridcolor': 'lightgray',
       'gridwidth': 0.5
   },
   yaxis={
       'title': '價格',
       'fixedrange': False,
       'showgrid': True,            # 顯示網格
       'dtick': y_grid_interval,    # Y 軸間隔
       'gridcolor': 'lightgray',
       'gridwidth': 0.5
   }
   ```

**成果**：
- X 軸網格根據時間週期自適應調整
- Y 軸網格根據價格位數動態計算
- 網格顏色為淺灰色，不會干擾主要視覺元素

---

### 階段 3：POC 延伸和標註 ✅

**目標**：將所有 POC 線延伸到圖表最右邊，並標註價位和漲跌幅

**修改檔案**：
- `src/visualization/vppa_plot.py`

**函數重構**：

1. **修改 `_add_poc_lines()` 函數簽名**（第 233 行）
   - 修改前：`_add_poc_lines(fig: go.Figure, ranges: list) -> None`
   - 修改後：`_add_poc_lines(fig: go.Figure, ranges: list, latest_time: pd.Timestamp, latest_price: float) -> None`

2. **POC 延伸邏輯**（第 254-262 行）
   ```python
   for range_data in ranges:
       x0 = pd.Timestamp(range_data['start_time'])
       x1 = latest_time  # 延伸到最右邊（原本是 range_data['end_time']）
       poc_price = range_data['poc']['price']

       # 添加線段（使用 None 分隔不同線段）
       all_x.extend([x0, x1, None])
       all_y.extend([poc_price, poc_price, None])
   ```

3. **漲跌幅計算**（第 264-270 行）
   ```python
   # 計算漲跌幅
   price_diff_pct = ((latest_price - poc_price) / poc_price) * 100

   # 添加標註
   annotation_x.append(x1)
   annotation_y.append(poc_price)
   annotation_text.append(f"{poc_price:.2f} ({price_diff_pct:+.1f}%)")
   ```

4. **添加標註 Trace**（第 287-297 行）
   ```python
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
   ```

**主函數調整**（第 496-497 行）：
```python
# 4. 添加輔助線（POC 延伸到最右邊並標註）
# 使用 all_ranges 以包含 developing_range 的 POC
_add_poc_lines(fig, all_ranges, latest_time, latest_price)
```

**成果**：
- 所有 POC 線均延伸到圖表最右邊
- 每條 POC 線的最右邊上方標註價位（例如：`4387.13`）
- 標註包含與最新價格的漲跌幅（例如：`+0.5%` 或 `-1.2%`）
- 漲跌幅四捨五入到小數第一位

---

### 階段 4：developing_range 繪製 ✅

**目標**：繪製最後一個未完成區間的 Volume Profile

**修改檔案**：
- `src/visualization/vppa_plot.py`

**實作邏輯**（第 474-487 行）：

```python
# 1. 先收集所有 shapes（方塊 + Volume Profile）
all_shapes = []

# 收集所有區間（包含 developing_range）
all_ranges = vppa_json['pivot_ranges'].copy()

# 如果存在 developing_range，也加入繪製
if show_developing and vppa_json.get('developing_range'):
    all_ranges.append(vppa_json['developing_range'])

# 建立 Pivot Range 方塊
range_shapes = _add_range_boxes(all_ranges, show_developing)
all_shapes.extend(range_shapes)

# 建立 Volume Profile shapes（最大寬度 = Range 寬度的 2/3）
vp_shapes = _add_volume_profiles(all_ranges, timeframe=timeframe)
all_shapes.extend(vp_shapes)
```

**關鍵設計**：
- 不需要修改 `_add_range_boxes()` 和 `_add_volume_profiles()` 函數
- 直接將 `developing_range` 加入 `all_ranges` 列表即可
- 這兩個函數已經支援處理含有 `developing_range` 資料結構的區間

**成果**：
- 最後一個未完成區間（developing_range）的方塊和 Volume Profile 均正確繪製
- developing_range 的 POC 也延伸到最右邊並標註
- 視覺上與歷史區間保持一致

---

## 測試驗證

### 測試命令

```powershell
cd "C:\Users\fatfi\works\chip-whisperer"
python scripts/analyze_vppa.py GOLD --count 500 --plot --plot-output "output/test_vppa_chart.png"
```

### 測試結果

**執行狀態**：✅ 成功

**輸出摘要**：
- 商品代碼：GOLD
- 時間週期：M1
- K 線數量：500 根
- Pivot Points：4 個（3 High, 1 Low）
- 歷史區間：3 個
- developing_range：存在（99 根 K 線）
- 圖表輸出：`output/test_vppa_chart.png`

**驗證項目**：
- ✅ Pivot Points 箭頭標記已移除
- ✅ VAH/VAL 綠色虛線已移除
- ✅ 區間背景透明度為 50%
- ✅ Volume Profile 中間區間為金黃色（#D5A634）
- ✅ POC 為紅色實線
- ✅ X 軸網格間隔為 1 小時（M1 時間週期）
- ✅ Y 軸網格間隔動態計算（價格 4000 左右 → 間隔 50）
- ✅ 所有 POC 線延伸到最右邊
- ✅ POC 線標註價位和漲跌幅
- ✅ developing_range 的 Volume Profile 已繪製
- ✅ 標題格式為 `GOLD, M1 - Volume Profile, Pivot Anchored`

**效能表現**：
- 繪製時間：約 0.1 秒
- 圖表尺寸：1920x1080 (scale=2)
- 無錯誤或警告訊息

---

## 程式碼修改總結

### 修改檔案列表

| 檔案 | 修改類型 | 修改行數 | 修改內容 |
|------|---------|---------|---------|
| `src/visualization/chart_config.py` | 配置調整 | 3 行 | 顏色和線條樣式修改 |
| `src/visualization/vppa_plot.py` | 功能增強 | 約 80 行 | 網格系統、POC 延伸、developing_range |

### 新增函數

| 函數名稱 | 位置 | 功能 |
|---------|------|------|
| `calculate_y_grid_interval()` | `vppa_plot.py` 第 24-42 行 | 計算 Y 軸網格間隔 |
| `get_x_grid_interval()` | `vppa_plot.py` 第 45-71 行 | 計算 X 軸網格間隔 |

### 修改函數

| 函數名稱 | 修改類型 | 修改內容 |
|---------|---------|---------|
| `_add_poc_lines()` | 函數簽名和邏輯 | 添加 `latest_time` 和 `latest_price` 參數，實作 POC 延伸和標註 |
| `plot_vppa_chart()` | 邏輯增強 | 添加網格計算、developing_range 處理 |

### 程式碼品質

- **可讀性**：所有修改均添加詳細註解
- **可維護性**：功能模組化，邏輯清晰
- **效能**：使用 `None` 分隔技巧合併多條線段，避免重複 Trace
- **向後相容性**：保留原有函數結構，僅擴展功能
- **錯誤處理**：保留原有的驗證和錯誤處理機制

---

## 技術亮點

### 1. 動態網格計算

**Y 軸網格間隔**：
```python
def calculate_y_grid_interval(latest_price: float) -> float:
    price_int = int(latest_price)
    price_digits = len(str(price_int))
    min_unit = 10 ** (price_digits - 1)
    interval = min_unit / 20
    return interval
```

**優勢**：
- 自適應不同價格範圍的商品
- 間隔大小合理，既不過密也不過疏

**X 軸網格間隔**：
```python
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
```

**優勢**：
- 根據時間週期自動調整網格密度
- 提升不同時間尺度圖表的可讀性

### 2. POC 延伸和標註

**技術方案**：
- 使用 Scatter Text Mode 而非 Annotations
- 批量添加標註，避免效能問題
- 自動計算漲跌幅並格式化（`+0.5%` 或 `-1.2%`）

**優勢**：
- 效能更好（避免大量 Annotations）
- 標註位置靈活（`textposition='top right'`）
- 視覺一致性高

### 3. developing_range 處理

**設計巧思**：
- 不修改 `_add_range_boxes()` 和 `_add_volume_profiles()` 函數
- 直接將 `developing_range` 加入 `all_ranges` 列表
- 利用現有函數的通用性

**優勢**：
- 程式碼修改最小化
- 降低引入錯誤的風險
- 保持架構一致性

### 4. 顏色配置集中管理

**配置檔案**：`chart_config.py`
```python
COLORS = {
    'range_fill': 'rgba(255, 255, 153, 0.5)',    # 透明度 50%
    'volume_in_va': 'rgba(213, 166, 52, 0.85)',  # 金黃色
    'poc_line': 'rgb(255, 0, 0)',                # 紅色
}

LINE_STYLES = {
    'poc': 'solid',    # 實線
}
```

**優勢**：
- 集中管理視覺樣式
- 易於調整和維護
- 符合 DRY 原則

---

## 視覺效果對比

### 修改前
- ❌ 有紅色/綠色箭頭標記（干擾視線）
- ❌ 有綠色 VAH/VAL 虛線（資訊過載）
- ❌ 區間背景透明度 30%（不夠明顯）
- ❌ Volume Profile 為藍色（顏色單調）
- ❌ POC 為紅色虛線（不夠清晰）
- ❌ 無網格（價格和時間難以估算）
- ❌ POC 僅延伸到區間終點（無法比較）
- ❌ 無 developing_range 的 Volume Profile

### 修改後
- ✅ 無箭頭標記（視覺簡潔）
- ✅ 無 VAH/VAL 線（減少干擾）
- ✅ 區間背景透明度 50%（更加明顯）
- ✅ Volume Profile 為金黃色（視覺醒目）
- ✅ POC 為紅色實線（清晰易讀）
- ✅ 有 X/Y 軸網格（便於估算）
- ✅ POC 延伸到最右邊並標註漲跌幅（便於比較）
- ✅ developing_range 的 Volume Profile 完整顯示

---

## 潛在改進方向

### 1. POC 標註重疊處理

**問題**：當多條 POC 線的價位接近時，標註可能重疊。

**可能的解決方案**：
- 方案 A：垂直錯開標註位置（自動檢測重疊並調整 Y 座標）
- 方案 B：僅標註最近 N 個區間的 POC
- 方案 C：使用 hover 顯示詳細資訊，減少常駐標註

**建議**：先觀察實際使用情況，再決定是否需要實作防重疊邏輯。

### 2. developing_range 視覺區分

**問題**：developing_range 與歷史區間視覺上無區別。

**可能的設計**：
- 使用虛線邊框（已確認區間為實線）
- 使用不同的透明度
- 添加「Developing」文字標註

**建議**：先保持一致的視覺樣式，在使用者回饋後再決定是否需要視覺區分。

### 3. 網格顏色和樣式自訂

**改進方向**：
- 將網格顏色和寬度移至 `chart_config.py`
- 支援不同主題（亮色/暗色模式）
- 支援網格虛線樣式

**優勢**：
- 更靈活的視覺自訂
- 更好的主題一致性

---

## 相關文件

- **研究文件**：`thoughts/shared/research/2025-12-31-vppa-chart-modification-research.md`
- **配置檔案**：`src/visualization/chart_config.py`
- **主繪圖模組**：`src/visualization/vppa_plot.py`
- **輔助工具**：`src/visualization/plotly_utils.py`
- **測試腳本**：`scripts/analyze_vppa.py`

---

## 結論

本次 VPPA 圖表修改實作圓滿完成，所有六大需求均已實現並通過測試驗證：

1. ✅ **移除功能**：移除了 Pivot Points 箭頭標記和 VAH/VAL 綠色虛線
2. ✅ **顏色樣式調整**：區間背景透明度 50%、Volume Profile 金黃色、POC 紅色實線
3. ✅ **網格系統**：X/Y 軸動態網格間隔
4. ✅ **POC 延伸**：延伸到最右邊並標註價位和漲跌幅
5. ✅ **developing_range**：最後一個未完成區間的 Volume Profile 正確繪製
6. ✅ **標題格式**：逗號分隔格式

**技術成就**：
- 程式碼修改量小，影響範圍可控
- 保持原有架構和效能優勢
- 新增功能模組化，易於維護
- 所有修改均有詳細註解

**視覺效果**：
- 圖表更簡潔、更專注於核心資訊
- 配色更和諧、更符合交易者習慣
- 網格系統提升可讀性
- POC 延伸和標註便於價格比較

**測試結果**：
- 測試腳本執行成功
- 圖表生成正常
- 所有功能均按預期運作
- 無錯誤或警告訊息

---

**實作完成時間**：2025-12-31
**實作狀態**：✅ 完成
**實作者**：Claude Code (Implementation Specialist)
**版本**：v1.0
