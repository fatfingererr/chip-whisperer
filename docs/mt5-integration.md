# Chip Whisperer - MT5 整合說明文件

## 目錄

- [簡介](#簡介)
- [系統需求](#系統需求)
- [安裝步驟](#安裝步驟)
- [設定](#設定)
- [快速開始](#快速開始)
- [核心模組](#核心模組)
- [使用範例](#使用範例)
- [測試](#測試)
- [常見問題](#常見問題)
- [授權](#授權)

---

## 簡介

Chip Whisperer 是一個整合 MetaTrader 5 (MT5) 的交易分析系統，提供完整的歷史資料取得和分析功能。本專案特別針對繁體中文使用者設計，所有程式碼註解和文件均使用繁體中文。

### 主要功能

- **MT5 連線管理**：自動化的連線、斷線和重連機制
- **歷史資料取得**：支援多種時間週期和查詢模式的 K 線資料取得
- **資料快取**：本地快取機制，減少重複查詢
- **Volume Profile 分析**：內建 POC 和 Value Area 計算
- **設定靈活**：支援環境變數、YAML 檔案、程式碼配置多種方式

---

## 系統需求

### 必要條件

- **Python**: 3.10 或更高版本
- **MetaTrader 5**: 已安裝並可正常運作的 MT5 終端機
- **作業系統**: Windows（MT5 官方僅支援 Windows）
- **MT5 帳戶**: 有效的 MT5 交易帳戶（實盤或模擬）

### Python 套件依賴

所有依賴套件列於 `requirements.txt`：

```
MetaTrader5>=5.0.4510
pandas>=2.0.0
numpy>=1.24.0
pyyaml>=6.0
python-dotenv>=1.0.0
loguru>=0.7.0
```

---

## 安裝步驟

### 1. 克隆專案

```bash
git clone https://github.com/your-username/chip-whisperer.git
cd chip-whisperer
```

### 2. 建立虛擬環境（建議）

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. 安裝依賴套件

```bash
pip install -r requirements.txt
```

---

## 設定

### 步驟 1：複製設定範本

```bash
copy .env.example .env
```

### 步驟 2：編輯 .env 檔案

開啟 `.env` 檔案，填入您的 MT5 帳號資訊：

```env
# MT5 登入資訊（必要）
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=YourBroker-Server

# 連線參數（選用，使用預設值即可）
MT5_TIMEOUT=60000
MT5_MAX_RETRIES=3
DEBUG=false

# 資料快取目錄（選用）
CACHE_DIR=data/cache
```

**重要提示**：
- `MT5_LOGIN`：您的 MT5 帳號號碼
- `MT5_PASSWORD`：您的 MT5 帳號密碼
- `MT5_SERVER`：券商提供的伺服器名稱（例如：`XMGlobal-MT5`）
- `.env` 檔案已在 `.gitignore` 中，不會被提交到 Git

### 步驟 3：驗證設定

```bash
python verify_installation.py
```

---

## 快速開始

### 方法一：執行內建範例（推薦）

設定完成後，直接執行範例程式：

```bash
# 基本 K 線資料取得範例
python examples/fetch_historical_data.py

# Volume Profile 分析範例
python examples/demo_volume_profile_data.py
```

### 方法二：在程式中使用

```python
from core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher

# 1. 載入設定（自動從 .env 讀取）
config = MT5Config()

# 2. 建立客戶端並連線（使用 with 自動管理連線）
with ChipWhispererMT5Client(config) as client:
    # 3. 建立資料取得器
    fetcher = HistoricalDataFetcher(client)

    # 4. 取得最新 100 根 H1 K 線
    df = fetcher.get_candles_latest(
        symbol='GOLD',
        timeframe='H1',
        count=100
    )

    # 5. 顯示資料
    print(f"取得 {len(df)} 根 K 線")
    print(df.head())
```

---

## 核心模組

### MT5Config - 設定管理

負責載入和管理 MT5 連線設定。

**主要方法**：
- `validate()`: 驗證設定完整性
- `get_connection_config()`: 取得連線設定字典
- `get(key, default)`: 取得設定值

**範例**：

```python
from core import MT5Config

# 自動從 .env 載入設定
config = MT5Config()
config.validate()  # 驗證設定是否完整

# 取得設定值
login = config.get('login')
server = config.get('server')
timeout = config.get('timeout', 60000)  # 可設預設值
```

### ChipWhispererMT5Client - MT5 客戶端封裝

提供 MT5 連線管理和基本操作。

**主要方法**：
- `connect()`: 連線到 MT5
- `disconnect()`: 斷開連線
- `is_connected()`: 檢查連線狀態
- `ensure_connected()`: 確保已連線（未連線則自動連線）
- `get_account_info()`: 取得帳戶資訊
- `get_terminal_info()`: 取得終端機資訊

**範例**：

```python
from core import MT5Config, ChipWhispererMT5Client

config = MT5Config()

# 方式一：手動管理連線
client = ChipWhispererMT5Client(config)
client.connect()
# ... 進行操作 ...
client.disconnect()

# 方式二：使用 context manager（推薦）
with ChipWhispererMT5Client(config) as client:
    account_info = client.get_account_info()
    print(f"帳戶餘額：{account_info['balance']}")
```

### HistoricalDataFetcher - 歷史資料取得器

取得和管理歷史 K 線資料。

**主要方法**：
- `get_candles_latest(symbol, timeframe, count)`: 取得最新 N 根 K 線
- `get_candles_by_date(symbol, timeframe, from_date, to_date)`: 取得指定日期範圍的 K 線
- `save_to_cache(df, symbol, timeframe, format)`: 儲存資料到快取
- `load_from_cache(filepath)`: 從快取載入資料

**支援的時間週期**：
- 分鐘線：M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30
- 小時線：H1, H2, H3, H4, H6, H8, H12
- 日線以上：D1, W1, MN1

**範例**：

```python
from core import ChipWhispererMT5Client, HistoricalDataFetcher

with ChipWhispererMT5Client(config) as client:
    fetcher = HistoricalDataFetcher(client)

    # 取得最新 100 根 H1 K 線
    df1 = fetcher.get_candles_latest('SILVER', 'H1', 100)

    # 取得 2024 年全年的日線資料
    df2 = fetcher.get_candles_by_date(
        'GOLD',
        'D1',
        from_date='2024-01-01',
        to_date='2024-12-31'
    )

    # 儲存到 CSV
    fetcher.save_to_cache(df2, 'GOLD', 'D1', 'csv')
```

---

## 使用範例

### 範例 1：取得多個商品的資料

```python
from core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher

symbols = ['GOLD', 'SILVER', 'BITCOIN']
timeframe = 'H1'
count = 200

with ChipWhispererMT5Client(MT5Config()) as client:
    fetcher = HistoricalDataFetcher(client)

    for symbol in symbols:
        df = fetcher.get_candles_latest(symbol, timeframe, count)
        print(f"{symbol}: 取得 {len(df)} 根 K 線")

        # 儲存到快取
        fetcher.save_to_cache(df, symbol, timeframe, 'csv')
```

### 範例 2：計算技術指標

```python
import pandas as pd
from core import ChipWhispererMT5Client, HistoricalDataFetcher, MT5Config

with ChipWhispererMT5Client(MT5Config()) as client:
    fetcher = HistoricalDataFetcher(client)
    df = fetcher.get_candles_latest('GOLD', 'H1', 500)

    # 計算簡單移動平均線（SMA）
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()

    # 計算 RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    print(df[['time', 'close', 'sma_20', 'sma_50', 'rsi']].head())
```

### 範例 3：批次下載歷史資料

```python
from datetime import datetime, timedelta
from core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher

# 下載最近一年的資料
end_date = datetime.now()
start_date = end_date - timedelta(days=365)

symbols = ['GOLD', 'SILVER', 'BITCOIN', 'USDJPY']
timeframes = ['H1', 'H4', 'D1']

with ChipWhispererMT5Client(MT5Config()) as client:
    fetcher = HistoricalDataFetcher(client)

    for symbol in symbols:
        for tf in timeframes:
            print(f"下載 {symbol} {tf}...")

            df = fetcher.get_candles_by_date(
                symbol=symbol,
                timeframe=tf,
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=end_date.strftime('%Y-%m-%d')
            )

            # 儲存為 Parquet 格式（更高效）
            filepath = fetcher.save_to_cache(df, symbol, tf, 'parquet')
            print(f"  已儲存：{filepath}，共 {len(df)} 根")
```

---

## 測試

### 執行所有測試

```bash
pytest tests/ -v
```

### 執行特定測試

```bash
# 測試設定模組
pytest tests/test_config.py -v

# 測試資料取得器
pytest tests/test_data_fetcher.py -v
```

### 查看測試覆蓋率

```bash
pytest tests/ --cov=src --cov-report=html
```

測試覆蓋率報告會產生在 `htmlcov/index.html`。

---

## 常見問題

### Q1: 連線失敗，顯示「初始化失敗」

**可能原因**：
- MT5 終端機未安裝或路徑不正確
- MT5 終端機未執行

**解決方法**：
1. 確認 MT5 已正確安裝
2. 手動啟動 MT5 終端機
3. 在設定中指定正確的 MT5 路徑：
   ```env
   MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
   ```

### Q2: 登入失敗，顯示「登入錯誤」

**可能原因**：
- 帳號、密碼或伺服器名稱錯誤
- 網路連線問題
- MT5 伺服器維護中

**解決方法**：
1. 確認帳號、密碼和伺服器名稱正確
2. 嘗試在 MT5 終端機中手動登入
3. 檢查網路連線
4. 聯絡券商確認伺服器狀態

### Q3: 商品不存在錯誤

**可能原因**：
- 商品代碼拼寫錯誤
- 該券商不提供此商品
- 商品未啟用

**解決方法**：
1. 確認商品代碼正確（大小寫敏感）
2. 在 MT5 終端機的「市場報價」視窗中檢查商品是否存在
3. 右鍵點擊商品 → 「顯示」來啟用商品

### Q4: 無法取得歷史資料

**可能原因**：
- 券商限制歷史資料存取
- 資料尚未下載到本地
- 查詢的時間範圍無資料

**解決方法**：
1. 在 MT5 中打開該商品的圖表，等待歷史資料下載
2. 縮小查詢的時間範圍
3. 聯絡券商確認歷史資料權限

### Q5: 中文亂碼問題

本專案所有檔案均使用 UTF-8 編碼，如遇到亂碼：

1. 確保您的編輯器使用 UTF-8 編碼
2. Windows 終端機設定為 UTF-8：
   ```powershell
   chcp 65001
   ```
3. CSV 檔案使用 UTF-8 with BOM 編碼（已自動處理）

---

## 專案結構

```
chip-whisperer/
├── src/                          # 原始碼
│   └── core/                     # 核心模組
│       ├── __init__.py
│       ├── mt5_config.py         # 設定管理
│       ├── mt5_client.py         # MT5 客戶端封裝
│       └── data_fetcher.py       # 歷史資料取得器
├── examples/                     # 範例程式
│   ├── fetch_historical_data.py  # 基本資料取得範例
│   └── demo_volume_profile_data.py  # Volume Profile 分析範例
├── tests/                        # 測試套件
│   ├── test_config.py
│   └── test_data_fetcher.py
├── data/                         # 資料目錄
│   └── cache/                    # 快取資料
├── logs/                         # 日誌檔案
├── output/                       # 分析輸出
├── .env.example                  # 設定檔範本（複製為 .env 使用）
├── .gitignore                    # Git 忽略規則
├── requirements.txt              # Python 依賴套件
├── pyproject.toml               # 專案設定
└── README_INTEGRATION.md        # 本文件
```

---

## 授權

本專案採用 MIT 授權條款。詳見 [LICENSE](LICENSE) 檔案。

---

## 支援與貢獻

如有問題或建議，歡迎：

1. 提交 Issue
2. 發送 Pull Request
3. 聯絡專案維護者
