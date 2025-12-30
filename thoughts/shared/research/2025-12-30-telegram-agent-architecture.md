---
title: "Telegram Bot + Claude Agent SDK + MT5 整合架構研究"
date: 2025-12-30
author: "Claude Code Researcher"
tags: ["telegram-bot", "claude-agent-sdk", "mt5", "architecture", "integration"]
status: "completed"
related_files:
  - "C:\\Users\\fatfi\\works\\chip-whisperer\\src\\core\\mt5_client.py"
  - "C:\\Users\\fatfi\\works\\chip-whisperer\\src\\core\\data_fetcher.py"
  - "C:\\Users\\fatfi\\works\\chip-whisperer\\src\\core\\mt5_config.py"
  - "C:\\Users\\fatfi\\works\\chip-whisperer\\examples\\demo_volume_profile_data.py"
last_updated: 2025-12-30
last_updated_by: "Claude Code Researcher"
---

# Telegram Bot + Claude Agent SDK + MT5 整合架構研究

## 研究問題

如何整合以下三個組件來建構完整的交易助手系統：
1. **Telegram Bot** - 接收用戶提問
2. **Claude Agent SDK** - 解析意圖並調用工具
3. **src/core 模組** - 取得 MT5 歷史數據並計算技術指標

## 執行摘要

本研究透過掃描現有程式碼庫和外部技術文件，提出了一個完整的整合架構方案。該方案將 Telegram Bot 作為前端界面，Claude Agent SDK 作為中央決策引擎，並封裝現有的 MT5 核心模組為 Agent Tools。整個系統採用非同步架構，支援長時間運算的優雅處理，並提供可擴展的技術指標計算框架。

**關鍵發現：**
- 現有 `src/core/` 模組已具備完整的 MT5 連線和資料取得功能
- Claude Agent SDK 支援透過 `@tool` 裝飾器定義自訂工具
- python-telegram-bot v20+ 採用完全非同步架構
- 建議採用三層架構：展示層（Telegram）、邏輯層（Claude Agent）、資料層（MT5 Core）

---

## 詳細研究結果

### 1. 現有程式碼分析（ANALYZER MODE）

#### 1.1 專案結構

```
chip-whisperer/
├── src/
│   └── core/                      # 核心模組
│       ├── __init__.py            # 匯出 MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher
│       ├── mt5_config.py          # 設定管理（支援 .env、YAML、程式碼配置）
│       ├── mt5_client.py          # MT5 客戶端封裝（支援 context manager）
│       └── data_fetcher.py        # 歷史資料取得器（支援多種查詢模式）
├── examples/                      # 範例程式
│   ├── fetch_historical_data.py   # 基本資料取得範例
│   └── demo_volume_profile_data.py # Volume Profile 分析範例
├── tests/                         # 測試套件
├── data/cache/                    # 資料快取目錄
├── logs/                          # 日誌檔案
├── output/                        # 分析輸出
├── requirements.txt               # 依賴套件清單
├── pyproject.toml                # 專案設定
└── .env                          # 環境變數設定（需複製 .env.example）
```

**檔案路徑：**
- 核心模組：`C:\Users\fatfi\works\chip-whisperer\src\core\`
- 範例程式：`C:\Users\fatfi\works\chip-whisperer\examples\`

#### 1.2 核心模組功能清單

##### MT5Config (C:\Users\fatfi\works\chip-whisperer\src\core\mt5_config.py)

**行數：第 1-232 行**

**主要功能：**
- 從多個來源載入設定（環境變數、.env 檔案、YAML 設定檔）
- 設定優先順序：環境變數 > .env 檔案 > YAML 設定檔 > 預設值
- 驗證設定完整性（必要欄位：login, password, server）

**關鍵方法：**
```python
# 行 24-49: 初始化
def __init__(
    self,
    env_file: Optional[str] = None,
    yaml_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None
)

# 行 124-135: 取得設定值
def get(self, key: str, default: Any = None) -> Any

# 行 137-154: 取得連線設定字典
def get_connection_config(self) -> Dict[str, Any]

# 行 156-192: 驗證設定
def validate(self) -> bool
```

**使用範例（第 175-186 行註解）：**
```python
from core import MT5Config

config = MT5Config()
config.validate()  # 驗證設定是否完整

login = config.get('login')
server = config.get('server')
timeout = config.get('timeout', 60000)  # 可設預設值
```

##### ChipWhispererMT5Client (C:\Users\fatfi\works\chip-whisperer\src\core\mt5_client.py)

**行數：第 1-233 行**

**主要功能：**
- MT5 連線管理（連線、斷線、重連）
- 支援 context manager (with 語句) 自動管理連線生命週期
- 帳戶和終端機資訊取得

**關鍵方法：**
```python
# 行 22-39: 初始化
def __init__(self, config: Optional[MT5Config] = None)

# 行 41-110: 連線到 MT5
def connect(self) -> bool

# 行 112-131: 斷開連線
def disconnect(self) -> bool

# 行 133-149: 檢查連線狀態
def is_connected(self) -> bool

# 行 151-160: 確保已連線（未連線則自動連線）
def ensure_connected(self) -> None

# 行 162-181: 取得帳戶資訊
def get_account_info(self) -> Optional[dict]

# 行 204-220: Context Manager 支援
def __enter__(self)
def __exit__(self, exc_type, exc_val, exc_tb)
```

**使用範例（第 206-217 行註解）：**
```python
from core import MT5Config, ChipWhispererMT5Client

# 方式一：手動管理連線
client = ChipWhispererMT5Client(MT5Config())
client.connect()
# ... 進行操作 ...
client.disconnect()

# 方式二：使用 context manager（推薦）
with ChipWhispererMT5Client(MT5Config()) as client:
    account_info = client.get_account_info()
    print(f"帳戶餘額：{account_info['balance']}")
```

##### HistoricalDataFetcher (C:\Users\fatfi\works\chip-whisperer\src\core\data_fetcher.py)

**行數：第 1-357 行**

**主要功能：**
- 取得歷史 K 線資料（支援多種時間週期）
- 資料快取管理（CSV、Parquet 格式）
- 商品驗證和日期解析

**支援的時間週期（第 24-47 行）：**
```python
TIMEFRAME_MAP = {
    'M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',  # 分鐘線
    'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12',                              # 小時線
    'D1', 'W1', 'MN1'                                                        # 日線、週線、月線
}
```

**關鍵方法：**
```python
# 行 152-199: 取得最新 N 根 K 線
def get_candles_latest(
    self,
    symbol: str,
    timeframe: str,
    count: int = 100
) -> pd.DataFrame

# 行 201-290: 取得指定日期範圍的 K 線
def get_candles_by_date(
    self,
    symbol: str,
    timeframe: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    default_count: int = 1000
) -> pd.DataFrame

# 行 292-326: 儲存資料到快取
def save_to_cache(
    self,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    file_format: str = 'csv'
) -> Path

# 行 328-356: 從快取載入資料
def load_from_cache(self, filepath: str) -> pd.DataFrame
```

**使用範例（第 236-255 行註解）：**
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

#### 1.3 現有範例程式分析

##### Volume Profile 計算範例 (C:\Users\fatfi\works\chip-whisperer\examples\demo_volume_profile_data.py)

**行數：第 56-168 行**

**核心函式：`calculate_volume_profile()`**

此函式展示了如何基於 K 線資料計算 Volume Profile，包含：
- POC (Point of Control)：成交量最大的價位
- VAH (Value Area High)：價值區域高點
- VAL (Value Area Low)：價值區域低點
- Value Area：涵蓋 70% 成交量的價格區間

**計算邏輯（第 72-167 行）：**
```python
def calculate_volume_profile(
    df: pd.DataFrame,
    price_bins: int = 100
) -> Tuple[pd.DataFrame, Dict]:
    """
    計算 Volume Profile

    參數：
        df: K 線資料 DataFrame
        price_bins: 價格區間數量

    回傳：
        (profile_df, metrics) 元組
        - profile_df: Volume Profile DataFrame
        - metrics: 包含 POC、VAH、VAL 的字典
    """
    # 1. 確定價格範圍（行 74-77）
    price_min = df['low'].min()
    price_max = df['high'].max()

    # 2. 建立價格區間（行 79-81）
    price_edges = np.linspace(price_min, price_max, price_bins + 1)
    price_centers = (price_edges[:-1] + price_edges[1:]) / 2

    # 3. 計算每個價格區間的成交量（行 83-100）
    volumes = np.zeros(price_bins)
    for _, row in df.iterrows():
        # 找出此 K 線涵蓋的價格區間
        # 將成交量分配到涵蓋的價格區間

    # 4. 建立 Volume Profile DataFrame（行 102-108）
    profile_df = pd.DataFrame({
        'price': price_centers,
        'volume': volumes
    })

    # 5. 計算 POC（行 110-114）
    poc_price = profile_df.iloc[0]['price']
    poc_volume = profile_df.iloc[0]['volume']

    # 6. 計算 Value Area（行 116-148）
    # 從 POC 開始向兩側擴展，直到達到 70% 成交量

    # 7. 回傳結果（行 158-167）
    metrics = {
        'poc_price': poc_price,
        'poc_volume': poc_volume,
        'vah': vah,
        'val': val,
        'value_area_volume': value_area_volume,
        'total_volume': total_volume,
        'value_area_percentage': value_area_volume / total_volume * 100
    }

    return profile_df, metrics
```

**使用範例（第 190-210 行）：**
```python
# 取得 GOLD 最近一週的 H1 資料
df = fetcher.get_candles_by_date(
    symbol='GOLD',
    timeframe='H1',
    from_date='2024-12-23',
    default_count=200
)

# 計算 Volume Profile
profile_df, metrics = calculate_volume_profile(df, price_bins=50)

# 存取結果
print(f"POC: {metrics['poc_price']:.2f}")
print(f"VAH: {metrics['vah']:.2f}")
print(f"VAL: {metrics['val']:.2f}")
```

#### 1.4 依賴套件清單

**檔案：C:\Users\fatfi\works\chip-whisperer\requirements.txt（第 1-23 行）**

```txt
# 核心依賴
MetaTrader5>=5.0.4510
pandas>=2.0.0
numpy>=1.24.0
pyyaml>=6.0
python-dotenv>=1.0.0

# 日誌和工具
loguru>=0.7.0

# 測試
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0

# 開發工具
black>=23.7.0
flake8>=6.1.0
mypy>=1.5.0
```

**需新增的套件（整合所需）：**
```txt
# Claude Agent SDK
claude-agent-sdk>=1.0.0

# Telegram Bot
python-telegram-bot>=20.0

# 非同步支援
aiohttp>=3.9.0
```

---

### 2. Claude Agent SDK 研究（EXTERNAL MODE）

#### 2.1 基本架構

**來源：** [Anthropic Engineering Blog](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)

Claude Agent SDK（前身為 Claude Code SDK）允許開發者以程式化方式建立 AI Agent，具備與 Claude Code 相同的工具、Agent Loop 和上下文管理能力。

**核心特色：**
- 內建工具（檔案操作、Bash、網路搜尋等）
- 支援 Model Context Protocol (MCP) 附加自訂外部工具
- 在進程內運作的 MCP 伺服器，無需額外的子進程
- 支援 Python 3.10+ 和 TypeScript/Node.js

#### 2.2 安裝與設定

**來源：** [Claude Agent SDK Python Reference](https://platform.claude.com/docs/en/agent-sdk/python)

```bash
# 安裝 Claude Agent SDK
pip install claude-agent-sdk

# 系統需求
# - Python 3.10+
# - Node.js 18+（某些功能需要）
```

#### 2.3 自訂工具定義方式

**來源：** [Custom Tools Documentation](https://platform.claude.com/docs/en/agent-sdk/custom-tools)

Claude Agent SDK 使用 `@tool` 裝飾器定義自訂工具，並透過 `create_sdk_mcp_server` 建立在進程內的 MCP 伺服器。

**基本模式：**

```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient
from typing import Any

# 1. 使用 @tool 裝飾器定義工具
@tool("greet", "Greet a user", {"name": str})
async def greet_user(args: dict[str, Any]) -> dict[str, Any]:
    """
    問候用戶的工具

    參數：
        args: 包含 'name' 鍵的字典

    回傳：
        包含 'content' 列表的字典
    """
    return {
        "content": [
            {"type": "text", "text": f"Hello, {args['name']}!"}
        ]
    }

# 2. 建立 SDK MCP 伺服器
server = create_sdk_mcp_server(
    name="my-tools",
    version="1.0.0",
    tools=[greet_user]
)

# 3. 在 ClaudeAgentOptions 中配置
options = ClaudeAgentOptions(
    mcp_servers={"tools": server},
    allowed_tools=["mcp__tools__greet"]  # 工具命名規則：mcp__<server_name>__<tool_name>
)

# 4. 使用 ClaudeSDKClient
async with ClaudeSDKClient(options=options) as client:
    await client.query("Greet Alice")
    async for msg in client.receive_response():
        print(msg)
```

**工具命名規則：**
- 工具名稱格式：`mcp__<server_name>__<tool_name>`
- 例如：伺服器名為 `my-custom-tools`，工具名為 `get_weather`，則完整名稱為 `mcp__my-custom-tools__get_weather`

**多個工具範例：**

```python
@tool("calculate", "Perform mathematical calculations", {"expression": str})
async def calculate(args: dict[str, Any]) -> dict[str, Any]:
    """執行數學運算"""
    try:
        result = eval(args["expression"], {"__builtins__": {}})
        return {"content": [{"type": "text", "text": f"Result: {result}"}]}
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }

@tool("get_time", "Get current time", {})
async def get_time(args: dict[str, Any]) -> dict[str, Any]:
    """取得當前時間"""
    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"content": [{"type": "text", "text": f"Current time: {current_time}"}]}

# 建立包含多個工具的伺服器
my_server = create_sdk_mcp_server(
    name="utilities",
    version="1.0.0",
    tools=[calculate, get_time]
)
```

#### 2.4 簡易查詢模式

**來源：** [DataCamp Tutorial](https://www.datacamp.com/tutorial/how-to-use-claude-agent-sdk)

對於簡單的查詢，可以使用 `query()` 函式：

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for message in query(
        prompt="Find and fix the bug in auth.py",
        options=ClaudeAgentOptions(allowed_tools=["Read", "Edit", "Bash"])
    ):
        print(message)

asyncio.run(main())
```

**內建工具列表：**
- `Read`：讀取檔案
- `Write`：寫入檔案
- `Edit`：編輯檔案
- `Bash`：執行 Bash 指令
- `WebSearch`：網路搜尋
- `Glob`：檔案模式匹配
- `Grep`：內容搜尋

#### 2.5 最佳實踐

**來源：** [Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)

1. **最小權限原則**：僅授予必要的工具權限
2. **危險操作保護**：將破壞性操作（如刪除檔案、發送郵件）放在 hooks 和審批流程後
3. **日誌記錄**：記錄工具使用、Hook 決策和錯誤，以便稽核
4. **輸出驗證**：將任何程式碼生成或檔案編輯的輸出視為需要驗證
5. **優先使用 MCP**：當需要可重用、類型良好的連接器時，優先使用 MCP 而非臨時內聯函式

---

### 3. Telegram Bot API 研究（EXTERNAL MODE）

#### 3.1 python-telegram-bot 架構

**來源：** [python-telegram-bot Official Documentation](https://python-telegram-bot.org/)

python-telegram-bot 是官方推薦的 Python Telegram Bot 套件，v20+ 版本採用完全非同步架構。

#### 3.2 基本使用模式

**來源：** [GitHub Discussion #2904](https://github.com/python-telegram-bot/python-telegram-bot/discussions/2904)

```python
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# 定義指令處理器（非同步函式）
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /start 指令"""
    await update.message.reply_text(
        f'你好 {update.effective_user.first_name}！\n'
        f'我是交易助手，可以幫你分析市場數據。\n'
        f'試試問我：「目前黃金的 H1 成本價位在哪裡？」'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /help 指令"""
    await update.message.reply_text(
        "可用指令：\n"
        "/start - 開始使用\n"
        "/help - 顯示說明\n"
        "/status - 檢查系統狀態\n\n"
        "你也可以直接問我問題，例如：\n"
        "「GOLD H1 的 POC 在哪？」"
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理一般訊息"""
    user_message = update.message.text
    # 這裡會調用 Claude Agent SDK
    await update.message.reply_text(f"收到訊息：{user_message}")

# 建立應用程式
app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

# 註冊處理器
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

# 啟動輪詢
app.run_polling()
```

#### 3.3 處理長時間運算

**來源：** 綜合分析和最佳實踐

對於需要長時間計算的請求（如取得大量歷史資料、複雜計算），有以下策略：

**策略 1：立即回應 + 狀態更新**

```python
async def long_running_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理長時間運算的請求"""
    # 立即回應用戶
    status_message = await update.message.reply_text("正在處理您的請求，請稍候...")

    try:
        # 執行長時間運算
        # 可以定期更新狀態訊息
        await status_message.edit_text("正在連接 MT5...")
        # ... MT5 連線 ...

        await status_message.edit_text("正在取得歷史資料...")
        # ... 資料取得 ...

        await status_message.edit_text("正在計算 Volume Profile...")
        # ... 計算 ...

        # 完成後更新為最終結果
        await status_message.edit_text(f"計算完成！\nPOC: {poc_price:.2f}")

    except Exception as e:
        await status_message.edit_text(f"發生錯誤：{str(e)}")
```

**策略 2：使用 asyncio.create_task**

```python
async def process_in_background(update: Update, query_text: str):
    """在背景處理請求"""
    # 執行 Claude Agent 查詢
    result = await agent_query(query_text)
    # 發送結果
    await update.message.reply_text(result)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """非同步訊息處理器"""
    await update.message.reply_text("收到您的請求，正在處理中...")

    # 在背景執行任務
    asyncio.create_task(process_in_background(update, update.message.text))
```

#### 3.4 錯誤處理

```python
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """全域錯誤處理器"""
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.message:
        await update.message.reply_text(
            "抱歉，處理您的請求時發生錯誤。\n"
            "請稍後再試，或聯繫管理員。"
        )

# 註冊錯誤處理器
app.add_error_handler(error_handler)
```

#### 3.5 替代方案：aiogram

**來源：** [aiogram Official Documentation](https://aiogram.dev/)

aiogram 是另一個流行的非同步 Telegram Bot 框架，基於 aiohttp。

```python
import asyncio
from os import getenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer("Hello!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

**選擇建議：**
- `python-telegram-bot`：官方推薦，文件完整，社群活躍
- `aiogram`：更現代的設計，基於 aiohttp，效能稍佳

本專案建議使用 `python-telegram-bot` 以獲得更好的社群支援。

---

## 整合架構設計

### 4.1 系統架構圖

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            用戶界面層                                       │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        Telegram Bot                                  │  │
│  │                                                                       │  │
│  │  • 接收用戶訊息                                                        │  │
│  │  • /start, /help, /status 指令                                        │  │
│  │  • 訊息處理和回覆                                                      │  │
│  │  • 長時間運算狀態更新                                                  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                   ▲                                        │
│                                   │ 非同步通訊                              │
│                                   ▼                                        │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │
┌──────────────────────────────────────────────────────────────────────────┐
│                           決策引擎層                                        │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    Claude Agent SDK                                  │  │
│  │                                                                       │  │
│  │  • 解析用戶意圖                                                        │  │
│  │  • 決定調用哪些工具                                                    │  │
│  │  • 組合多個工具調用                                                    │  │
│  │  • 生成自然語言回覆                                                    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                   ▲                                        │
│                                   │ 工具調用                               │
│                                   ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    自訂 MCP 工具伺服器                                 │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │  │
│  │  │ get_candles     │  │ calculate_vp     │  │ get_account_info │   │  │
│  │  │                 │  │                  │  │                  │   │  │
│  │  │ 取得 K 線資料    │  │ 計算 Volume      │  │ 取得帳戶資訊      │   │  │
│  │  │                 │  │ Profile          │  │                  │   │  │
│  │  └─────────────────┘  └──────────────────┘  └──────────────────┘   │  │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │  │
│  │  │ calculate_sma   │  │ calculate_rsi    │  │ get_market_info  │   │  │
│  │  │                 │  │                  │  │                  │   │  │
│  │  │ 計算移動平均線   │  │ 計算 RSI         │  │ 取得市場資訊      │   │  │
│  │  │                 │  │                  │  │                  │   │  │
│  │  └─────────────────┘  └──────────────────┘  └──────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                   ▲                                        │
│                                   │ 調用核心模組                            │
│                                   ▼                                        │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │
┌──────────────────────────────────────────────────────────────────────────┐
│                            資料層                                          │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        src/core 模組                                  │  │
│  │                                                                       │  │
│  │  ┌──────────────┐  ┌────────────────────┐  ┌──────────────────────┐ │  │
│  │  │  MT5Config   │  │ ChipWhispererMT5   │  │ HistoricalData       │ │  │
│  │  │              │  │ Client             │  │ Fetcher              │ │  │
│  │  │  設定管理     │  │                    │  │                      │ │  │
│  │  │              │  │  連線管理           │  │  資料取得             │ │  │
│  │  └──────────────┘  └────────────────────┘  └──────────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                   ▲                                        │
│                                   │ MT5 API                               │
│                                   ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    MetaTrader 5 終端機                                 │  │
│  │                                                                       │  │
│  │  • 歷史資料                                                            │  │
│  │  • 即時報價                                                            │  │
│  │  • 帳戶資訊                                                            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.2 資料流程圖

```
用戶提問：「目前黃金的 H1 成本價位在哪裡？」
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Telegram Bot 接收訊息                                         │
│    - 記錄用戶 ID、訊息內容、時間戳                                 │
│    - 立即回覆：「正在處理您的請求...」                              │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. 調用 Claude Agent SDK                                         │
│    - 將用戶訊息傳遞給 Agent                                        │
│    - Agent 分析意圖：需要取得 GOLD H1 資料並計算 Volume Profile   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Agent 決定工具調用順序                                         │
│    Step 1: mcp__mt5_tools__get_candles(symbol="GOLD", tf="H1")  │
│    Step 2: mcp__mt5_tools__calculate_volume_profile(df)         │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. 執行工具：get_candles                                          │
│    - 更新 Telegram 狀態：「正在連接 MT5...」                       │
│    - 使用 ChipWhispererMT5Client 連線                            │
│    - 使用 HistoricalDataFetcher.get_candles_latest()            │
│    - 回傳 DataFrame 給 Agent                                     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. 執行工具：calculate_volume_profile                            │
│    - 更新 Telegram 狀態：「正在計算 Volume Profile...」           │
│    - 調用 calculate_volume_profile() 函式                        │
│    - 計算 POC、VAH、VAL                                          │
│    - 回傳 metrics 字典給 Agent                                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Agent 生成自然語言回覆                                         │
│    - 根據工具回傳結果組合答案                                      │
│    - 生成：「根據最新 H1 資料，黃金的成本價位：                     │
│      POC: 2050.50                                               │
│      VAH: 2055.20                                               │
│      VAL: 2045.80」                                             │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. Telegram Bot 發送最終結果                                     │
│    - 更新之前的狀態訊息                                            │
│    - 或發送新訊息                                                 │
│    - 記錄到日誌                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 目錄結構規劃

在現有專案基礎上，新增以下目錄和檔案：

```
chip-whisperer/
├── src/
│   ├── core/                          # 現有核心模組（保持不變）
│   │   ├── __init__.py
│   │   ├── mt5_config.py
│   │   ├── mt5_client.py
│   │   └── data_fetcher.py
│   ├── agent/                         # 新增：Agent 工具層
│   │   ├── __init__.py
│   │   ├── tools.py                   # Agent 自訂工具定義
│   │   ├── mcp_server.py              # MCP 伺服器建立
│   │   └── indicators.py              # 技術指標計算模組
│   └── bot/                           # 新增：Telegram Bot 層
│       ├── __init__.py
│       ├── telegram_bot.py            # Telegram Bot 主程式
│       ├── handlers.py                # 訊息和指令處理器
│       └── config.py                  # Bot 設定管理
├── examples/                          # 現有範例（保持不變）
├── tests/                             # 測試
│   ├── test_agent_tools.py            # 新增：Agent 工具測試
│   └── test_telegram_bot.py           # 新增：Bot 測試
├── config/                            # 設定檔
│   ├── bot_config.yaml                # 新增：Bot 設定
│   └── mt5_config.yaml                # 現有 MT5 設定
├── data/cache/                        # 資料快取
├── logs/                              # 日誌
├── scripts/                           # 腳本
│   └── run_bot.py                     # 新增：Bot 啟動腳本
├── .env.example                       # 環境變數範本（需更新）
├── requirements.txt                   # 依賴套件（需更新）
└── README.md                          # 說明文件（需更新）
```

### 4.4 各模組職責劃分

#### 4.4.1 src/core/ - 資料層（現有模組）

**職責：**
- MT5 連線管理
- 歷史資料取得
- 設定管理
- 資料快取

**不變更：** 保持現有介面和功能

#### 4.4.2 src/agent/ - Agent 工具層（新增）

**職責：**
- 定義 Claude Agent SDK 自訂工具
- 封裝 core 模組為 Agent 可調用的工具
- 實作技術指標計算邏輯
- 建立和管理 MCP 伺服器

**檔案：**
- `tools.py`：定義所有 Agent 工具
- `mcp_server.py`：建立 MCP 伺服器
- `indicators.py`：技術指標計算（Volume Profile、SMA、RSI 等）

#### 4.4.3 src/bot/ - 展示層（新增）

**職責：**
- 接收和發送 Telegram 訊息
- 處理用戶指令（/start, /help, /status）
- 調用 Claude Agent SDK
- 管理對話狀態
- 錯誤處理和日誌記錄

**檔案：**
- `telegram_bot.py`：Bot 主程式和應用程式建立
- `handlers.py`：訊息、指令、錯誤處理器
- `config.py`：Bot 設定管理

---

## 程式碼實作範例

### 5.1 Agent 工具定義 (src/agent/tools.py)

```python
"""
Agent 自訂工具定義

此模組定義所有 Claude Agent SDK 可調用的工具，
封裝 src/core 模組的功能。
"""

from typing import Any, Dict
from claude_agent_sdk import tool
from loguru import logger
import pandas as pd

# 匯入核心模組
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher
from .indicators import calculate_volume_profile, calculate_sma, calculate_rsi


# ============================================================================
# MT5 連線管理工具
# ============================================================================

# 全域 MT5 客戶端實例（單例模式）
_mt5_client = None
_mt5_config = None

def get_mt5_client() -> ChipWhispererMT5Client:
    """取得 MT5 客戶端單例"""
    global _mt5_client, _mt5_config

    if _mt5_client is None:
        logger.info("初始化 MT5 客戶端")
        _mt5_config = MT5Config()
        _mt5_client = ChipWhispererMT5Client(_mt5_config)
        _mt5_client.connect()

    # 確保連線
    _mt5_client.ensure_connected()
    return _mt5_client


# ============================================================================
# 資料取得工具
# ============================================================================

@tool(
    "get_candles",
    "取得指定商品和時間週期的 K 線資料",
    {
        "symbol": str,      # 商品代碼，例如 'GOLD', 'SILVER'
        "timeframe": str,   # 時間週期，例如 'H1', 'H4', 'D1'
        "count": int        # 要取得的 K 線數量，預設 100
    }
)
async def get_candles(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    取得歷史 K 線資料

    參數：
        symbol: 商品代碼（例如 'GOLD', 'SILVER', 'BITCOIN'）
        timeframe: 時間週期（例如 'H1', 'H4', 'D1'）
        count: K 線數量（預設 100）

    回傳：
        包含 K 線資料的字典，格式：
        {
            "content": [{"type": "text", "text": "成功訊息"}],
            "data": {
                "candles": [...],
                "summary": {...}
            }
        }
    """
    try:
        # 取得參數
        symbol = args.get("symbol", "GOLD").upper()
        timeframe = args.get("timeframe", "H1").upper()
        count = int(args.get("count", 100))

        logger.info(f"工具調用：get_candles(symbol={symbol}, timeframe={timeframe}, count={count})")

        # 取得 MT5 客戶端
        client = get_mt5_client()

        # 建立資料取得器
        fetcher = HistoricalDataFetcher(client)

        # 取得 K 線資料
        df = fetcher.get_candles_latest(
            symbol=symbol,
            timeframe=timeframe,
            count=count
        )

        # 準備回傳資料
        # 將 DataFrame 轉換為可序列化的格式
        candles_data = df.head(10).to_dict(orient='records')  # 只回傳前 10 筆給 Agent 參考

        # 計算摘要統計
        summary = {
            "total_candles": len(df),
            "date_range": {
                "from": str(df['time'].min()),
                "to": str(df['time'].max())
            },
            "price_range": {
                "high": float(df['high'].max()),
                "low": float(df['low'].min())
            },
            "average_volume": float(df['real_volume'].mean())
        }

        # 將完整 DataFrame 儲存到快取供後續工具使用
        # 使用全域變數或快取機制
        global _cached_candles
        _cached_candles = df

        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"成功取得 {symbol} {timeframe} 的 {len(df)} 根 K 線資料。\n"
                        f"日期範圍：{summary['date_range']['from']} ~ {summary['date_range']['to']}\n"
                        f"價格範圍：{summary['price_range']['low']:.2f} ~ {summary['price_range']['high']:.2f}\n"
                        f"平均成交量：{summary['average_volume']:.0f}"
                    )
                }
            ],
            "data": {
                "candles": candles_data,
                "summary": summary
            }
        }

    except ValueError as e:
        logger.error(f"參數錯誤：{e}")
        return {
            "content": [{"type": "text", "text": f"參數錯誤：{str(e)}"}],
            "is_error": True
        }
    except Exception as e:
        logger.exception(f"取得 K 線資料失敗：{e}")
        return {
            "content": [{"type": "text", "text": f"取得資料失敗：{str(e)}"}],
            "is_error": True
        }


# ============================================================================
# 技術指標計算工具
# ============================================================================

@tool(
    "calculate_volume_profile",
    "計算 Volume Profile，包含 POC、VAH、VAL",
    {
        "use_cached": bool,  # 是否使用快取的 K 線資料
        "price_bins": int    # 價格區間數量，預設 50
    }
)
async def calculate_vp_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    計算 Volume Profile

    參數：
        use_cached: 是否使用快取的 K 線資料（預設 True）
        price_bins: 價格區間數量（預設 50）

    回傳：
        包含 POC、VAH、VAL 的字典
    """
    try:
        use_cached = args.get("use_cached", True)
        price_bins = int(args.get("price_bins", 50))

        logger.info(f"工具調用：calculate_volume_profile(use_cached={use_cached}, price_bins={price_bins})")

        # 取得 K 線資料
        global _cached_candles
        if use_cached and _cached_candles is not None:
            df = _cached_candles
        else:
            return {
                "content": [{"type": "text", "text": "錯誤：請先使用 get_candles 工具取得資料"}],
                "is_error": True
            }

        # 計算 Volume Profile
        profile_df, metrics = calculate_volume_profile(df, price_bins=price_bins)

        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Volume Profile 計算完成：\n"
                        f"POC (Point of Control): {metrics['poc_price']:.2f}\n"
                        f"VAH (Value Area High): {metrics['vah']:.2f}\n"
                        f"VAL (Value Area Low): {metrics['val']:.2f}\n"
                        f"Value Area 範圍: {metrics['vah'] - metrics['val']:.2f} 點\n"
                        f"Value Area 成交量佔比: {metrics['value_area_percentage']:.1f}%"
                    )
                }
            ],
            "data": {
                "metrics": {
                    "poc_price": float(metrics['poc_price']),
                    "poc_volume": float(metrics['poc_volume']),
                    "vah": float(metrics['vah']),
                    "val": float(metrics['val']),
                    "value_area_range": float(metrics['vah'] - metrics['val']),
                    "value_area_percentage": float(metrics['value_area_percentage'])
                }
            }
        }

    except Exception as e:
        logger.exception(f"計算 Volume Profile 失敗：{e}")
        return {
            "content": [{"type": "text", "text": f"計算失敗：{str(e)}"}],
            "is_error": True
        }


@tool(
    "calculate_sma",
    "計算簡單移動平均線 (Simple Moving Average)",
    {
        "window": int  # 週期，例如 20, 50, 200
    }
)
async def calculate_sma_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """計算 SMA"""
    try:
        window = int(args.get("window", 20))

        global _cached_candles
        if _cached_candles is None:
            return {
                "content": [{"type": "text", "text": "錯誤：請先使用 get_candles 工具取得資料"}],
                "is_error": True
            }

        df = _cached_candles.copy()
        sma_values = calculate_sma(df, window)

        current_sma = float(sma_values.iloc[0])

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"SMA({window}) 當前值：{current_sma:.2f}"
                }
            ],
            "data": {
                "sma": current_sma,
                "window": window
            }
        }

    except Exception as e:
        logger.exception(f"計算 SMA 失敗：{e}")
        return {
            "content": [{"type": "text", "text": f"計算失敗：{str(e)}"}],
            "is_error": True
        }


@tool(
    "calculate_rsi",
    "計算相對強弱指標 (Relative Strength Index)",
    {
        "period": int  # 週期，預設 14
    }
)
async def calculate_rsi_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """計算 RSI"""
    try:
        period = int(args.get("period", 14))

        global _cached_candles
        if _cached_candles is None:
            return {
                "content": [{"type": "text", "text": "錯誤：請先使用 get_candles 工具取得資料"}],
                "is_error": True
            }

        df = _cached_candles.copy()
        rsi_values = calculate_rsi(df, period)

        current_rsi = float(rsi_values.iloc[0])

        # RSI 解讀
        if current_rsi > 70:
            interpretation = "超買區（可能回調）"
        elif current_rsi < 30:
            interpretation = "超賣區（可能反彈）"
        else:
            interpretation = "中性區間"

        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"RSI({period}) 當前值：{current_rsi:.2f}\n"
                        f"解讀：{interpretation}"
                    )
                }
            ],
            "data": {
                "rsi": current_rsi,
                "period": period,
                "interpretation": interpretation
            }
        }

    except Exception as e:
        logger.exception(f"計算 RSI 失敗：{e}")
        return {
            "content": [{"type": "text", "text": f"計算失敗：{str(e)}"}],
            "is_error": True
        }


# ============================================================================
# 帳戶資訊工具
# ============================================================================

@tool(
    "get_account_info",
    "取得 MT5 帳戶資訊",
    {}
)
async def get_account_info_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """取得帳戶資訊"""
    try:
        client = get_mt5_client()
        account_info = client.get_account_info()

        if account_info is None:
            return {
                "content": [{"type": "text", "text": "無法取得帳戶資訊"}],
                "is_error": True
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"帳戶資訊：\n"
                        f"帳號：{account_info['login']}\n"
                        f"餘額：{account_info['balance']} {account_info['currency']}\n"
                        f"淨值：{account_info['equity']} {account_info['currency']}\n"
                        f"槓桿：1:{account_info['leverage']}"
                    )
                }
            ],
            "data": account_info
        }

    except Exception as e:
        logger.exception(f"取得帳戶資訊失敗：{e}")
        return {
            "content": [{"type": "text", "text": f"取得失敗：{str(e)}"}],
            "is_error": True
        }


# ============================================================================
# 全域快取變數
# ============================================================================

_cached_candles: pd.DataFrame = None
```

### 5.2 技術指標計算模組 (src/agent/indicators.py)

```python
"""
技術指標計算模組

此模組包含各種技術指標的計算邏輯。
"""

from typing import Dict, Tuple
import numpy as np
import pandas as pd
from loguru import logger


def calculate_volume_profile(
    df: pd.DataFrame,
    price_bins: int = 100
) -> Tuple[pd.DataFrame, Dict]:
    """
    計算 Volume Profile

    此函式從 examples/demo_volume_profile_data.py 移植而來。

    參數：
        df: K 線資料 DataFrame
        price_bins: 價格區間數量

    回傳：
        (profile_df, metrics) 元組
        - profile_df: Volume Profile DataFrame
        - metrics: 包含 POC、VAH、VAL 的字典
    """
    logger.info(f"開始計算 Volume Profile（價格區間數：{price_bins}）")

    # 1. 確定價格範圍
    price_min = df['low'].min()
    price_max = df['high'].max()
    logger.debug(f"價格範圍：{price_min:.2f} ~ {price_max:.2f}")

    # 2. 建立價格區間
    price_edges = np.linspace(price_min, price_max, price_bins + 1)
    price_centers = (price_edges[:-1] + price_edges[1:]) / 2

    # 3. 計算每個價格區間的成交量
    volumes = np.zeros(price_bins)

    for _, row in df.iterrows():
        # 找出此 K 線涵蓋的價格區間
        low_idx = np.searchsorted(price_edges, row['low'], side='left')
        high_idx = np.searchsorted(price_edges, row['high'], side='right') - 1

        # 確保索引在有效範圍內
        low_idx = max(0, min(low_idx, price_bins - 1))
        high_idx = max(0, min(high_idx, price_bins - 1))

        # 將成交量分配到涵蓋的價格區間
        span = high_idx - low_idx + 1
        if span > 0:
            volume_per_bin = row['real_volume'] / span
            volumes[low_idx:high_idx + 1] += volume_per_bin

    # 4. 建立 Volume Profile DataFrame
    profile_df = pd.DataFrame({
        'price': price_centers,
        'volume': volumes
    })

    # 按成交量排序
    profile_df = profile_df.sort_values('volume', ascending=False)

    # 5. 計算 POC (Point of Control) - 成交量最大的價位
    poc_price = profile_df.iloc[0]['price']
    poc_volume = profile_df.iloc[0]['volume']

    logger.info(f"POC (Point of Control)：{poc_price:.2f}，成交量：{poc_volume:.0f}")

    # 6. 計算 Value Area (70% 成交量區間)
    total_volume = volumes.sum()
    target_volume = total_volume * 0.70

    # 從 POC 開始向兩側擴展，直到達到 70% 成交量
    profile_df_sorted = profile_df.sort_values('price')
    poc_idx = profile_df_sorted[profile_df_sorted['price'] == poc_price].index[0]

    # 初始化 Value Area
    value_area_volume = poc_volume
    lower_idx = poc_idx
    upper_idx = poc_idx

    # 向兩側擴展
    while value_area_volume < target_volume:
        # 檢查是否還有空間擴展
        can_expand_lower = lower_idx > 0
        can_expand_upper = upper_idx < len(profile_df_sorted) - 1

        if not can_expand_lower and not can_expand_upper:
            break

        # 選擇成交量較大的一側擴展
        lower_volume = profile_df_sorted.iloc[lower_idx - 1]['volume'] if can_expand_lower else 0
        upper_volume = profile_df_sorted.iloc[upper_idx + 1]['volume'] if can_expand_upper else 0

        if lower_volume > upper_volume and can_expand_lower:
            lower_idx -= 1
            value_area_volume += lower_volume
        elif can_expand_upper:
            upper_idx += 1
            value_area_volume += upper_volume

    # Value Area High (VAH) 和 Low (VAL)
    vah = profile_df_sorted.iloc[upper_idx]['price']
    val = profile_df_sorted.iloc[lower_idx]['price']

    logger.info(f"Value Area High (VAH)：{vah:.2f}")
    logger.info(f"Value Area Low (VAL)：{val:.2f}")
    logger.info(f"Value Area 成交量：{value_area_volume:.0f} ({value_area_volume/total_volume*100:.1f}%)")

    # 7. 整理結果
    metrics = {
        'poc_price': poc_price,
        'poc_volume': poc_volume,
        'vah': vah,
        'val': val,
        'value_area_volume': value_area_volume,
        'total_volume': total_volume,
        'value_area_percentage': value_area_volume / total_volume * 100
    }

    return profile_df, metrics


def calculate_sma(df: pd.DataFrame, window: int) -> pd.Series:
    """
    計算簡單移動平均線 (Simple Moving Average)

    參數：
        df: K 線資料 DataFrame
        window: 週期（例如 20, 50, 200）

    回傳：
        SMA 數值的 Series
    """
    logger.debug(f"計算 SMA({window})")
    return df['close'].rolling(window=window).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    計算相對強弱指標 (Relative Strength Index)

    參數：
        df: K 線資料 DataFrame
        period: 週期（預設 14）

    回傳：
        RSI 數值的 Series
    """
    logger.debug(f"計算 RSI({period})")

    # 計算價格變化
    delta = df['close'].diff()

    # 分離漲幅和跌幅
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # 計算平均漲幅和跌幅
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # 計算 RS 和 RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_ema(df: pd.DataFrame, span: int) -> pd.Series:
    """
    計算指數移動平均線 (Exponential Moving Average)

    參數：
        df: K 線資料 DataFrame
        span: 週期

    回傳：
        EMA 數值的 Series
    """
    logger.debug(f"計算 EMA({span})")
    return df['close'].ewm(span=span, adjust=False).mean()


def calculate_bollinger_bands(
    df: pd.DataFrame,
    window: int = 20,
    num_std: int = 2
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    計算布林通道 (Bollinger Bands)

    參數：
        df: K 線資料 DataFrame
        window: 週期（預設 20）
        num_std: 標準差倍數（預設 2）

    回傳：
        (upper_band, middle_band, lower_band) 元組
    """
    logger.debug(f"計算 Bollinger Bands({window}, {num_std})")

    middle_band = df['close'].rolling(window=window).mean()
    std = df['close'].rolling(window=window).std()

    upper_band = middle_band + (std * num_std)
    lower_band = middle_band - (std * num_std)

    return upper_band, middle_band, lower_band
```

### 5.3 MCP 伺服器建立 (src/agent/mcp_server.py)

```python
"""
MCP 伺服器建立模組

此模組負責建立和配置 Claude Agent SDK 的 MCP 伺服器。
"""

from claude_agent_sdk import create_sdk_mcp_server
from loguru import logger

# 匯入所有工具
from .tools import (
    get_candles,
    calculate_vp_tool,
    calculate_sma_tool,
    calculate_rsi_tool,
    get_account_info_tool
)


def create_mt5_mcp_server():
    """
    建立 MT5 工具的 MCP 伺服器

    回傳：
        MCP 伺服器實例
    """
    logger.info("建立 MT5 MCP 伺服器")

    server = create_sdk_mcp_server(
        name="mt5_tools",
        version="1.0.0",
        tools=[
            get_candles,
            calculate_vp_tool,
            calculate_sma_tool,
            calculate_rsi_tool,
            get_account_info_tool
        ]
    )

    logger.info("MT5 MCP 伺服器建立完成")
    return server


def get_allowed_tools() -> list[str]:
    """
    取得允許的工具列表

    回傳：
        工具名稱列表（格式：mcp__<server_name>__<tool_name>）
    """
    return [
        "mcp__mt5_tools__get_candles",
        "mcp__mt5_tools__calculate_volume_profile",
        "mcp__mt5_tools__calculate_sma",
        "mcp__mt5_tools__calculate_rsi",
        "mcp__mt5_tools__get_account_info"
    ]
```

### 5.4 Telegram Bot 主程式 (src/bot/telegram_bot.py)

```python
"""
Telegram Bot 主程式

此模組建立和啟動 Telegram Bot，整合 Claude Agent SDK。
"""

import asyncio
from telegram.ext import ApplicationBuilder
from loguru import logger

from .config import BotConfig
from .handlers import (
    register_command_handlers,
    register_message_handlers,
    register_error_handler
)


class TradingAssistantBot:
    """交易助手 Bot"""

    def __init__(self, config: BotConfig):
        """
        初始化 Bot

        參數：
            config: Bot 設定
        """
        self.config = config
        self.app = None

        logger.info("初始化交易助手 Bot")

    def build(self):
        """建立 Bot 應用程式"""
        logger.info("建立 Telegram Bot 應用程式")

        # 建立應用程式
        self.app = ApplicationBuilder().token(self.config.bot_token).build()

        # 註冊處理器
        register_command_handlers(self.app)
        register_message_handlers(self.app)
        register_error_handler(self.app)

        logger.info("Bot 應用程式建立完成")
        return self

    def run(self):
        """啟動 Bot（阻塞模式）"""
        logger.info("啟動 Telegram Bot 輪詢")
        self.app.run_polling()

    async def start(self):
        """啟動 Bot（非同步模式）"""
        logger.info("啟動 Telegram Bot（非同步）")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def stop(self):
        """停止 Bot"""
        logger.info("停止 Telegram Bot")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()


def main():
    """主函式"""
    # 設定日誌
    logger.remove()
    logger.add(
        "logs/telegram_bot.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG"
    )
    logger.add(
        lambda msg: print(msg, end=''),
        level="INFO"
    )

    try:
        # 載入設定
        config = BotConfig()

        # 建立並啟動 Bot
        bot = TradingAssistantBot(config)
        bot.build()
        bot.run()

    except KeyboardInterrupt:
        logger.info("收到中斷信號，正在關閉...")
    except Exception as e:
        logger.exception(f"Bot 執行失敗：{e}")
        raise


if __name__ == "__main__":
    main()
```

### 5.5 訊息處理器 (src/bot/handlers.py)

```python
"""
Telegram Bot 處理器

此模組定義所有指令和訊息的處理器。
"""

import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from loguru import logger
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from ..agent.mcp_server import create_mt5_mcp_server, get_allowed_tools


# ============================================================================
# 指令處理器
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /start 指令"""
    user = update.effective_user
    logger.info(f"用戶 {user.id} ({user.username}) 執行 /start")

    welcome_message = (
        f"你好 {user.first_name}！👋\n\n"
        "我是 MT5 交易助手，可以幫你分析市場數據。\n\n"
        "📊 我可以做什麼：\n"
        "• 取得歷史 K 線資料\n"
        "• 計算 Volume Profile（POC、VAH、VAL）\n"
        "• 計算技術指標（SMA、RSI 等）\n"
        "• 提供帳戶資訊\n\n"
        "💡 試試問我：\n"
        "「目前黃金的 H1 成本價位在哪裡？」\n"
        "「SILVER 的 RSI 是多少？」\n\n"
        "輸入 /help 查看更多說明"
    )

    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /help 指令"""
    logger.info(f"用戶 {update.effective_user.id} 執行 /help")

    help_message = (
        "📖 使用說明\n\n"
        "🔹 指令列表：\n"
        "/start - 開始使用\n"
        "/help - 顯示說明\n"
        "/status - 檢查系統狀態\n"
        "/account - 查看帳戶資訊\n\n"
        "🔹 問題範例：\n"
        "• 「取得 GOLD H1 最新 100 根 K 線」\n"
        "• 「計算 GOLD H1 的 Volume Profile」\n"
        "• 「SILVER 的 20 期 SMA 是多少？」\n"
        "• 「幫我分析 BITCOIN H4 的 RSI」\n\n"
        "🔹 支援的商品：\n"
        "GOLD, SILVER, BITCOIN, USDJPY 等\n\n"
        "🔹 支援的時間週期：\n"
        "M1, M5, M15, M30, H1, H4, D1, W1 等\n\n"
        "💡 提示：直接用自然語言問我問題即可！"
    )

    await update.message.reply_text(help_message)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /status 指令"""
    logger.info(f"用戶 {update.effective_user.id} 執行 /status")

    status_message = await update.message.reply_text("正在檢查系統狀態...")

    try:
        # 檢查 MT5 連線
        from ..agent.tools import get_mt5_client
        client = get_mt5_client()

        if client.is_connected():
            mt5_status = "✅ 已連線"
            account_info = client.get_account_info()
            account_status = f"帳號：{account_info['login']}"
        else:
            mt5_status = "❌ 未連線"
            account_status = "N/A"

        # 檢查 Claude Agent SDK
        agent_status = "✅ 正常"

        status_text = (
            "🔍 系統狀態\n\n"
            f"MT5 連線：{mt5_status}\n"
            f"帳戶狀態：{account_status}\n"
            f"Agent SDK：{agent_status}\n\n"
            "✅ 系統運作正常"
        )

        await status_message.edit_text(status_text)

    except Exception as e:
        logger.error(f"檢查狀態失敗：{e}")
        await status_message.edit_text(f"❌ 系統狀態異常：{str(e)}")


async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /account 指令"""
    logger.info(f"用戶 {update.effective_user.id} 執行 /account")

    status_message = await update.message.reply_text("正在取得帳戶資訊...")

    try:
        from ..agent.tools import get_mt5_client
        client = get_mt5_client()
        account_info = client.get_account_info()

        if account_info:
            account_text = (
                "💼 帳戶資訊\n\n"
                f"帳號：{account_info['login']}\n"
                f"伺服器：{account_info['server']}\n"
                f"餘額：{account_info['balance']} {account_info['currency']}\n"
                f"淨值：{account_info['equity']} {account_info['currency']}\n"
                f"槓桿：1:{account_info['leverage']}\n"
                f"保證金：{account_info['margin']} {account_info['currency']}"
            )
            await status_message.edit_text(account_text)
        else:
            await status_message.edit_text("❌ 無法取得帳戶資訊")

    except Exception as e:
        logger.error(f"取得帳戶資訊失敗：{e}")
        await status_message.edit_text(f"❌ 取得失敗：{str(e)}")


# ============================================================================
# 訊息處理器
# ============================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理一般訊息（透過 Claude Agent SDK）"""
    user = update.effective_user
    user_message = update.message.text

    logger.info(f"收到用戶 {user.id} 的訊息：{user_message}")

    # 立即回應
    status_message = await update.message.reply_text("正在處理您的請求，請稍候...")

    try:
        # 建立 MCP 伺服器
        mcp_server = create_mt5_mcp_server()

        # 配置 Agent 選項
        options = ClaudeAgentOptions(
            mcp_servers={"mt5_tools": mcp_server},
            allowed_tools=get_allowed_tools()
        )

        # 使用 Claude Agent SDK 處理請求
        async with ClaudeSDKClient(options=options) as client:
            # 發送查詢
            await client.query(user_message)

            # 接收回應
            response_text = ""
            async for message in client.receive_response():
                if hasattr(message, 'text'):
                    response_text += message.text
                elif hasattr(message, 'content'):
                    # 處理不同類型的內容
                    if isinstance(message.content, str):
                        response_text += message.content
                    elif isinstance(message.content, list):
                        for item in message.content:
                            if isinstance(item, dict) and 'text' in item:
                                response_text += item['text']

            # 更新為最終結果
            if response_text:
                await status_message.edit_text(response_text)
            else:
                await status_message.edit_text("✅ 請求已處理完成")

        logger.info(f"成功處理用戶 {user.id} 的請求")

    except Exception as e:
        logger.exception(f"處理訊息失敗：{e}")
        await status_message.edit_text(
            f"❌ 處理失敗：{str(e)}\n\n"
            "請稍後再試，或輸入 /help 查看使用說明"
        )


# ============================================================================
# 錯誤處理器
# ============================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """全域錯誤處理器"""
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.message:
        await update.message.reply_text(
            "❌ 抱歉，處理您的請求時發生錯誤。\n"
            "請稍後再試，或聯繫管理員。"
        )


# ============================================================================
# 處理器註冊函式
# ============================================================================

def register_command_handlers(app: Application) -> None:
    """註冊所有指令處理器"""
    logger.info("註冊指令處理器")

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("account", account_command))


def register_message_handlers(app: Application) -> None:
    """註冊訊息處理器"""
    logger.info("註冊訊息處理器")

    # 處理所有非指令的文字訊息
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )


def register_error_handler(app: Application) -> None:
    """註冊錯誤處理器"""
    logger.info("註冊錯誤處理器")

    app.add_error_handler(error_handler)
```

### 5.6 Bot 設定管理 (src/bot/config.py)

```python
"""
Bot 設定管理模組
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger


class BotConfig:
    """Bot 設定類別"""

    def __init__(self, env_file: str = None):
        """
        初始化設定

        參數：
            env_file: .env 檔案路徑（可選）
        """
        # 載入 .env 檔案
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
        else:
            default_env = Path.cwd() / '.env'
            if default_env.exists():
                load_dotenv(default_env)

        # Bot Token（必要）
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN 未設定")

        # Claude API Key（必要）
        self.claude_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.claude_api_key:
            raise ValueError("ANTHROPIC_API_KEY 未設定")

        # 設定 Claude API Key 為環境變數
        os.environ['ANTHROPIC_API_KEY'] = self.claude_api_key

        # 其他設定
        self.admin_user_ids = self._parse_admin_ids()
        self.debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'

        logger.info(f"Bot 設定載入完成（Debug: {self.debug_mode}）")

    def _parse_admin_ids(self) -> list[int]:
        """解析管理員 ID 列表"""
        admin_ids_str = os.getenv('TELEGRAM_ADMIN_IDS', '')
        if not admin_ids_str:
            return []

        try:
            return [int(id_str.strip()) for id_str in admin_ids_str.split(',') if id_str.strip()]
        except ValueError:
            logger.warning("TELEGRAM_ADMIN_IDS 格式錯誤")
            return []

    def is_admin(self, user_id: int) -> bool:
        """檢查是否為管理員"""
        return user_id in self.admin_user_ids
```

### 5.7 環境變數設定範本 (.env.example)

```env
# ============================================================================
# MT5 連線設定
# ============================================================================

# MT5 帳號資訊（必要）
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=YourBroker-Server

# MT5 連線參數（選用）
MT5_TIMEOUT=60000
MT5_MAX_RETRIES=3
MT5_PATH=

# ============================================================================
# Telegram Bot 設定
# ============================================================================

# Telegram Bot Token（必要）
# 從 @BotFather 取得
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# 管理員用戶 ID（選用，多個以逗號分隔）
# 可從 @userinfobot 取得
TELEGRAM_ADMIN_IDS=123456789,987654321

# ============================================================================
# Claude Agent SDK 設定
# ============================================================================

# Anthropic API Key（必要）
# 從 https://console.anthropic.com/ 取得
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ============================================================================
# 其他設定
# ============================================================================

# 除錯模式
DEBUG=false

# 資料快取目錄
CACHE_DIR=data/cache

# 日誌目錄
LOG_DIR=logs
```

### 5.8 啟動腳本 (scripts/run_bot.py)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot 啟動腳本

使用方式：
    python scripts/run_bot.py
"""

import sys
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from bot.telegram_bot import main

if __name__ == "__main__":
    main()
```

### 5.9 更新後的 requirements.txt

```txt
# ============================================================================
# 核心依賴
# ============================================================================

MetaTrader5>=5.0.4510
pandas>=2.0.0
numpy>=1.24.0
pyyaml>=6.0
python-dotenv>=1.0.0

# ============================================================================
# Claude Agent SDK
# ============================================================================

claude-agent-sdk>=1.0.0
anthropic>=0.39.0

# ============================================================================
# Telegram Bot
# ============================================================================

python-telegram-bot>=20.0
aiohttp>=3.9.0

# ============================================================================
# 日誌和工具
# ============================================================================

loguru>=0.7.0

# ============================================================================
# 測試
# ============================================================================

pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
pytest-asyncio>=0.21.0

# ============================================================================
# 開發工具
# ============================================================================

black>=23.7.0
flake8>=6.1.0
mypy>=1.5.0
```

---

## 實作計畫

### 6.1 階段一：基礎整合（1-2 天）

**目標：** 建立最小可行原型 (MVP)

**任務：**
1. 安裝新增的依賴套件
   ```bash
   pip install -r requirements.txt
   ```

2. 建立 Agent 工具層
   - 建立 `src/agent/` 目錄
   - 實作 `tools.py`：定義 `get_candles` 和 `calculate_vp_tool`
   - 實作 `indicators.py`：移植 Volume Profile 計算邏輯
   - 實作 `mcp_server.py`：建立 MCP 伺服器

3. 測試 Agent 工具
   - 撰寫簡單的測試腳本驗證工具可正常調用
   ```python
   # test_agent_tools.py
   import asyncio
   from src.agent.tools import get_candles, calculate_vp_tool

   async def test():
       result = await get_candles({
           "symbol": "GOLD",
           "timeframe": "H1",
           "count": 100
       })
       print(result)

   asyncio.run(test())
   ```

4. 設定環境變數
   - 複製 `.env.example` 為 `.env`
   - 填入 MT5 帳號、Telegram Bot Token、Anthropic API Key

**驗收標準：**
- Agent 工具可成功取得 MT5 資料
- Volume Profile 計算結果正確
- MCP 伺服器可正常建立

### 6.2 階段二：Telegram Bot 整合（2-3 天）

**目標：** 完成 Bot 基本功能

**任務：**
1. 建立 Bot 層
   - 建立 `src/bot/` 目錄
   - 實作 `config.py`：設定管理
   - 實作 `handlers.py`：指令和訊息處理器
   - 實作 `telegram_bot.py`：Bot 主程式

2. 整合 Claude Agent SDK
   - 在訊息處理器中調用 Agent
   - 實作狀態更新機制
   - 處理長時間運算

3. 測試基本功能
   - 測試 `/start`, `/help`, `/status` 指令
   - 測試簡單的問題處理
   - 測試錯誤處理

4. 建立啟動腳本
   - 實作 `scripts/run_bot.py`

**驗收標準：**
- Bot 可正常啟動並回應指令
- 可處理簡單的用戶問題
- 錯誤處理機制正常運作

### 6.3 階段三：功能完善（3-5 天）

**目標：** 完成所有計畫功能

**任務：**
1. 新增更多技術指標工具
   - 實作 `calculate_sma_tool`
   - 實作 `calculate_rsi_tool`
   - 實作 `calculate_ema_tool`（可選）
   - 實作 `calculate_bollinger_bands_tool`（可選）

2. 優化用戶體驗
   - 改善回覆訊息格式
   - 新增更多提示和說明
   - 實作進度條或狀態更新

3. 新增資料視覺化（可選）
   - 產生簡單的圖表（使用 matplotlib）
   - 以圖片形式發送給用戶

4. 效能優化
   - 實作資料快取機制
   - 優化 Agent 工具調用流程
   - 減少重複的 MT5 連線

**驗收標準：**
- 所有技術指標工具正常運作
- 用戶體驗良好
- 系統效能穩定

### 6.4 階段四：測試和部署（2-3 天）

**目標：** 確保系統穩定並準備部署

**任務：**
1. 撰寫測試
   - 單元測試：Agent 工具
   - 整合測試：Bot 處理流程
   - 使用 pytest-asyncio 測試非同步函式

2. 文件更新
   - 更新 README.md
   - 撰寫使用手冊
   - 建立 FAQ

3. 部署準備
   - 建立 Docker 容器（可選）
   - 準備部署腳本
   - 設定監控和日誌

4. 安全性檢查
   - 確保 .env 不被提交到 Git
   - 驗證 API Key 安全性
   - 檢查用戶權限控制

**驗收標準：**
- 測試覆蓋率 > 70%
- 文件完整且清晰
- 系統可穩定運行

---

## 測試方案

### 7.1 單元測試

**檔案：tests/test_agent_tools.py**

```python
"""
Agent 工具單元測試
"""

import pytest
import pandas as pd
from src.agent.tools import get_candles, calculate_vp_tool
from src.agent.indicators import calculate_volume_profile


class TestGetCandles:
    """測試 get_candles 工具"""

    @pytest.mark.asyncio
    async def test_get_candles_success(self):
        """測試成功取得 K 線"""
        result = await get_candles({
            "symbol": "GOLD",
            "timeframe": "H1",
            "count": 100
        })

        assert "content" in result
        assert "data" in result
        assert result["data"]["summary"]["total_candles"] == 100

    @pytest.mark.asyncio
    async def test_get_candles_invalid_symbol(self):
        """測試無效商品代碼"""
        result = await get_candles({
            "symbol": "INVALID_SYMBOL",
            "timeframe": "H1",
            "count": 100
        })

        assert "is_error" in result
        assert result["is_error"] is True


class TestVolumeProfile:
    """測試 Volume Profile 計算"""

    def test_calculate_volume_profile(self):
        """測試 Volume Profile 計算邏輯"""
        # 建立測試資料
        df = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=100, freq='H'),
            'open': [2000 + i for i in range(100)],
            'high': [2010 + i for i in range(100)],
            'low': [1990 + i for i in range(100)],
            'close': [2005 + i for i in range(100)],
            'real_volume': [1000] * 100
        })

        profile_df, metrics = calculate_volume_profile(df, price_bins=50)

        assert 'poc_price' in metrics
        assert 'vah' in metrics
        assert 'val' in metrics
        assert metrics['vah'] > metrics['val']
        assert metrics['value_area_percentage'] >= 70
```

**檔案：tests/test_telegram_bot.py**

```python
"""
Telegram Bot 測試
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

from src.bot.handlers import start_command, help_command


class TestCommandHandlers:
    """測試指令處理器"""

    @pytest.mark.asyncio
    async def test_start_command(self):
        """測試 /start 指令"""
        # 建立模擬的 Update
        update = MagicMock(spec=Update)
        update.effective_user = User(id=123, first_name="Test", is_bot=False)
        update.message = AsyncMock(spec=Message)

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # 執行處理器
        await start_command(update, context)

        # 驗證回覆
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Test" in call_args
        assert "交易助手" in call_args
```

### 7.2 整合測試

**手動測試流程：**

1. **環境準備**
   - 確保 MT5 已連線
   - 確保 Telegram Bot Token 有效
   - 確保 Anthropic API Key 有效

2. **測試 Bot 啟動**
   ```bash
   python scripts/run_bot.py
   ```
   - 驗證無錯誤訊息
   - 驗證日誌正常輸出

3. **測試基本指令**
   - 發送 `/start` → 檢查歡迎訊息
   - 發送 `/help` → 檢查說明訊息
   - 發送 `/status` → 檢查系統狀態
   - 發送 `/account` → 檢查帳戶資訊

4. **測試簡單問題**
   - 「取得 GOLD H1 最新 100 根 K 線」
   - 驗證回覆包含 K 線資料摘要

5. **測試 Volume Profile**
   - 「計算 GOLD H1 的 Volume Profile」
   - 驗證回覆包含 POC、VAH、VAL

6. **測試技術指標**
   - 「GOLD 的 20 期 SMA 是多少？」
   - 「SILVER 的 RSI 是多少？」
   - 驗證計算結果合理

7. **測試錯誤處理**
   - 發送無效商品代碼
   - 發送無意義的問題
   - 驗證錯誤訊息友善

8. **效能測試**
   - 同時發送多個請求
   - 測試長時間運算的回應時間
   - 驗證系統穩定性

### 7.3 自動化測試腳本

**檔案：tests/integration_test.py**

```python
"""
整合測試腳本

需要先啟動 Bot，然後執行此腳本發送測試訊息。
"""

import asyncio
from telegram import Bot

async def run_integration_tests():
    """執行整合測試"""
    bot_token = "YOUR_BOT_TOKEN"
    chat_id = "YOUR_CHAT_ID"

    bot = Bot(token=bot_token)

    test_messages = [
        "/start",
        "/help",
        "/status",
        "取得 GOLD H1 最新 100 根 K 線",
        "計算 GOLD H1 的 Volume Profile",
        "GOLD 的 20 期 SMA 是多少？"
    ]

    for msg in test_messages:
        print(f"發送測試訊息：{msg}")
        await bot.send_message(chat_id=chat_id, text=msg)
        await asyncio.sleep(5)  # 等待處理

    print("整合測試完成")

if __name__ == "__main__":
    asyncio.run(run_integration_tests())
```

---

## 開放問題和後續研究

### 8.1 需要進一步確認的技術細節

1. **Claude Agent SDK 的 streaming 回應處理**
   - 如何處理 Agent 的中間步驟回應
   - 是否需要顯示工具調用過程給用戶

2. **資料快取策略**
   - K 線資料的快取時效
   - 是否需要實作分散式快取（Redis）

3. **並發處理**
   - 多用戶同時請求的處理策略
   - 是否需要請求佇列機制

4. **成本控制**
   - Claude API 的使用成本估算
   - 是否需要實作用戶配額限制

### 8.2 潛在的擴展方向

1. **更多技術指標**
   - MACD、KD、布林通道等
   - 自訂指標公式

2. **即時警報**
   - 價格突破提醒
   - 技術指標信號提醒

3. **策略回測**
   - 基於歷史資料的策略測試
   - 績效報告生成

4. **多語言支援**
   - 英文、簡體中文等
   - 自動語言檢測

5. **網頁介面**
   - 除了 Telegram Bot，提供網頁版
   - 資料視覺化儀表板

---

## 程式碼引用參考

### 現有程式碼

- **MT5Config**：`C:\Users\fatfi\works\chip-whisperer\src\core\mt5_config.py`（第 1-232 行）
- **ChipWhispererMT5Client**：`C:\Users\fatfi\works\chip-whisperer\src\core\mt5_client.py`（第 1-233 行）
- **HistoricalDataFetcher**：`C:\Users\fatfi\works\chip-whisperer\src\core\data_fetcher.py`（第 1-357 行）
- **calculate_volume_profile**：`C:\Users\fatfi\works\chip-whisperer\examples\demo_volume_profile_data.py`（第 56-168 行）

### 新增程式碼（範例）

- **Agent 工具**：本文件第 5.1 節
- **技術指標模組**：本文件第 5.2 節
- **MCP 伺服器**：本文件第 5.3 節
- **Telegram Bot**：本文件第 5.4-5.6 節

---

## 參考資源

### 外部文件來源

**Claude Agent SDK：**
- [Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [GitHub - anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)
- [Claude Agent SDK Tutorial - DataCamp](https://www.datacamp.com/tutorial/how-to-use-claude-agent-sdk)
- [Agent SDK Overview - Claude Docs](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Custom Tools Documentation](https://platform.claude.com/docs/en/agent-sdk/custom-tools)
- [Agent SDK Python Reference](https://platform.claude.com/docs/en/agent-sdk/python)

**Telegram Bot：**
- [python-telegram-bot Official](https://python-telegram-bot.org/)
- [GitHub - aiogram/aiogram](https://github.com/aiogram/aiogram)
- [AsyncTeleBot Documentation](https://pytba.readthedocs.io/en/latest/async_version/index.html)

**其他參考：**
- MetaTrader 5 Python API 官方文件
- pandas 資料處理文件
- loguru 日誌套件文件

---

## 結論

本研究提供了一個完整的 Telegram Bot + Claude Agent SDK + MT5 整合架構方案，包含：

1. **現有程式碼分析**：詳細記錄了 `src/core/` 模組的功能和使用方式
2. **外部技術研究**：深入研究了 Claude Agent SDK 和 Telegram Bot API
3. **系統架構設計**：提出三層架構（展示層、決策層、資料層）
4. **完整程式碼範例**：提供可直接使用的程式碼實作
5. **實作計畫**：分階段的開發路線圖
6. **測試方案**：單元測試、整合測試和自動化測試策略

**下一步行動：**
1. 更新 `.env` 檔案，填入必要的 API Key
2. 安裝新增的依賴套件
3. 按照階段一的任務開始實作 Agent 工具層
4. 逐步完成各階段任務
5. 持續測試和優化

此架構設計充分利用了現有的 MT5 核心模組，並透過 Claude Agent SDK 提供智能的自然語言界面，最終透過 Telegram Bot 提供友善的用戶體驗。整個系統採用非同步架構，可良好支援並發請求和長時間運算。
