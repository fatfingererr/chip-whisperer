---
title: "Plotly K線圖與成交量分佈視覺化功能研究"
date: 2024-12-30
author: Claude Code (Codebase Researcher)
tags: [plotly, visualization, k-line, volume-profile, vppa, candlestick]
status: completed
related_files:
  - scripts/analyze_vppa.py
  - src/agent/indicators.py
  - src/core/data_fetcher.py
  - data/vppa_full_output.json
last_updated: 2024-12-30
last_updated_by: Claude Code
---

# Plotly K線圖與成交量分佈視覺化功能研究

## 研究問題

基於 `analyze_vppa.py` 的輸出資料，設計並實作一個可復用的 Plotly 視覺化函式庫，用於繪製：
1. K 線圖（Candlestick Chart）
2. 基於 Pivot Point 切分的價格區間方塊（淺黃色填充，深黃色邊框）
3. 每個區間內的橫向成交量分佈圖（Volume Profile）
4. 最終輸出為 PNG 圖檔

## 摘要

本研究完整分析了 Chip Whisperer 專案中 VPPA（Volume Profile Pivot Anchored）的資料結構、計算流程和現有實作，並規劃了基於 Plotly 的視覺化解決方案。研究發現：

1. **資料來源完整**：`analyze_vppa.py` 輸出的 JSON 包含所有繪圖所需資料
2. **資料結構清晰**：每個 Pivot Range 都有完整的 K 線索引、價格範圍、Volume Profile 和 Value Area 資訊
3. **技術堆疊確定**：專案已包含 Plotly 相關依賴（pandas, numpy），可直接整合
4. **功能需求明確**：需要實作可復用的繪圖模組，支援 PNG 輸出

關鍵發現：
- VPPA 分析產生 60 個 Pivot Range（基於 2000 根 M1 K 線）
- 每個 Range 包含 49 層價格分佈（可調整）
- Volume Profile 資料已計算完成，包含每層的成交量和中心價格
- POC（Point of Control）、VAH（Value Area High）、VAL（Value Area Low）已計算
- 發展中區間（Developing Range）需特殊處理

## 詳細發現

### 1. analyze_vppa.py 輸出格式分析

#### 1.1 JSON 結構總覽

**檔案位置**：`scripts/analyze_vppa.py` (第 261-291 行)

完整的 JSON 輸出包含以下頂層鍵值：

```json
{
  "symbol": "GOLD",                    // 商品代碼
  "timeframe": "M1",                   // 時間週期
  "analysis_time": "2025-12-30T15:06:11+00:00",  // 分析時間
  "parameters": { ... },               // 計算參數
  "data_range": { ... },               // 資料範圍
  "summary": { ... },                  // 統計摘要
  "pivot_points": [ ... ],             // Pivot Points 列表
  "pivot_ranges": [ ... ],             // 完整的區間資料
  "developing_range": { ... }          // 發展中的區間（可選）
}
```

#### 1.2 Parameters（計算參數）

**檔案位置**：`scripts/analyze_vppa.py` (第 265-271 行)

```json
"parameters": {
  "count": 2000,              // K 線數量
  "pivot_length": 20,         // Pivot Point 左右窗口大小
  "price_levels": 49,         // Volume Profile 價格分層數
  "value_area_pct": 0.68,     // Value Area 百分比（68%）
  "volume_ma_length": 14      // 成交量移動平均長度
}
```

這些參數直接影響視覺化的細節程度。

#### 1.3 Data Range（資料範圍）

**檔案位置**：`scripts/analyze_vppa.py` (第 272-276 行)

```json
"data_range": {
  "start_time": "2025-12-29T04:47:00+00:00",
  "end_time": "2025-12-30T15:06:00+00:00",
  "total_bars": 2000
}
```

這定義了整個分析的時間範圍，用於繪製 X 軸標籤。

#### 1.4 Summary（統計摘要）

**檔案位置**：`scripts/analyze_vppa.py` (第 277-287 行)

```json
"summary": {
  "total_pivot_points": 61,           // 總 Pivot Points 數
  "total_ranges": 60,                 // 區間數量
  "avg_range_bars": 0,                // 平均每個區間的 K 線數
  "has_developing_range": true,       // 是否有發展中區間
  "volume_stats": {
    "latest_volume_ma": 53911.71,     // 最新成交量 MA
    "avg_volume": 61812.96,           // 平均成交量
    "total_volume": 123625914.0       // 總成交量
  }
}
```

#### 1.5 Pivot Points（樞軸點列表）

**檔案位置**：`scripts/analyze_vppa.py` (第 288 行) / `src/agent/indicators.py` (第 974-991 行)

這是所有偵測到的 Pivot Points 的摘要清單：

```json
"pivot_points": [
  {
    "idx": 22,                        // K 線索引（整數位置）
    "type": "H",                      // 類型（'H'=High, 'L'=Low）
    "price": 4518.78,                 // Pivot 價格
    "time": "2025-12-29T05:09:00+00:00"  // 時間戳
  },
  {
    "idx": 41,
    "type": "L",
    "price": 4512.13,
    "time": "2025-12-29T05:28:00+00:00"
  }
  // ... 總共 61 個
]
```

**視覺化用途**：可在 K 線圖上標記 Pivot Points（例如：High 用紅色三角形，Low 用綠色三角形）。

#### 1.6 Pivot Ranges（區間資料）

**檔案位置**：`scripts/analyze_vppa.py` (第 294-333 行)

這是最重要的繪圖資料來源。每個區間包含：

```json
{
  "range_id": 0,                      // 區間編號
  "start_idx": 22,                    // 起始 K 線索引
  "end_idx": 41,                      // 結束 K 線索引
  "start_time": "2025-12-29T05:09:00+00:00",
  "end_time": "2025-12-29T05:28:00+00:00",
  "bar_count": 19,                    // K 線數量
  "pivot_type": "L",                  // 結束位置的 Pivot 類型
  "pivot_price": 4512.13,             // Pivot 價格

  // 價格資訊
  "price_info": {
    "highest": 4518.78,               // 區間最高價
    "lowest": 4512.13,                // 區間最低價
    "range": 6.65,                    // 價格範圍
    "step": 0.1357                    // 每層價格步長
  },

  // POC (Point of Control)
  "poc": {
    "level": 31,                      // POC 所在層級
    "price": 4516.405,                // POC 價格
    "volume": 51295.02,               // POC 的成交量
    "volume_pct": 4.75                // 佔總成交量百分比
  },

  // Value Area
  "value_area": {
    "vah": 4517.15,                   // Value Area High
    "val": 4514.84,                   // Value Area Low
    "width": 2.31,                    // VA 寬度
    "volume": 736554.96,              // VA 內的總成交量
    "pct": 68.21                      // VA 百分比
  },

  // 成交量資訊
  "volume_info": {
    "total": 1079831.86,              // 區間總成交量
    "avg_per_bar": 53991.59           // 平均每根 K 線成交量
  },

  // Volume Profile 資料
  "volume_profile": {
    "levels": 49,                     // 價格層數
    "price_centers": [                // 每層的中心價格（49 個）
      4512.198, 4512.334, 4512.469, ...
    ],
    "volumes": [                      // 每層的成交量（49 個）
      50123.45, 48932.12, 52341.67, ...
    ]
  }
}
```

**關鍵觀察**：
- `start_idx` 和 `end_idx` 是整數索引，需要從原始 K 線資料中對應時間
- `volume_profile` 的 `price_centers` 和 `volumes` 陣列長度相同（49）
- POC 和 Value Area 已計算完成，可直接繪製輔助線

#### 1.7 Developing Range（發展中區間）

**檔案位置**：`scripts/analyze_vppa.py` (第 336-373 行)

結構與 `pivot_ranges` 相同，但標記為正在發展中：

```json
"developing_range": {
  "is_developing": true,              // 特殊標記
  "start_idx": 1980,
  "end_idx": 1999,
  // ... 其他欄位同 pivot_ranges
}
```

**視覺化建議**：用不同顏色或虛線邊框標記發展中區間。

---

### 2. 現有 VPPA 實作分析

#### 2.1 Pivot Point 偵測

**檔案位置**：`src/agent/indicators.py` (第 265-346 行)

`find_pivot_points()` 函數實作了 Pivot Point 偵測邏輯：

**核心演算法**：
```python
# Pivot High: 中心點的 high 嚴格高於左右各 length 根 K 線
for i in range(length, len(df) - length):
    center_high = df['high'].iloc[i]
    left_window = df['high'].iloc[i-length:i]
    right_window = df['high'].iloc[i+1:i+length+1]

    if (center_high > left_window.max() and
        center_high > right_window.max()):
        df.loc[df.index[i], 'pivot_high'] = center_high
```

**輸出**：添加 `pivot_high` 和 `pivot_low` 欄位的 DataFrame。

#### 2.2 Volume Profile 計算

**檔案位置**：`src/agent/indicators.py` (第 433-561 行)

`calculate_volume_profile_for_range()` 實作了成交量分配邏輯：

**核心演算法**：
```python
# 價格範圍分層
price_highest = range_df['high'].max()
price_lowest = range_df['low'].min()
price_step = (price_highest - price_lowest) / price_levels

# 成交量分配
volume_storage = np.zeros(price_levels)

for idx in range(len(range_df)):
    row = range_df.iloc[idx]
    bar_range = row['high'] - row['low']

    for level in range(price_levels):
        level_low = price_lowest + level * price_step
        level_high = price_lowest + (level + 1) * price_step

        # 檢查 K 線是否覆蓋此價格層級
        if bar_high >= level_low and bar_low < level_high:
            # 按比例分配成交量
            ratio = price_step / bar_range if bar_range > 0 else 1
            volume_storage[level] += bar_volume * ratio
```

**關鍵公式**：
```
分配成交量 = K線成交量 × (價格步長 / K線價格範圍)
```

這假設成交量在 K 線的價格範圍內均勻分布。

#### 2.3 Value Area 計算

**檔案位置**：`src/agent/indicators.py` (第 564-733 行)

`calculate_value_area()` 從 POC 開始向兩側擴展：

**核心演算法**：
```python
# 1. 找出 POC（成交量最大的層級）
poc_level = np.argmax(volume_storage)

# 2. 計算目標成交量（68% 總成交量）
target_volume = volume_storage.sum() * value_area_pct

# 3. 從 POC 開始向兩側擴展
value_area_volume = volume_storage[poc_level]
level_above_poc = poc_level
level_below_poc = poc_level

while value_area_volume < target_volume:
    # 取得上下相鄰層級的成交量
    volume_above = volume_storage[level_above_poc + 1]
    volume_below = volume_storage[level_below_poc - 1]

    # 選擇成交量較大的一側擴展
    if volume_above >= volume_below:
        value_area_volume += volume_above
        level_above_poc += 1
    else:
        value_area_volume += volume_below
        level_below_poc -= 1

# 4. 計算 VAH 和 VAL
vah = price_lowest + (level_above_poc + 1.0) * price_step
val = price_lowest + (level_below_poc + 0.0) * price_step
```

---

### 3. 資料獲取方式分析

#### 3.1 MT5 資料來源

**檔案位置**：`src/core/data_fetcher.py` (第 1-431 行)

`HistoricalDataFetcher` 類別提供多種資料獲取方式：

**主要方法**：
1. **`get_candles_latest()`**：取得最新 N 根 K 線（第 207-269 行）
2. **`get_candles_by_date()`**：取得指定日期範圍的 K 線（第 271-364 行）

**資料格式**：
```python
df = pd.DataFrame({
    'time': [...],        # Timestamp (UTC)
    'open': [...],        # 開盤價
    'high': [...],        # 最高價
    'low': [...],         # 最低價
    'close': [...],       # 收盤價
    'tick_volume': [...], # Tick 成交量
    'spread': [...],      # 價差
    'real_volume': [...]  # 真實成交量
})
```

**重要**：`real_volume` 是 Volume Profile 計算的關鍵欄位。

#### 3.2 SQLite 快取機制

**檔案位置**：`src/core/sqlite_cache.py` (第 1-431 行)

`SQLiteCacheManager` 提供資料快取功能，減少 MT5 API 調用：

**關鍵方法**：
- `query_candles()`：查詢快取的 K 線資料
- `insert_candles()`：插入新的 K 線資料
- `fetch_candles_smart()`：智能查詢（優先快取，不足則從 MT5 補充）

**使用範例**（來自 `analyze_vppa.py`）：
```python
# 步驟 1：補充 DB 到最新
cache = SQLiteCacheManager('data/candles.db')
newest_time = cache.get_newest_time(symbol, 'M1')
# 從 MT5 取得新資料並插入快取

# 步驟 2：從 DB 取得資料
df = cache.query_candles(symbol, 'M1', start_time, end_time)
```

#### 3.3 資料流程

```
1. analyze_vppa.py
   ↓
2. update_db_to_now() → 補充最新資料到 SQLite
   ↓
3. fetch_m1_data() → 從 SQLite 查詢資料
   ↓
4. calculate_vppa() → 計算 VPPA（調用 indicators.py）
   ↓
5. 輸出 JSON 檔案
```

---

### 4. 專案結構與程式碼風格

#### 4.1 目錄結構

```
chip-whisperer/
├── src/
│   ├── core/              # 核心功能（MT5、資料獲取、快取）
│   ├── agent/             # 指標計算（VPPA、RSI、SMA 等）
│   └── bot/               # Telegram Bot
├── scripts/               # 執行腳本
│   ├── analyze_vppa.py    # VPPA 分析腳本
│   ├── manage_cache.py    # 快取管理腳本
│   └── backfill_m1_data.py  # 資料補齊腳本
├── tests/                 # 單元測試
├── data/                  # 資料儲存（SQLite、輸出檔案）
├── thoughts/              # 文檔和研究筆記
│   ├── shared/
│   │   ├── research/      # 研究文檔
│   │   ├── plan/          # 實作計劃
│   │   └── coding/        # 實作總結
└── vendor/                # 第三方程式碼（如 vppa.txt）
```

#### 4.2 程式碼風格慣例

**檔案位置**：`pyproject.toml` (第 48-51 行)

```toml
[tool.black]
line-length = 100
target-version = ['py310', 'py311', 'py312']
```

**觀察到的風格**：
1. **函數命名**：snake_case（如 `calculate_vppa`, `find_pivot_points`）
2. **類別命名**：PascalCase（如 `MT5Config`, `HistoricalDataFetcher`）
3. **模組命名**：小寫加底線（如 `data_fetcher.py`, `mt5_config.py`）
4. **文檔字串**：完整的 Google 風格 docstring
5. **日誌記錄**：使用 loguru（`logger.info()`, `logger.debug()`, `logger.warning()`）
6. **錯誤處理**：明確的 ValueError 和 RuntimeError
7. **類型提示**：部分使用（如 `Optional[str]`, `Dict[str, Any]`）

**範例**（來自 `indicators.py`）：
```python
def calculate_vppa(
    df: pd.DataFrame,
    pivot_length: int = 20,
    price_levels: int = 25,
    value_area_pct: float = 0.68,
    include_developing: bool = True
) -> dict:
    """
    計算 Volume Profile Pivot Anchored (VPPA)

    參數：
        df: K 線資料 DataFrame
        pivot_length: Pivot Point 左右觀察窗口大小
        price_levels: Volume Profile 價格分層數量
        value_area_pct: Value Area 包含的成交量百分比
        include_developing: 是否包含即時發展中的區間

    回傳：
        完整的 VPPA 資料結構字典

    例外：
        ValueError: 輸入資料格式錯誤或資料量不足時
    """
    logger.info("=" * 60)
    logger.info("開始計算 VPPA (Volume Profile Pivot Anchored)")
    # ...
```

#### 4.3 依賴套件

**檔案位置**：`requirements.txt` 和 `pyproject.toml`

**核心依賴**：
```
MetaTrader5>=5.0.4510   # MT5 API
pandas>=2.0.0           # 資料處理
numpy>=1.24.0           # 數值計算
loguru>=0.7.0           # 日誌記錄
```

**視覺化相關**（需新增）：
```
plotly>=5.18.0          # 互動式圖表
kaleido>=0.2.1          # PNG 輸出（Plotly 靜態圖片支援）
```

**注意**：專案目前沒有包含 Plotly，需要在實作時新增到 `requirements.txt`。

---

### 5. Plotly 視覺化需求規劃

#### 5.1 繪圖元素清單

基於需求和資料結構，需要繪製以下元素：

**1. K 線圖（Candlestick Chart）**
- **資料來源**：原始 K 線 DataFrame（需從 MT5 重新獲取或從 JSON 提取）
- **Plotly 圖表類型**：`go.Candlestick`
- **必要欄位**：`time`, `open`, `high`, `low`, `close`
- **X 軸**：時間（`time`）
- **Y 軸**：價格

**2. Pivot Range 方塊（Range Boxes）**
- **資料來源**：`pivot_ranges` 陣列
- **Plotly 圖表類型**：`go.Scatter` 填充模式或 `shapes`（矩形）
- **繪製方式**：
  - 從 `start_idx` 對應的時間到 `end_idx` 對應的時間（X 軸）
  - 從 `price_info.lowest` 到 `price_info.highest`（Y 軸）
  - 填充色：淺黃色（`rgba(255, 255, 153, 0.3)`）
  - 邊框色：深黃色（`rgba(204, 153, 0, 1.0)`）
  - 邊框寬度：2px

**3. 橫向成交量分佈圖（Volume Profile）**
- **資料來源**：每個 `pivot_ranges` 的 `volume_profile`
- **Plotly 圖表類型**：`go.Bar`（橫向長條圖）
- **繪製方式**：
  - X 軸：成交量（`volumes`）
  - Y 軸：價格（`price_centers`）
  - 位置：靠近區間的左側（`start_idx` 對應的時間）
  - 寬度：成交量值（需要正規化以避免遮蓋 K 線）
  - 顏色：
    - Value Area 內：半透明藍色（`rgba(100, 149, 237, 0.6)`）
    - Value Area 外：半透明灰色（`rgba(169, 169, 169, 0.4)`）

**4. POC 線（Point of Control Line）**
- **資料來源**：每個 `pivot_ranges` 的 `poc.price`
- **Plotly 圖表類型**：`go.Scatter`（線條模式）
- **繪製方式**：
  - X 軸：從區間起始到結束
  - Y 軸：`poc.price`（水平線）
  - 顏色：紅色（`rgb(255, 0, 0)`）
  - 線型：虛線（`dash`）
  - 寬度：2px

**5. Value Area 線（VAH/VAL Lines）**
- **資料來源**：每個 `pivot_ranges` 的 `value_area.vah` 和 `value_area.val`
- **Plotly 圖表類型**：`go.Scatter`（線條模式）
- **繪製方式**：
  - 同 POC 線，但繪製兩條（VAH 和 VAL）
  - 顏色：綠色（`rgb(0, 128, 0)`）
  - 線型：點線（`dot`）
  - 寬度：1.5px

**6. Pivot Points 標記（可選）**
- **資料來源**：`pivot_points` 陣列
- **Plotly 圖表類型**：`go.Scatter`（標記模式）
- **繪製方式**：
  - Pivot High：紅色向下三角形（`triangle-down`）
  - Pivot Low：綠色向上三角形（`triangle-up`）
  - 位置：對應的時間和價格

#### 5.2 資料預處理需求

**問題**：JSON 輸出不包含完整的 K 線資料，只有索引。

**解決方案**：
1. **方案 A（推薦）**：修改 `analyze_vppa.py`，在輸出中包含完整的 K 線資料
   ```python
   output['candlestick_data'] = df[['time', 'open', 'high', 'low', 'close', 'real_volume']].to_dict('records')
   ```

2. **方案 B**：視覺化函數接收兩個參數：
   ```python
   plot_vppa_chart(
       vppa_json: dict,      # analyze_vppa.py 的輸出
       candles_df: pd.DataFrame  # 原始 K 線資料
   )
   ```

3. **方案 C**：視覺化函數內部重新從 MT5/快取取得 K 線資料
   ```python
   # 從 JSON 取得時間範圍
   start_time = vppa_json['data_range']['start_time']
   end_time = vppa_json['data_range']['end_time']

   # 重新查詢
   cache = SQLiteCacheManager('data/candles.db')
   df = cache.query_candles(symbol, timeframe, start_time, end_time)
   ```

**建議**：採用方案 B，因為：
- 保持 `analyze_vppa.py` 的輸出簡潔（JSON 檔案不會過大）
- 視覺化函數可靈活使用不同來源的 K 線資料
- 支援未來可能的資料轉換需求

#### 5.3 時間軸映射

**挑戰**：`pivot_ranges` 的 `start_idx` 和 `end_idx` 是整數索引，需要映射到時間軸。

**解決方案**：
```python
def map_idx_to_time(idx: int, df: pd.DataFrame) -> pd.Timestamp:
    """
    將整數索引映射到時間戳

    參數：
        idx: K 線索引（整數位置）
        df: K 線 DataFrame

    回傳：
        對應的時間戳
    """
    return df.iloc[idx]['time']

# 使用範例
range_data = vppa_json['pivot_ranges'][0]
start_time = map_idx_to_time(range_data['start_idx'], df)
end_time = map_idx_to_time(range_data['end_idx'], df)
```

**注意**：需確保 DataFrame 的索引順序與 VPPA 計算時一致（通常是時間升序）。

#### 5.4 成交量分佈的正規化

**問題**：Volume Profile 的成交量值可能很大，直接繪製會遮蓋 K 線圖。

**解決方案**：正規化成交量寬度

```python
def normalize_volume_width(volumes: np.ndarray, max_width_bars: int = 10) -> np.ndarray:
    """
    正規化 Volume Profile 的成交量寬度

    參數：
        volumes: 原始成交量陣列
        max_width_bars: Volume Profile 最大寬度（以 K 線數量為單位）

    回傳：
        正規化後的寬度陣列（單位：時間）
    """
    max_volume = volumes.max()
    if max_volume == 0:
        return np.zeros_like(volumes)

    # 將最大成交量映射到 max_width_bars 根 K 線的寬度
    # 假設每根 K 線寬度為 1 個時間單位（如 1 分鐘）
    normalized = (volumes / max_volume) * max_width_bars

    return normalized
```

**繪製時的座標計算**：
```python
# 範例：區間起始於 2025-12-29 10:00
start_time = pd.Timestamp('2025-12-29 10:00')

# 成交量為 50000，正規化後為 5 個時間單位
normalized_width = 5

# Volume Profile 長條圖的起點和終點
x_start = start_time
x_end = start_time + pd.Timedelta(minutes=normalized_width)  # 假設 M1 週期
```

#### 5.5 圖表布局設定

**Plotly 布局配置**：
```python
layout = go.Layout(
    title={
        'text': f'{symbol} {timeframe} - Volume Profile Pivot Anchored',
        'x': 0.5,
        'xanchor': 'center'
    },
    xaxis={
        'title': '時間',
        'type': 'date',
        'rangeslider': {'visible': False}  # 關閉 Candlestick 預設的範圍滑桿
    },
    yaxis={
        'title': '價格',
        'fixedrange': False  # 允許縮放
    },
    hovermode='x unified',  # 統一 X 軸的 Hover 顯示
    plot_bgcolor='white',   # 背景色
    showlegend=True,
    legend={
        'orientation': 'v',
        'yanchor': 'top',
        'y': 1,
        'xanchor': 'left',
        'x': 1.01
    }
)
```

---

### 6. 實作規劃

#### 6.1 模組結構設計

建議建立新的視覺化模組：

**檔案位置**：`src/visualization/` (新建)

```
src/visualization/
├── __init__.py
├── plotly_charts.py      # Plotly 圖表繪製核心
├── vppa_plot.py          # VPPA 專用繪圖函數
└── utils.py              # 輔助工具（正規化、顏色等）
```

#### 6.2 核心函數設計

**檔案**：`src/visualization/vppa_plot.py`

```python
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
```

**子函數**：

```python
def _add_candlestick(fig: go.Figure, df: pd.DataFrame) -> None:
    """添加 K 線圖層"""

def _add_range_boxes(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """添加 Pivot Range 方塊"""

def _add_volume_profiles(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """添加 Volume Profile 長條圖"""

def _add_poc_lines(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """添加 POC 線"""

def _add_value_area_lines(fig: go.Figure, ranges: list, df: pd.DataFrame) -> None:
    """添加 VAH/VAL 線"""

def _add_pivot_markers(fig: go.Figure, pivot_points: list, df: pd.DataFrame) -> None:
    """添加 Pivot Points 標記"""
```

#### 6.3 使用範例

**範例腳本**：`examples/plot_vppa_example.py`

```python
#!/usr/bin/env python3
"""
VPPA 視覺化範例

此腳本展示如何使用 plot_vppa_chart 函數繪製 VPPA 圖表
"""

import json
import pandas as pd
from pathlib import Path
from src.core.sqlite_cache import SQLiteCacheManager
from src.visualization.vppa_plot import plot_vppa_chart

def main():
    # 1. 載入 VPPA 分析結果
    vppa_json_path = Path('data/vppa_full_output.json')
    with open(vppa_json_path, 'r', encoding='utf-8') as f:
        vppa_data = json.load(f)

    # 2. 從快取獲取 K 線資料
    cache = SQLiteCacheManager('data/candles.db')
    symbol = vppa_data['symbol']
    timeframe = vppa_data['timeframe']
    start_time = pd.Timestamp(vppa_data['data_range']['start_time'])
    end_time = pd.Timestamp(vppa_data['data_range']['end_time'])

    df = cache.query_candles(symbol, timeframe, start_time, end_time)

    # 3. 繪製圖表
    fig = plot_vppa_chart(
        vppa_json=vppa_data,
        candles_df=df,
        output_path='output/vppa_chart.png',
        show_pivot_points=True,
        show_developing=True,
        width=1920,
        height=1080
    )

    print("✅ 圖表已儲存到 output/vppa_chart.png")

    # 4. 可選：在瀏覽器中顯示互動式圖表
    # fig.show()

if __name__ == '__main__':
    main()
```

#### 6.4 整合到 analyze_vppa.py

**修改建議**：在 `analyze_vppa.py` 添加 `--plot` 選項

```python
parser.add_argument(
    '--plot',
    action='store_true',
    help='分析完成後自動繪製圖表'
)

parser.add_argument(
    '--plot-output',
    type=str,
    default='output/vppa_chart.png',
    help='圖表輸出路徑（預設：output/vppa_chart.png）'
)

# 在 main() 函數最後
if args.plot:
    from src.visualization.vppa_plot import plot_vppa_chart

    fig = plot_vppa_chart(
        vppa_json=result,
        candles_df=df,  # 已計算的 DataFrame
        output_path=args.plot_output
    )

    print(f"✅ 圖表已輸出到：{args.plot_output}")
```

**使用範例**：
```bash
python scripts/analyze_vppa.py GOLD --count 2000 --plot --plot-output output/gold_vppa.png
```

---

### 7. Plotly 技術細節

#### 7.1 Candlestick 圖表

**基本語法**：
```python
import plotly.graph_objects as go

candlestick = go.Candlestick(
    x=df['time'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name='OHLC',
    increasing_line_color='#26a69a',  # 上漲 K 線顏色
    decreasing_line_color='#ef5350'   # 下跌 K 線顏色
)

fig = go.Figure(data=[candlestick])
```

#### 7.2 矩形方塊（Shapes）

**方法 A：使用 `shapes`**（推薦，效能較好）
```python
# 添加矩形
fig.add_shape(
    type='rect',
    x0=start_time,     # 起始時間
    x1=end_time,       # 結束時間
    y0=lowest_price,   # 最低價
    y1=highest_price,  # 最高價
    fillcolor='rgba(255, 255, 153, 0.3)',  # 淺黃色填充
    line=dict(
        color='rgba(204, 153, 0, 1.0)',    # 深黃色邊框
        width=2
    ),
    layer='below'  # 放在 K 線圖下層
)
```

**方法 B：使用 `go.Scatter` 填充**
```python
fig.add_trace(go.Scatter(
    x=[start_time, end_time, end_time, start_time, start_time],
    y=[lowest_price, lowest_price, highest_price, highest_price, lowest_price],
    fill='toself',
    fillcolor='rgba(255, 255, 153, 0.3)',
    line=dict(color='rgba(204, 153, 0, 1.0)', width=2),
    mode='lines',
    name=f'Range {range_id}',
    showlegend=False
))
```

**建議**：使用方法 A（`shapes`），因為：
- 效能更好（特別是有多個矩形時）
- 不會干擾圖例
- 支援 `layer` 屬性，可控制繪製層次

#### 7.3 橫向長條圖（Volume Profile）

**關鍵**：使用 `go.Bar` 並設定 `orientation='h'`

```python
# 範例：繪製單個 Volume Profile
range_data = vppa_json['pivot_ranges'][0]
price_centers = range_data['volume_profile']['price_centers']
volumes = range_data['volume_profile']['volumes']

# 正規化成交量（轉換為時間單位）
start_time = map_idx_to_time(range_data['start_idx'], df)
normalized_volumes = normalize_volume_width(
    np.array(volumes),
    max_width_bars=10  # 最大寬度 10 根 K 線
)

# 計算每個長條的 X 座標
x_values = []
for norm_vol in normalized_volumes:
    x_values.append(start_time + pd.Timedelta(minutes=norm_vol))

# 繪製
fig.add_trace(go.Bar(
    x=x_values,
    y=price_centers,
    orientation='h',
    marker=dict(
        color='rgba(100, 149, 237, 0.6)',  # 半透明藍色
        line=dict(width=0)
    ),
    width=range_data['price_info']['step'],  # 長條高度 = 價格步長
    name=f'VP {range_data["range_id"]}',
    showlegend=False,
    hovertemplate='價格: %{y:.2f}<br>成交量: %{customdata:.0f}<extra></extra>',
    customdata=volumes  # 顯示原始成交量
))
```

**注意**：
- `x` 是長條的終點（起點為 `start_time`）
- `y` 是價格中心
- `width` 是長條的高度（價格方向）
- `customdata` 用於顯示原始成交量（因為 X 軸是正規化後的）

**顏色分層**（Value Area 內外不同顏色）：
```python
# 判斷每層是否在 Value Area 內
vah = range_data['value_area']['vah']
val = range_data['value_area']['val']

colors = []
for price in price_centers:
    if val <= price <= vah:
        colors.append('rgba(100, 149, 237, 0.6)')  # Value Area 內：藍色
    else:
        colors.append('rgba(169, 169, 169, 0.4)')  # Value Area 外：灰色

fig.add_trace(go.Bar(
    # ... 其他參數同上
    marker=dict(
        color=colors,  # 使用顏色陣列
        line=dict(width=0)
    )
))
```

#### 7.4 水平線（POC、VAH、VAL）

**繪製水平線段**：
```python
# POC 線
poc_price = range_data['poc']['price']

fig.add_trace(go.Scatter(
    x=[start_time, end_time],
    y=[poc_price, poc_price],
    mode='lines',
    line=dict(
        color='red',
        width=2,
        dash='dash'
    ),
    name=f'POC {range_data["range_id"]}',
    showlegend=False,
    hovertemplate=f'POC: {poc_price:.2f}<extra></extra>'
))

# VAH 和 VAL 線（類似，但顏色改為綠色，線型改為點線）
```

#### 7.5 Pivot Points 標記

**使用 `go.Scatter` 的標記模式**：
```python
# 分離 Pivot High 和 Pivot Low
high_points = [p for p in vppa_json['pivot_points'] if p['type'] == 'H']
low_points = [p for p in vppa_json['pivot_points'] if p['type'] == 'L']

# 映射到時間
high_times = [map_idx_to_time(p['idx'], df) for p in high_points]
high_prices = [p['price'] for p in high_points]

low_times = [map_idx_to_time(p['idx'], df) for p in low_points]
low_prices = [p['price'] for p in low_points]

# 繪製 Pivot High
fig.add_trace(go.Scatter(
    x=high_times,
    y=high_prices,
    mode='markers',
    marker=dict(
        symbol='triangle-down',
        size=12,
        color='red'
    ),
    name='Pivot High',
    hovertemplate='Pivot High: %{y:.2f}<extra></extra>'
))

# 繪製 Pivot Low
fig.add_trace(go.Scatter(
    x=low_times,
    y=low_prices,
    mode='markers',
    marker=dict(
        symbol='triangle-up',
        size=12,
        color='green'
    ),
    name='Pivot Low',
    hovertemplate='Pivot Low: %{y:.2f}<extra></extra>'
))
```

#### 7.6 PNG 輸出

**安裝依賴**：
```bash
pip install kaleido
```

**輸出 PNG**：
```python
fig.write_image(
    'output/vppa_chart.png',
    width=1920,
    height=1080,
    scale=2  # 提高解析度（2x 超採樣）
)
```

**注意**：
- Kaleido 是 Plotly 的靜態圖片輸出引擎
- 支援 PNG、JPEG、SVG、PDF 等格式
- `scale=2` 可提高圖片清晰度（檔案會變大）

---

### 8. 效能與最佳化建議

#### 8.1 大數據量處理

**問題**：當 `pivot_ranges` 數量很多時（如 60 個），繪製所有元素可能會很慢。

**優化策略**：

**1. 批量添加 Shapes**
```python
# 不佳：逐個添加矩形
for range_data in pivot_ranges:
    fig.add_shape(...)  # 每次調用都會重新渲染

# 較佳：一次性添加所有 shapes
shapes = []
for range_data in pivot_ranges:
    shapes.append(dict(
        type='rect',
        x0=..., x1=..., y0=..., y1=...,
        fillcolor=..., line=...
    ))

fig.update_layout(shapes=shapes)  # 僅渲染一次
```

**2. 減少 Trace 數量**
```python
# 將所有 POC 線合併為一個 Trace
all_poc_x = []
all_poc_y = []

for range_data in pivot_ranges:
    start_time = map_idx_to_time(range_data['start_idx'], df)
    end_time = map_idx_to_time(range_data['end_idx'], df)
    poc_price = range_data['poc']['price']

    all_poc_x.extend([start_time, end_time, None])  # None 用於分段
    all_poc_y.extend([poc_price, poc_price, None])

fig.add_trace(go.Scatter(
    x=all_poc_x,
    y=all_poc_y,
    mode='lines',
    line=dict(color='red', width=2, dash='dash'),
    name='POC Lines',
    showlegend=True
))
```

**3. 使用 Plotly 的 `scattergl`**（適用於大量資料點）
```python
# 對於超過 10000 個資料點，使用 WebGL 渲染
fig.add_trace(go.Scattergl(  # 注意：Scattergl 而非 Scatter
    x=..., y=...,
    mode='markers'
))
```

#### 8.2 記憶體優化

**避免資料重複**：
```python
# 不佳：每次都複製整個 DataFrame
def _add_candlestick(fig, df):
    df_copy = df.copy()  # 不必要的複製
    fig.add_trace(go.Candlestick(...))

# 較佳：直接使用原始 DataFrame
def _add_candlestick(fig, df):
    fig.add_trace(go.Candlestick(
        x=df['time'].values,  # 使用 .values 避免複製索引
        open=df['open'].values,
        # ...
    ))
```

#### 8.3 互動性優化

**禁用不必要的功能**：
```python
fig.update_layout(
    dragmode='pan',  # 預設為拖曳模式（而非縮放）
    hovermode='x unified',  # 統一 X 軸 hover
    modebar_remove=[
        'zoom2d', 'pan2d', 'select2d', 'lasso2d',
        'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'
    ]  # 移除不需要的工具列按鈕
)
```

---

### 9. 測試與驗證

#### 9.1 單元測試建議

**測試檔案**：`tests/test_vppa_plot.py`

```python
import pytest
import json
import pandas as pd
from src.visualization.vppa_plot import plot_vppa_chart, map_idx_to_time

def test_map_idx_to_time():
    """測試索引到時間的映射"""
    df = pd.DataFrame({
        'time': pd.date_range('2025-01-01', periods=10, freq='1min')
    })

    assert map_idx_to_time(0, df) == pd.Timestamp('2025-01-01 00:00:00')
    assert map_idx_to_time(5, df) == pd.Timestamp('2025-01-01 00:05:00')

def test_plot_vppa_chart_basic():
    """測試基本繪圖功能"""
    # 載入測試資料
    with open('tests/fixtures/sample_vppa.json') as f:
        vppa_data = json.load(f)

    df = pd.read_csv('tests/fixtures/sample_candles.csv')
    df['time'] = pd.to_datetime(df['time'])

    # 執行繪圖
    fig = plot_vppa_chart(vppa_data, df, output_path=None)

    # 驗證
    assert len(fig.data) > 0  # 至少有一個 trace
    assert fig.layout.xaxis.title.text == '時間'
    assert fig.layout.yaxis.title.text == '價格'

def test_plot_vppa_chart_output():
    """測試 PNG 輸出"""
    # ... 類似 test_plot_vppa_chart_basic

    output_path = 'tests/output/test_chart.png'
    fig = plot_vppa_chart(vppa_data, df, output_path=output_path)

    # 驗證檔案已建立
    assert Path(output_path).exists()
```

#### 9.2 視覺化驗證

**建立參考圖表**：
1. 使用 `analyze_vppa.py` 產生 JSON
2. 使用 `plot_vppa_chart` 產生 PNG
3. 人工檢查以下項目：
   - [ ] K 線圖正確顯示
   - [ ] Pivot Range 方塊位置正確（對應 Pivot Points）
   - [ ] Volume Profile 位置在區間左側
   - [ ] Volume Profile 高度對應價格層級
   - [ ] POC 線在成交量最大的價格
   - [ ] VAH/VAL 線包含 68% 成交量
   - [ ] Pivot Points 標記位置正確
   - [ ] 圖表清晰可讀（解析度足夠）

**建立視覺化 Checklist 腳本**：
```python
# scripts/visual_verification.py
"""視覺化驗證腳本"""

def verify_vppa_chart(json_path: str, output_path: str):
    """
    產生 VPPA 圖表並輸出驗證 Checklist
    """
    # 1. 產生圖表
    # 2. 輸出統計資訊
    print("=== 視覺化驗證 Checklist ===")
    print(f"[ ] K 線數量：{len(df)}")
    print(f"[ ] Pivot Points 數量：{len(vppa_data['pivot_points'])}")
    print(f"[ ] Pivot Ranges 數量：{len(vppa_data['pivot_ranges'])}")
    print(f"[ ] 圖表已輸出到：{output_path}")
    print("\n請人工檢查以下項目：")
    print("[ ] K 線圖正確顯示")
    print("[ ] Pivot Range 方塊位置正確")
    # ... 其他項目
```

---

### 10. 實作步驟建議

#### 階段 1：基礎設施（1-2 天）

**目標**：建立基本的繪圖框架

1. ✅ 建立 `src/visualization/` 模組結構
2. ✅ 安裝 Plotly 和 Kaleido（更新 `requirements.txt`）
3. ✅ 實作 `map_idx_to_time()` 輔助函數
4. ✅ 實作 `normalize_volume_width()` 輔助函數
5. ✅ 建立基本的 `plot_vppa_chart()` 框架（空函數）

**交付物**：
- `src/visualization/__init__.py`
- `src/visualization/utils.py`（包含輔助函數）
- `src/visualization/vppa_plot.py`（框架）

#### 階段 2：K 線圖與方塊（1 天）

**目標**：繪製 K 線圖和 Pivot Range 方塊

1. ✅ 實作 `_add_candlestick()` - 添加 K 線圖
2. ✅ 實作 `_add_range_boxes()` - 添加方塊
3. ✅ 測試基本繪圖（不含 Volume Profile）

**交付物**：
- 可運行的基本圖表（K 線 + 方塊）
- 測試腳本驗證功能

#### 階段 3：Volume Profile（2-3 天）

**目標**：繪製 Volume Profile 長條圖

1. ✅ 實作成交量正規化邏輯
2. ✅ 實作 `_add_volume_profiles()` - 添加 Volume Profile
3. ✅ 實作顏色分層（Value Area 內外不同顏色）
4. ✅ 測試單個和多個 Volume Profile 顯示

**挑戰**：
- 正規化參數調整（避免遮蓋 K 線）
- 顏色對比度調整（確保可讀性）

**交付物**：
- 完整的 Volume Profile 繪圖功能

#### 階段 4：輔助線與標記（1 天）

**目標**：添加 POC、VAH、VAL 線和 Pivot Points 標記

1. ✅ 實作 `_add_poc_lines()` - 添加 POC 線
2. ✅ 實作 `_add_value_area_lines()` - 添加 VAH/VAL 線
3. ✅ 實作 `_add_pivot_markers()` - 添加 Pivot Points 標記（可選）

**交付物**：
- 完整的輔助線和標記功能

#### 階段 5：整合與優化（1-2 天）

**目標**：整合所有功能並優化效能

1. ✅ 整合所有繪圖函數到 `plot_vppa_chart()`
2. ✅ 實作 PNG 輸出功能
3. ✅ 效能優化（批量添加 shapes）
4. ✅ 圖表布局美化（標題、圖例、顏色）
5. ✅ 撰寫完整的 docstring

**交付物**：
- 完整的 `plot_vppa_chart()` 函數
- PNG 輸出功能

#### 階段 6：整合到 analyze_vppa.py（0.5 天）

**目標**：添加 `--plot` 選項

1. ✅ 修改 `analyze_vppa.py` 添加 `--plot` 參數
2. ✅ 整合繪圖功能到分析流程
3. ✅ 測試端到端流程

**交付物**：
- 更新的 `analyze_vppa.py`
- 使用範例

#### 階段 7：測試與文檔（1 天）

**目標**：完整的測試覆蓋和使用文檔

1. ✅ 撰寫單元測試（`tests/test_vppa_plot.py`）
2. ✅ 建立視覺化驗證腳本
3. ✅ 撰寫使用範例（`examples/plot_vppa_example.py`）
4. ✅ 更新 README.md

**交付物**：
- 測試套件
- 範例腳本
- 使用文檔

---

### 11. 風險與挑戰

#### 11.1 技術風險

**1. 成交量正規化參數調整**
- **風險**：Volume Profile 可能過大（遮蓋 K 線）或過小（看不清楚）
- **緩解**：提供可調整的 `max_width_bars` 參數，預設值需多次測試確定

**2. 效能問題（大量 Pivot Ranges）**
- **風險**：60+ 個區間可能導致繪圖緩慢或瀏覽器卡頓
- **緩解**：
  - 使用批量添加 shapes
  - 合併 POC/VAH/VAL 線為單一 Trace
  - 提供 `max_ranges` 參數限制顯示的區間數

**3. 時間軸映射錯誤**
- **風險**：索引映射不正確導致方塊或 Volume Profile 位置錯誤
- **緩解**：
  - 嚴格驗證 DataFrame 排序順序
  - 添加索引範圍檢查
  - 撰寫單元測試驗證映射邏輯

#### 11.2 可用性風險

**1. 圖表過於複雜**
- **風險**：過多元素導致圖表難以閱讀
- **緩解**：
  - 提供開關選項（如 `show_pivot_points`, `show_volume_profile`）
  - 使用適當的透明度和顏色
  - 支援圖例篩選（點擊隱藏特定圖層）

**2. PNG 解析度不足**
- **風險**：輸出的 PNG 圖片模糊或文字太小
- **緩解**：
  - 預設使用 `scale=2` 提高解析度
  - 提供可調整的 `width` 和 `height` 參數
  - 建議最小尺寸（如 1600x900）

#### 11.3 維護風險

**1. Plotly API 變更**
- **風險**：未來 Plotly 版本可能不相容
- **緩解**：
  - 在 `requirements.txt` 中固定版本範圍（如 `plotly>=5.18.0,<6.0.0`）
  - 撰寫單元測試確保相容性

**2. 資料格式變更**
- **風險**：`analyze_vppa.py` 的 JSON 格式變更導致繪圖失敗
- **緩解**：
  - 添加版本檢查（JSON 中包含 `version` 欄位）
  - 撰寫資料驗證函數
  - 提供清楚的錯誤訊息

---

## 輸出資料結構總結

### analyze_vppa.py 完整輸出

基於實際執行結果（2000 根 M1 K 線，GOLD 商品）：

```json
{
  "symbol": "GOLD",
  "timeframe": "M1",
  "analysis_time": "2025-12-30T15:06:11.390731+00:00",
  "parameters": {
    "count": 2000,
    "pivot_length": 20,
    "price_levels": 49,
    "value_area_pct": 0.68,
    "volume_ma_length": 14
  },
  "data_range": {
    "start_time": "2025-12-29T04:47:00+00:00",
    "end_time": "2025-12-30T15:06:00+00:00",
    "total_bars": 2000
  },
  "summary": {
    "total_pivot_points": 61,
    "total_ranges": 60,
    "avg_range_bars": 0,
    "has_developing_range": true,
    "volume_stats": {
      "latest_volume_ma": 53911.71428571428,
      "avg_volume": 61812.957,
      "total_volume": 123625914.0
    }
  },
  "pivot_points": [
    {
      "idx": 22,
      "type": "H",
      "price": 4518.78,
      "time": "2025-12-29T05:09:00+00:00"
    }
    // ... 共 61 個
  ],
  "pivot_ranges": [
    {
      "range_id": 0,
      "start_idx": 22,
      "end_idx": 41,
      "start_time": "2025-12-29T05:09:00+00:00",
      "end_time": "2025-12-29T05:28:00+00:00",
      "bar_count": 19,
      "pivot_type": "L",
      "pivot_price": 4512.13,
      "price_info": {
        "highest": 4518.78,
        "lowest": 4512.13,
        "range": 6.649999999999636,
        "step": 0.1357142857142783
      },
      "poc": {
        "level": 31,
        "price": 4516.405,
        "volume": 51295.01832033814,
        "volume_pct": 4.750278300471695
      },
      "value_area": {
        "vah": 4517.151428571428,
        "val": 4514.844285714285,
        "width": 2.307142857142935,
        "volume": 736554.9605263671,
        "pct": 68.2101529673481
      },
      "volume_info": {
        "total": 1079831.855646113,
        "avg_per_bar": 53991.59278230565
      },
      "volume_profile": {
        "levels": 49,
        "price_centers": [4512.197857142857, ...],  // 49 個價格中心
        "volumes": [50123.45, 48932.12, ...]        // 49 個成交量值
      }
    }
    // ... 共 60 個區間
  ],
  "developing_range": {
    "is_developing": true,
    "start_idx": 1980,
    "end_idx": 1999,
    // ... 結構同 pivot_ranges
  }
}
```

### K 線資料格式（來自 data_fetcher.py）

```python
df = pd.DataFrame({
    'time': pd.DatetimeIndex,  # UTC 時間戳
    'open': float64,            # 開盤價
    'high': float64,            # 最高價
    'low': float64,             # 最低價
    'close': float64,           # 收盤價
    'tick_volume': int64,       # Tick 成交量
    'spread': int32,            # 價差
    'real_volume': int64        # 真實成交量（用於 Volume Profile）
})
```

---

## 相關檔案列表

| 檔案路徑 | 用途 | 關鍵內容 |
|---------|------|---------|
| `scripts/analyze_vppa.py` | VPPA 分析主腳本 | 第 169-384 行：主分析函數 |
| `src/agent/indicators.py` | 指標計算模組 | 第 736-1109 行：`calculate_vppa()` |
| `src/core/data_fetcher.py` | 資料獲取模組 | 第 207-364 行：K 線資料獲取 |
| `src/core/sqlite_cache.py` | SQLite 快取管理 | 第 1-431 行：快取查詢與插入 |
| `src/core/mt5_config.py` | MT5 設定管理 | 第 1-192 行：連線參數管理 |
| `data/vppa_full_output.json` | 範例輸出 | 完整的 VPPA 分析結果（60 區間） |
| `requirements.txt` | 依賴套件清單 | 需新增：`plotly>=5.18.0`, `kaleido>=0.2.1` |
| `pyproject.toml` | 專案配置 | 第 1-65 行：專案元數據和工具配置 |

---

## 實作建議總結

### 必須實作的功能

1. ✅ **`plot_vppa_chart()` 主函數**
   - 接收 VPPA JSON 和 K 線 DataFrame
   - 整合所有子繪圖函數
   - 輸出 Plotly Figure 和 PNG 檔案

2. ✅ **子繪圖函數**
   - `_add_candlestick()`: K 線圖
   - `_add_range_boxes()`: Pivot Range 方塊
   - `_add_volume_profiles()`: Volume Profile 長條圖
   - `_add_poc_lines()`: POC 線
   - `_add_value_area_lines()`: VAH/VAL 線

3. ✅ **輔助函數**
   - `map_idx_to_time()`: 索引到時間映射
   - `normalize_volume_width()`: 成交量寬度正規化

4. ✅ **整合到 analyze_vppa.py**
   - 添加 `--plot` 和 `--plot-output` 參數
   - 分析完成後自動繪圖（可選）

### 可選功能

1. ⭕ **Pivot Points 標記**
   - `_add_pivot_markers()`: 在 K 線圖上標記 Pivot Points
   - 可能會使圖表過於擁擠，建議作為可選功能

2. ⭕ **互動式註解**
   - 滑鼠 hover 顯示詳細資訊（POC 成交量、Value Area 百分比等）
   - Plotly 內建支援，僅需配置 `hovertemplate`

3. ⭕ **圖表匯出選項**
   - 支援 HTML、SVG、PDF 等格式
   - Plotly 內建支援

### 技術堆疊

- **繪圖**：Plotly (plotly.graph_objects)
- **靜態輸出**：Kaleido
- **資料處理**：pandas, numpy（已在專案中）
- **日誌記錄**：loguru（已在專案中）

### 程式碼風格

- 遵循專案現有的 Google 風格 docstring
- 使用 loguru 記錄關鍵步驟
- 函數命名：snake_case
- 行長度限制：100 字元（Black 格式化）
- 完整的錯誤處理和輸入驗證

---

## 後續行動建議

1. **立即行動**：
   - 更新 `requirements.txt` 添加 Plotly 和 Kaleido
   - 建立 `src/visualization/` 模組結構

2. **短期（1 週內）**：
   - 完成階段 1-3（K 線圖、方塊、Volume Profile）
   - 進行初步視覺化測試

3. **中期（2 週內）**：
   - 完成所有繪圖功能
   - 整合到 `analyze_vppa.py`
   - 撰寫測試和文檔

4. **長期優化**：
   - 效能優化（批量處理、WebGL）
   - 使用者體驗改進（顏色主題、互動式功能）
   - 支援其他商品和時間週期

---

## 結論

本研究完整分析了 Chip Whisperer 專案中 VPPA 的資料結構和實作細節，並規劃了基於 Plotly 的視覺化解決方案。研究發現：

1. **資料來源充足**：`analyze_vppa.py` 的 JSON 輸出包含所有繪圖所需資料
2. **技術可行性高**：Plotly 支援所有需要的圖表類型（Candlestick、Bar、Scatter、Shapes）
3. **整合容易**：可無縫整合到現有的分析流程
4. **擴展性強**：模組化設計支援未來功能擴展

**關鍵技術挑戰**：
- 成交量正規化（避免遮蓋 K 線）
- 時間軸映射（索引到時間戳）
- 效能優化（大量區間時）

**建議實作順序**：
1. K 線圖 + 方塊（基礎）
2. Volume Profile（核心）
3. 輔助線和標記（增強）
4. 整合和優化（完善）

實作完成後，將為 Chip Whisperer 提供專業級的 VPPA 視覺化功能，大幅提升市場分析的直觀性和實用性。

---

**研究完成時間**：2024-12-30
**下一步行動**：建立實作計劃文檔（`thoughts/shared/plan/2024-12-30-plotly-vppa-visualization-plan.md`）並開始階段 1 實作

---

**研究者備註**：

本研究採用系統化的探索方法，從資料來源（analyze_vppa.py）、資料結構（JSON 格式）、現有實作（indicators.py）、到視覺化技術（Plotly）進行全面分析。所有發現都基於實際的程式碼和資料，並提供了具體的檔案位置和行號引用。

特別感謝專案中完整的文檔和程式碼註解，使得研究過程非常順利。VPPA 的實作品質很高，為視覺化提供了堅實的基礎。

建議在實作過程中持續進行視覺化測試，確保輸出的圖表既美觀又實用。
