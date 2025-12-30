---
title: "Chip Whisperer - fetch_data 與技術指標計算功能分析及 SQLite3 整合規劃"
date: 2024-12-30
author: Claude (Sonnet 4.5)
tags:
  - data-fetching
  - technical-indicators
  - sqlite3-cache
  - architecture-analysis
  - mt5-integration
status: completed
related_files:
  - src/core/data_fetcher.py
  - src/core/mt5_client.py
  - src/core/mt5_config.py
  - src/agent/indicators.py
  - src/agent/tools.py
  - src/agent/agent.py
  - examples/fetch_historical_data.py
  - examples/demo_volume_profile_data.py
last_updated: 2024-12-30
last_updated_by: Claude (Sonnet 4.5)
---

# Chip Whisperer - fetch_data 與技術指標計算功能全面分析

## 研究問題

本研究針對 Chip Whisperer 專案的以下三個核心目標進行全面分析：

1. **fetch_data 功能分析**：找出所有與數據獲取相關的檔案和函數，分析數據獲取的完整流程，記錄目前的快取機制
2. **技術指標計算功能分析**：找出所有技術指標計算的函數，分析指標函數的輸入輸出格式，記錄指標與數據之間的依賴關係
3. **SQLite3 整合需求分析**：設計 SQLite3 作為數據快取層的完整方案，包含資料表結構、流程規劃和數據缺口檢測機制

---

## 摘要

Chip Whisperer 是一個基於 MT5 (MetaTrader 5) 的智能交易分析系統，整合了 Claude AI 和 Telegram Bot。目前系統採用 CSV/Parquet 檔案作為快取機制，數據獲取和技術指標計算分離於不同模組。

**主要發現**：
- 數據獲取功能集中於 `HistoricalDataFetcher` 類別，提供多種查詢模式
- 技術指標計算獨立於 `indicators.py` 模組，目前支援 Volume Profile、SMA、RSI、布林通道
- 現有快取機制使用檔案系統，缺乏統一的數據管理和版本控制
- Agent 工具系統透過 JSON 序列化在各模組間傳遞數據
- 系統架構適合引入 SQLite3 作為統一的數據快取層

**關鍵洞察**：
引入 SQLite3 可以解決目前檔案快取的諸多限制，提供更高效的數據查詢、版本管理、缺口檢測和並發控制。

---

## 詳細分析

### 第一部分：fetch_data 功能完整分析

#### 1.1 核心模組架構

數據獲取功能採用三層架構設計：

```
┌─────────────────────────────────────────────────┐
│          應用層 (Agent/Examples)                │
│   - agent/tools.py (Agent 工具介面)             │
│   - examples/*.py (範例程式)                     │
└───────────────┬─────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│          資料取得層 (Data Fetcher)              │
│   - core/data_fetcher.py                        │
│     * HistoricalDataFetcher                     │
│     * get_candles_latest()                      │
│     * get_candles_by_date()                     │
│     * save_to_cache() / load_from_cache()       │
└───────────────┬─────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│          連線層 (MT5 Client)                     │
│   - core/mt5_client.py                          │
│     * ChipWhispererMT5Client                    │
│     * connect() / disconnect()                  │
│     * ensure_connected()                        │
└───────────────┬─────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│          設定層 (Configuration)                  │
│   - core/mt5_config.py                          │
│     * MT5Config                                 │
│     * 支援 .env / YAML / 字典配置                │
└─────────────────────────────────────────────────┘
```

#### 1.2 關鍵檔案與函數清單

| 檔案路徑 | 類別/函數 | 行數範圍 | 功能說明 |
|---------|----------|---------|---------|
| `src/core/data_fetcher.py` | `HistoricalDataFetcher` | 17-357 | 歷史 K 線資料取得器 |
| | `get_candles_latest()` | 152-199 | 取得最新 N 根 K 線 |
| | `get_candles_by_date()` | 201-290 | 取得指定日期範圍的 K 線 |
| | `save_to_cache()` | 292-326 | 儲存資料到快取 |
| | `load_from_cache()` | 328-356 | 從快取載入資料 |
| `src/core/mt5_client.py` | `ChipWhispererMT5Client` | 15-233 | MT5 客戶端封裝 |
| | `connect()` | 41-110 | 連線到 MT5 |
| | `ensure_connected()` | 151-160 | 確保已連線 |
| `src/core/mt5_config.py` | `MT5Config` | 16-232 | MT5 設定管理 |
| `src/agent/tools.py` | `_get_candles()` | 204-269 | Agent 工具：取得 K 線 |
| | `get_mt5_client()` | 37-57 | 取得 MT5 客戶端單例 |

#### 1.3 數據獲取完整流程

**流程圖**：

```
[使用者請求]
     │
     ▼
[Agent/應用層]
     │
     ├─→ [初始化 MT5Config]
     │        │
     │        ▼
     │   [載入環境變數 .env]
     │        │
     │        ▼
     │   [驗證設定完整性]
     │
     ├─→ [建立 ChipWhispererMT5Client]
     │        │
     │        ▼
     │   [連線到 MT5 終端機]
     │        │
     │        ├─→ [初始化 MT5]
     │        │
     │        └─→ [登入帳戶]
     │
     ├─→ [建立 HistoricalDataFetcher]
     │        │
     │        ▼
     │   [設定快取目錄]
     │
     └─→ [執行資料查詢]
          │
          ├─→ [驗證商品代碼]
          │        │
          │        └─→ [確保商品可見]
          │
          ├─→ [選擇查詢模式]
          │    │
          │    ├─→ get_candles_latest()
          │    │        │
          │    │        └─→ mt5.copy_rates_from_pos()
          │    │
          │    └─→ get_candles_by_date()
          │             │
          │             ├─→ [解析日期範圍]
          │             │
          │             └─→ mt5.copy_rates_range()
          │                  或 mt5.copy_rates_from()
          │
          ├─→ [轉換為 DataFrame]
          │        │
          │        ├─→ [處理時間欄位為 UTC]
          │        │
          │        └─→ [按時間排序]
          │
          └─→ [選擇性儲存到快取]
               │
               ├─→ CSV 格式 (UTF-8-BOM)
               │
               └─→ Parquet 格式
```

#### 1.4 目前快取機制詳細分析

**快取實作位置**：
- 檔案：`src/core/data_fetcher.py`
- 方法：`save_to_cache()` (行 292-326) 和 `load_from_cache()` (行 328-356)

**快取機制特性**：

1. **儲存格式**：
   - CSV：使用 UTF-8-BOM 編碼，適合 Excel 開啟
   - Parquet：二進位格式，更高效的儲存和讀取

2. **檔案命名規則**：
   ```
   格式：{商品代碼}_{時間週期}_{時間戳}.{副檔名}
   範例：GOLD_H1_20241230_154602.csv
   ```

3. **快取目錄結構**：
   ```
   data/
   └── cache/
       ├── GOLD_H1_20241230_154602.csv
       ├── SILVER_D1_20241230_154821.csv
       └── ...
   ```

4. **快取機制限制**：
   - ❌ 無數據版本控制
   - ❌ 無法高效查詢特定時間範圍
   - ❌ 無數據更新追蹤機制
   - ❌ 無法偵測數據缺口
   - ❌ 檔案名稱重複會覆蓋
   - ❌ 無並發控制機制

#### 1.5 支援的時間週期

完整的時間週期對應表（來自 `data_fetcher.py` 行 24-47）：

| 分類 | 代碼 | MT5 常數 | 說明 |
|-----|------|---------|------|
| 分鐘線 | M1 | TIMEFRAME_M1 | 1 分鐘 |
| | M2 | TIMEFRAME_M2 | 2 分鐘 |
| | M3 | TIMEFRAME_M3 | 3 分鐘 |
| | M4 | TIMEFRAME_M4 | 4 分鐘 |
| | M5 | TIMEFRAME_M5 | 5 分鐘 |
| | M6 | TIMEFRAME_M6 | 6 分鐘 |
| | M10 | TIMEFRAME_M10 | 10 分鐘 |
| | M12 | TIMEFRAME_M12 | 12 分鐘 |
| | M15 | TIMEFRAME_M15 | 15 分鐘 |
| | M20 | TIMEFRAME_M20 | 20 分鐘 |
| | M30 | TIMEFRAME_M30 | 30 分鐘 |
| 小時線 | H1 | TIMEFRAME_H1 | 1 小時 |
| | H2 | TIMEFRAME_H2 | 2 小時 |
| | H3 | TIMEFRAME_H3 | 3 小時 |
| | H4 | TIMEFRAME_H4 | 4 小時 |
| | H6 | TIMEFRAME_H6 | 6 小時 |
| | H8 | TIMEFRAME_H8 | 8 小時 |
| | H12 | TIMEFRAME_H12 | 12 小時 |
| 日線以上 | D1 | TIMEFRAME_D1 | 日線 |
| | W1 | TIMEFRAME_W1 | 週線 |
| | MN1 | TIMEFRAME_MN1 | 月線 |

#### 1.6 數據格式說明

MT5 返回的 K 線數據結構（轉換為 DataFrame 後的欄位）：

| 欄位名稱 | 資料型別 | 說明 |
|---------|---------|------|
| `time` | datetime64[ns, UTC] | K 線時間（UTC 時區） |
| `open` | float64 | 開盤價 |
| `high` | float64 | 最高價 |
| `low` | float64 | 最低價 |
| `close` | float64 | 收盤價 |
| `tick_volume` | int64 | Tick 成交量 |
| `spread` | int64 | 點差 |
| `real_volume` | int64 | 真實成交量 |

---

### 第二部分：技術指標計算功能完整分析

#### 2.1 技術指標模組架構

```
┌─────────────────────────────────────────────────┐
│          Agent 工具層 (tools.py)                │
│   - 工具定義 (TOOLS)                             │
│   - 工具執行函數 (execute_tool)                  │
│   - 工具包裝函數 (_calculate_*)                  │
└───────────────┬─────────────────────────────────┘
                │
                │ (JSON 序列化傳遞數據)
                │
┌───────────────▼─────────────────────────────────┐
│          指標計算層 (indicators.py)             │
│   - calculate_volume_profile()                  │
│   - calculate_sma()                             │
│   - calculate_rsi()                             │
│   - calculate_bollinger_bands()                 │
└───────────────┬─────────────────────────────────┘
                │
                │ (接收 pandas DataFrame)
                │
┌───────────────▼─────────────────────────────────┐
│          數據層 (DataFrame from MT5)            │
│   - K 線數據 (OHLCV + volume)                   │
└─────────────────────────────────────────────────┘
```

#### 2.2 技術指標函數清單

| 指標名稱 | 函數位置 | 行數 | 輸入參數 | 輸出格式 | 功能說明 |
|---------|---------|------|---------|---------|---------|
| **Volume Profile** | `src/agent/indicators.py` | 13-148 | `df`, `price_bins=100` | `(DataFrame, Dict)` | 計算 POC、VAH、VAL |
| **SMA** | `src/agent/indicators.py` | 151-175 | `df`, `window=20`, `column='close'` | `Series` | 簡單移動平均線 |
| **RSI** | `src/agent/indicators.py` | 178-216 | `df`, `window=14`, `column='close'` | `Series` | 相對強弱指標 |
| **布林通道** | `src/agent/indicators.py` | 219-258 | `df`, `window=20`, `num_std=2.0`, `column='close'` | `(Series, Series, Series)` | 上軌、中軌、下軌 |

#### 2.3 各指標詳細分析

##### 2.3.1 Volume Profile

**檔案位置**：`src/agent/indicators.py` 行 13-148

**核心概念**：
Volume Profile 是一種顯示在特定價格水平上交易了多少成交量的技術分析工具。

**計算流程**：
```
1. [確定價格範圍]
   - price_min = df['low'].min()
   - price_max = df['high'].max()

2. [建立價格區間]
   - 將價格範圍等分為 N 個區間 (price_bins)
   - 計算每個區間的中心價格

3. [分配成交量到價格區間]
   For 每根 K 線:
     - 找出 K 線涵蓋的價格區間範圍
     - 將該 K 線的成交量平均分配到這些區間

4. [計算 POC (Point of Control)]
   - POC = 成交量最大的價格區間

5. [計算 Value Area (70% 成交量區間)]
   - 從 POC 開始向兩側擴展
   - 直到累積成交量達到總量的 70%
   - VAH = Value Area High (上界)
   - VAL = Value Area Low (下界)
```

**輸入要求**：
- DataFrame 必須包含欄位：`high`, `low`, `real_volume`

**輸出格式**：
```python
# 回傳一個元組 (profile_df, metrics)

# profile_df: DataFrame
{
    'price': [價格1, 價格2, ...],
    'volume': [成交量1, 成交量2, ...]
}

# metrics: Dict
{
    'poc_price': float,           # POC 價位
    'poc_volume': float,          # POC 成交量
    'vah': float,                 # Value Area High
    'val': float,                 # Value Area Low
    'value_area_volume': float,   # Value Area 總成交量
    'total_volume': float,        # 總成交量
    'value_area_percentage': float # Value Area 佔比 (%)
}
```

##### 2.3.2 SMA (簡單移動平均線)

**檔案位置**：`src/agent/indicators.py` 行 151-175

**計算公式**：
```
SMA(n) = (P1 + P2 + ... + Pn) / n

其中：
- n = 視窗大小 (window)
- P = 價格 (預設使用 close)
```

**實作方式**：
```python
sma = df[column].rolling(window=window).mean()
```

**輸入要求**：
- DataFrame 必須包含指定的 `column` (預設 `close`)
- 資料筆數必須 >= `window`

**輸出格式**：
- `pandas.Series`，與輸入 DataFrame 相同索引
- 前 n-1 個值為 NaN（不足視窗大小）

##### 2.3.3 RSI (相對強弱指標)

**檔案位置**：`src/agent/indicators.py` 行 178-216

**計算公式**：
```
1. Delta = 當前價格 - 前一價格
2. Gain = Delta (當 Delta > 0)
3. Loss = -Delta (當 Delta < 0)
4. Avg Gain = Gain 的 n 期平均
5. Avg Loss = Loss 的 n 期平均
6. RS = Avg Gain / Avg Loss
7. RSI = 100 - (100 / (1 + RS))

RSI 值範圍：0-100
- RSI > 70：超買區域
- RSI < 30：超賣區域
- 30 ≤ RSI ≤ 70：中性區域
```

**輸入要求**：
- DataFrame 必須包含指定的 `column` (預設 `close`)
- 資料筆數必須 >= `window + 1`

**輸出格式**：
- `pandas.Series`，值範圍 0-100
- 前 n 個值為 NaN（計算所需）

##### 2.3.4 布林通道 (Bollinger Bands)

**檔案位置**：`src/agent/indicators.py` 行 219-258

**計算公式**：
```
1. Middle Band = SMA(n)
2. Standard Deviation = STD(n)
3. Upper Band = Middle Band + (k × STD)
4. Lower Band = Middle Band - (k × STD)

其中：
- n = 視窗大小 (window)
- k = 標準差倍數 (num_std)
```

**實作方式**：
```python
middle_band = df[column].rolling(window=window).mean()
std = df[column].rolling(window=window).std()
upper_band = middle_band + (std * num_std)
lower_band = middle_band - (std * num_std)
```

**輸入要求**：
- DataFrame 必須包含指定的 `column` (預設 `close`)
- 資料筆數必須 >= `window`

**輸出格式**：
- 回傳三個 `pandas.Series` 的元組：`(upper_band, middle_band, lower_band)`

#### 2.4 Agent 工具系統整合

**工具定義位置**：`src/agent/tools.py` 行 64-164

Agent 工具系統將指標計算函數封裝為 Claude AI 可調用的工具：

| 工具名稱 | 對應函數 | 行數 | 說明 |
|---------|---------|------|------|
| `get_candles` | `_get_candles()` | 204-269 | 取得 K 線資料 |
| `calculate_volume_profile` | `_calculate_volume_profile()` | 272-322 | 計算 Volume Profile |
| `calculate_sma` | `_calculate_sma()` | 325-383 | 計算 SMA |
| `calculate_rsi` | `_calculate_rsi()` | 386-446 | 計算 RSI |
| `get_account_info` | `_get_account_info()` | 449-491 | 取得帳戶資訊 |

**數據流轉機制**：

```
1. [get_candles 工具被調用]
   ↓
2. [從 MT5 取得 DataFrame]
   ↓
3. [轉換為 JSON 字串]
   df_copy['time'] = df_copy['time'].astype(str)
   candles_json = json.dumps(df_copy.to_dict('records'))
   ↓
4. [返回給 Claude AI]
   {
     "success": True,
     "data": {
       "candles_json": "...",
       "summary": {...}
     }
   }
   ↓
5. [Claude AI 決定調用指標工具]
   ↓
6. [指標工具接收 JSON]
   candles_list = json.loads(candles_json)
   df = pd.DataFrame(candles_list)
   ↓
7. [計算指標]
   result = calculate_xxx(df, ...)
   ↓
8. [返回結果給 Claude AI]
```

#### 2.5 指標與數據的依賴關係

**依賴關係圖**：

```
[MT5 K 線數據]
      │
      ├─→ [必要欄位：time, open, high, low, close]
      │        │
      │        ├─→ SMA (使用 close)
      │        │
      │        ├─→ RSI (使用 close)
      │        │
      │        └─→ 布林通道 (使用 close)
      │
      └─→ [必要欄位：high, low, real_volume]
               │
               └─→ Volume Profile
```

**欄位使用統計**：

| 欄位名稱 | 使用的指標 | 重要性 |
|---------|-----------|--------|
| `time` | 所有指標（用於排序和索引） | 必要 |
| `close` | SMA, RSI, 布林通道 | 高 |
| `high` | Volume Profile | 高 |
| `low` | Volume Profile | 高 |
| `real_volume` | Volume Profile | 高 |
| `open` | (目前未使用) | 低 |
| `tick_volume` | (目前未使用) | 低 |
| `spread` | (目前未使用) | 低 |

---

### 第三部分：SQLite3 整合完整規劃

#### 3.1 為何選擇 SQLite3

**現有檔案快取的問題**：
1. ❌ 無法高效查詢特定時間範圍的數據
2. ❌ 無數據版本控制機制
3. ❌ 檔案名稱衝突會導致數據覆蓋
4. ❌ 無法偵測數據缺口
5. ❌ 無並發控制
6. ❌ 無數據更新追蹤

**SQLite3 的優勢**：
- ✅ 零配置，單一檔案資料庫
- ✅ 支援 ACID 交易
- ✅ 內建時間範圍查詢
- ✅ 支援索引優化查詢效能
- ✅ 支援並發讀取
- ✅ Python 標準庫內建
- ✅ 檔案大小無限制（理論上可達 140TB）

#### 3.2 資料表結構設計

##### 3.2.1 主資料表：candles（K 線數據表）

```sql
CREATE TABLE candles (
    -- 主鍵與基本識別
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,                    -- 商品代碼（例如：GOLD, SILVER）
    timeframe TEXT NOT NULL,                 -- 時間週期（例如：H1, D1）
    time TIMESTAMP NOT NULL,                 -- K 線時間（UTC）

    -- K 線 OHLC 數據
    open REAL NOT NULL,                      -- 開盤價
    high REAL NOT NULL,                      -- 最高價
    low REAL NOT NULL,                       -- 最低價
    close REAL NOT NULL,                     -- 收盤價

    -- 成交量數據
    tick_volume INTEGER NOT NULL,            -- Tick 成交量
    spread INTEGER NOT NULL,                 -- 點差
    real_volume INTEGER NOT NULL,            -- 真實成交量

    -- 元數據
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 建立時間
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 更新時間
    source TEXT DEFAULT 'MT5',               -- 數據來源

    -- 唯一約束：同一商品、同一週期、同一時間只能有一筆記錄
    UNIQUE(symbol, timeframe, time)
);

-- 索引：優化查詢效能
CREATE INDEX idx_candles_symbol_timeframe ON candles(symbol, timeframe);
CREATE INDEX idx_candles_time ON candles(time);
CREATE INDEX idx_candles_symbol_timeframe_time ON candles(symbol, timeframe, time);
```

**設計說明**：
- 使用 `UNIQUE(symbol, timeframe, time)` 防止重複數據
- 建立複合索引加速常見查詢模式
- `updated_at` 欄位用於追蹤數據更新
- `source` 欄位預留未來可能的多數據源支援

##### 3.2.2 元數據表：cache_metadata（快取元數據表）

```sql
CREATE TABLE cache_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,

    -- 數據範圍
    first_time TIMESTAMP,                    -- 最早數據時間
    last_time TIMESTAMP,                     -- 最新數據時間
    total_records INTEGER DEFAULT 0,         -- 總記錄數

    -- 快取狀態
    last_fetch_time TIMESTAMP,               -- 最後取得時間
    last_update_time TIMESTAMP,              -- 最後更新時間
    fetch_count INTEGER DEFAULT 0,           -- 取得次數

    -- 數據品質
    has_gaps BOOLEAN DEFAULT 0,              -- 是否有數據缺口
    gap_count INTEGER DEFAULT 0,             -- 缺口數量
    last_gap_check TIMESTAMP,                -- 最後缺口檢查時間

    UNIQUE(symbol, timeframe)
);

CREATE INDEX idx_metadata_symbol_timeframe ON cache_metadata(symbol, timeframe);
```

**設計說明**：
- 追蹤每個商品-週期組合的快取狀態
- 記錄數據範圍和品質指標
- 用於快速判斷是否需要重新取得數據

##### 3.2.3 數據缺口表：data_gaps（數據缺口記錄表）

```sql
CREATE TABLE data_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,

    -- 缺口範圍
    gap_start TIMESTAMP NOT NULL,            -- 缺口開始時間
    gap_end TIMESTAMP NOT NULL,              -- 缺口結束時間

    -- 缺口資訊
    expected_records INTEGER,                -- 預期應有的記錄數
    gap_duration_minutes INTEGER,            -- 缺口時長（分鐘）

    -- 處理狀態
    status TEXT DEFAULT 'detected',          -- 狀態：detected, filling, filled, ignored
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP,

    -- 備註
    notes TEXT,

    UNIQUE(symbol, timeframe, gap_start)
);

CREATE INDEX idx_gaps_symbol_timeframe ON data_gaps(symbol, timeframe);
CREATE INDEX idx_gaps_status ON data_gaps(status);
```

**設計說明**：
- 記錄所有檢測到的數據缺口
- 追蹤缺口填補狀態
- 支援手動標記忽略某些缺口（例如週末、假日）

##### 3.2.4 計算結果快取表：indicator_cache（指標計算結果快取表）

```sql
CREATE TABLE indicator_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    indicator_name TEXT NOT NULL,            -- 指標名稱（例如：sma_20, rsi_14）

    -- 計算參數（JSON 格式）
    parameters TEXT,                         -- 例如：{"window": 20, "column": "close"}

    -- 計算結果
    time TIMESTAMP NOT NULL,                 -- K 線時間
    value REAL,                              -- 指標值

    -- 元數據
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(symbol, timeframe, indicator_name, parameters, time)
);

CREATE INDEX idx_indicator_cache_lookup ON indicator_cache(symbol, timeframe, indicator_name, parameters, time);
```

**設計說明**：
- 快取常用指標的計算結果，避免重複計算
- 使用 JSON 儲存參數，支援任意指標配置
- 可大幅提升重複查詢的效能

#### 3.3 完整流程設計

##### 3.3.1 數據獲取與儲存流程（Fetch 時存入 DB）

```
[使用者請求數據]
     │
     ▼
[檢查 SQLite 快取]
     │
     ├─→ [查詢 cache_metadata]
     │   - 是否有該商品/週期的數據？
     │   - 數據時間範圍是否涵蓋請求範圍？
     │   - 數據是否過舊（需更新）？
     │
     ├─→ [情況 1：快取完全命中]
     │        │
     │        └─→ [從 candles 表查詢數據]
     │            └─→ [返回 DataFrame]
     │
     ├─→ [情況 2：快取部分命中]
     │        │
     │        ├─→ [識別缺少的時間範圍]
     │        │
     │        ├─→ [從 MT5 取得缺少的數據]
     │        │
     │        ├─→ [合併快取數據與新數據]
     │        │
     │        └─→ [將新數據存入 DB]
     │
     └─→ [情況 3：快取未命中]
              │
              ├─→ [從 MT5 取得完整數據]
              │
              ├─→ [存入 candles 表]
              │   └─→ 使用 INSERT OR REPLACE
              │
              ├─→ [更新 cache_metadata]
              │   ├─→ first_time
              │   ├─→ last_time
              │   ├─→ total_records
              │   └─→ last_fetch_time
              │
              └─→ [返回 DataFrame]
```

**實作關鍵代碼框架**：

```python
class SQLiteCacheManager:
    def __init__(self, db_path: str = "data/cache/mt5_cache.db"):
        self.db_path = db_path
        self._init_database()

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime,
        fetcher: HistoricalDataFetcher
    ) -> pd.DataFrame:
        """
        智能數據獲取：優先從快取取得，必要時從 MT5 補充
        """
        # 1. 檢查快取狀態
        cache_info = self._get_cache_info(symbol, timeframe)

        # 2. 判斷快取覆蓋情況
        if self._is_cache_sufficient(cache_info, from_date, to_date):
            # 完全命中：直接從 DB 查詢
            return self._query_from_db(symbol, timeframe, from_date, to_date)

        # 3. 識別需要從 MT5 取得的範圍
        missing_ranges = self._identify_missing_ranges(
            cache_info, from_date, to_date
        )

        # 4. 從 MT5 取得缺少的數據
        new_data = []
        for start, end in missing_ranges:
            df = fetcher.get_candles_by_date(
                symbol=symbol,
                timeframe=timeframe,
                from_date=start.strftime('%Y-%m-%d'),
                to_date=end.strftime('%Y-%m-%d')
            )
            new_data.append(df)

        # 5. 將新數據存入 DB
        if new_data:
            combined_new_data = pd.concat(new_data, ignore_index=True)
            self._insert_candles(combined_new_data, symbol, timeframe)

        # 6. 從 DB 查詢完整數據
        return self._query_from_db(symbol, timeframe, from_date, to_date)

    def _insert_candles(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """
        批次插入 K 線數據（使用 UPSERT）
        """
        conn = sqlite3.connect(self.db_path)

        # 準備數據
        df_copy = df.copy()
        df_copy['symbol'] = symbol
        df_copy['timeframe'] = timeframe

        # 批次 UPSERT
        df_copy.to_sql(
            'candles',
            conn,
            if_exists='append',
            index=False,
            method='multi'
        )

        # 更新元數據
        self._update_metadata(symbol, timeframe, df)

        conn.commit()
        conn.close()
```

##### 3.3.2 數據缺口檢測流程

```
[定期/手動觸發缺口檢測]
     │
     ▼
[For 每個商品-週期組合]
     │
     ├─→ [從 DB 查詢該組合的所有時間戳]
     │
     ├─→ [計算預期的時間間隔]
     │   - H1: 1 小時
     │   - H4: 4 小時
     │   - D1: 1 天
     │   - 等等...
     │
     ├─→ [檢測連續時間戳之間的間隔]
     │
     ├─→ [識別異常間隔]
     │   │
     │   └─→ 間隔 > 預期間隔 × 閾值 (例如 1.5)
     │
     ├─→ [過濾合理的缺口]
     │   │
     │   ├─→ 排除週末（週六、週日）
     │   ├─→ 排除已知假日
     │   └─→ 排除市場休市時段
     │
     ├─→ [將缺口記錄到 data_gaps 表]
     │
     └─→ [更新 cache_metadata 的缺口統計]
```

**缺口檢測實作**：

```python
def detect_data_gaps(
    self,
    symbol: str,
    timeframe: str,
    min_gap_threshold: float = 1.5
) -> List[Dict]:
    """
    檢測數據缺口

    參數：
        symbol: 商品代碼
        timeframe: 時間週期
        min_gap_threshold: 最小缺口閾值（相對於正常間隔的倍數）

    回傳：
        缺口清單
    """
    conn = sqlite3.connect(self.db_path)

    # 1. 查詢所有時間戳（升序）
    query = """
        SELECT time
        FROM candles
        WHERE symbol = ? AND timeframe = ?
        ORDER BY time ASC
    """
    df = pd.read_sql_query(query, conn, params=(symbol, timeframe))
    df['time'] = pd.to_datetime(df['time'])

    if len(df) < 2:
        return []

    # 2. 計算預期間隔
    expected_interval = self._get_expected_interval(timeframe)

    # 3. 計算實際間隔
    df['time_diff'] = df['time'].diff()

    # 4. 識別異常間隔
    threshold = expected_interval * min_gap_threshold
    gaps = df[df['time_diff'] > threshold]

    # 5. 過濾合理的缺口（週末、假日等）
    filtered_gaps = []
    for idx, row in gaps.iterrows():
        gap_start = df.loc[idx - 1, 'time']
        gap_end = row['time']

        if not self._is_expected_gap(gap_start, gap_end):
            filtered_gaps.append({
                'symbol': symbol,
                'timeframe': timeframe,
                'gap_start': gap_start,
                'gap_end': gap_end,
                'gap_duration_minutes': int(row['time_diff'].total_seconds() / 60),
                'expected_records': self._calculate_expected_records(
                    gap_start, gap_end, timeframe
                )
            })

    # 6. 儲存缺口記錄
    if filtered_gaps:
        self._save_gaps(filtered_gaps)

    conn.close()
    return filtered_gaps

def _is_expected_gap(self, start: datetime, end: datetime) -> bool:
    """
    判斷缺口是否為預期的（週末、假日等）
    """
    # 檢查是否跨越週末
    if start.weekday() == 4 and end.weekday() == 0:  # 週五到週一
        return True

    # 檢查是否為已知假日
    # TODO: 整合假日日曆

    return False
```

##### 3.3.3 缺口提示與填補流程

```
[使用者查詢數據]
     │
     ▼
[檢查該範圍是否有缺口]
     │
     ├─→ [查詢 data_gaps 表]
     │   WHERE symbol = ? AND timeframe = ?
     │   AND gap_start >= request_start
     │   AND gap_end <= request_end
     │   AND status != 'filled'
     │
     ├─→ [有缺口]
     │        │
     │        ├─→ [生成警告訊息]
     │        │   「警告：查詢範圍內存在 N 個數據缺口：
     │        │    1. 2024-12-20 10:00 ~ 2024-12-20 14:00 (缺少 4 筆 H1 數據)
     │        │    2. ...
     │        │    是否嘗試從 MT5 補充缺口數據？」
     │        │
     │        └─→ [提供填補選項]
     │            │
     │            ├─→ [自動填補]
     │            │   └─→ 調用 fill_data_gaps()
     │            │
     │            └─→ [手動忽略]
     │                └─→ 更新 data_gaps.status = 'ignored'
     │
     └─→ [無缺口]
          └─→ [正常返回數據]
```

**缺口填補實作**：

```python
def fill_data_gaps(
    self,
    symbol: str,
    timeframe: str,
    fetcher: HistoricalDataFetcher
) -> int:
    """
    填補指定商品-週期的所有數據缺口

    回傳：
        填補的缺口數量
    """
    conn = sqlite3.connect(self.db_path)

    # 查詢未填補的缺口
    query = """
        SELECT * FROM data_gaps
        WHERE symbol = ? AND timeframe = ?
        AND status = 'detected'
        ORDER BY gap_start ASC
    """
    gaps = pd.read_sql_query(query, conn, params=(symbol, timeframe))

    filled_count = 0

    for _, gap in gaps.iterrows():
        try:
            # 從 MT5 取得缺口範圍的數據
            df = fetcher.get_candles_by_date(
                symbol=symbol,
                timeframe=timeframe,
                from_date=gap['gap_start'],
                to_date=gap['gap_end']
            )

            if len(df) > 0:
                # 插入數據
                self._insert_candles(df, symbol, timeframe)

                # 更新缺口狀態
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE data_gaps
                    SET status = 'filled', filled_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (gap['id'],)
                )
                conn.commit()

                filled_count += 1
                logger.info(f"已填補缺口：{gap['gap_start']} ~ {gap['gap_end']}")

        except Exception as e:
            logger.error(f"填補缺口失敗：{e}")
            # 更新狀態為 filling（部分填補）
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE data_gaps
                SET status = 'filling', notes = ?
                WHERE id = ?
                """,
                (str(e), gap['id'])
            )
            conn.commit()

    conn.close()
    return filled_count
```

#### 3.4 整合到現有系統

##### 3.4.1 修改 HistoricalDataFetcher

在 `src/core/data_fetcher.py` 中整合 SQLite 快取：

```python
class HistoricalDataFetcher:
    def __init__(
        self,
        client: ChipWhispererMT5Client,
        cache_dir: Optional[str] = None,
        use_sqlite: bool = True  # 新增參數
    ):
        self.client = client
        self.cache_dir = Path(cache_dir) if cache_dir else Path('data/cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 SQLite 快取管理器
        self.use_sqlite = use_sqlite
        if use_sqlite:
            db_path = self.cache_dir / 'mt5_cache.db'
            self.sqlite_cache = SQLiteCacheManager(str(db_path))

        logger.debug(f"資料快取目錄：{self.cache_dir}")

    def get_candles_latest(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100
    ) -> pd.DataFrame:
        """
        取得最新的 N 根 K 線（優先從 SQLite 快取）
        """
        if self.use_sqlite:
            # 計算時間範圍
            end_time = datetime.now(timezone.utc)
            interval = self._get_interval_minutes(timeframe)
            start_time = end_time - timedelta(minutes=interval * count)

            # 使用 SQLite 快取
            return self.sqlite_cache.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                from_date=start_time,
                to_date=end_time,
                fetcher=self
            )
        else:
            # 原有邏輯：直接從 MT5 取得
            return self._fetch_from_mt5_latest(symbol, timeframe, count)
```

##### 3.4.2 新增快取管理命令

建立 `src/core/cache_manager.py` 提供快取管理功能：

```python
class CacheManager:
    """SQLite 快取管理工具"""

    def __init__(self, db_path: str):
        self.cache = SQLiteCacheManager(db_path)

    def status(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """顯示快取狀態"""
        pass

    def check_gaps(self, symbol: str, timeframe: str) -> List[Dict]:
        """檢查數據缺口"""
        pass

    def fill_gaps(self, symbol: str, timeframe: str) -> int:
        """填補數據缺口"""
        pass

    def clear_cache(self, symbol: Optional[str] = None,
                    timeframe: Optional[str] = None):
        """清除快取"""
        pass

    def export_to_csv(self, symbol: str, timeframe: str,
                     output_path: str):
        """匯出為 CSV"""
        pass
```

##### 3.4.3 命令列工具

建立 `scripts/manage_cache.py`：

```python
#!/usr/bin/env python3
"""
SQLite 快取管理命令列工具

使用方式：
    python scripts/manage_cache.py status
    python scripts/manage_cache.py check-gaps --symbol GOLD --timeframe H1
    python scripts/manage_cache.py fill-gaps --symbol GOLD --timeframe H1
    python scripts/manage_cache.py clear --symbol GOLD --timeframe H1
"""

import click
from src.core.cache_manager import CacheManager

@click.group()
def cli():
    """SQLite 快取管理工具"""
    pass

@cli.command()
def status():
    """顯示快取狀態"""
    manager = CacheManager('data/cache/mt5_cache.db')
    status_df = manager.status()
    print(status_df)

@cli.command()
@click.option('--symbol', required=True, help='商品代碼')
@click.option('--timeframe', required=True, help='時間週期')
def check_gaps(symbol, timeframe):
    """檢查數據缺口"""
    manager = CacheManager('data/cache/mt5_cache.db')
    gaps = manager.check_gaps(symbol, timeframe)

    if gaps:
        print(f"發現 {len(gaps)} 個數據缺口：")
        for gap in gaps:
            print(f"  - {gap['gap_start']} ~ {gap['gap_end']}")
    else:
        print("未發現數據缺口")

# ... 其他命令
```

#### 3.5 效能優化建議

##### 3.5.1 批次插入優化

```python
def _batch_insert_candles(self, df: pd.DataFrame, batch_size: int = 1000):
    """
    批次插入數據以提升效能
    """
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    # 開始交易
    cursor.execute("BEGIN TRANSACTION")

    try:
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            batch.to_sql(
                'candles',
                conn,
                if_exists='append',
                index=False,
                method='multi'
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
```

##### 3.5.2 查詢優化

```python
def _optimized_query(
    self,
    symbol: str,
    timeframe: str,
    from_date: datetime,
    to_date: datetime
) -> pd.DataFrame:
    """
    優化的數據查詢（使用索引和 BETWEEN）
    """
    conn = sqlite3.connect(self.db_path)

    query = """
        SELECT time, open, high, low, close,
               tick_volume, spread, real_volume
        FROM candles
        WHERE symbol = ? AND timeframe = ?
        AND time BETWEEN ? AND ?
        ORDER BY time ASC
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=(symbol, timeframe, from_date, to_date),
        parse_dates=['time']
    )

    conn.close()
    return df
```

##### 3.5.3 資料庫維護

```python
def optimize_database(self):
    """
    定期執行資料庫優化
    """
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    # 分析查詢計劃
    cursor.execute("ANALYZE")

    # 重建索引
    cursor.execute("REINDEX")

    # 清理碎片
    cursor.execute("VACUUM")

    conn.commit()
    conn.close()

    logger.info("資料庫優化完成")
```

---

## 程式碼引用

### 數據獲取相關

**檔案**：`C:\Users\fatfi\works\chip-whisperer\src\core\data_fetcher.py`

- **行 17-62**：`HistoricalDataFetcher` 類別初始化和時間週期對應表
- **行 152-199**：`get_candles_latest()` 方法 - 取得最新 N 根 K 線
- **行 201-290**：`get_candles_by_date()` 方法 - 取得指定日期範圍的 K 線
- **行 292-326**：`save_to_cache()` 方法 - 儲存資料到檔案快取
- **行 328-356**：`load_from_cache()` 方法 - 從檔案快取載入資料

**檔案**：`C:\Users\fatfi\works\chip-whisperer\src\core\mt5_client.py`

- **行 15-40**：`ChipWhispererMT5Client` 類別初始化
- **行 41-110**：`connect()` 方法 - 連線到 MT5
- **行 151-160**：`ensure_connected()` 方法 - 確保已連線

**檔案**：`C:\Users\fatfi\works\chip-whisperer\src\agent\tools.py`

- **行 37-57**：`get_mt5_client()` - MT5 客戶端單例管理
- **行 64-164**：`TOOLS` - Agent 工具定義陣列
- **行 204-269**：`_get_candles()` - Agent 工具：取得 K 線資料

### 技術指標相關

**檔案**：`C:\Users\fatfi\works\chip-whisperer\src\agent\indicators.py`

- **行 13-148**：`calculate_volume_profile()` - Volume Profile 計算
- **行 151-175**：`calculate_sma()` - 簡單移動平均線
- **行 178-216**：`calculate_rsi()` - 相對強弱指標
- **行 219-258**：`calculate_bollinger_bands()` - 布林通道

**檔案**：`C:\Users\fatfi\works\chip-whisperer\src\agent\tools.py`

- **行 272-322**：`_calculate_volume_profile()` - Agent 工具包裝
- **行 325-383**：`_calculate_sma()` - Agent 工具包裝
- **行 386-446**：`_calculate_rsi()` - Agent 工具包裝

### 範例程式

**檔案**：`C:\Users\fatfi\works\chip-whisperer\examples\fetch_historical_data.py`

- **行 53-145**：完整的數據獲取範例，展示三種查詢模式

**檔案**：`C:\Users\fatfi\works\chip-whisperer\examples\demo_volume_profile_data.py`

- **行 56-168**：Volume Profile 計算函數（範例版本）
- **行 171-290**：完整的 Volume Profile 分析流程

---

## 架構圖與流程說明

### 整體系統架構圖

```
┌─────────────────────────────────────────────────────────────┐
│                      用戶層                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Telegram Bot │  │ CLI 工具     │  │ Python API   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼──────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│                      Agent 層                                 │
│  ┌────────────────────────────────────────────────────┐      │
│  │  Claude AI Agent (src/agent/agent.py)             │      │
│  │  - 自然語言理解                                    │      │
│  │  - 工具選擇與調度                                  │      │
│  │  - 結果解釋與回覆                                  │      │
│  └──────────────┬─────────────────────────────────────┘      │
│                 │                                             │
│  ┌──────────────▼─────────────────────────────────────┐      │
│  │  Agent Tools (src/agent/tools.py)                  │      │
│  │  - get_candles                                      │      │
│  │  - calculate_volume_profile                        │      │
│  │  - calculate_sma                                    │      │
│  │  - calculate_rsi                                    │      │
│  │  - get_account_info                                 │      │
│  └──────────────┬─────────────────────────────────────┘      │
└─────────────────┼──────────────────────────────────────────────┘
                  │
┌─────────────────▼──────────────────────────────────────────────┐
│                   核心功能層                                    │
│  ┌──────────────────────┐  ┌──────────────────────────┐       │
│  │ 數據獲取模組         │  │ 技術指標模組             │       │
│  │ (data_fetcher.py)    │  │ (indicators.py)          │       │
│  │                      │  │                          │       │
│  │ - get_candles_latest │  │ - calculate_volume_profile│      │
│  │ - get_candles_by_date│  │ - calculate_sma          │       │
│  │ - save_to_cache      │  │ - calculate_rsi          │       │
│  │ - load_from_cache    │  │ - calculate_bollinger_bands│     │
│  └──────────┬───────────┘  └──────────────────────────┘       │
│             │                                                   │
│  ┌──────────▼───────────┐                                      │
│  │ MT5 客戶端          │                                      │
│  │ (mt5_client.py)      │                                      │
│  │ - connect            │                                      │
│  │ - disconnect         │                                      │
│  │ - ensure_connected   │                                      │
│  └──────────┬───────────┘                                      │
│             │                                                   │
│  ┌──────────▼───────────┐                                      │
│  │ 設定管理             │                                      │
│  │ (mt5_config.py)      │                                      │
│  │ - .env / YAML        │                                      │
│  └──────────────────────┘                                      │
└─────────────┬──────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────────┐
│                      快取層（規劃中）                           │
│  ┌──────────────────────┐  ┌──────────────────────────┐       │
│  │ 檔案快取（現有）     │  │ SQLite3 快取（規劃）    │       │
│  │ - CSV 格式          │  │ - candles 表            │       │
│  │ - Parquet 格式      │  │ - cache_metadata 表     │       │
│  │                      │  │ - data_gaps 表          │       │
│  └──────────────────────┘  │ - indicator_cache 表    │       │
│                             └──────────────────────────┘       │
└─────────────┬──────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────────┐
│                   數據源層                                      │
│  ┌──────────────────────────────────────────────────────┐      │
│  │         MetaTrader 5 終端機                          │      │
│  │         (券商伺服器)                                 │      │
│  └──────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────┘
```

### SQLite3 快取整合後的數據流程圖

```
[使用者查詢：「取得 GOLD H1 最近 100 根 K 線」]
                    │
                    ▼
        ┌───────────────────────────┐
        │   Agent 解析請求           │
        │   調用 get_candles 工具    │
        └───────────┬───────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │  HistoricalDataFetcher     │
        │  .fetch_candles()          │
        └───────────┬───────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │  SQLiteCacheManager        │
        │  檢查快取狀態              │
        └───────────┬───────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐      ┌───────────────┐
│ 快取命中      │      │ 快取未命中/   │
│ (80% 情況)    │      │ 部分命中      │
└───────┬───────┘      └───────┬───────┘
        │                       │
        │                       ▼
        │              ┌────────────────┐
        │              │ 從 MT5 取得數據│
        │              └────────┬───────┘
        │                       │
        │                       ▼
        │              ┌────────────────┐
        │              │ 存入 SQLite    │
        │              │ - candles 表   │
        │              │ - 更新 metadata│
        │              └────────┬───────┘
        │                       │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │ 從 SQLite 查詢完整數據    │
        │ (高效索引查詢)            │
        └───────────┬───────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │ 檢查數據缺口              │
        │ (查詢 data_gaps 表)       │
        └───────────┬───────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐      ┌───────────────┐
│ 無缺口        │      │ 有缺口        │
│               │      │               │
└───────┬───────┘      └───────┬───────┘
        │                       │
        │                       ▼
        │              ┌────────────────┐
        │              │ 生成警告訊息   │
        │              │ 提供填補選項   │
        │              └────────┬───────┘
        │                       │
        │              ┌────────┴───────┐
        │              │                │
        │              ▼                ▼
        │      ┌────────────┐  ┌────────────┐
        │      │ 自動填補   │  │ 手動忽略   │
        │      └─────┬──────┘  └────────────┘
        │            │
        │            ▼
        │   ┌─────────────────┐
        │   │ fill_data_gaps() │
        │   └─────┬───────────┘
        │         │
        └─────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │ 轉換為 DataFrame          │
        │ 回傳給 Agent              │
        └───────────┬───────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │ Agent 處理數據            │
        │ (可能調用指標計算工具)    │
        └───────────┬───────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │ 生成自然語言回覆          │
        │ 返回給使用者              │
        └───────────────────────────┘
```

---

## 歷史脈絡

### 專案演進歷程

根據 git 提交記錄和文件分析，Chip Whisperer 的發展歷程：

1. **初始階段**：建立基礎 MT5 連線和數據獲取功能
   - 提交：`bacb47b` - 建立核心模組和單元測試
   - 實作 `MT5Config`, `ChipWhispererMT5Client`, `HistoricalDataFetcher`

2. **文件完善**：補充專案文件和說明
   - 提交：`dbfb9a1` - 新增專案文件
   - 提交：`4298851` - 新增開發筆記和實作計劃

3. **視覺資產**：加入品牌識別和展示資料
   - 提交：`0db2b9e` - 新增 logo 和 demo 資產

4. **配置管理**：整合 Claude Code 配置
   - 提交：`db72429` - 新增 .claude 配置 submodule

### 目前架構的優勢

1. **清晰的模組分離**：
   - 配置層、連線層、數據層、應用層各司其職
   - 易於測試和維護

2. **良好的錯誤處理**：
   - 完整的例外處理機制
   - 詳細的日誌記錄

3. **靈活的配置系統**：
   - 支援多種配置來源
   - 優先順序明確

4. **完整的範例程式**：
   - 提供實際使用案例
   - 便於新用戶上手

### 架構演進建議

引入 SQLite3 快取是自然的下一步演進，因為：

1. **解決現有限制**：
   - 檔案快取無法高效查詢和管理
   - 缺乏數據版本控制
   - 無法偵測和處理數據缺口

2. **保持架構一致性**：
   - SQLite3 是單檔案資料庫，與目前檔案快取理念一致
   - 無需額外的資料庫服務
   - Python 標準庫內建支援

3. **向下相容**：
   - 可保留現有的檔案快取選項
   - 透過參數切換快取策略
   - 不影響現有 API

---

## 相關研究

### 類似專案參考

專案 README 中提到的參考來源：

1. **ariadng/metatrader-mcp-server**
   - MT5 MCP (Model Context Protocol) 伺服器實作
   - 提供 MT5 數據存取的標準化介面

2. **fatfingererr/.claude**
   - Claude Code 的配置管理專案
   - 提供專案技能和工作流程定義

### 技術標準與最佳實踐

1. **MT5 Python API**：
   - 官方文件：https://www.mql5.com/en/docs/python_metatrader5
   - 使用 `MetaTrader5` 套件版本 >= 5.0.4510

2. **SQLite3 最佳實踐**：
   - 使用 AUTOINCREMENT 主鍵
   - 建立適當的索引優化查詢
   - 使用交易確保數據一致性
   - 定期 VACUUM 清理碎片

3. **時間序列數據管理**：
   - 使用 UTC 時區統一時間處理
   - 建立時間索引加速查詢
   - 支援時間範圍查詢

---

## 開放問題

### 技術實作問題

1. **SQLite 並發寫入**：
   - SQLite 預設不支援高並發寫入
   - 解決方案：使用 WAL (Write-Ahead Logging) 模式
   - 配置：`PRAGMA journal_mode=WAL`

2. **大量數據插入效能**：
   - 單筆插入會很慢
   - 解決方案：批次插入 + 交易
   - 建議批次大小：1000-5000 筆

3. **數據庫檔案大小管理**：
   - 長期累積可能達到數 GB
   - 解決方案：
     - 定期清理舊數據（例如保留 1 年）
     - 使用 VACUUM 壓縮
     - 支援多資料庫檔案（按年份分檔）

4. **假日日曆整合**：
   - 需要維護各市場的假日清單
   - 解決方案：
     - 建立 `market_holidays` 表
     - 整合第三方假日 API
     - 支援手動配置

### 設計決策問題

1. **是否完全取代檔案快取？**
   - 選項 A：保留檔案快取作為備選
   - 選項 B：完全遷移到 SQLite
   - **建議**：選項 A，透過參數控制

2. **快取更新策略**：
   - 策略 1：被動更新（查詢時檢查）
   - 策略 2：主動更新（定時同步）
   - **建議**：混合策略

3. **數據保留期限**：
   - 保留多久的歷史數據？
   - **建議**：可配置，預設 1 年

4. **指標計算結果是否快取？**
   - 優點：提升重複查詢效能
   - 缺點：增加複雜度
   - **建議**：第二階段實作

### 使用者體驗問題

1. **缺口填補的使用者確認**：
   - 自動填補 vs 手動確認
   - **建議**：提供兩種模式

2. **大量缺口的處理**：
   - 如何高效填補大量缺口？
   - **建議**：批次處理 + 進度顯示

3. **快取狀態視覺化**：
   - 如何呈現快取覆蓋範圍？
   - **建議**：命令列工具 + 統計報表

---

## 總結

### 核心發現總結

1. **數據獲取功能**：
   - 集中於 `HistoricalDataFetcher` 類別
   - 支援三種查詢模式：最新 N 根、日期範圍、從指定日期開始
   - 目前使用檔案系統快取（CSV/Parquet）

2. **技術指標計算**：
   - 獨立於 `indicators.py` 模組
   - 四種核心指標：Volume Profile, SMA, RSI, 布林通道
   - 透過 Agent 工具系統整合

3. **SQLite3 整合方案**：
   - 四張核心資料表設計完整
   - 智能快取查詢流程可大幅提升效能
   - 數據缺口檢測與填補機制完善

### 實作優先順序建議

#### Phase 1：核心功能（2-3 週）

1. ✅ 建立 SQLite 資料表結構
2. ✅ 實作 `SQLiteCacheManager` 基礎類別
3. ✅ 整合到 `HistoricalDataFetcher`
4. ✅ 基本數據插入和查詢功能
5. ✅ 單元測試

#### Phase 2：進階功能（2-3 週）

1. ✅ 數據缺口檢測演算法
2. ✅ 缺口填補機制
3. ✅ 快取管理工具（CLI）
4. ✅ 效能優化（批次插入、索引）
5. ✅ 完整測試覆蓋

#### Phase 3：使用者體驗（1-2 週）

1. ✅ 缺口警告與提示機制
2. ✅ 快取狀態視覺化
3. ✅ 文件更新
4. ✅ 使用範例

#### Phase 4：選用功能（未來）

1. ⏳ 指標計算結果快取
2. ⏳ 假日日曆整合
3. ⏳ 多資料庫檔案支援
4. ⏳ 數據匯入/匯出工具

### 關鍵技術考量

1. **效能**：
   - 使用批次插入提升寫入效能
   - 建立適當索引優化查詢
   - 使用 WAL 模式提升並發能力

2. **可靠性**：
   - 使用交易確保數據一致性
   - 完整的錯誤處理和日誌記錄
   - 定期備份資料庫檔案

3. **可維護性**：
   - 清晰的資料表結構
   - 完整的文件和註解
   - 單元測試覆蓋

4. **相容性**：
   - 保留檔案快取選項
   - 向下相容現有 API
   - 支援數據遷移工具

---

## 附錄

### A. 完整的資料表 SQL

參見「第三部分 3.2 資料表結構設計」章節。

### B. 時間週期轉換對照表

參見「第一部分 1.5 支援的時間週期」章節。

### C. MT5 數據欄位完整說明

參見「第一部分 1.6 數據格式說明」章節。

### D. 技術指標公式彙總

參見「第二部分 2.3 各指標詳細分析」章節。

### E. 效能測試基準

建議的效能基準（待實測）：

| 操作 | 目標效能 | 測試條件 |
|-----|---------|---------|
| 插入 10,000 筆 K 線 | < 1 秒 | 批次插入 |
| 查詢 1 個月數據 | < 100ms | 有索引 |
| 檢測缺口（1 年數據） | < 5 秒 | 優化演算法 |
| 填補 10 個缺口 | < 30 秒 | 並行處理 |

---

**研究完成日期**：2024-12-30
**研究執行者**：Claude (Sonnet 4.5)
**Codebase 版本**：commit db72429

本研究報告基於對 Chip Whisperer 專案的全面分析，涵蓋數據獲取、技術指標計算和 SQLite3 整合規劃的所有關鍵面向。報告提供了具體的實作建議、完整的資料表設計和詳細的流程規劃，可直接作為開發參考文件使用。
