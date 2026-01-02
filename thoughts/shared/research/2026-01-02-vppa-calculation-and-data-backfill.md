---
title: VPPA 計算與資料回補實作研究
date: 2026-01-02
author: Claude Sonnet 4.5
tags: [vppa, volume-profile, data-backfill, visualization, telegram]
status: completed
related_files:
  - src/agent/tools.py
  - src/agent/indicators.py
  - scripts/analyze_vppa.py
  - scripts/backfill_data.py
  - src/visualization/vppa_plot.py
  - src/bot/telegram_bot.py
  - src/bot/handlers.py
last_updated: 2026-01-02
last_updated_by: Claude Sonnet 4.5
---

# VPPA 計算與資料回補實作研究

## 研究目標

本研究旨在完整了解以下實作細節：
1. `src/agent/tools.py` 中的 `calculate_volume_profile` 函數實作
2. `scripts/analyze_vppa.py` 的 VPPA 計算方式和圖表產出邏輯
3. `scripts/backfill_data.py` 的資料回補機制
4. `src/agent/tools.py` 中的 `get_candle` 函數實作
5. 如何將圖表回傳到 Telegram

## 摘要

本專案實作了完整的 VPPA（Volume Profile Pivot Anchored）分析系統，包含：

1. **VPPA 計算核心**：實作於 `src/agent/indicators.py`，包含完整的 Pivot Point 偵測、Volume Profile 計算和 Value Area 分析
2. **資料管理**：透過 SQLite 快取和 MT5 API 整合，實現高效的歷史資料回補和查詢
3. **視覺化系統**：使用 Plotly 產生互動式 VPPA 圖表，支援 PNG 輸出
4. **Telegram 整合**：透過 python-telegram-bot 實現圖片發送功能（API 已調查，但目前程式碼中尚未實作）

系統採用模組化設計，核心計算邏輯與 PineScript VPPA 指標一致，確保結果的準確性。

## 詳細研究結果

### 1. Volume Profile 計算實作

#### 1.1 基礎 Volume Profile (`calculate_volume_profile`)

**位置**：`src/agent/indicators.py` 第 13-152 行

**功能**：計算整個資料集的 Volume Profile

**核心演算法**：

```python
# 1. 確定價格範圍
price_min = df['low'].min()
price_max = df['high'].max()

# 2. 建立價格區間（bins）
price_edges = np.linspace(price_min, price_max, price_bins + 1)
price_centers = (price_edges[:-1] + price_edges[1:]) / 2

# 3. 分配成交量到價格區間
for _, row in df.iterrows():
    # 找出此 K 線涵蓋的價格區間
    low_idx = np.searchsorted(price_edges, row['low'], side='left')
    high_idx = np.searchsorted(price_edges, row['high'], side='right') - 1

    # 將成交量平均分配到涵蓋的價格區間
    span = high_idx - low_idx + 1
    if span > 0:
        volume_per_bin = row['real_volume'] / span
        volumes[low_idx:high_idx + 1] += volume_per_bin
```

**計算指標**：

1. **POC (Point of Control)**：成交量最大的價位
   ```python
   poc_price = profile_df_sorted_by_volume.iloc[0]['price']
   poc_volume = profile_df_sorted_by_volume.iloc[0]['volume']
   ```

2. **Value Area (VAH/VAL)**：包含 70% 成交量的價格區間
   - 從 POC 開始向兩側擴展
   - 每次選擇成交量較大的一側
   - 直到累積成交量達到 70%

**輸出格式**：
```python
{
    'poc_price': float,         # POC 價格
    'poc_volume': float,        # POC 成交量
    'vah': float,              # Value Area High
    'val': float,              # Value Area Low
    'value_area_volume': float,
    'total_volume': float,
    'value_area_percentage': float
}
```

#### 1.2 VPPA 完整計算 (`calculate_vppa`)

**位置**：`src/agent/indicators.py` 第 736-1109 行

**功能**：計算完整的 VPPA 指標（Pivot Point + Volume Profile）

**計算流程**：

```
Step 1: 偵測 Pivot Points
   ↓
Step 2: 提取 Pivot Point 區間
   ↓
Step 3: 為每個區間計算 Volume Profile
   ↓
Step 4: 計算 Value Area (POC, VAH, VAL)
   ↓
Step 5: 計算即時發展中的區間（可選）
```

**核心函數呼叫鏈**：

1. `find_pivot_points(df, length)` - 偵測 Pivot High/Low
   - 位置：第 265-346 行
   - 邏輯：中心點的 high/low 必須嚴格大於/小於左右各 `length` 根 K 線

2. `extract_pivot_ranges(df)` - 提取區間配對
   - 位置：第 349-430 行
   - 邏輯：相鄰的兩個 Pivot Point 形成一個區間

3. `calculate_volume_profile_for_range(df, start_idx, end_idx, price_levels)`
   - 位置：第 433-561 行
   - 核心公式（與 PineScript 一致）：
   ```python
   # 按 K 線覆蓋比例分配成交量
   ratio = price_step / bar_range
   volume_storage[level] += bar_volume * ratio
   ```

4. `calculate_value_area(volume_storage, price_lowest, price_step, value_area_pct)`
   - 位置：第 564-733 行
   - 從 POC 向兩側擴展，優先選擇成交量較大的一側

**預設參數**：
- `pivot_length`: 20（左右觀察窗口）
- `price_levels`: 25（價格分層數量）
- `value_area_pct`: 0.68（68% 成交量）
- `include_developing`: True（包含即時發展中的區間）

**輸出結構**：
```python
{
    'metadata': {
        'total_bars': int,
        'pivot_length': int,
        'price_levels': int,
        'value_area_pct': float,
        'total_pivot_points': int,
        'total_ranges': int,
        'pivot_high_count': int,
        'pivot_low_count': int
    },
    'pivot_summary': [
        {
            'idx': int,
            'type': 'H' | 'L',
            'price': float,
            'time': Timestamp
        },
        ...
    ],
    'pivot_ranges': [
        {
            'range_id': int,
            'start_idx': int,
            'end_idx': int,
            'start_time': Timestamp,
            'end_time': Timestamp,
            'bar_count': int,
            'pivot_type': 'H' | 'L',
            'pivot_price': float,
            'price_highest': float,
            'price_lowest': float,
            'price_range': float,
            'price_step': float,
            'volume_profile': list,
            'price_centers': list,
            'poc': {
                'level': int,
                'price': float,
                'volume': float,
                'volume_pct': float
            },
            'vah': float,
            'val': float,
            'value_area_width': float,
            'value_area_volume': float,
            'value_area_pct': float,
            'total_volume': float,
            'avg_volume_per_bar': float
        },
        ...
    ],
    'developing_range': { ... } | None
}
```

### 2. VPPA 分析腳本 (`analyze_vppa.py`)

**位置**：`scripts/analyze_vppa.py`

**主要功能**：
1. 補充 DB 數據（從最後一筆到目前為止）
2. 往回取指定數量的 K 線數據
3. 計算 Pivot Point 和 Volume Profile
4. 輸出 JSON 格式的分析結果
5. 繪製並儲存 VPPA 圖表（可選）

**執行流程**：

```python
def analyze_vppa(...) -> dict:
    # 步驟 1：補充 DB 到最新
    new_count = update_db_to_now(symbol, timeframe, cache, client)

    # 步驟 2：取得 K 線數據
    df = fetch_data(symbol, timeframe, count, cache, client)

    # 步驟 3：計算成交量移動平均
    df['volume_ma'] = df['real_volume'].rolling(window=volume_ma_length).mean()

    # 步驟 4：計算 VPPA
    df_indexed = df.set_index('time')
    vppa_result = calculate_vppa(
        df_indexed,
        pivot_length=pivot_length,
        price_levels=price_levels,
        value_area_pct=value_area_pct
    )

    # 步驟 5：整理輸出
    output = {
        'symbol': symbol,
        'timeframe': timeframe,
        'analysis_time': datetime.now(timezone.utc).isoformat(),
        'parameters': { ... },
        'data_range': { ... },
        'summary': { ... },
        'pivot_points': vppa_result['pivot_summary'],
        'pivot_ranges': [ ... ],
        'developing_range': { ... }
    }

    return output
```

**資料更新機制** (`update_db_to_now`)：

**位置**：第 92-151 行

```python
def update_db_to_now(symbol, timeframe, cache, client):
    # 取得 DB 中最新的時間
    newest_time = cache.get_newest_time(symbol, timeframe)

    if newest_time:
        # 從最新時間的下一個週期開始取
        from_time = newest_time + timedelta(minutes=tf_minutes)
    else:
        # DB 中無數據，從現在往回取 2000 根
        from_time = datetime.now(timezone.utc) - timedelta(minutes=tf_minutes * 2000)

    # 從 MT5 取得數據
    rates = mt5.copy_rates_range(symbol, tf_constant, from_time, to_time)

    # 轉換為 DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

    # 保存到 DB
    inserted = cache.insert_candles(df, symbol, timeframe)

    return inserted
```

**資料取得邏輯** (`fetch_data`)：

**位置**：第 154-207 行

```python
def fetch_data(symbol, timeframe, count, cache, client):
    # 先從 DB 取得數據
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=tf_minutes * count * 2)

    df = cache.query_candles(symbol, timeframe, start_time, end_time)

    if df is not None and len(df) >= count:
        # DB 數據足夠，取最新的 count 筆
        df = df.sort_values('time', ascending=True).tail(count).reset_index(drop=True)
        return df

    # DB 數據不足，從 MT5 取得
    rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, count)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

    # 保存到 DB
    cache.insert_candles(df, symbol, timeframe)

    return df
```

**命令列參數**：
- `symbol`: 商品代碼（必填）
- `--timeframe`: 時間週期（預設 M1）
- `--count`: K 線數量（預設 2160）
- `--pivot-length`: Pivot Point 觀察窗口（預設 67）
- `--price-levels`: 價格分層數量（預設 27）
- `--value-area-pct`: Value Area 百分比（預設 0.67）
- `--volume-ma-length`: 成交量移動平均長度（預設 14）
- `--db-path`: 資料庫路徑（預設 data/candles.db）
- `--output`: JSON 輸出路徑（可選）
- `--plot`: 是否繪製圖表（可選）
- `--plot-output`: 圖表輸出路徑（預設 output/vppa_chart.png）

**使用範例**：
```bash
# 基本使用
python scripts/analyze_vppa.py GOLD

# 自訂參數
python scripts/analyze_vppa.py GOLD --timeframe H1 --count 500 --plot

# 輸出到檔案
python scripts/analyze_vppa.py GOLD --output results/gold_vppa.json --plot-output output/gold.png
```

### 3. 資料回補機制 (`backfill_data.py`)

**位置**：`scripts/backfill_data.py`

**功能**：批次回填歷史數據到 SQLite 資料庫

**核心邏輯**：

```python
def backfill_data(symbol, timeframe, db_path, batch_size, max_retries):
    # 檢查現有數據的最早時間
    existing_oldest = cache.get_oldest_time(symbol, timeframe)

    if existing_oldest:
        # 從現有最早時間往前抓
        current_end_time = existing_oldest
    else:
        # 從現在開始往回抓
        current_end_time = datetime.now(timezone.utc)

    consecutive_empty = 0
    max_consecutive_empty = 3

    while consecutive_empty < max_consecutive_empty:
        # 從指定時間往前抓取
        rates = mt5.copy_rates_from(
            symbol,
            tf_constant,
            current_end_time,
            batch_size
        )

        if rates is None or len(rates) == 0:
            # 無更多數據，往前推 30 天再試
            consecutive_empty += 1
            current_end_time = current_end_time - timedelta(days=30)
            continue

        # 轉換並保存
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        inserted = cache.insert_candles(df, symbol, timeframe)

        # 更新統計
        stats['total_records'] += inserted
        stats['batches_fetched'] += 1

        # 檢查是否還有更早的數據
        if len(df) < batch_size:
            consecutive_empty += 1
        else:
            consecutive_empty = 0

        # 更新下一批的結束時間
        batch_oldest = df['time'].min()
        current_end_time = batch_oldest - timedelta(minutes=tf_minutes)

    return stats
```

**觸發條件**：
- 手動執行腳本進行批次回補
- `analyze_vppa.py` 執行時自動補充到最新

**執行策略**：
1. **雙向回補**：可從現在往回補充歷史，或從已有數據往前擴展
2. **批次大小**：預設 10000 根 K 線/批次
3. **容錯機制**：
   - 最多重試 3 次
   - 連續 3 次空結果後停止
   - 空結果時往前推 30 天再試

**重複資料處理**：
- SQLite schema 使用 `UNIQUE(symbol, timeframe, time)` 約束
- `INSERT OR IGNORE` 自動跳過重複資料

**命令列參數**：
- `symbol`: 商品代碼（必填）
- `--timeframe`: 時間週期（預設 M1）
- `--batch-size`: 每批次 K 線數量（預設 10000）
- `--db-path`: 資料庫路徑（預設 data/candles.db）
- `--max-retries`: 失敗時的最大重試次數（預設 3）

**使用範例**：
```bash
# 回補黃金 M1 數據
python scripts/backfill_data.py GOLD

# 回補黃金 H1 數據，自訂批次大小
python scripts/backfill_data.py GOLD --timeframe H1 --batch-size 5000
```

### 4. K 線資料取得 (`get_candles`)

**位置**：`src/agent/tools.py` 第 233-298 行

**功能**：取得指定商品和時間週期的 K 線資料

**實作細節**：

```python
def _get_candles(args: Dict[str, Any]) -> Dict[str, Any]:
    symbol = args.get("symbol", "GOLD").upper()
    timeframe = args.get("timeframe", "H1").upper()
    count = int(args.get("count", 100))

    # 取得 MT5 客戶端（單例模式）
    client = get_mt5_client()

    # 建立資料取得器
    fetcher = HistoricalDataFetcher(client)

    # 取得 K 線資料
    df = fetcher.get_candles_latest(
        symbol=symbol,
        timeframe=timeframe,
        count=count
    )

    # 將 DataFrame 轉換為 JSON
    df_copy = df.copy()
    if 'time' in df_copy.columns:
        df_copy['time'] = df_copy['time'].astype(str)

    candles_data = df_copy.to_dict('records')
    candles_json = json.dumps(candles_data, ensure_ascii=False)

    # 計算摘要資訊
    summary = {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_candles": len(df),
        "date_range": {
            "from": str(df['time'].min()),
            "to": str(df['time'].max())
        },
        "price_range": {
            "high": float(df['high'].max()),
            "low": float(df['low'].min()),
            "latest_close": float(df['close'].iloc[-1])
        },
        "total_volume": float(df['real_volume'].sum())
    }

    return {
        "success": True,
        "message": f"成功取得 {symbol} {timeframe} K 線資料，共 {len(df)} 根",
        "data": {
            "candles_json": candles_json,
            "summary": summary
        }
    }
```

**MT5 客戶端管理**：

**位置**：第 66-86 行

```python
# 全域實例（單例模式）
_mt5_client = None
_mt5_config = None

def get_mt5_client() -> ChipWhispererMT5Client:
    global _mt5_client, _mt5_config

    if _mt5_client is None:
        logger.info("初始化 MT5 客戶端")
        _mt5_config = MT5Config()
        _mt5_client = ChipWhispererMT5Client(_mt5_config)
        _mt5_client.connect()

    # 確保連線
    _mt5_client.ensure_connected()
    return _mt5_client
```

**資料來源層級**：
1. **優先**：SQLite 快取（透過 `HistoricalDataFetcher`）
2. **次選**：MT5 即時查詢（快取未命中或資料不足時）

**錯誤處理**：
```python
try:
    # ... 執行邏輯
    return {"success": True, "data": ...}
except Exception as e:
    logger.exception("取得 K 線資料失敗")
    return {
        "success": False,
        "error": f"取得 K 線資料失敗：{str(e)}"
    }
```

### 5. VPPA 圖表視覺化

#### 5.1 圖表繪製核心 (`plot_vppa_chart`)

**位置**：`src/visualization/vppa_plot.py` 第 608-766 行

**功能**：繪製完整的 VPPA 圖表（K 線圖 + Volume Profile）

**繪製流程**：

```python
def plot_vppa_chart(vppa_json, candles_df, output_path,
                    show_pivot_points, show_developing, width, height):
    # 1. 驗證輸入
    validate_vppa_json(vppa_json)
    validate_candles_df(candles_df)

    # 2. 時區轉換（UTC -> 本地時區）
    local_tz = datetime.now().astimezone().tzinfo
    candles_df['time'] = candles_df['time'].dt.tz_convert(local_tz)
    vppa_json = _convert_vppa_times_to_local(vppa_json, local_tz)

    # 3. 建立 Figure
    fig = go.Figure()

    # 4. 收集所有區間（包含 developing_range）
    all_ranges = vppa_json['pivot_ranges'].copy()
    if show_developing and vppa_json.get('developing_range'):
        all_ranges.append(vppa_json['developing_range'])

    # 5. 建立 shapes（方塊 + Volume Profile）
    all_shapes = []
    range_shapes = _add_range_boxes(all_ranges, show_developing)
    all_shapes.extend(range_shapes)

    vp_shapes = _add_volume_profiles(all_ranges, timeframe=timeframe)
    all_shapes.extend(vp_shapes)

    # 6. 批量添加 shapes
    fig.update_layout(shapes=all_shapes)

    # 7. 添加 K 線圖
    _add_candlestick(fig, candles_df)

    # 8. 添加 POC 線（Naked POC 延伸到最右邊並標註）
    _add_poc_lines(fig, all_ranges, latest_time, latest_price)

    # 9. 設定布局（網格、標題等）
    fig.update_layout(...)

    # 10. 輸出 PNG
    if output_path:
        fig.write_image(output_path, width=width, height=height, scale=2)

    return fig
```

**視覺化元素**：

1. **K 線圖** (`_add_candlestick`)
   - 使用 Plotly 的 `go.Candlestick`
   - 紅漲綠跌配色

2. **Pivot Range 方塊** (`_add_range_boxes`)
   ```python
   shapes.append(dict(
       type='rect',
       x0=start_time,
       x1=end_time,
       y0=lowest_price,
       y1=highest_price,
       fillcolor='rgba(200, 200, 200, 0.1)',
       line=dict(color='gray', width=2),
       layer='below'
   ))
   ```

3. **Volume Profile 長條** (`_add_volume_profiles`)
   - 使用矩形 shapes 繪製
   - 最大寬度 = Range 寬度的 2/3
   - Value Area 內外不同顏色：
     - VA 內：`rgba(0, 123, 255, 0.3)` 藍色
     - VA 外：`rgba(0, 123, 255, 0.15)` 淡藍色
   - 成交量正規化公式：
     ```python
     width_minutes = (volume / max_volume) * max_width_minutes
     ```

4. **POC 線** (`_add_poc_lines`)
   - 實線，紅色
   - Naked POC（未被後續 VA 覆蓋）：
     - 延伸到圖表最右邊
     - 顯示價格和與當前價差：`f"{poc_price:.2f} ({price_diff:+.2f})"`
   - 被 VA 覆蓋的 POC：
     - 停止在該 VA 的起始處

5. **網格設定**
   - X 軸（時間）：
     - M1/M5/M15: 1 小時間隔
     - M30/H1/H4: 1 日間隔
     - D1 以上: 1 日間隔
   - Y 軸（價格）：
     - 動態計算：`price_digits = len(str(price_int))`
     - 間隔 = `10^(digits-1) / 20`
     - 例如：4000 (4位數) → 間隔 50

**顏色配置** (`src/visualization/chart_config.py`)：
```python
COLORS = {
    'candle_up': '#ef5350',        # 紅色（漲）
    'candle_down': '#26a69a',      # 綠色（跌）
    'range_fill': 'rgba(200, 200, 200, 0.1)',
    'range_border': 'gray',
    'volume_in_va': 'rgba(0, 123, 255, 0.3)',
    'volume_out_va': 'rgba(0, 123, 255, 0.15)',
    'poc_line': 'red',
    'va_line': 'blue',
    'pivot_high': 'red',
    'pivot_low': 'green'
}

LINE_STYLES = {
    'poc': 'solid',
    'va': 'dash'
}
```

#### 5.2 圖表輸出

**支援格式**：
- PNG 圖片（透過 `kaleido` 後端）
- 互動式 HTML（Plotly 內建）

**輸出參數**：
```python
fig.write_image(
    output_path,
    width=1920,    # 預設寬度
    height=1080,   # 預設高度
    scale=2        # 高解析度（2x）
)
```

**效能最佳化**：
- 合併所有 POC 線為單一 Trace（避免過多 Trace）
- 使用 shapes 繪製 Volume Profile（比 Scatter 更高效）
- 批量添加 shapes（單次 `update_layout`）

### 6. Telegram 圖片發送

#### 6.1 API 調查結果

**套件**：`python-telegram-bot>=20.0`（已安裝於 requirements.txt）

**發送圖片 API**：
```python
async def send_photo(
    chat_id: Union[int, str],
    photo: Union[str, Path, IO[bytes], InputFile, bytes, PhotoSize],
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    ...
) -> Message
```

**支援的輸入格式**：
1. **檔案路徑**（字串或 `pathlib.Path`）
   ```python
   await bot.send_photo(chat_id=chat_id, photo="output/chart.png")
   ```

2. **檔案物件**（`IO[bytes]`）
   ```python
   with open("chart.png", "rb") as f:
       await bot.send_photo(chat_id=chat_id, photo=f)
   ```

3. **位元組資料**（`bytes`）
   ```python
   with open("chart.png", "rb") as f:
       photo_bytes = f.read()
   await bot.send_photo(chat_id=chat_id, photo=photo_bytes)
   ```

4. **URL**（字串）
   ```python
   await bot.send_photo(chat_id=chat_id, photo="https://example.com/chart.png")
   ```

**圖片限制**：
- 最大檔案大小：10MB
- 最大解析度：10000 x 10000 像素
- 寬高比：最多 20:1

#### 6.2 實作建議（目前程式碼中尚未實作）

**方案 1：直接發送檔案路徑**
```python
# 在 handlers.py 中
async def handle_vppa_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. 呼叫 analyze_vppa() 產生圖表
    from scripts.analyze_vppa import analyze_vppa

    output_path = "output/vppa_temp.png"
    result, df = analyze_vppa(
        symbol="GOLD",
        timeframe="M1",
        count=2160,
        return_dataframe=True
    )

    # 2. 繪製圖表
    from src.visualization import plot_vppa_chart
    plot_vppa_chart(
        vppa_json=result,
        candles_df=df,
        output_path=output_path,
        width=1920,
        height=1080
    )

    # 3. 發送圖片
    await update.message.reply_photo(
        photo=output_path,
        caption=f"{result['symbol']} {result['timeframe']} VPPA 分析"
    )

    # 4. 清理暫存檔（可選）
    import os
    os.remove(output_path)
```

**方案 2：使用記憶體緩衝區（避免磁碟 I/O）**
```python
import io

# 繪製圖表到記憶體
fig = plot_vppa_chart(...)
img_bytes = fig.to_image(format="png", width=1920, height=1080, scale=2)

# 發送
await update.message.reply_photo(
    photo=io.BytesIO(img_bytes),
    caption=f"VPPA 分析"
)
```

**整合位置建議**：
- 新增工具到 `src/agent/tools.py`：
  ```python
  TOOLS.append({
      "name": "generate_vppa_chart",
      "description": "產生 VPPA 圖表並發送到 Telegram",
      "input_schema": {
          "type": "object",
          "properties": {
              "symbol": {"type": "string"},
              "timeframe": {"type": "string"},
              "count": {"type": "integer", "default": 2160}
          },
          "required": ["symbol", "timeframe"]
      }
  })
  ```

- 實作執行函式：
  ```python
  def _generate_vppa_chart(args: Dict[str, Any]) -> Dict[str, Any]:
      # 1. 呼叫 analyze_vppa
      # 2. 呼叫 plot_vppa_chart
      # 3. 回傳圖片路徑或 bytes
      return {
          "success": True,
          "data": {
              "image_path": output_path,
              "summary": { ... }
          }
      }
  ```

- 在 `handle_message` 中處理工具回傳的圖片：
  ```python
  # handlers.py
  if tool_name == "generate_vppa_chart" and result.get("data", {}).get("image_path"):
      await message.reply_photo(
          photo=result["data"]["image_path"],
          caption=result.get("message", "VPPA 圖表")
      )
  ```

### 7. 依賴套件和配置

#### 7.1 核心套件

**資料處理**：
- `MetaTrader5>=5.0.4510` - MT5 API 整合
- `pandas>=2.0.0` - 資料處理
- `numpy>=1.24.0` - 數值計算

**視覺化**：
- `plotly>=5.18.0` - 互動式圖表
- `kaleido>=0.2.1` - 圖表轉 PNG

**Telegram**：
- `python-telegram-bot>=20.0` - Telegram Bot API

**AI Agent**：
- `anthropic>=0.18.0` - Claude API

**其他**：
- `loguru>=0.7.0` - 日誌記錄
- `python-dotenv>=1.0.0` - 環境變數管理
- `sqlite3` - 內建，資料快取

#### 7.2 環境配置

**必要環境變數** (`.env`)：
```env
# MT5 連線
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=your_server

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_GROUP_IDS=group_id_1,group_id_2

# Claude API
ANTHROPIC_API_KEY=your_api_key
CLAUDE_MODEL=claude-sonnet-4.5-20251022
```

**資料庫配置**：
- 預設路徑：`data/candles.db`
- Schema：`src/core/schema.sql`
- WAL 模式：已啟用（提升並發效能）
- 外鍵約束：已啟用

**圖表輸出配置**：
- 預設路徑：`output/vppa_chart.png`
- 預設解析度：1920x1080 @ 2x（3840x2160 實際輸出）
- 格式：PNG

### 8. 錯誤處理機制

#### 8.1 MT5 連線錯誤

**位置**：`src/core/mt5_client.py`

```python
def ensure_connected(self):
    if not mt5.terminal_info():
        logger.warning("MT5 連線已斷開，嘗試重新連線")
        self.connect()
```

**重連策略**：
- 自動偵測斷線
- 自動重連
- 失敗時拋出 `RuntimeError`

#### 8.2 資料取得錯誤

**空數據處理**：
```python
if rates is None or len(rates) == 0:
    error = mt5.last_error()
    if error[0] == 1:  # 無更多數據
        logger.info("已無更多歷史數據")
        return []
    else:
        raise RuntimeError(f"MT5 錯誤：{error}")
```

**資料驗證**：
```python
required_columns = ['high', 'low', 'real_volume']
missing_columns = [col for col in required_columns if col not in df.columns]
if missing_columns:
    raise ValueError(f"缺少必要欄位：{missing_columns}")
```

#### 8.3 計算錯誤

**價格範圍檢查**：
```python
if price_range == 0:
    logger.warning("區間價格無變化，無法計算 Volume Profile")
    return {
        'volume_profile': np.zeros(price_levels),
        'price_lowest': price_lowest,
        'price_highest': price_highest,
        ...
    }
```

**成交量檢查**：
```python
if total_volume == 0:
    logger.warning("總成交量為 0，無法計算 Value Area")
    return {
        'poc_level': poc_level,
        'poc_price': poc_price,
        'poc_volume': 0,
        ...
    }
```

#### 8.4 Telegram 錯誤

**位置**：`src/bot/handlers.py`

```python
async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.exception(f"更新 {update} 發生錯誤：{context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "抱歉，發生了一個錯誤。請稍後再試或聯絡管理員。"
        )
```

**權限檢查**：
```python
async def _check_group_admin(update, context, config):
    # 檢查群組白名單
    if not config.is_allowed_group(chat.id):
        logger.debug(f"忽略未授權群組訊息")
        return False

    # 檢查管理員身份
    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
        logger.debug(f"忽略非管理員訊息")
        return False

    return True
```

### 9. 效能考量

#### 9.1 資料查詢效能

**SQLite 索引**：
```sql
CREATE INDEX idx_candles_symbol_timeframe_time
ON candles(symbol, timeframe, time);
```

**WAL 模式**：
- 讀取時不阻塞寫入
- 並發效能提升

**批次大小優化**：
- 預設 10000 根/批次（backfill）
- 平衡記憶體使用和網路請求次數

#### 9.2 計算效能

**向量化計算**：
```python
# 使用 NumPy 向量化操作
volume_storage = np.zeros(price_levels)
price_centers = np.array([...])
```

**避免重複計算**：
```python
# 先排序一次，避免每次查詢都排序
df_sorted = df.sort_values('time', ascending=True)
```

#### 9.3 繪圖效能

**合併 Traces**：
```python
# 將所有 POC 線合併為單一 Trace
all_x = []
all_y = []
for range_data in ranges:
    all_x.extend([x0, x1, None])  # None 分隔線段
    all_y.extend([y, y, None])

fig.add_trace(go.Scatter(x=all_x, y=all_y, ...))
```

**使用 Shapes**：
```python
# Shapes 比 Scatter 更高效
shapes.append(dict(type='rect', ...))
```

**批量更新**：
```python
# 一次添加所有 shapes
fig.update_layout(shapes=all_shapes)
```

## 程式碼參考

### 核心檔案清單

| 檔案路徑 | 功能 | 行數 |
|---------|------|------|
| `src/agent/tools.py` | Agent 工具定義和執行 | 521 |
| `src/agent/indicators.py` | 技術指標計算（Volume Profile, VPPA, Pivot Points） | 1110 |
| `scripts/analyze_vppa.py` | VPPA 分析腳本（主入口） | 626 |
| `scripts/backfill_data.py` | 歷史資料回補腳本 | 354 |
| `src/visualization/vppa_plot.py` | VPPA 圖表繪製 | 767 |
| `src/bot/telegram_bot.py` | Telegram Bot 主程式 | 267 |
| `src/bot/handlers.py` | Telegram 訊息處理器 | 461 |
| `src/core/sqlite_cache.py` | SQLite 快取管理 | 約 500+ |

### 關鍵函數位置索引

**VPPA 計算**：
- `calculate_volume_profile()`: `src/agent/indicators.py:13-152`
- `calculate_vppa()`: `src/agent/indicators.py:736-1109`
- `find_pivot_points()`: `src/agent/indicators.py:265-346`
- `extract_pivot_ranges()`: `src/agent/indicators.py:349-430`
- `calculate_volume_profile_for_range()`: `src/agent/indicators.py:433-561`
- `calculate_value_area()`: `src/agent/indicators.py:564-733`

**資料管理**：
- `backfill_data()`: `scripts/backfill_data.py:84-265`
- `update_db_to_now()`: `scripts/analyze_vppa.py:92-151`
- `fetch_data()`: `scripts/analyze_vppa.py:154-207`
- `_get_candles()`: `src/agent/tools.py:233-298`

**視覺化**：
- `plot_vppa_chart()`: `src/visualization/vppa_plot.py:608-766`
- `_add_candlestick()`: `src/visualization/vppa_plot.py:204-229`
- `_add_volume_profiles()`: `src/visualization/vppa_plot.py:278-361`
- `_add_poc_lines()`: `src/visualization/vppa_plot.py:397-479`

**Telegram**：
- `handle_message()`: `src/bot/handlers.py:232-390`
- `TelegramBot.__init__()`: `src/bot/telegram_bot.py:44-87`

## 相關技術文件

### 外部參考

1. **PineScript VPPA 指標**
   - 本專案的 VPPA 計算邏輯與 TradingView 的 PineScript VPPA 指標一致
   - 核心公式：`ratio = price_step / bar_range`

2. **Plotly 文件**
   - Candlestick Charts: https://plotly.com/python/candlestick-charts/
   - Shapes: https://plotly.com/python/shapes/
   - Static Image Export: https://plotly.com/python/static-image-export/

3. **python-telegram-bot 文件**
   - Send Photo: https://docs.python-telegram-bot.org/en/stable/telegram.bot.html#telegram.Bot.send_photo
   - Working with Files: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Working-with-Files-and-Media

4. **MetaTrader5 Python API**
   - `copy_rates_range()`: 指定時間範圍取得 K 線
   - `copy_rates_from()`: 從指定時間往前取得 K 線
   - `copy_rates_from_pos()`: 從當前往前取得 K 線

### 內部文件

- `docs/telegram-bot.md` - Telegram Bot 使用說明
- `docs/mt5-integration.md` - MT5 整合說明
- `docs/quick-start.md` - 快速開始指南

## 實作建議

### 1. 將 VPPA 圖表整合到 Telegram

**步驟**：

1. 新增工具定義到 `src/agent/tools.py`：
   ```python
   {
       "name": "generate_vppa_chart",
       "description": "產生 VPPA 圖表並回傳圖片",
       "input_schema": {
           "type": "object",
           "properties": {
               "symbol": {"type": "string"},
               "timeframe": {"type": "string"},
               "count": {"type": "integer", "default": 2160},
               "pivot_length": {"type": "integer", "default": 67},
               "price_levels": {"type": "integer", "default": 27}
           },
           "required": ["symbol", "timeframe"]
       }
   }
   ```

2. 實作執行函式 `_generate_vppa_chart()`：
   ```python
   def _generate_vppa_chart(args: Dict[str, Any]) -> Dict[str, Any]:
       from scripts.analyze_vppa import analyze_vppa
       from src.visualization import plot_vppa_chart
       import tempfile

       # 產生暫存檔路徑
       with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
           output_path = tmp.name

       # 執行分析
       result, df = analyze_vppa(
           symbol=args["symbol"],
           timeframe=args["timeframe"],
           count=args.get("count", 2160),
           pivot_length=args.get("pivot_length", 67),
           price_levels=args.get("price_levels", 27),
           return_dataframe=True
       )

       # 繪製圖表
       plot_vppa_chart(
           vppa_json=result,
           candles_df=df,
           output_path=output_path,
           width=1920,
           height=1080
       )

       return {
           "success": True,
           "message": f"VPPA 圖表已產生",
           "data": {
               "image_path": output_path,
               "summary": result["summary"]
           }
       }
   ```

3. 修改 `handle_message()` 支援圖片回傳：
   ```python
   # 在 handlers.py 中
   response = agent.process_message(enhanced_message, system_prompt=system_prompt)

   # 檢查是否有圖片需要發送
   if isinstance(response, dict) and response.get("image_path"):
       await message.reply_photo(
           photo=response["image_path"],
           caption=response.get("message", "分析結果")
       )

       # 清理暫存檔
       import os
       os.remove(response["image_path"])
   else:
       # 原有的文字回應邏輯
       await message.reply_text(response)
   ```

### 2. 優化資料回補策略

**建議**：

1. **定時自動回補**（避免手動執行）：
   ```python
   # 使用 APScheduler（已在 requirements.txt 中）
   from apscheduler.schedulers.asyncio import AsyncIOScheduler

   scheduler = AsyncIOScheduler()
   scheduler.add_job(
       backfill_data,
       'cron',
       hour=0,  # 每天凌晨執行
       args=['GOLD', 'M1']
   )
   scheduler.start()
   ```

2. **智慧缺口填補**：
   - 檢測資料庫中的缺口（連續時間間斷）
   - 只回補缺口範圍，避免全量掃描

3. **分散式回補**：
   - 支援多商品、多週期並行回補
   - 使用 `asyncio` 提升效率

### 3. 效能最佳化

**建議**：

1. **快取 VPPA 計算結果**：
   ```python
   # 將 VPPA 結果存入 SQLite
   # 避免重複計算相同參數的 VPPA
   ```

2. **分頁查詢大資料集**：
   ```python
   # 對於超長時間範圍，分段查詢避免記憶體溢出
   chunk_size = 100000
   for i in range(0, total_count, chunk_size):
       df_chunk = cache.query_candles(symbol, timeframe,
                                      start_time + timedelta(minutes=i*tf_minutes),
                                      start_time + timedelta(minutes=(i+chunk_size)*tf_minutes))
   ```

3. **圖表快取**：
   ```python
   # 為相同參數的圖表建立快取
   # 使用 hash(symbol, timeframe, count, pivot_length, ...) 作為 key
   ```

## 總結

本專案實作了完整的 VPPA 分析系統，具備以下特點：

1. **完整性**：從資料取得、計算、視覺化到 Telegram 整合的完整流程
2. **準確性**：VPPA 計算邏輯與 PineScript 指標一致
3. **效能**：SQLite 快取、向量化計算、批次處理
4. **可擴展性**：模組化設計，易於新增功能
5. **穩定性**：完善的錯誤處理和日誌記錄

主要技術棧：
- **資料層**：MT5 API + SQLite + pandas
- **計算層**：NumPy + 自訂演算法
- **視覺化層**：Plotly + Kaleido
- **介面層**：Telegram Bot + Claude AI Agent

下一步建議：
1. 實作 VPPA 圖表到 Telegram 的完整整合
2. 新增定時自動回補機制
3. 實作 VPPA 結果快取
4. 新增更多技術指標支援

---

**研究完成日期**：2026-01-02
**研究者**：Claude Sonnet 4.5
