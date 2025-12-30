---
title: "MetaTrader MCP Server 整合至 Chip Whisperer 專案研究報告"
date: 2025-12-30
author: "Claude Sonnet 4.5"
tags: ["mcp-server", "metatrader5", "integration", "mt5", "historical-data", "candles"]
status: "completed"
related_files:
  - "metatrader-mcp-server/src/metatrader_client/client.py"
  - "metatrader-mcp-server/src/metatrader_mcp/server.py"
  - "metatrader-mcp-server/src/metatrader_client/market/get_candles_by_date.py"
  - "metatrader-mcp-server/src/metatrader_client/market/get_candles_latest.py"
  - "metatrader-mcp-server/pyproject.toml"
last_updated: 2025-12-30
last_updated_by: "Claude Sonnet 4.5"
---

# MetaTrader MCP Server 整合研究報告

## 研究問題

如何將 MetaTrader MCP Server 功能整合到 Chip Whisperer 專案中，以支援從 MT5 平台取得歷史 K 線資料，並建立一個獨立、可維護的整合方案？

## 摘要

本研究針對 [ariadng/metatrader-mcp-server](https://github.com/ariadng/metatrader-mcp-server) 專案進行了全面分析，該專案提供了一個完整的 Python 套件，用於透過 Model Context Protocol (MCP) 或 HTTP API 與 MetaTrader 5 平台互動。

**主要發現**：

1. **架構清晰**：metatrader-mcp-server 採用三層架構設計，核心為 `metatrader_client` 函式庫，提供完整的 MT5 操作封裝
2. **歷史資料支援完善**：提供兩種 K 線資料取得方法（依日期範圍、依最新 N 根），支援多種時間週期
3. **整合方式靈活**：可作為 Python 函式庫、MCP Server 或 REST API 使用
4. **相依套件明確**：主要依賴 MetaTrader5、pandas、numpy 等成熟套件

**建議整合策略**：將 metatrader-mcp-server 作為獨立的 Python 套件整合到 Chip Whisperer 專案中，透過套件管理工具安裝，而非直接複製程式碼。

---

## 詳細研究發現

### 一、metatrader-mcp-server 專案架構分析

#### 1.1 專案結構

```
metatrader-mcp-server/
├── src/
│   ├── metatrader_client/      # 核心 MT5 客戶端函式庫
│   │   ├── account/            # 帳戶資訊操作模組
│   │   ├── connection/         # MT5 連線管理模組
│   │   ├── history/            # 歷史交易記錄模組
│   │   ├── market/             # 市場資料模組（包含 K 線取得）
│   │   ├── order/              # 訂單執行與管理模組
│   │   ├── types/              # 型別定義與列舉
│   │   ├── client.py           # 主要客戶端類別
│   │   ├── client_*.py         # 各模組的客戶端包裝類別
│   │   └── exceptions.py       # 自訂例外類別
│   │
│   ├── metatrader_mcp/         # MCP Server 實作
│   │   ├── server.py           # FastMCP 伺服器與工具定義
│   │   ├── cli.py              # 命令列介面
│   │   └── utils.py            # 工具函式
│   │
│   └── metatrader_openapi/     # HTTP REST API 實作
│       ├── main.py             # FastAPI 應用程式進入點
│       ├── config.py           # API 設定
│       └── routers/            # API 路由模組
│
├── docs/                       # 完整的 API 文檔
├── tests/                      # 測試套件
└── pyproject.toml             # 專案設定與依賴定義
```

#### 1.2 核心模組：metatrader_client

這是整個專案的基礎函式庫，提供了與 MT5 平台互動的所有功能。

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\metatrader-mcp-server\src\metatrader_client\client.py`

**關鍵類別**：`MT5Client`

```python
class MT5Client:
    """
    Main client class for MetaTrader 5 operations.

    Provides a unified interface for all MT5 operations including
    connection management, account information, market data,
    order execution, and history retrieval.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the MT5 client.

        Args:
            config: Optional configuration dictionary with connection parameters.
                   Can include: path, login, password, server, timeout, portable
        """
        self._config = config or {}
        self._connection = MT5Connection(config)
        self.account = MT5Account(self._connection)
        self.market = MT5Market(self._connection)
        self.order = MT5Order(self._connection)
        self.history = MT5History(self._connection)
```

**設計特點**：
- 採用組合模式，將不同功能區分為獨立模組（account、market、order、history）
- 所有操作都透過統一的 connection 物件進行
- 提供完整的型別提示和文檔字串

#### 1.3 市場資料模組：MT5Market

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\metatrader-mcp-server\src\metatrader_client\client_market.py`

這個模組負責所有市場資料相關的操作，包括：
- 取得商品列表
- 取得商品資訊
- 取得即時報價
- **取得歷史 K 線資料**（核心功能）

**關鍵方法**：

```python
class MT5Market:
    def get_candles_latest(
        self,
        symbol_name: str,
        timeframe: str,
        count: int = 100
    ) -> pd.DataFrame:
        """取得最新的 N 根 K 線"""
        return get_candles_latest(self._connection, symbol_name, timeframe, count)

    def get_candles_by_date(
        self,
        symbol_name: str,
        timeframe: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> pd.DataFrame:
        """取得指定日期範圍的 K 線資料"""
        return get_candles_by_date(self._connection, symbol_name, timeframe, from_date, to_date)
```

---

### 二、K 線資料取得功能深入分析

#### 2.1 get_candles_by_date - 依日期範圍取得 K 線

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\metatrader-mcp-server\src\metatrader_client\market\get_candles_by_date.py`

**完整程式碼分析**：

```python
def get_candles_by_date(
    connection,
    symbol_name: str,
    timeframe: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    取得指定商品在特定時間週期和日期範圍內的 K 線資料

    參數：
        connection: MT5 連線物件
        symbol_name: 商品代碼（例如 'SILVER'）
        timeframe: 時間週期字串（例如 'M1', 'H1', 'D1'）
        from_date: 起始日期（格式：'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM'）
        to_date: 結束日期（格式：'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM'）

    回傳：
        pd.DataFrame: 包含 K 線資料的 DataFrame

    欄位說明：
        - time: 時間戳記（pandas datetime，UTC 時區）
        - open: 開盤價
        - high: 最高價
        - low: 最低價
        - close: 收盤價
        - tick_volume: 跳動次數
        - spread: 買賣價差
        - real_volume: 實際成交量
    """
    # 1. 驗證商品是否存在
    if not get_symbols(connection, symbol_name):
        raise SymbolNotFoundError(f"Symbol '{symbol_name}' not found")

    # 2. 驗證並轉換時間週期
    tf = Timeframe.get(timeframe)
    if tf is None:
        raise InvalidTimeframeError(f"Invalid timeframe: '{timeframe}'")

    # 3. 解析日期參數
    from_datetime = None
    to_datetime = None

    def parse_date(date_str, is_to_date=False):
        """解析日期字串，支援兩種格式"""
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_str, fmt)
                if fmt == "%Y-%m-%d":
                    # 如果只有日期，自動補齊時間
                    if is_to_date:
                        dt = dt.replace(hour=23, minute=59)
                    else:
                        dt = dt.replace(hour=0, minute=0)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {date_str}")

    if from_date:
        from_datetime = parse_date(from_date)
    if to_date:
        to_datetime = parse_date(to_date, is_to_date=True)

    # 4. 確保日期順序正確
    if from_datetime and to_datetime and from_datetime > to_datetime:
        from_datetime, to_datetime = to_datetime, from_datetime

    # 5. 根據參數組合選擇適當的 MT5 API
    candles = None
    if from_datetime and to_datetime:
        # 兩個日期都提供：使用範圍查詢
        candles = mt5.copy_rates_range(symbol_name, tf, from_datetime, to_datetime)
    elif from_datetime:
        # 只有起始日期：從該日期開始取得 1000 根
        candles = mt5.copy_rates_from(symbol_name, tf, from_datetime, 1000)
    elif to_datetime:
        # 只有結束日期：往前推 30 天
        lookback_days = 30
        start_date = to_datetime - timedelta(days=lookback_days)
        candles = mt5.copy_rates_range(symbol_name, tf, start_date, to_datetime)
    else:
        # 沒有日期：取得最新 1000 根
        candles = mt5.copy_rates_from_pos(symbol_name, tf, 0, 1000)

    # 6. 驗證資料
    if candles is None or len(candles) == 0:
        raise MarketDataError(
            f"Failed to retrieve historical data for symbol '{symbol_name}' with timeframe '{timeframe}'"
        )

    # 7. 轉換為 DataFrame 並處理時間欄位
    df = pd.DataFrame(candles)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time', ascending=False)  # 最新的在前

    return df
```

**關鍵設計決策**：
1. **靈活的日期參數**：支援完整日期時間或僅日期，自動補齊時間部分
2. **智慧預設行為**：未提供日期時自動取得最新資料
3. **資料驗證**：檢查商品和時間週期有效性
4. **錯誤處理**：使用自訂例外提供清楚的錯誤訊息
5. **時區處理**：統一使用 UTC 時區

#### 2.2 get_candles_latest - 取得最新 K 線

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\metatrader-mcp-server\src\metatrader_client\market\get_candles_latest.py`

```python
def get_candles_latest(
    connection,
    symbol_name: str,
    timeframe: str,
    count: int = 100
) -> pd.DataFrame:
    """
    取得最新的 N 根 K 線資料

    參數：
        connection: MT5 連線物件
        symbol_name: 商品代碼
        timeframe: 時間週期
        count: 要取得的 K 線數量（預設 100）

    回傳：
        pd.DataFrame: K 線資料
    """
    # 1. 驗證商品
    if not get_symbols(connection, symbol_name):
        raise SymbolNotFoundError(f"Symbol '{symbol_name}' not found")

    # 2. 驗證時間週期
    tf = Timeframe.get(timeframe)
    if tf is None:
        raise InvalidTimeframeError(f"Invalid timeframe: '{timeframe}'")

    # 3. 從最新位置取得指定數量的 K 線
    candles = mt5.copy_rates_from_pos(symbol_name, tf, 0, count)

    # 4. 驗證資料
    if candles is None or len(candles) == 0:
        raise MarketDataError(
            f"Failed to retrieve candle data for symbol '{symbol_name}' with timeframe '{timeframe}'"
        )

    # 5. 轉換為 DataFrame
    df = pd.DataFrame(candles)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time', ascending=False)

    return df
```

**特點**：
- 更簡潔的介面，適合快速取得最新資料
- 適用於即時監控和最新市場狀況分析

#### 2.3 時間週期 (Timeframe) 定義

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\metatrader-mcp-server\src\metatrader_client\types\timeframe.py`

```python
class TimeframeClass:
    """
    MetaTrader5 時間週期常數的字串對應
    """
    _timeframes = {
        "M1": mt5.TIMEFRAME_M1,      # 1 分鐘
        "M2": mt5.TIMEFRAME_M2,      # 2 分鐘
        "M3": mt5.TIMEFRAME_M3,      # 3 分鐘
        "M4": mt5.TIMEFRAME_M4,      # 4 分鐘
        "M5": mt5.TIMEFRAME_M5,      # 5 分鐘
        "M6": mt5.TIMEFRAME_M6,      # 6 分鐘
        "M10": mt5.TIMEFRAME_M10,    # 10 分鐘
        "M12": mt5.TIMEFRAME_M12,    # 12 分鐘
        "M15": mt5.TIMEFRAME_M15,    # 15 分鐘
        "M20": mt5.TIMEFRAME_M20,    # 20 分鐘
        "M30": mt5.TIMEFRAME_M30,    # 30 分鐘
        "H1": mt5.TIMEFRAME_H1,      # 1 小時
        "H2": mt5.TIMEFRAME_H2,      # 2 小時
        "H3": mt5.TIMEFRAME_H3,      # 3 小時
        "H4": mt5.TIMEFRAME_H4,      # 4 小時
        "H6": mt5.TIMEFRAME_H6,      # 6 小時
        "H8": mt5.TIMEFRAME_H8,      # 8 小時
        "H12": mt5.TIMEFRAME_H12,    # 12 小時
        "D1": mt5.TIMEFRAME_D1,      # 日線
        "W1": mt5.TIMEFRAME_W1,      # 週線
        "MN1": mt5.TIMEFRAME_MN1,    # 月線
    }

    def get(self, key: str, default=None) -> Optional[int]:
        """
        使用字串鍵取得時間週期常數

        範例：
            Timeframe.get("H1")  # 回傳 mt5.TIMEFRAME_H1
            Timeframe.get("m1")  # 大小寫不敏感
        """
        try:
            return self[key]
        except KeyError:
            return default

# 建立單例實例
Timeframe = TimeframeClass()
```

**支援的時間週期**：從 1 分鐘 (M1) 到月線 (MN1)，涵蓋所有 MT5 標準時間週期。

---

### 三、MT5 連線管理分析

#### 3.1 連線配置

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\metatrader-mcp-server\src\metatrader_client\client_connection.py`

```python
class MT5Connection:
    """
    MetaTrader 5 連線管理類別

    負責建立、維護和關閉與 MT5 終端機的連線
    """

    def __init__(self, config: Dict):
        """
        初始化 MT5 連線

        config 參數：
            - path (str): MT5 終端機執行檔路徑（預設：None，自動偵測）
            - login (int): 登入帳號（必要）
            - password (str): 密碼（必要）
            - server (str): 伺服器名稱（必要）
            - timeout (int): 連線逾時（毫秒，預設：60000）
            - portable (bool): 是否使用可攜式模式（預設：False）
            - debug (bool): 是否啟用除錯日誌（預設：False）
            - max_retries (int): 最大重試次數（預設：3）
            - backoff_factor (float): 重試延遲倍數（預設：1.5）
            - cooldown_time (float): 連線間隔時間（秒，預設：2.0）
        """
        self.config = config
        self.path = config.get("path")
        self.login = config.get("login")
        self.password = config.get("password")
        self.server = config.get("server")
        self.timeout = config.get("timeout", 60000)
        self.portable = config.get("portable", False)
        self.debug = config.get("debug", False)
        self.max_retries = config.get("max_retries", 3)
        self.backoff_factor = config.get("backoff_factor", 1.5)
        self.cooldown_time = config.get("cooldown_time", 2.0)
        self._connected = False
        self._last_connection_time = 0

        # MT5 終端機標準路徑
        self.standard_paths = [
            "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
            "C:\\Program Files (x86)\\MetaTrader 5\\terminal.exe",
            os.path.expanduser("~\\AppData\\Roaming\\MetaQuotes\\Terminal\\*\\terminal64.exe"),
        ]
```

**連線流程**：

1. **初始化終端機**：自動啟動 MT5 終端機（如果未運行）
2. **登入帳戶**：使用提供的憑證進行登入
3. **重試機制**：連線失敗時自動重試，使用指數退避策略
4. **冷卻時間**：避免頻繁連線導致的問題

#### 3.2 自動路徑偵測

系統會自動搜尋以下位置的 MT5 終端機：
1. `C:\Program Files\MetaTrader 5\terminal64.exe`
2. `C:\Program Files (x86)\MetaTrader 5\terminal.exe`
3. 使用者設定檔目錄下的 MetaQuotes 資料夾

---

### 四、例外處理架構

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\metatrader-mcp-server\src\metatrader_client\exceptions.py`

完整的例外類別階層：

```
MT5ClientError (基礎例外)
├── ConnectionError (連線相關)
│   ├── InitializationError (初始化失敗)
│   ├── LoginError (登入失敗)
│   └── DisconnectionError (斷線失敗)
├── AccountError (帳戶相關)
│   ├── AccountInfoError (帳戶資訊錯誤)
│   ├── TradingNotAllowedError (不允許交易)
│   └── MarginLevelError (保證金不足)
├── MarketError (市場資料相關)
│   ├── SymbolError (商品錯誤)
│   │   └── SymbolNotFoundError (商品不存在)
│   ├── InvalidTimeframeError (無效時間週期)
│   ├── MarketDataError (市場資料錯誤)
│   ├── PriceError (價格資料錯誤)
│   └── HistoryDataError (歷史資料錯誤)
├── OrderError (訂單相關)
│   ├── OrderExecutionError (訂單執行錯誤)
│   ├── OrderModificationError (訂單修改錯誤)
│   └── OrderCancellationError (訂單取消錯誤)
├── PositionError (部位相關)
│   ├── PositionModificationError (部位修改錯誤)
│   └── PositionCloseError (部位關閉錯誤)
├── HistoryError (歷史記錄相關)
│   ├── DealsHistoryError (成交記錄錯誤)
│   ├── OrdersHistoryError (訂單記錄錯誤)
│   └── StatisticsError (統計資料錯誤)
├── CalculationError (計算相關)
│   ├── MarginCalculationError (保證金計算錯誤)
│   └── ProfitCalculationError (盈虧計算錯誤)
├── TimeoutError (逾時錯誤)
├── PermissionError (權限錯誤)
├── InvalidParameterError (無效參數)
└── ServerError (伺服器錯誤)
```

**使用範例**：

```python
from metatrader_client.exceptions import SymbolNotFoundError, InvalidTimeframeError

try:
    candles = client.market.get_candles_by_date("INVALID_SYMBOL", "H1")
except SymbolNotFoundError as e:
    print(f"商品不存在: {e.message}")
except InvalidTimeframeError as e:
    print(f"時間週期錯誤: {e.message}")
```

---

### 五、依賴套件分析

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\metatrader-mcp-server\pyproject.toml`

```toml
[project]
name = "metatrader-mcp-server"
version = "0.2.9"
requires-python = ">=3.10"

dependencies = [
  "python-dotenv>=1.1.0",         # 環境變數管理
  "MetaTrader5>=5.0.45",          # MT5 官方 Python SDK
  "numpy>=2.2.4",                 # 數值運算
  "pandas>=2.2.3",                # 資料處理與 DataFrame
  "tabulate>=0.9.0",              # 表格格式化
  "pytest>=8.3.5",                # 測試框架
  "httpx>=0.24.0",                # HTTP 客戶端
  "build>=1.2.2.post1",           # 建置工具
  "fastapi>=0.115.12",            # REST API 框架
  "uvicorn[standard]>=0.34.1",    # ASGI 伺服器
  "pydantic>=2.11.3",             # 資料驗證
  "pydantic-settings>=2.8.1",     # 設定管理
  "mcp[cli]>=1.6.0",              # Model Context Protocol
  "click>=8.0.0",                 # CLI 框架
]
```

**關鍵依賴說明**：

1. **MetaTrader5 (>=5.0.45)**
   - MT5 官方 Python SDK
   - 提供所有 MT5 API 功能
   - **重要**：僅支援 Windows 平台

2. **pandas (>=2.2.3)**
   - 用於處理 K 線資料
   - 提供 DataFrame 結構
   - 支援時間序列操作

3. **numpy (>=2.2.4)**
   - 底層數值運算
   - pandas 的依賴

4. **mcp[cli] (>=1.6.0)**
   - Model Context Protocol 實作
   - 用於 MCP Server 功能

5. **fastapi (>=0.115.12) + uvicorn**
   - REST API 伺服器
   - 提供 HTTP 介面

---

### 六、Chip Whisperer 專案現況分析

#### 6.1 專案目錄結構

```
chip-whisperer/
├── .claude/                    # Claude 設定檔（排除）
├── .git/                       # Git 版本控制
├── assets/                     # 資源檔案（圖片、logo）
├── metatrader-mcp-server/      # 參考程式碼（待移除）
├── thoughts/                   # 思考筆記與研究文件
│   └── shared/
│       └── research/           # 研究報告目錄
├── .gitignore                  # Git 忽略清單
├── .gitmodules                 # Git 子模組設定
├── LICENSE                     # MIT 授權
└── README.md                   # 專案說明文件
```

#### 6.2 專案特性

根據 README.md 分析：

**專案定位**：基於量價分析的 MT5 AI 交易代理

**核心功能（規劃中）**：
1. Volume Profile 分析（POC、Value Area、高低成交量節點）
2. 關鍵價格水平計算
3. AI 輔助決策

**技術需求（從 README 推斷）**：
- Python 3.8+
- MT5 連線能力
- 資料分析能力（pandas、numpy）
- 視覺化能力（matplotlib、plotly）

**規劃的目錄結構**：
```
chip-whisperer/
├── config/              # 配置檔案
├── models/              # AI 模型
├── src/
│   ├── analyzers/       # 分析模組
│   ├── indicators/      # 技術指標
│   ├── traders/         # 交易邏輯
│   └── utils/           # 工具函式
├── tests/               # 測試檔案
└── docs/                # 文檔
```

#### 6.3 整合需求分析

Chip Whisperer 需要從 MT5 取得歷史 K 線資料來進行量價分析，具體需求：

1. **資料取得**：
   - 多種商品（GOLD, CRUDE_OIL, COPPER）
   - 多種時間週期（M1 到 D1）
   - 歷史資料回溯能力

2. **資料處理**：
   - 轉換為適合分析的格式
   - 計算成交量分布
   - 識別關鍵價格水平

3. **連線管理**：
   - 穩定的 MT5 連線
   - 錯誤處理與重試
   - 設定檔管理

---

## 整合方案設計

### 方案一：作為 Python 套件安裝（推薦）

#### 優點
✅ **簡潔乾淨**：不需要複製大量程式碼
✅ **版本管理**：可以輕鬆升級到新版本
✅ **依賴自動處理**：pip 會自動安裝所有依賴
✅ **程式碼隔離**：保持 Chip Whisperer 程式碼庫清爽
✅ **官方支援**：可以獲得原作者的更新和修復

#### 缺點
❌ **網路依賴**：需要 PyPI 連線（可透過本地安裝緩解）
❌ **客製化受限**：如需修改核心功能較困難

#### 實作步驟

**步驟 1：建立虛擬環境與安裝套件**

```bash
# 在 Chip Whisperer 專案根目錄
cd C:\Users\fatfi\works\chip-whisperer

# 建立虛擬環境（如果尚未建立）
python -m venv venv

# 啟動虛擬環境
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

# 安裝 metatrader-mcp-server
pip install metatrader-mcp-server
```

**步驟 2：建立設定檔目錄和檔案**

```bash
# 建立設定檔目錄
mkdir config

# 建立 MT5 設定檔
```

**檔案**：`config/mt5_config.yaml`

```yaml
# MT5 連線設定
mt5:
  # 必要參數
  login: 12345678                # 您的 MT5 帳號
  password: "your_password"      # 您的 MT5 密碼
  server: "MetaQuotes-Demo"      # 伺服器名稱

  # 選用參數
  path: null                     # MT5 路徑（null = 自動偵測）
  timeout: 60000                 # 連線逾時（毫秒）
  portable: false                # 可攜式模式
  debug: false                   # 除錯模式

  # 重試設定
  max_retries: 3                 # 最大重試次數
  backoff_factor: 1.5            # 重試延遲倍數
  cooldown_time: 2.0             # 連線間隔（秒）

# 資料取得設定
data:
  # 預設商品列表
  default_symbols:
    - "GOLD"      # 黃金
    - "BRENT"      # 原油
    - "COPPER"      # 銅

  # 預設時間週期
  default_timeframe: "H1"

  # 資料快取設定
  cache:
    enabled: true
    directory: "data/cache"
    max_age_hours: 24
```

**檔案**：`config/.env.example`（環境變數範本）

```bash
# MT5 連線憑證（敏感資訊，請勿提交到 Git）
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=MetaQuotes-Demo

# 選用：MT5 路徑（留空則自動偵測）
# MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# 應用程式設定
DEBUG=false
LOG_LEVEL=INFO

# 資料儲存路徑
DATA_DIR=data
CACHE_DIR=data/cache
```

**步驟 3：建立核心整合模組**

**檔案**：`src/mt5_integration/__init__.py`

```python
"""
MT5 Integration Module

提供 Chip Whisperer 與 MetaTrader 5 的整合介面
"""

from .client import ChipWhispererMT5Client
from .data_fetcher import HistoricalDataFetcher
from .config import MT5Config

__all__ = [
    'ChipWhispererMT5Client',
    'HistoricalDataFetcher',
    'MT5Config',
]
```

**檔案**：`src/mt5_integration/config.py`

```python
"""
MT5 設定管理模組
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
from dotenv import load_dotenv


class MT5Config:
    """
    MT5 設定管理類別

    支援從以下來源載入設定（優先順序由高到低）：
    1. 環境變數
    2. .env 檔案
    3. YAML 設定檔
    4. 預設值
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化設定管理器

        Args:
            config_path: YAML 設定檔路徑（預設：config/mt5_config.yaml）
        """
        self.config_path = config_path or "config/mt5_config.yaml"
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """載入設定"""
        # 1. 載入 .env 檔案
        load_dotenv()

        # 2. 載入 YAML 設定檔
        yaml_config = {}
        if Path(self.config_path).exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f) or {}

        # 3. 合併設定（環境變數優先）
        mt5_config = yaml_config.get('mt5', {})

        return {
            'login': int(os.getenv('MT5_LOGIN', mt5_config.get('login', 0))),
            'password': os.getenv('MT5_PASSWORD', mt5_config.get('password', '')),
            'server': os.getenv('MT5_SERVER', mt5_config.get('server', '')),
            'path': os.getenv('MT5_PATH', mt5_config.get('path')),
            'timeout': int(os.getenv('MT5_TIMEOUT', mt5_config.get('timeout', 60000))),
            'portable': os.getenv('MT5_PORTABLE', str(mt5_config.get('portable', False))).lower() == 'true',
            'debug': os.getenv('DEBUG', str(mt5_config.get('debug', False))).lower() == 'true',
            'max_retries': int(os.getenv('MT5_MAX_RETRIES', mt5_config.get('max_retries', 3))),
            'backoff_factor': float(os.getenv('MT5_BACKOFF_FACTOR', mt5_config.get('backoff_factor', 1.5))),
            'cooldown_time': float(os.getenv('MT5_COOLDOWN_TIME', mt5_config.get('cooldown_time', 2.0))),
        }

    def get_connection_config(self) -> Dict[str, Any]:
        """
        取得 MT5Client 所需的連線設定

        Returns:
            Dict: 連線設定字典
        """
        return self._config

    def validate(self) -> bool:
        """
        驗證設定是否完整

        Returns:
            bool: 設定是否有效

        Raises:
            ValueError: 必要設定缺失時
        """
        required_fields = ['login', 'password', 'server']
        missing_fields = [field for field in required_fields if not self._config.get(field)]

        if missing_fields:
            raise ValueError(f"缺少必要的 MT5 設定欄位: {', '.join(missing_fields)}")

        return True

    def __repr__(self) -> str:
        """字串表示（隱藏敏感資訊）"""
        safe_config = self._config.copy()
        safe_config['password'] = '***' if safe_config.get('password') else ''
        return f"MT5Config({safe_config})"
```

**檔案**：`src/mt5_integration/client.py`

```python
"""
Chip Whisperer MT5 客戶端封裝
"""

from typing import Optional
import logging
from metatrader_client import MT5Client
from metatrader_client.exceptions import (
    ConnectionError,
    InitializationError,
    LoginError,
)

from .config import MT5Config


logger = logging.getLogger(__name__)


class ChipWhispererMT5Client:
    """
    Chip Whisperer 專用的 MT5 客戶端封裝

    提供簡化的介面和額外的錯誤處理
    """

    def __init__(self, config: Optional[MT5Config] = None):
        """
        初始化客戶端

        Args:
            config: MT5 設定物件（若為 None 則使用預設設定）
        """
        self.config = config or MT5Config()
        self.config.validate()

        self._client: Optional[MT5Client] = None
        self._connected = False

    def connect(self) -> bool:
        """
        連線到 MT5

        Returns:
            bool: 連線是否成功

        Raises:
            ConnectionError: 連線失敗時
        """
        try:
            logger.info("正在連線到 MT5...")

            # 建立 MT5Client 實例
            self._client = MT5Client(config=self.config.get_connection_config())

            # 執行連線
            result = self._client.connect()

            if result:
                self._connected = True
                logger.info("MT5 連線成功")

                # 顯示帳戶資訊
                account_info = self._client.account.get_trade_statistics()
                logger.info(f"帳戶餘額: {account_info.get('balance')} {account_info.get('currency')}")
            else:
                logger.error("MT5 連線失敗")

            return result

        except (InitializationError, LoginError) as e:
            logger.error(f"MT5 連線錯誤: {e}")
            raise ConnectionError(f"無法連線到 MT5: {e}") from e

    def disconnect(self) -> bool:
        """
        斷開 MT5 連線

        Returns:
            bool: 斷線是否成功
        """
        if self._client:
            result = self._client.disconnect()
            self._connected = False
            logger.info("已斷開 MT5 連線")
            return result
        return True

    def is_connected(self) -> bool:
        """
        檢查連線狀態

        Returns:
            bool: 是否已連線
        """
        if self._client:
            return self._client.is_connected()
        return False

    @property
    def client(self) -> MT5Client:
        """
        取得底層的 MT5Client 實例

        Returns:
            MT5Client: MT5 客戶端實例

        Raises:
            RuntimeError: 尚未連線時
        """
        if not self._client:
            raise RuntimeError("尚未建立 MT5 連線，請先呼叫 connect()")
        return self._client

    def __enter__(self):
        """支援 context manager（with 語句）"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """自動斷線"""
        self.disconnect()
```

**檔案**：`src/mt5_integration/data_fetcher.py`

```python
"""
歷史資料取得模組
"""

from typing import Optional, List
from datetime import datetime, timedelta
import pandas as pd
import logging
from pathlib import Path

from metatrader_client.exceptions import (
    SymbolNotFoundError,
    InvalidTimeframeError,
    MarketDataError,
)

from .client import ChipWhispererMT5Client


logger = logging.getLogger(__name__)


class HistoricalDataFetcher:
    """
    歷史 K 線資料取得器

    提供多種方式取得和管理歷史 K 線資料
    """

    def __init__(self, client: ChipWhispererMT5Client, cache_dir: Optional[str] = None):
        """
        初始化資料取得器

        Args:
            client: MT5 客戶端實例
            cache_dir: 快取目錄路徑（可選）
        """
        self.client = client
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/cache")

        # 建立快取目錄
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        count: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        取得 K 線資料（統一介面）

        Args:
            symbol: 商品代碼（例如 'GOLD'）
            timeframe: 時間週期（例如 'H1', 'D1'）
            from_date: 起始日期（格式：'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM'）
            to_date: 結束日期（格式：'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM'）
            count: 取得數量（如果指定，忽略日期參數）

        Returns:
            pd.DataFrame: K 線資料

        Raises:
            SymbolNotFoundError: 商品不存在
            InvalidTimeframeError: 時間週期無效
            MarketDataError: 資料取得失敗
        """
        try:
            if count:
                # 使用數量方式取得
                logger.info(f"取得 {symbol} {timeframe} 最新 {count} 根 K 線")
                df = self.client.client.market.get_candles_latest(
                    symbol_name=symbol,
                    timeframe=timeframe,
                    count=count
                )
            else:
                # 使用日期範圍方式取得
                logger.info(f"取得 {symbol} {timeframe} K 線資料: {from_date} ~ {to_date}")
                df = self.client.client.market.get_candles_by_date(
                    symbol_name=symbol,
                    timeframe=timeframe,
                    from_date=from_date,
                    to_date=to_date
                )

            logger.info(f"成功取得 {len(df)} 根 K 線")
            return df

        except SymbolNotFoundError:
            logger.error(f"商品不存在: {symbol}")
            raise
        except InvalidTimeframeError:
            logger.error(f"無效的時間週期: {timeframe}")
            raise
        except MarketDataError as e:
            logger.error(f"資料取得失敗: {e}")
            raise

    def get_latest_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 100
    ) -> pd.DataFrame:
        """
        取得最新的 N 根 K 線

        Args:
            symbol: 商品代碼
            timeframe: 時間週期
            count: 取得數量（預設 100）

        Returns:
            pd.DataFrame: K 線資料
        """
        return self.get_candles(symbol, timeframe, count=count)

    def get_candles_by_date_range(
        self,
        symbol: str,
        timeframe: str,
        from_date: str,
        to_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        取得指定日期範圍的 K 線

        Args:
            symbol: 商品代碼
            timeframe: 時間週期
            from_date: 起始日期
            to_date: 結束日期（預設為今天）

        Returns:
            pd.DataFrame: K 線資料
        """
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        return self.get_candles(symbol, timeframe, from_date, to_date)

    def get_candles_last_n_days(
        self,
        symbol: str,
        timeframe: str,
        days: int = 30
    ) -> pd.DataFrame:
        """
        取得最近 N 天的 K 線資料

        Args:
            symbol: 商品代碼
            timeframe: 時間週期
            days: 天數（預設 30 天）

        Returns:
            pd.DataFrame: K 線資料
        """
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        return self.get_candles(
            symbol,
            timeframe,
            from_date.strftime("%Y-%m-%d"),
            to_date.strftime("%Y-%m-%d")
        )

    def save_to_csv(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        suffix: str = ""
    ) -> Path:
        """
        儲存 K 線資料到 CSV

        Args:
            df: K 線資料
            symbol: 商品代碼
            timeframe: 時間週期
            suffix: 檔名後綴（可選）

        Returns:
            Path: 儲存的檔案路徑
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{symbol}_{timeframe}_{timestamp}"
        if suffix:
            filename += f"_{suffix}"
        filename += ".csv"

        filepath = self.cache_dir / filename
        df.to_csv(filepath, index=False)
        logger.info(f"K 線資料已儲存至: {filepath}")

        return filepath

    def load_from_csv(self, filepath: str) -> pd.DataFrame:
        """
        從 CSV 載入 K 線資料

        Args:
            filepath: CSV 檔案路徑

        Returns:
            pd.DataFrame: K 線資料
        """
        df = pd.read_csv(filepath)
        df['time'] = pd.to_datetime(df['time'])
        logger.info(f"已從 {filepath} 載入 {len(df)} 根 K 線")
        return df

    def get_multiple_symbols(
        self,
        symbols: List[str],
        timeframe: str,
        **kwargs
    ) -> dict:
        """
        一次取得多個商品的 K 線資料

        Args:
            symbols: 商品代碼列表
            timeframe: 時間週期
            **kwargs: 傳遞給 get_candles 的其他參數

        Returns:
            dict: {商品代碼: DataFrame} 的字典
        """
        results = {}

        for symbol in symbols:
            try:
                logger.info(f"正在取得 {symbol} 的資料...")
                df = self.get_candles(symbol, timeframe, **kwargs)
                results[symbol] = df
            except Exception as e:
                logger.error(f"取得 {symbol} 資料時發生錯誤: {e}")
                results[symbol] = None

        return results
```

**步驟 4：建立使用範例**

**檔案**：`examples/fetch_historical_data.py`

```python
"""
範例：取得歷史 K 線資料

示範如何使用 Chip Whisperer MT5 整合模組取得歷史資料
"""

import logging
from src.mt5_integration import ChipWhispererMT5Client, HistoricalDataFetcher, MT5Config


# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_1_basic_usage():
    """範例 1：基本用法 - 取得最新 K 線"""
    print("\n" + "="*60)
    print("範例 1：基本用法 - 取得最新 100 根 H1 K 線")
    print("="*60)

    # 使用 context manager 自動管理連線
    with ChipWhispererMT5Client() as client:
        # 建立資料取得器
        fetcher = HistoricalDataFetcher(client)

        # 取得黃金最新 100 根 H1 K 線
        df = fetcher.get_latest_candles(
            symbol="GOLD",
            timeframe="H1",
            count=100
        )

        # 顯示資料
        print(f"\n取得 {len(df)} 根 K 線")
        print("\n前 5 根 K 線:")
        print(df.head())

        print("\n資料欄位:")
        print(df.columns.tolist())

        print("\n基本統計:")
        print(df[['open', 'high', 'low', 'close', 'tick_volume']].describe())


def example_2_date_range():
    """範例 2：取得指定日期範圍的資料"""
    print("\n" + "="*60)
    print("範例 2：取得 2024 年 1 月的 D1 K 線")
    print("="*60)

    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 取得 2024 年 1 月的日線資料
        df = fetcher.get_candles_by_date_range(
            symbol="GOLD",
            timeframe="D1",
            from_date="2024-01-01",
            to_date="2024-01-31"
        )

        print(f"\n取得 {len(df)} 根日 K 線")
        print(df[['time', 'open', 'high', 'low', 'close', 'tick_volume']])


def example_3_last_n_days():
    """範例 3：取得最近 N 天的資料"""
    print("\n" + "="*60)
    print("範例 3：取得最近 7 天的 H4 K 線")
    print("="*60)

    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 取得最近 7 天的 H4 K 線
        df = fetcher.get_candles_last_n_days(
            symbol="GOLD",
            timeframe="H4",
            days=7
        )

        print(f"\n取得 {len(df)} 根 H4 K 線")
        print(df[['time', 'close']].tail(10))


def example_4_multiple_symbols():
    """範例 4：一次取得多個商品的資料"""
    print("\n" + "="*60)
    print("範例 4：取得多個商品的最新資料")
    print("="*60)

    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 定義要取得的商品
        symbols = ["GOLD", "BRENT", "SILVER"]

        # 一次取得多個商品的資料
        results = fetcher.get_multiple_symbols(
            symbols=symbols,
            timeframe="H1",
            count=50
        )

        # 顯示結果
        for symbol, df in results.items():
            if df is not None:
                latest_price = df.iloc[0]['close']
                print(f"\n{symbol}: {len(df)} 根 K 線, 最新價格: {latest_price}")


def example_5_save_to_csv():
    """範例 5：儲存資料到 CSV"""
    print("\n" + "="*60)
    print("範例 5：取得資料並儲存到 CSV")
    print("="*60)

    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 取得資料
        df = fetcher.get_latest_candles(
            symbol="GOLD",
            timeframe="H1",
            count=200
        )

        # 儲存到 CSV
        filepath = fetcher.save_to_csv(
            df=df,
            symbol="GOLD",
            timeframe="H1",
            suffix="example"
        )

        print(f"\n資料已儲存至: {filepath}")


def example_6_custom_config():
    """範例 6：使用自訂設定"""
    print("\n" + "="*60)
    print("範例 6：使用自訂設定檔")
    print("="*60)

    # 載入自訂設定
    config = MT5Config(config_path="config/mt5_config.yaml")

    # 驗證設定
    try:
        config.validate()
        print("設定驗證成功")
        print(f"設定內容: {config}")
    except ValueError as e:
        print(f"設定驗證失敗: {e}")
        return

    # 使用自訂設定建立客戶端
    with ChipWhispererMT5Client(config=config) as client:
        fetcher = HistoricalDataFetcher(client)

        df = fetcher.get_latest_candles("GOLD", "H1", 10)
        print(f"\n成功取得 {len(df)} 根 K 線")


def example_7_error_handling():
    """範例 7：錯誤處理示範"""
    print("\n" + "="*60)
    print("範例 7：錯誤處理")
    print("="*60)

    from metatrader_client.exceptions import (
        SymbolNotFoundError,
        InvalidTimeframeError,
        MarketDataError,
    )

    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 測試 1：無效商品
        try:
            print("\n測試 1：嘗試取得不存在的商品...")
            df = fetcher.get_latest_candles("INVALID_SYMBOL", "H1", 10)
        except SymbolNotFoundError as e:
            print(f"✓ 成功捕獲例外: {e}")

        # 測試 2：無效時間週期
        try:
            print("\n測試 2：嘗試使用無效的時間週期...")
            df = fetcher.get_latest_candles("GOLD", "INVALID_TF", 10)
        except InvalidTimeframeError as e:
            print(f"✓ 成功捕獲例外: {e}")

        # 測試 3：正常取得
        try:
            print("\n測試 3：正常取得資料...")
            df = fetcher.get_latest_candles("GOLD", "H1", 10)
            print(f"✓ 成功取得 {len(df)} 根 K 線")
        except Exception as e:
            print(f"✗ 發生錯誤: {e}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Chip Whisperer - MT5 歷史資料取得範例")
    print("="*60)

    # 執行所有範例
    try:
        example_1_basic_usage()
        example_2_date_range()
        example_3_last_n_days()
        example_4_multiple_symbols()
        example_5_save_to_csv()
        example_6_custom_config()
        example_7_error_handling()

        print("\n" + "="*60)
        print("所有範例執行完畢！")
        print("="*60)

    except Exception as e:
        logger.error(f"執行範例時發生錯誤: {e}", exc_info=True)
```

**步驟 5：建立 requirements.txt**

**檔案**：`requirements.txt`

```txt
# MT5 整合
metatrader-mcp-server>=0.2.9

# 資料處理
pandas>=2.2.0
numpy>=1.24.0

# 設定管理
python-dotenv>=1.0.0
PyYAML>=6.0

# 視覺化（根據 README 需求）
matplotlib>=3.7.0
plotly>=5.18.0

# 量價分析（待實作）
# scipy>=1.11.0
# scikit-learn>=1.3.0

# 開發工具
pytest>=7.4.0
black>=23.0.0
flake8>=6.0.0
mypy>=1.5.0

# 文檔
sphinx>=7.0.0
sphinx-rtd-theme>=1.3.0
```

**步驟 6：更新 .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# 虛擬環境
venv/
env/
ENV/
.venv/

# MT5 敏感資訊
config/.env
config/mt5_config.yaml
*.env

# 資料快取
data/
data/cache/
*.csv
*.parquet

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# 日誌
logs/
*.log

# 作業系統
.DS_Store
Thumbs.db

# 參考程式碼（整合後移除）
metatrader-mcp-server/
```

**步驟 7：建立測試檔案**

**檔案**：`tests/test_mt5_integration.py`

```python
"""
MT5 整合模組測試
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd

from src.mt5_integration import ChipWhispererMT5Client, HistoricalDataFetcher, MT5Config
from metatrader_client.exceptions import SymbolNotFoundError, InvalidTimeframeError


class TestMT5Config:
    """MT5Config 測試"""

    def test_config_from_env(self, monkeypatch):
        """測試從環境變數載入設定"""
        monkeypatch.setenv("MT5_LOGIN", "12345678")
        monkeypatch.setenv("MT5_PASSWORD", "test_password")
        monkeypatch.setenv("MT5_SERVER", "TestServer")

        config = MT5Config()
        conn_config = config.get_connection_config()

        assert conn_config['login'] == 12345678
        assert conn_config['password'] == "test_password"
        assert conn_config['server'] == "TestServer"

    def test_config_validation(self):
        """測試設定驗證"""
        config = MT5Config()

        # 應該因缺少必要欄位而失敗
        with pytest.raises(ValueError, match="缺少必要的 MT5 設定欄位"):
            config.validate()


class TestChipWhispererMT5Client:
    """ChipWhispererMT5Client 測試"""

    @patch('src.mt5_integration.client.MT5Client')
    def test_connect_success(self, mock_mt5_client):
        """測試成功連線"""
        # 模擬 MT5Client
        mock_instance = Mock()
        mock_instance.connect.return_value = True
        mock_instance.account.get_trade_statistics.return_value = {
            'balance': 10000.0,
            'currency': 'USD'
        }
        mock_mt5_client.return_value = mock_instance

        # 建立有效設定
        config = Mock()
        config.validate.return_value = True
        config.get_connection_config.return_value = {
            'login': 12345678,
            'password': 'test',
            'server': 'TestServer'
        }

        client = ChipWhispererMT5Client(config=config)
        result = client.connect()

        assert result is True
        assert client.is_connected() is True

    def test_context_manager(self):
        """測試 context manager 功能"""
        config = Mock()
        config.validate.return_value = True

        with patch('src.mt5_integration.client.MT5Client'):
            with ChipWhispererMT5Client(config=config) as client:
                # 應該自動連線
                pass
            # 離開 context 時應該自動斷線


class TestHistoricalDataFetcher:
    """HistoricalDataFetcher 測試"""

    def test_get_latest_candles(self):
        """測試取得最新 K 線"""
        # 模擬客戶端
        mock_client = Mock()
        mock_market = Mock()

        # 模擬回傳的 DataFrame
        sample_data = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=10, freq='H'),
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10,
        })

        mock_market.get_candles_latest.return_value = sample_data
        mock_client.client.market = mock_market

        fetcher = HistoricalDataFetcher(mock_client)
        df = fetcher.get_latest_candles("GOLD", "H1", 10)

        assert len(df) == 10
        assert 'time' in df.columns
        assert 'close' in df.columns

    def test_save_and_load_csv(self, tmp_path):
        """測試 CSV 儲存和載入"""
        mock_client = Mock()

        # 建立臨時快取目錄
        cache_dir = tmp_path / "cache"
        fetcher = HistoricalDataFetcher(mock_client, cache_dir=str(cache_dir))

        # 建立測試資料
        test_data = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=5, freq='H'),
            'close': [100.0, 101.0, 102.0, 103.0, 104.0],
        })

        # 儲存
        filepath = fetcher.save_to_csv(test_data, "GOLD", "H1", "test")
        assert filepath.exists()

        # 載入
        loaded_data = fetcher.load_from_csv(str(filepath))
        assert len(loaded_data) == 5
        pd.testing.assert_frame_equal(
            test_data.reset_index(drop=True),
            loaded_data.reset_index(drop=True)
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**步驟 8：建立專案文檔**

**檔案**：`docs/mt5_integration_guide.md`

```markdown
# MT5 整合使用指南

## 目錄

1. [快速開始](#快速開始)
2. [設定說明](#設定說明)
3. [基本使用](#基本使用)
4. [進階功能](#進階功能)
5. [常見問題](#常見問題)

## 快速開始

### 安裝

```bash
# 安裝依賴套件
pip install -r requirements.txt
```

### 設定 MT5 連線

1. 複製環境變數範本：
```bash
cp config/.env.example config/.env
```

2. 編輯 `config/.env`，填入您的 MT5 帳號資訊：
```bash
MT5_LOGIN=您的帳號
MT5_PASSWORD=您的密碼
MT5_SERVER=您的伺服器
```

3. （選用）複製並編輯 YAML 設定檔：
```bash
cp config/mt5_config.yaml.example config/mt5_config.yaml
```

### 第一個程式

```python
from src.mt5_integration import ChipWhispererMT5Client, HistoricalDataFetcher

# 連線到 MT5
with ChipWhispererMT5Client() as client:
    # 建立資料取得器
    fetcher = HistoricalDataFetcher(client)

    # 取得黃金最新 100 根 H1 K 線
    df = fetcher.get_latest_candles("GOLD", "H1", 100)

    # 顯示資料
    print(df.head())
```

## 設定說明

### 環境變數設定

支援的環境變數：

| 變數名稱       | 必要 | 說明             | 預設值   |
|----------------|------|------------------|----------|
| `MT5_LOGIN`    | ✓    | MT5 帳號         | -        |
| `MT5_PASSWORD` | ✓    | MT5 密碼         | -        |
| `MT5_SERVER`   | ✓    | MT5 伺服器名稱   | -        |
| `MT5_PATH`     |      | MT5 終端機路徑   | 自動偵測 |
| `MT5_TIMEOUT`  |      | 連線逾時（毫秒） | 60000    |
| `DEBUG`        |      | 除錯模式         | false    |

### YAML 設定檔

詳細的設定選項請參考 `config/mt5_config.yaml.example`。

## 基本使用

### 取得最新 K 線

```python
# 取得最新 100 根 H1 K 線
df = fetcher.get_latest_candles("GOLD", "H1", 100)
```

### 取得指定日期範圍的 K 線

```python
# 取得 2024 年 1 月的資料
df = fetcher.get_candles_by_date_range(
    symbol="GOLD",
    timeframe="D1",
    from_date="2024-01-01",
    to_date="2024-01-31"
)
```

### 取得最近 N 天的 K 線

```python
# 取得最近 30 天的 H4 K 線
df = fetcher.get_candles_last_n_days("GOLD", "H4", days=30)
```

## 進階功能

### 批次取得多個商品

```python
symbols = ["GOLD", "BRENT", "SILVER"]
results = fetcher.get_multiple_symbols(
    symbols=symbols,
    timeframe="H1",
    count=100
)

for symbol, df in results.items():
    if df is not None:
        print(f"{symbol}: {len(df)} 根 K 線")
```

### 資料快取

```python
# 取得資料
df = fetcher.get_latest_candles("GOLD", "H1", 200)

# 儲存到 CSV
filepath = fetcher.save_to_csv(df, "GOLD", "H1")

# 稍後載入
loaded_df = fetcher.load_from_csv(filepath)
```

## 常見問題

### Q: 如何確認 MT5 連線成功？

A: 使用 `is_connected()` 方法：

```python
if client.is_connected():
    print("MT5 連線正常")
else:
    print("MT5 未連線")
```

### Q: 如何處理連線錯誤？

A: 使用 try-except 捕獲例外：

```python
from metatrader_client.exceptions import ConnectionError

try:
    with ChipWhispererMT5Client() as client:
        # 您的程式碼
        pass
except ConnectionError as e:
    print(f"連線錯誤: {e}")
```

### Q: 支援哪些時間週期？

A: 支援所有 MT5 標準時間週期：
- 分鐘線：M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30
- 小時線：H1, H2, H3, H4, H6, H8, H12
- 日線：D1
- 週線：W1
- 月線：MN1

### Q: 如何處理無效的商品代碼？

A: 系統會自動拋出 `SymbolNotFoundError`：

```python
from metatrader_client.exceptions import SymbolNotFoundError

try:
    df = fetcher.get_latest_candles("INVALID", "H1", 10)
except SymbolNotFoundError as e:
    print(f"商品不存在: {e}")
```
```

---

### 方案一實作清單

完成以上步驟後，您的專案結構將如下：

```
chip-whisperer/
├── config/
│   ├── .env.example
│   ├── .env                    # (自行建立，不納入版本控制)
│   └── mt5_config.yaml         # (自行建立，不納入版本控制)
├── src/
│   └── mt5_integration/
│       ├── __init__.py
│       ├── client.py
│       ├── config.py
│       └── data_fetcher.py
├── examples/
│   └── fetch_historical_data.py
├── tests/
│   └── test_mt5_integration.py
├── docs/
│   └── mt5_integration_guide.md
├── data/
│   └── cache/                  # (自動建立)
├── requirements.txt
├── .gitignore
└── README.md
```

---

### 方案二：複製核心程式碼（不推薦）

如果因特殊需求必須將程式碼內嵌到專案中，可採用此方案。

#### 優點
✅ **完全自主**：可自由修改程式碼
✅ **無外部依賴**：不依賴 PyPI
✅ **客製化容易**：可針對專案需求調整

#### 缺點
❌ **維護負擔**：需要自行追蹤上游更新
❌ **程式碼膨脹**：增加專案大小
❌ **重複造輪子**：浪費開發時間
❌ **授權問題**：需確保符合 MIT 授權要求

#### 實作概要

1. 僅複製核心 `metatrader_client` 模組到 `src/external/metatrader_client/`
2. 不包含 MCP Server 和 OpenAPI 部分
3. 修改 import 路徑
4. 確保在專案中註明原始來源和授權

**不推薦此方案，除非有明確的客製化需求。**

---

## 程式碼參考

### K 線資料欄位說明

從 MT5 取得的 K 線資料 DataFrame 包含以下欄位：

| 欄位          | 型別     | 說明                       |
|---------------|----------|----------------------------|
| `time`        | datetime | K 線時間（UTC 時區）       |
| `open`        | float    | 開盤價                     |
| `high`        | float    | 最高價                     |
| `low`         | float    | 最低價                     |
| `close`       | float    | 收盤價                     |
| `tick_volume` | int      | 跳動次數（Tick 數量）      |
| `spread`      | int      | 買賣價差（點數）           |
| `real_volume` | int      | 實際成交量（如果券商提供） |

**範例資料**：

```
                           time      open      high       low     close  tick_volume  spread  real_volume
0 2024-12-30 14:00:00+00:00  2634.50  2635.20  2633.80  2634.90        1523       3            0
1 2024-12-30 13:00:00+00:00  2633.20  2634.60  2632.90  2634.50        1842       3            0
2 2024-12-30 12:00:00+00:00  2632.80  2633.50  2632.10  2633.20        1654       3            0
...
```

### 完整的 Demo 程式碼

**檔案**：`examples/demo_volume_profile_data.py`

```python
"""
Demo: 為量價分析準備資料

示範如何取得適合進行 Volume Profile 分析的 K 線資料
"""

import logging
from datetime import datetime, timedelta
import pandas as pd
from src.mt5_integration import ChipWhispererMT5Client, HistoricalDataFetcher


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def prepare_volume_profile_data(
    symbol: str,
    timeframe: str,
    days_back: int = 30
) -> pd.DataFrame:
    """
    為 Volume Profile 分析準備資料

    Args:
        symbol: 商品代碼
        timeframe: 時間週期
        days_back: 回溯天數

    Returns:
        pd.DataFrame: 處理後的 K 線資料
    """
    logger.info(f"正在為 {symbol} 準備 Volume Profile 分析資料...")

    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 取得歷史資料
        df = fetcher.get_candles_last_n_days(
            symbol=symbol,
            timeframe=timeframe,
            days=days_back
        )

        # 資料處理
        df = df.sort_values('time', ascending=True)  # 從舊到新排序
        df['price_range'] = df['high'] - df['low']
        df['body_size'] = abs(df['close'] - df['open'])
        df['is_bullish'] = df['close'] > df['open']

        # 計算價格區間（用於 Volume Profile 分格）
        price_min = df['low'].min()
        price_max = df['high'].max()
        df['price_normalized'] = (df['close'] - price_min) / (price_max - price_min)

        logger.info(f"資料準備完成：{len(df)} 根 K 線")
        logger.info(f"價格範圍: {price_min:.2f} ~ {price_max:.2f}")
        logger.info(f"總成交量: {df['tick_volume'].sum()}")

        return df


def analyze_volume_distribution(df: pd.DataFrame, bins: int = 20):
    """
    分析成交量分布（簡化版 Volume Profile）

    Args:
        df: K 線資料
        bins: 價格區間數量

    Returns:
        pd.DataFrame: 成交量分布統計
    """
    logger.info(f"分析成交量分布（{bins} 個價格區間）...")

    # 建立價格區間
    price_min = df['low'].min()
    price_max = df['high'].max()
    price_bins = pd.cut(
        df['close'],
        bins=bins,
        labels=False
    )

    # 計算每個價格區間的成交量
    df['price_bin'] = price_bins
    volume_dist = df.groupby('price_bin').agg({
        'tick_volume': 'sum',
        'close': ['min', 'max', 'mean'],
        'time': 'count'
    }).reset_index()

    volume_dist.columns = ['price_bin', 'total_volume', 'price_min', 'price_max', 'price_mean', 'bar_count']
    volume_dist = volume_dist.sort_values('total_volume', ascending=False)

    # 找出 POC (Point of Control) - 成交量最大的價格區間
    poc_idx = volume_dist.iloc[0]['price_bin']
    poc_price = volume_dist.iloc[0]['price_mean']

    logger.info(f"POC (Point of Control): 價格區間 {poc_idx}, 平均價格 {poc_price:.2f}")
    logger.info(f"該區間成交量: {volume_dist.iloc[0]['total_volume']}")

    return volume_dist


def calculate_value_area(volume_dist: pd.DataFrame, percentage: float = 0.7):
    """
    計算 Value Area（70% 成交量集中的價格區間）

    Args:
        volume_dist: 成交量分布資料
        percentage: 成交量百分比（預設 0.7 = 70%）

    Returns:
        tuple: (value_area_high, value_area_low, 涵蓋的價格區間列表)
    """
    logger.info(f"計算 Value Area（{percentage*100}% 成交量）...")

    total_volume = volume_dist['total_volume'].sum()
    target_volume = total_volume * percentage

    # 從成交量最大的區間開始累積
    volume_dist_sorted = volume_dist.sort_values('total_volume', ascending=False)

    accumulated_volume = 0
    value_area_bins = []

    for _, row in volume_dist_sorted.iterrows():
        accumulated_volume += row['total_volume']
        value_area_bins.append(row['price_bin'])

        if accumulated_volume >= target_volume:
            break

    # 找出 Value Area 的高低點
    value_area_prices = volume_dist[volume_dist['price_bin'].isin(value_area_bins)]
    value_area_high = value_area_prices['price_max'].max()
    value_area_low = value_area_prices['price_min'].min()

    logger.info(f"Value Area High: {value_area_high:.2f}")
    logger.info(f"Value Area Low: {value_area_low:.2f}")
    logger.info(f"涵蓋 {len(value_area_bins)} 個價格區間")

    return value_area_high, value_area_low, value_area_bins


def main():
    """主程式"""
    print("\n" + "="*70)
    print("Chip Whisperer - Volume Profile 資料分析 Demo")
    print("="*70)

    # 設定參數
    SYMBOL = "GOLD"          # 黃金
    TIMEFRAME = "H1"           # 1 小時線
    DAYS_BACK = 30             # 回溯 30 天
    PRICE_BINS = 20            # 20 個價格區間

    # 步驟 1：取得並準備資料
    print("\n步驟 1：取得歷史 K 線資料")
    print("-" * 70)
    df = prepare_volume_profile_data(SYMBOL, TIMEFRAME, DAYS_BACK)

    # 顯示基本統計
    print(f"\n資料統計:")
    print(f"  時間範圍: {df['time'].min()} ~ {df['time'].max()}")
    print(f"  K 線數量: {len(df)}")
    print(f"  價格範圍: {df['low'].min():.2f} ~ {df['high'].max():.2f}")
    print(f"  平均成交量: {df['tick_volume'].mean():.0f}")

    # 步驟 2：分析成交量分布
    print(f"\n步驟 2：分析成交量分布（{PRICE_BINS} 個價格區間）")
    print("-" * 70)
    volume_dist = analyze_volume_distribution(df, bins=PRICE_BINS)

    # 顯示成交量分布前 5 名
    print("\n成交量最大的 5 個價格區間:")
    print(volume_dist.head(5).to_string(index=False))

    # 步驟 3：計算 Value Area
    print("\n步驟 3：計算 Value Area (70% 成交量區間)")
    print("-" * 70)
    va_high, va_low, va_bins = calculate_value_area(volume_dist, percentage=0.7)

    # 步驟 4：儲存結果
    print("\n步驟 4：儲存分析結果")
    print("-" * 70)

    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 儲存原始 K 線資料
        candles_path = fetcher.save_to_csv(
            df,
            SYMBOL,
            TIMEFRAME,
            f"vp_data_{DAYS_BACK}days"
        )
        print(f"K 線資料已儲存: {candles_path}")

        # 儲存成交量分布
        volume_dist_path = fetcher.cache_dir / f"{SYMBOL}_{TIMEFRAME}_volume_distribution.csv"
        volume_dist.to_csv(volume_dist_path, index=False)
        print(f"成交量分布已儲存: {volume_dist_path}")

    # 最終摘要
    print("\n" + "="*70)
    print("分析完成！關鍵指標摘要：")
    print("="*70)
    print(f"商品: {SYMBOL}")
    print(f"時間週期: {TIMEFRAME}")
    print(f"分析期間: {DAYS_BACK} 天")
    print(f"K 線數量: {len(df)}")
    print(f"POC 價格: {volume_dist.iloc[0]['price_mean']:.2f}")
    print(f"Value Area High: {va_high:.2f}")
    print(f"Value Area Low: {va_low:.2f}")
    print(f"Value Area 範圍: {va_high - va_low:.2f}")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"執行過程中發生錯誤: {e}", exc_info=True)
```

---

## 實作步驟總結

### Phase 1：環境準備（1 小時）

1. ✅ 安裝 Python 3.10+ 和虛擬環境
2. ✅ 安裝 metatrader-mcp-server 套件
3. ✅ 安裝 MT5 終端機並啟用演算法交易
4. ✅ 建立設定檔目錄和範本

### Phase 2：核心整合開發（3-4 小時）

1. ✅ 實作 `MT5Config` 類別
2. ✅ 實作 `ChipWhispererMT5Client` 類別
3. ✅ 實作 `HistoricalDataFetcher` 類別
4. ✅ 撰寫單元測試

### Phase 3：範例與文檔（2-3 小時）

1. ✅ 撰寫基本使用範例
2. ✅ 撰寫 Volume Profile Demo
3. ✅ 撰寫整合指南文檔
4. ✅ 更新專案 README

### Phase 4：測試與驗證（1-2 小時）

1. ⬜ 使用 MT5 模擬帳戶測試連線
2. ⬜ 驗證資料取得功能
3. ⬜ 測試錯誤處理
4. ⬜ 執行所有範例程式

### Phase 5：清理與優化（1 小時）

1. ⬜ 移除 `metatrader-mcp-server/` 參考目錄
2. ⬜ 更新 `.gitignore`
3. ⬜ 確認敏感資訊不被提交
4. ⬜ 執行程式碼格式化和 linting

**預估總時間**：8-11 小時

---

## 測試與驗證方法

### 1. 連線測試

```python
# test_connection.py
from src.mt5_integration import ChipWhispererMT5Client

def test_connection():
    """測試 MT5 連線"""
    try:
        with ChipWhispererMT5Client() as client:
            print("✓ 連線成功")

            # 顯示帳戶資訊
            stats = client.client.account.get_trade_statistics()
            print(f"✓ 帳戶餘額: {stats['balance']} {stats['currency']}")

            return True
    except Exception as e:
        print(f"✗ 連線失敗: {e}")
        return False

if __name__ == "__main__":
    test_connection()
```

### 2. 資料取得測試

```python
# test_data_fetch.py
from src.mt5_integration import ChipWhispererMT5Client, HistoricalDataFetcher

def test_data_fetch():
    """測試資料取得功能"""
    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 測試 1：取得最新資料
        print("測試 1：取得最新 10 根 H1 K 線")
        df = fetcher.get_latest_candles("GOLD", "H1", 10)
        assert len(df) == 10
        print(f"✓ 成功取得 {len(df)} 根 K 線")

        # 測試 2：取得日期範圍資料
        print("\n測試 2：取得指定日期範圍資料")
        df = fetcher.get_candles_by_date_range(
            "GOLD", "D1", "2024-01-01", "2024-01-31"
        )
        print(f"✓ 成功取得 {len(df)} 根日 K 線")

        # 測試 3：儲存和載入
        print("\n測試 3：儲存和載入 CSV")
        path = fetcher.save_to_csv(df, "GOLD", "D1", "test")
        loaded_df = fetcher.load_from_csv(str(path))
        assert len(loaded_df) == len(df)
        print(f"✓ 成功儲存和載入，資料筆數一致")

        print("\n所有測試通過！")

if __name__ == "__main__":
    test_data_fetch()
```

### 3. 錯誤處理測試

```python
# test_error_handling.py
from src.mt5_integration import ChipWhispererMT5Client, HistoricalDataFetcher
from metatrader_client.exceptions import SymbolNotFoundError, InvalidTimeframeError

def test_error_handling():
    """測試錯誤處理"""
    with ChipWhispererMT5Client() as client:
        fetcher = HistoricalDataFetcher(client)

        # 測試 1：無效商品
        try:
            fetcher.get_latest_candles("INVALID_SYMBOL", "H1", 10)
            print("✗ 應該拋出 SymbolNotFoundError")
        except SymbolNotFoundError:
            print("✓ 正確捕獲 SymbolNotFoundError")

        # 測試 2：無效時間週期
        try:
            fetcher.get_latest_candles("GOLD", "INVALID_TF", 10)
            print("✗ 應該拋出 InvalidTimeframeError")
        except InvalidTimeframeError:
            print("✓ 正確捕獲 InvalidTimeframeError")

        print("\n錯誤處理測試通過！")

if __name__ == "__main__":
    test_error_handling()
```

---

## 相關文件

### 專案內部文件

- `docs/mt5_integration_guide.md` - MT5 整合使用指南
- `examples/fetch_historical_data.py` - 基本使用範例
- `examples/demo_volume_profile_data.py` - Volume Profile 資料準備示範
- `config/mt5_config.yaml` - 設定檔範本

### 外部文件

- [metatrader-mcp-server GitHub](https://github.com/ariadng/metatrader-mcp-server)
- [metatrader-mcp-server PyPI](https://pypi.org/project/metatrader-mcp-server/)
- [MetaTrader 5 Python 文檔](https://www.mql5.com/en/docs/python_metatrader5)
- [Model Context Protocol 規範](https://spec.modelcontextprotocol.io/)

---

## 開放問題與後續研究

### 1. 效能最佳化

**問題**：大量歷史資料取得時的效能瓶頸？

**待研究**：
- 批次資料取得策略
- 資料快取機制優化
- 多執行緒/非同步資料取得

### 2. 資料品質

**問題**：如何處理資料缺失或異常值？

**待研究**：
- 資料驗證機制
- 異常值偵測和處理
- 資料補全策略

### 3. 即時資料

**問題**：如何整合即時報價和歷史資料？

**待研究**：
- WebSocket 即時資料流
- 資料更新策略
- 即時 Volume Profile 計算

### 4. 多商品支援

**問題**：如何有效管理多個商品的資料？

**待研究**：
- 資料庫整合（SQLite, PostgreSQL）
- 資料版本控制
- 跨商品分析

### 5. 客製化時間週期

**問題**：如何支援非標準時間週期（例如 15 分鐘的倍數）？

**待研究**：
- K 線重採樣技術
- 自訂時間週期實作
- 資料聚合策略

---

## 附錄：技術細節

### A. MT5 API 方法對應表

| 功能               | MT5 API 方法            | metatrader_client 封裝         |
|--------------------|-------------------------|--------------------------------|
| 取得最新 N 根 K 線 | `copy_rates_from_pos()` | `get_candles_latest()`         |
| 取得日期範圍 K 線  | `copy_rates_range()`    | `get_candles_by_date()`        |
| 從指定日期開始取得 | `copy_rates_from()`     | 包含在 `get_candles_by_date()` |
| 取得商品列表       | `symbols_get()`         | `get_symbols()`                |
| 取得商品資訊       | `symbol_info()`         | `get_symbol_info()`            |
| 取得即時報價       | `symbol_info_tick()`    | `get_symbol_price()`           |

### B. 時間週期常數對應

| 字串 | MT5 常數      | 說明    | 典型用途   |
|------|---------------|---------|------------|
| M1   | TIMEFRAME_M1  | 1 分鐘  | 超短線交易 |
| M5   | TIMEFRAME_M5  | 5 分鐘  | 短線交易   |
| M15  | TIMEFRAME_M15 | 15 分鐘 | 短線交易   |
| M30  | TIMEFRAME_M30 | 30 分鐘 | 日內交易   |
| H1   | TIMEFRAME_H1  | 1 小時  | 日內交易   |
| H4   | TIMEFRAME_H4  | 4 小時  | 波段交易   |
| D1   | TIMEFRAME_D1  | 日線    | 中長線交易 |
| W1   | TIMEFRAME_W1  | 週線    | 長線交易   |
| MN1  | TIMEFRAME_MN1 | 月線    | 長線投資   |

### C. DataFrame 欄位型別

```python
df.dtypes

# 輸出：
# time             datetime64[ns, UTC]
# open                         float64
# high                         float64
# low                          float64
# close                        float64
# tick_volume                    int64
# spread                         int32
# real_volume                    int64
```

### D. 記憶體使用估算

假設單根 K 線約 80 bytes：

| K 線數量  | 預估記憶體 | 適用場景     |
|-----------|------------|--------------|
| 100       | ~8 KB      | 快速查詢     |
| 1,000     | ~80 KB     | 日內分析     |
| 10,000    | ~800 KB    | 週/月分析    |
| 100,000   | ~8 MB      | 年度分析     |
| 1,000,000 | ~80 MB     | 多年歷史資料 |

---

## 研究總結

### 關鍵發現

1. **metatrader-mcp-server 是一個成熟、文檔完善的套件**
   - 提供完整的 MT5 功能封裝
   - 支援多種使用方式（Python 函式庫、MCP Server、REST API）
   - 持續維護且版本更新頻繁

2. **K 線資料取得功能強大且靈活**
   - 支援多種查詢方式（日期範圍、最新 N 根）
   - 自動處理時區和日期格式
   - 完善的錯誤處理機制

3. **整合難度低**
   - 透過 pip 安裝即可使用
   - 設定簡單直觀
   - 提供豐富的範例和文檔

### 建議方案

**強烈推薦採用方案一**：將 metatrader-mcp-server 作為 Python 套件安裝使用。

**理由**：
- ✅ 維護成本低
- ✅ 可獲得官方更新支援
- ✅ 程式碼簡潔清晰
- ✅ 符合 Python 最佳實踐

### 後續步驟

1. **立即可做**：
   - 建立虛擬環境
   - 安裝 metatrader-mcp-server
   - 測試 MT5 連線
   - 執行基本範例

2. **短期目標**（1-2 週）：
   - 完成核心整合模組開發
   - 撰寫單元測試
   - 建立資料快取機制

3. **中期目標**（1 個月）：
   - 整合 Volume Profile 分析功能
   - 開發視覺化工具
   - 建立完整的資料處理流程

4. **長期目標**（2-3 個月）：
   - AI 模型整合
   - 即時資料處理
   - 完整的交易代理系統

---

## 參考資料索引

### 程式碼檔案

| 檔案路徑                                                                    | 行號範圍 | 說明                 |
|-----------------------------------------------------------------------------|----------|----------------------|
| `metatrader-mcp-server/src/metatrader_client/client.py`                     | 1-109    | MT5Client 主類別定義 |
| `metatrader-mcp-server/src/metatrader_client/client_market.py`              | 1-58     | MT5Market 類別定義   |
| `metatrader-mcp-server/src/metatrader_client/market/get_candles_by_date.py` | 1-59     | 依日期取得 K 線實作  |
| `metatrader-mcp-server/src/metatrader_client/market/get_candles_latest.py`  | 1-21     | 取得最新 K 線實作    |
| `metatrader-mcp-server/src/metatrader_client/client_connection.py`          | 1-116    | MT5 連線管理         |
| `metatrader-mcp-server/src/metatrader_client/types/timeframe.py`            | 1-79     | 時間週期定義         |
| `metatrader-mcp-server/src/metatrader_client/exceptions.py`                 | 1-187    | 例外類別定義         |
| `metatrader-mcp-server/src/metatrader_mcp/server.py`                        | 1-251    | MCP Server 實作      |
| `metatrader-mcp-server/src/metatrader_mcp/utils.py`                         | 1-41     | MCP 工具函式         |
| `metatrader-mcp-server/pyproject.toml`                                      | 1-58     | 專案設定與依賴       |

### 外部連結

- [ariadng/metatrader-mcp-server](https://github.com/ariadng/metatrader-mcp-server) - 原始專案
- [MetaTrader5 Python 套件](https://pypi.org/project/MetaTrader5/) - MT5 官方 SDK
- [pandas 文檔](https://pandas.pydata.org/docs/) - DataFrame 操作
- [Model Context Protocol](https://spec.modelcontextprotocol.io/) - MCP 規範

---

**研究完成日期**：2025-12-30
**研究者**：Claude Sonnet 4.5
**專案版本**：metatrader-mcp-server 0.2.9
**文件版本**：1.0
