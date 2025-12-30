# Telegram Agent 開發計畫

## 計畫概覽

### 目標

建立一個整合 Telegram Bot、Claude Agent SDK 和現有 MT5 核心模組的交易助手系統，讓用戶可以透過 Telegram 自然語言對話來查詢市場數據、計算技術指標，並取得智能分析結果。

### 範圍

**包含：**
1. 建立 Agent 工具層，封裝現有 `src/core` 模組為 Claude Agent SDK 可調用的工具
2. 實作 Telegram Bot 整合層，處理用戶對話和訊息
3. 整合 Claude Agent SDK 作為中央決策引擎
4. 實作基本技術指標計算（Volume Profile、SMA、RSI 等）
5. 提供完整的錯誤處理和日誌記錄

**不包含：**
- 修改現有 `src/core` 模組的任何功能
- 實作複雜的交易策略或自動下單功能
- 建立 Web 界面或其他前端
- 實作用戶權限管理系統（僅支援基本的管理員檢查）

### 時程估算

- **階段一（環境設定）**：0.5 天
- **階段二（Agent 工具層）**：2 天
- **階段三（Telegram Bot 整合）**：1.5 天
- **階段四（完整整合和優化）**：1 天
- **總計**：約 5 個工作天

---

## 階段一：基礎環境設定

### 概覽

設定專案所需的依賴套件、環境變數和目錄結構，確保開發環境準備完成。

### 1.1 更新依賴套件

#### 目標
在現有 `requirements.txt` 中新增 Telegram Bot 和 Claude Agent SDK 相關套件。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\requirements.txt`

#### 變更內容

在現有內容後新增：

```txt
# Telegram Bot
python-telegram-bot>=20.0
python-telegram-bot[job-queue]>=20.0

# Claude Agent SDK
claude-agent-sdk>=1.0.0

# Async support
aiohttp>=3.9.0
asyncio>=3.4.3
```

#### 執行步驟

```bash
# 1. 備份現有 requirements.txt
cp requirements.txt requirements.txt.backup

# 2. 安裝新增的依賴套件
pip install python-telegram-bot>=20.0 python-telegram-bot[job-queue]>=20.0
pip install claude-agent-sdk>=1.0.0
pip install aiohttp>=3.9.0

# 3. 驗證安裝
py -3.12 -c "import telegram; print(f'python-telegram-bot version: {telegram.__version__}')"
py -3.12 -c "import claude_agent_sdk; print('claude-agent-sdk installed')"
```

#### 成功標準

**自動驗證：**
- [ ] 所有套件安裝成功，無錯誤訊息
- [ ] 可成功 import telegram 和 claude_agent_sdk

**手動驗證：**
- [ ] requirements.txt 已更新並包含新套件
- [ ] 無套件版本衝突

---

### 1.2 更新環境變數設定

#### 目標
新增 Telegram Bot Token 和 Anthropic API Key 到環境變數設定檔。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\.env.example`

#### 變更內容

在現有 MT5 設定後新增：

```env
# ============================================================================
# Telegram Bot 設定
# ============================================================================

# Telegram Bot Token（必要）
# 從 @BotFather 取得
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# 管理員用戶 ID（可選，用逗號分隔）
# 可以透過 @userinfobot 取得自己的 Telegram User ID
TELEGRAM_ADMIN_IDS=123456789,987654321

# ============================================================================
# Claude API 設定
# ============================================================================

# Anthropic API Key（必要）
# 從 https://console.anthropic.com/ 取得
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ============================================================================
# 其他設定
# ============================================================================

# 除錯模式（可選，預設為 false）
DEBUG=false
```

#### 執行步驟

```bash
# 1. 如果尚未建立 .env 檔案，複製範本
cp .env.example .env

# 2. 編輯 .env 檔案，填入實際的 Token 和 API Key
# （手動編輯，或使用以下指令）

# 3. 驗證 .env 檔案格式
py -3.12 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('TELEGRAM_BOT_TOKEN:', 'SET' if os.getenv('TELEGRAM_BOT_TOKEN') else 'NOT SET')"
```

#### 成功標準

**自動驗證：**
- [ ] .env.example 已更新
- [ ] .env 檔案存在且可被 python-dotenv 正確載入

**手動驗證：**
- [ ] TELEGRAM_BOT_TOKEN 已設定為有效的 Bot Token
- [ ] ANTHROPIC_API_KEY 已設定為有效的 API Key
- [ ] .env 檔案不在版本控制中（確認 .gitignore 包含 .env）

---

### 1.3 建立目錄結構

#### 目標
建立 Agent 工具層和 Bot 層所需的目錄結構。

#### 執行步驟

```bash
# 建立 Agent 工具層目錄
mkdir -p src/agent

# 建立 Bot 層目錄
mkdir -p src/bot

# 建立測試目錄
mkdir -p tests/agent
mkdir -p tests/bot

# 建立設定檔目錄（如果不存在）
mkdir -p config

# 建立啟動腳本目錄
mkdir -p scripts

# 驗證目錄結構
tree src -L 2
```

#### 預期目錄結構

```
chip-whisperer/
├── src/
│   ├── core/                    # 現有核心模組
│   │   ├── __init__.py
│   │   ├── mt5_config.py
│   │   ├── mt5_client.py
│   │   └── data_fetcher.py
│   ├── agent/                   # 新增：Agent 工具層
│   │   └── （此階段為空）
│   └── bot/                     # 新增：Telegram Bot 層
│       └── （此階段為空）
├── tests/
│   ├── agent/                   # 新增：Agent 測試
│   └── bot/                     # 新增：Bot 測試
├── config/                      # 設定檔目錄
├── scripts/                     # 啟動腳本目錄
└── ...（其他現有目錄）
```

#### 成功標準

**自動驗證：**
- [ ] 所有目錄建立成功：`ls src/agent src/bot tests/agent tests/bot config scripts`

**手動驗證：**
- [ ] 目錄結構與預期一致

---

## 階段二：Agent 工具層

### 概覽

建立 Claude Agent SDK 自訂工具，封裝現有 `src/core` 模組的功能，並實作技術指標計算模組。

### 2.1 建立技術指標計算模組

#### 目標
建立獨立的技術指標計算模組，提供 Volume Profile、SMA、RSI 等指標計算功能。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\agent\__init__.py`

#### 內容

```python
"""
Agent 工具層模組

此模組提供 Claude Agent SDK 自訂工具和技術指標計算功能。
"""

from .indicators import (
    calculate_volume_profile,
    calculate_sma,
    calculate_rsi,
    calculate_bollinger_bands
)
from .tools import (
    get_candles,
    calculate_vp_tool,
    calculate_sma_tool,
    calculate_rsi_tool,
    get_account_info_tool
)
from .mcp_server import create_mt5_mcp_server, get_allowed_tools

__all__ = [
    # 指標計算函式
    'calculate_volume_profile',
    'calculate_sma',
    'calculate_rsi',
    'calculate_bollinger_bands',
    # Agent 工具
    'get_candles',
    'calculate_vp_tool',
    'calculate_sma_tool',
    'calculate_rsi_tool',
    'get_account_info_tool',
    # MCP 伺服器
    'create_mt5_mcp_server',
    'get_allowed_tools',
]
```

---

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\agent\indicators.py`

#### 內容

```python
"""
技術指標計算模組

此模組提供各種技術指標的計算功能，可被 Agent 工具調用。
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

    參數：
        df: K 線資料 DataFrame（必須包含 'high', 'low', 'real_volume' 欄位）
        price_bins: 價格區間數量（預設 100）

    回傳：
        (profile_df, metrics) 元組
        - profile_df: Volume Profile DataFrame，包含 'price' 和 'volume' 欄位
        - metrics: 包含 POC、VAH、VAL 的字典

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    logger.info(f"開始計算 Volume Profile（價格區間數：{price_bins}）")

    # 驗證輸入資料
    required_columns = ['high', 'low', 'real_volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    if len(df) == 0:
        raise ValueError("輸入資料為空")

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
    profile_df_sorted_by_volume = profile_df.sort_values('volume', ascending=False)

    # 5. 計算 POC (Point of Control) - 成交量最大的價位
    poc_price = profile_df_sorted_by_volume.iloc[0]['price']
    poc_volume = profile_df_sorted_by_volume.iloc[0]['volume']

    logger.info(f"POC (Point of Control)：{poc_price:.2f}，成交量：{poc_volume:.0f}")

    # 6. 計算 Value Area (70% 成交量區間)
    total_volume = volumes.sum()
    target_volume = total_volume * 0.70

    # 從 POC 開始向兩側擴展，直到達到 70% 成交量
    profile_df_sorted_by_price = profile_df.sort_values('price')
    poc_idx = profile_df_sorted_by_price[
        profile_df_sorted_by_price['price'] == poc_price
    ].index[0]

    # 初始化 Value Area
    value_area_volume = poc_volume
    lower_idx = poc_idx
    upper_idx = poc_idx

    # 向兩側擴展
    while value_area_volume < target_volume:
        # 檢查是否還有空間擴展
        can_expand_lower = lower_idx > 0
        can_expand_upper = upper_idx < len(profile_df_sorted_by_price) - 1

        if not can_expand_lower and not can_expand_upper:
            break

        # 選擇成交量較大的一側擴展
        lower_volume = (
            profile_df_sorted_by_price.iloc[lower_idx - 1]['volume']
            if can_expand_lower else 0
        )
        upper_volume = (
            profile_df_sorted_by_price.iloc[upper_idx + 1]['volume']
            if can_expand_upper else 0
        )

        if lower_volume > upper_volume and can_expand_lower:
            lower_idx -= 1
            value_area_volume += lower_volume
        elif can_expand_upper:
            upper_idx += 1
            value_area_volume += upper_volume

    # Value Area High (VAH) 和 Low (VAL)
    vah = profile_df_sorted_by_price.iloc[upper_idx]['price']
    val = profile_df_sorted_by_price.iloc[lower_idx]['price']

    logger.info(f"Value Area High (VAH)：{vah:.2f}")
    logger.info(f"Value Area Low (VAL)：{val:.2f}")
    logger.info(
        f"Value Area 成交量：{value_area_volume:.0f} "
        f"({value_area_volume/total_volume*100:.1f}%)"
    )

    # 7. 整理結果
    metrics = {
        'poc_price': float(poc_price),
        'poc_volume': float(poc_volume),
        'vah': float(vah),
        'val': float(val),
        'value_area_volume': float(value_area_volume),
        'total_volume': float(total_volume),
        'value_area_percentage': float(value_area_volume / total_volume * 100)
    }

    return profile_df, metrics


def calculate_sma(df: pd.DataFrame, window: int = 20, column: str = 'close') -> pd.Series:
    """
    計算簡單移動平均線 (Simple Moving Average)

    參數：
        df: K 線資料 DataFrame
        window: 移動平均視窗大小（預設 20）
        column: 用於計算的欄位名稱（預設 'close'）

    回傳：
        包含 SMA 值的 Series

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    if column not in df.columns:
        raise ValueError(f"DataFrame 中缺少欄位：{column}")

    if len(df) < window:
        raise ValueError(f"資料筆數（{len(df)}）少於視窗大小（{window}）")

    logger.info(f"計算 SMA（視窗大小：{window}）")
    sma = df[column].rolling(window=window).mean()

    return sma


def calculate_rsi(df: pd.DataFrame, window: int = 14, column: str = 'close') -> pd.Series:
    """
    計算相對強弱指標 (Relative Strength Index)

    參數：
        df: K 線資料 DataFrame
        window: RSI 視窗大小（預設 14）
        column: 用於計算的欄位名稱（預設 'close'）

    回傳：
        包含 RSI 值的 Series（範圍 0-100）

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    if column not in df.columns:
        raise ValueError(f"DataFrame 中缺少欄位：{column}")

    if len(df) < window + 1:
        raise ValueError(f"資料筆數（{len(df)}）不足以計算 RSI（需要至少 {window + 1} 筆）")

    logger.info(f"計算 RSI（視窗大小：{window}）")

    # 計算價格變動
    delta = df[column].diff()

    # 分離漲跌
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # 計算平均漲跌
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    # 計算 RS 和 RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_bollinger_bands(
    df: pd.DataFrame,
    window: int = 20,
    num_std: float = 2.0,
    column: str = 'close'
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    計算布林通道 (Bollinger Bands)

    參數：
        df: K 線資料 DataFrame
        window: 移動平均視窗大小（預設 20）
        num_std: 標準差倍數（預設 2.0）
        column: 用於計算的欄位名稱（預設 'close'）

    回傳：
        (upper_band, middle_band, lower_band) 元組

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    if column not in df.columns:
        raise ValueError(f"DataFrame 中缺少欄位：{column}")

    if len(df) < window:
        raise ValueError(f"資料筆數（{len(df)}）少於視窗大小（{window}）")

    logger.info(f"計算布林通道（視窗：{window}，標準差倍數：{num_std}）")

    # 中軌 = SMA
    middle_band = df[column].rolling(window=window).mean()

    # 計算標準差
    std = df[column].rolling(window=window).std()

    # 上軌和下軌
    upper_band = middle_band + (std * num_std)
    lower_band = middle_band - (std * num_std)

    return upper_band, middle_band, lower_band
```

#### 成功標準

**自動驗證：**
- [ ] 檔案可成功 import：`py -3.12 -c "from src.agent.indicators import calculate_volume_profile, calculate_sma, calculate_rsi"`
- [ ] 無語法錯誤

**手動驗證：**
- [ ] 所有函式都有完整的 docstring
- [ ] 所有函式都有適當的錯誤處理

---

### 2.2 建立 Agent 工具定義

#### 目標
使用 `@tool` 裝飾器定義 Claude Agent SDK 可調用的工具，封裝 `src/core` 模組和指標計算功能。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\agent\tools.py`

#### 內容

```python
"""
Agent 自訂工具定義

此模組定義所有 Claude Agent SDK 可調用的工具，
封裝 src/core 模組的功能和技術指標計算。
"""

from typing import Any, Dict
from claude_agent_sdk import tool
from loguru import logger
import pandas as pd
import json

# 匯入核心模組
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher
from .indicators import (
    calculate_volume_profile,
    calculate_sma,
    calculate_rsi,
    calculate_bollinger_bands
)


# ============================================================================
# MT5 連線管理
# ============================================================================

# 全域 MT5 客戶端實例（單例模式）
_mt5_client = None
_mt5_config = None


def get_mt5_client() -> ChipWhispererMT5Client:
    """
    取得 MT5 客戶端單例

    回傳：
        MT5 客戶端實例

    例外：
        RuntimeError: MT5 連線失敗時
    """
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

        logger.info(
            f"工具調用：get_candles(symbol={symbol}, "
            f"timeframe={timeframe}, count={count})"
        )

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

        # 將 DataFrame 轉換為可序列化的格式
        candles_data = df.to_dict('records')

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

        result_message = (
            f"成功取得 {symbol} {timeframe} K 線資料\n"
            f"數量：{len(df)} 根\n"
            f"時間範圍：{summary['date_range']['from']} ~ {summary['date_range']['to']}\n"
            f"最新收盤價：{summary['price_range']['latest_close']:.2f}"
        )

        logger.info(result_message)

        return {
            "content": [{"type": "text", "text": result_message}],
            "data": {
                "candles": candles_data,
                "summary": summary
            }
        }

    except ValueError as e:
        error_msg = f"參數錯誤：{str(e)}"
        logger.error(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "is_error": True
        }
    except Exception as e:
        error_msg = f"取得 K 線資料失敗：{str(e)}"
        logger.exception(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "is_error": True
        }


# ============================================================================
# 技術指標計算工具
# ============================================================================

@tool(
    "calculate_volume_profile",
    "計算 Volume Profile（POC、VAH、VAL）",
    {
        "candles_data": str,  # JSON 格式的 K 線資料
        "price_bins": int     # 價格區間數量，預設 100
    }
)
async def calculate_vp_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    計算 Volume Profile

    參數：
        candles_data: JSON 格式的 K 線資料（由 get_candles 工具提供）
        price_bins: 價格區間數量（預設 100）

    回傳：
        包含 POC、VAH、VAL 的結果字典
    """
    try:
        # 解析 K 線資料
        candles_json = args.get("candles_data")
        if isinstance(candles_json, str):
            candles_list = json.loads(candles_json)
        else:
            candles_list = candles_json

        df = pd.DataFrame(candles_list)

        # 取得價格區間數量
        price_bins = int(args.get("price_bins", 100))

        logger.info(f"工具調用：calculate_volume_profile(price_bins={price_bins})")

        # 計算 Volume Profile
        profile_df, metrics = calculate_volume_profile(df, price_bins)

        result_message = (
            f"Volume Profile 計算完成\n\n"
            f"關鍵價位：\n"
            f"  POC (Point of Control):  {metrics['poc_price']:.2f}\n"
            f"  VAH (Value Area High):   {metrics['vah']:.2f}\n"
            f"  VAL (Value Area Low):    {metrics['val']:.2f}\n"
            f"  Value Area 範圍:          {metrics['vah'] - metrics['val']:.2f} 點\n\n"
            f"成交量統計：\n"
            f"  總成交量:                 {metrics['total_volume']:.0f}\n"
            f"  POC 成交量:              {metrics['poc_volume']:.0f}\n"
            f"  Value Area 佔比:         {metrics['value_area_percentage']:.1f}%"
        )

        logger.info("Volume Profile 計算成功")

        return {
            "content": [{"type": "text", "text": result_message}],
            "data": {
                "metrics": metrics,
                "profile": profile_df.to_dict('records')
            }
        }

    except ValueError as e:
        error_msg = f"參數錯誤：{str(e)}"
        logger.error(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "is_error": True
        }
    except Exception as e:
        error_msg = f"計算 Volume Profile 失敗：{str(e)}"
        logger.exception(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "is_error": True
        }


@tool(
    "calculate_sma",
    "計算簡單移動平均線 (SMA)",
    {
        "candles_data": str,  # JSON 格式的 K 線資料
        "window": int,        # 移動平均視窗大小
        "column": str         # 計算欄位（預設 'close'）
    }
)
async def calculate_sma_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    計算簡單移動平均線

    參數：
        candles_data: JSON 格式的 K 線資料
        window: 移動平均視窗大小（預設 20）
        column: 計算欄位（預設 'close'）

    回傳：
        包含 SMA 值的結果字典
    """
    try:
        # 解析 K 線資料
        candles_json = args.get("candles_data")
        if isinstance(candles_json, str):
            candles_list = json.loads(candles_json)
        else:
            candles_list = candles_json

        df = pd.DataFrame(candles_list)

        # 取得參數
        window = int(args.get("window", 20))
        column = args.get("column", "close")

        logger.info(f"工具調用：calculate_sma(window={window}, column={column})")

        # 計算 SMA
        sma = calculate_sma(df, window, column)

        # 取得最新值
        latest_sma = float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None

        result_message = (
            f"SMA 計算完成\n"
            f"視窗大小：{window}\n"
            f"計算欄位：{column}\n"
            f"最新 SMA 值：{latest_sma:.2f if latest_sma else 'N/A'}"
        )

        logger.info("SMA 計算成功")

        return {
            "content": [{"type": "text", "text": result_message}],
            "data": {
                "window": window,
                "column": column,
                "latest_value": latest_sma,
                "values": sma.tolist()
            }
        }

    except ValueError as e:
        error_msg = f"參數錯誤：{str(e)}"
        logger.error(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "is_error": True
        }
    except Exception as e:
        error_msg = f"計算 SMA 失敗：{str(e)}"
        logger.exception(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "is_error": True
        }


@tool(
    "calculate_rsi",
    "計算相對強弱指標 (RSI)",
    {
        "candles_data": str,  # JSON 格式的 K 線資料
        "window": int,        # RSI 視窗大小
        "column": str         # 計算欄位（預設 'close'）
    }
)
async def calculate_rsi_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    計算相對強弱指標

    參數：
        candles_data: JSON 格式的 K 線資料
        window: RSI 視窗大小（預設 14）
        column: 計算欄位（預設 'close'）

    回傳：
        包含 RSI 值的結果字典
    """
    try:
        # 解析 K 線資料
        candles_json = args.get("candles_data")
        if isinstance(candles_json, str):
            candles_list = json.loads(candles_json)
        else:
            candles_list = candles_json

        df = pd.DataFrame(candles_list)

        # 取得參數
        window = int(args.get("window", 14))
        column = args.get("column", "close")

        logger.info(f"工具調用：calculate_rsi(window={window}, column={column})")

        # 計算 RSI
        rsi = calculate_rsi(df, window, column)

        # 取得最新值
        latest_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

        # 判斷超買超賣
        if latest_rsi:
            if latest_rsi > 70:
                status = "超買區域"
            elif latest_rsi < 30:
                status = "超賣區域"
            else:
                status = "中性區域"
        else:
            status = "N/A"

        result_message = (
            f"RSI 計算完成\n"
            f"視窗大小：{window}\n"
            f"計算欄位：{column}\n"
            f"最新 RSI 值：{latest_rsi:.2f if latest_rsi else 'N/A'}\n"
            f"狀態：{status}"
        )

        logger.info("RSI 計算成功")

        return {
            "content": [{"type": "text", "text": result_message}],
            "data": {
                "window": window,
                "column": column,
                "latest_value": latest_rsi,
                "status": status,
                "values": rsi.tolist()
            }
        }

    except ValueError as e:
        error_msg = f"參數錯誤：{str(e)}"
        logger.error(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "is_error": True
        }
    except Exception as e:
        error_msg = f"計算 RSI 失敗：{str(e)}"
        logger.exception(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
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
    """
    取得 MT5 帳戶資訊

    回傳：
        包含帳戶資訊的結果字典
    """
    try:
        logger.info("工具調用：get_account_info()")

        # 取得 MT5 客戶端
        client = get_mt5_client()

        # 取得帳戶資訊
        account_info = client.get_account_info()

        if not account_info:
            raise RuntimeError("無法取得帳戶資訊")

        result_message = (
            f"帳戶資訊\n\n"
            f"帳號：{account_info['login']}\n"
            f"伺服器：{account_info['server']}\n"
            f"餘額：{account_info['balance']} {account_info['currency']}\n"
            f"淨值：{account_info['equity']} {account_info['currency']}\n"
            f"槓桿：1:{account_info['leverage']}\n"
            f"保證金：{account_info['margin']} {account_info['currency']}\n"
            f"可用保證金：{account_info['margin_free']} {account_info['currency']}"
        )

        logger.info("成功取得帳戶資訊")

        return {
            "content": [{"type": "text", "text": result_message}],
            "data": account_info
        }

    except Exception as e:
        error_msg = f"取得帳戶資訊失敗：{str(e)}"
        logger.exception(error_msg)
        return {
            "content": [{"type": "text", "text": error_msg}],
            "is_error": True
        }
```

#### 成功標準

**自動驗證：**
- [ ] 檔案可成功 import：`py -3.12 -c "from src.agent.tools import get_candles, calculate_vp_tool"`
- [ ] 無語法錯誤

**手動驗證：**
- [ ] 所有工具都使用 `@tool` 裝飾器正確定義
- [ ] 所有工具都有完整的錯誤處理

---

### 2.3 建立 MCP 伺服器

#### 目標
建立 MCP 伺服器，將所有工具整合並提供給 Claude Agent SDK 使用。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\agent\mcp_server.py`

#### 內容

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

#### 成功標準

**自動驗證：**
- [ ] 檔案可成功 import：`py -3.12 -c "from src.agent.mcp_server import create_mt5_mcp_server"`
- [ ] 可成功建立 MCP 伺服器（需要有效的 ANTHROPIC_API_KEY）

**手動驗證：**
- [ ] MCP 伺服器包含所有預期的工具

---

### 2.4 單元測試

#### 目標
建立 Agent 工具層的單元測試，確保各模組功能正常。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\tests\agent\test_indicators.py`

#### 內容

```python
"""
技術指標計算模組測試
"""

import pytest
import pandas as pd
import numpy as np
from src.agent.indicators import (
    calculate_volume_profile,
    calculate_sma,
    calculate_rsi,
    calculate_bollinger_bands
)


@pytest.fixture
def sample_candles():
    """產生測試用 K 線資料"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='H')

    df = pd.DataFrame({
        'time': dates,
        'open': np.random.uniform(2000, 2100, 100),
        'high': np.random.uniform(2050, 2150, 100),
        'low': np.random.uniform(1950, 2050, 100),
        'close': np.random.uniform(2000, 2100, 100),
        'real_volume': np.random.randint(1000, 10000, 100)
    })

    return df


def test_calculate_volume_profile(sample_candles):
    """測試 Volume Profile 計算"""
    profile_df, metrics = calculate_volume_profile(sample_candles, price_bins=50)

    # 驗證回傳格式
    assert isinstance(profile_df, pd.DataFrame)
    assert isinstance(metrics, dict)

    # 驗證 DataFrame 欄位
    assert 'price' in profile_df.columns
    assert 'volume' in profile_df.columns

    # 驗證 metrics 欄位
    assert 'poc_price' in metrics
    assert 'vah' in metrics
    assert 'val' in metrics
    assert 'total_volume' in metrics

    # 驗證邏輯正確性
    assert metrics['vah'] > metrics['val']
    assert metrics['poc_price'] >= metrics['val']
    assert metrics['poc_price'] <= metrics['vah']


def test_calculate_sma(sample_candles):
    """測試 SMA 計算"""
    sma = calculate_sma(sample_candles, window=20)

    # 驗證回傳類型
    assert isinstance(sma, pd.Series)

    # 驗證長度
    assert len(sma) == len(sample_candles)

    # 驗證前 19 個值為 NaN（視窗大小 20）
    assert pd.isna(sma.iloc[:19]).all()

    # 驗證第 20 個值不為 NaN
    assert not pd.isna(sma.iloc[19])


def test_calculate_rsi(sample_candles):
    """測試 RSI 計算"""
    rsi = calculate_rsi(sample_candles, window=14)

    # 驗證回傳類型
    assert isinstance(rsi, pd.Series)

    # 驗證長度
    assert len(rsi) == len(sample_candles)

    # 驗證 RSI 值在 0-100 範圍內（排除 NaN）
    valid_rsi = rsi.dropna()
    assert (valid_rsi >= 0).all()
    assert (valid_rsi <= 100).all()


def test_calculate_bollinger_bands(sample_candles):
    """測試布林通道計算"""
    upper, middle, lower = calculate_bollinger_bands(sample_candles, window=20, num_std=2.0)

    # 驗證回傳類型
    assert isinstance(upper, pd.Series)
    assert isinstance(middle, pd.Series)
    assert isinstance(lower, pd.Series)

    # 驗證長度
    assert len(upper) == len(sample_candles)

    # 驗證邏輯正確性（排除 NaN）
    valid_idx = ~middle.isna()
    assert (upper[valid_idx] >= middle[valid_idx]).all()
    assert (middle[valid_idx] >= lower[valid_idx]).all()


def test_volume_profile_error_handling():
    """測試 Volume Profile 錯誤處理"""
    # 測試空 DataFrame
    empty_df = pd.DataFrame()
    with pytest.raises(ValueError):
        calculate_volume_profile(empty_df)

    # 測試缺少必要欄位
    incomplete_df = pd.DataFrame({'close': [1, 2, 3]})
    with pytest.raises(ValueError):
        calculate_volume_profile(incomplete_df)
```

#### 執行測試

```bash
# 執行所有 agent 測試
pytest tests/agent/ -v

# 執行特定測試
pytest tests/agent/test_indicators.py::test_calculate_volume_profile -v
```

#### 成功標準

**自動驗證：**
- [ ] 所有測試通過：`pytest tests/agent/test_indicators.py -v`
- [ ] 測試覆蓋率達 80% 以上

**手動驗證：**
- [ ] 測試涵蓋主要功能和錯誤情況

---

## 階段三：Telegram Bot 整合

### 概覽

建立 Telegram Bot 主程式和訊息處理器，整合 Claude Agent SDK 處理用戶查詢。

### 3.1 建立 Bot 設定管理

#### 目標
建立 Bot 設定管理模組，載入環境變數和驗證設定。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\bot\__init__.py`

#### 內容

```python
"""
Telegram Bot 模組

此模組提供 Telegram Bot 整合功能。
"""

from .config import BotConfig
from .telegram_bot import TradingAssistantBot
from .handlers import (
    start_command,
    help_command,
    status_command,
    account_command,
    message_handler,
    error_handler
)

__all__ = [
    'BotConfig',
    'TradingAssistantBot',
    'start_command',
    'help_command',
    'status_command',
    'account_command',
    'message_handler',
    'error_handler',
]
```

---

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\bot\config.py`

#### 內容

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
            raise ValueError(
                "TELEGRAM_BOT_TOKEN 未設定。\n"
                "請在 .env 檔案中設定 TELEGRAM_BOT_TOKEN"
            )

        # Claude API Key（必要）
        self.claude_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.claude_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY 未設定。\n"
                "請在 .env 檔案中設定 ANTHROPIC_API_KEY"
            )

        # 設定 Claude API Key 為環境變數（供 Claude SDK 使用）
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
            return [
                int(id_str.strip())
                for id_str in admin_ids_str.split(',')
                if id_str.strip()
            ]
        except ValueError:
            logger.warning("TELEGRAM_ADMIN_IDS 格式錯誤，應為逗號分隔的數字")
            return []

    def is_admin(self, user_id: int) -> bool:
        """
        檢查是否為管理員

        參數：
            user_id: Telegram 用戶 ID

        回傳：
            True 如果是管理員，否則 False
        """
        return user_id in self.admin_user_ids
```

#### 成功標準

**自動驗證：**
- [ ] 檔案可成功 import：`py -3.12 -c "from src.bot.config import BotConfig"`
- [ ] 設定載入成功（需要有效的 .env 檔案）

**手動驗證：**
- [ ] 缺少 TELEGRAM_BOT_TOKEN 時會拋出 ValueError
- [ ] 缺少 ANTHROPIC_API_KEY 時會拋出 ValueError

---

### 3.2 建立訊息處理器

#### 目標
建立 Telegram Bot 的訊息和指令處理器。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\bot\handlers.py`

#### 內容

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

# 匯入 Agent 模組
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.mcp_server import create_mt5_mcp_server, get_allowed_tools


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
        from agent.tools import get_mt5_client
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
        from agent.tools import get_mt5_client
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
                f"保證金：{account_info['margin']} {account_info['currency']}\n"
                f"可用保證金：{account_info['margin_free']} {account_info['currency']}"
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
                # 處理不同類型的訊息
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
                # Telegram 訊息長度限制為 4096 字元
                if len(response_text) > 4000:
                    # 分段發送
                    chunks = [
                        response_text[i:i+4000]
                        for i in range(0, len(response_text), 4000)
                    ]
                    await status_message.edit_text(chunks[0])
                    for chunk in chunks[1:]:
                        await update.message.reply_text(chunk)
                else:
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

#### 成功標準

**自動驗證：**
- [ ] 檔案可成功 import：`py -3.12 -c "from src.bot.handlers import start_command, message_handler"`
- [ ] 無語法錯誤

**手動驗證：**
- [ ] 所有處理器函式都是非同步函式
- [ ] 錯誤處理完整

---

### 3.3 建立 Bot 主程式

#### 目標
建立 Telegram Bot 主程式，整合所有處理器並提供啟動介面。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\bot\telegram_bot.py`

#### 內容

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
        logger.info("按 Ctrl+C 停止 Bot")
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
        level="DEBUG",
        encoding="utf-8"
    )
    logger.add(
        lambda msg: print(msg, end=''),
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
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

#### 成功標準

**自動驗證：**
- [ ] 檔案可成功 import：`py -3.12 -c "from src.bot.telegram_bot import TradingAssistantBot"`
- [ ] 無語法錯誤

**手動驗證：**
- [ ] Bot 可成功建立（需要有效的 Bot Token）

---

### 3.4 建立啟動腳本

#### 目標
建立簡便的啟動腳本，方便執行 Bot。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\scripts\run_bot.py`

#### 內容

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot 啟動腳本

使用方式：
    py -3.12 scripts/run_bot.py

環境變數：
    TELEGRAM_BOT_TOKEN - Telegram Bot Token（必要）
    ANTHROPIC_API_KEY - Anthropic API Key（必要）
    MT5_LOGIN - MT5 帳號（必要）
    MT5_PASSWORD - MT5 密碼（必要）
    MT5_SERVER - MT5 伺服器（必要）
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

#### 執行步驟

```bash
# 確保所有環境變數都已設定
cat .env

# 啟動 Bot
py -3.12 scripts/run_bot.py
```

#### 成功標準

**自動驗證：**
- [ ] 腳本可成功執行（需要有效的環境變數）

**手動驗證：**
- [ ] Bot 在 Telegram 上可正常回應 /start 指令
- [ ] Bot 可回應簡單的文字訊息

---

### 3.5 整合測試

#### 目標
進行完整的整合測試，確保 Bot、Agent 和 MT5 三層整合正常。

#### 測試步驟

```bash
# 1. 啟動 Bot
py -3.12 scripts/run_bot.py

# 2. 在 Telegram 中測試以下指令和訊息：

# 指令測試
/start
/help
/status
/account

# 簡單查詢測試
「取得 GOLD H1 最新 10 根 K 線」
「計算 GOLD H1 的 Volume Profile」
「SILVER 的 20 期 SMA 是多少？」
「幫我分析 GOLD H1 的 RSI」

# 複雜查詢測試
「目前黃金的 H1 成本價位在哪裡？」
「分析 SILVER H4 的技術指標」
```

#### 成功標準

**自動驗證：**
無（整合測試需要手動執行）

**手動驗證：**
- [ ] Bot 可正常啟動並連線到 Telegram
- [ ] 所有指令都能正確回應
- [ ] Bot 能正確調用 MT5 工具取得資料
- [ ] Bot 能正確計算技術指標
- [ ] 錯誤訊息清晰易懂
- [ ] 回應時間合理（< 10 秒）

---

## 階段四：完整整合和優化

### 概覽

整合所有組件，進行錯誤處理優化、效能調校和部署準備。

### 4.1 錯誤處理優化

#### 目標
完善錯誤處理機制，提供更友善的錯誤訊息。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\bot\error_formatter.py`

#### 內容

```python
"""
錯誤訊息格式化模組

將技術性錯誤訊息轉換為用戶友善的說明。
"""

from typing import Dict


class ErrorFormatter:
    """錯誤訊息格式化器"""

    # 錯誤訊息對應表
    ERROR_MESSAGES: Dict[str, str] = {
        "MT5_LOGIN_FAILED": (
            "❌ MT5 登入失敗\n\n"
            "可能原因：\n"
            "• 帳號或密碼錯誤\n"
            "• 伺服器連線問題\n"
            "• MT5 終端機未啟動\n\n"
            "請聯繫管理員檢查設定。"
        ),
        "MT5_NOT_CONNECTED": (
            "❌ MT5 未連線\n\n"
            "請稍後再試，或輸入 /status 檢查系統狀態。"
        ),
        "INVALID_SYMBOL": (
            "❌ 無效的商品代碼\n\n"
            "請確認商品代碼是否正確，例如：\n"
            "• GOLD（黃金）\n"
            "• SILVER（白銀）\n"
            "• USDJPY（美元日圓）"
        ),
        "INVALID_TIMEFRAME": (
            "❌ 無效的時間週期\n\n"
            "支援的時間週期：\n"
            "• M1, M5, M15, M30（分鐘線）\n"
            "• H1, H4（小時線）\n"
            "• D1（日線）\n"
            "• W1（週線）"
        ),
        "INSUFFICIENT_DATA": (
            "❌ 資料不足\n\n"
            "無法取得足夠的歷史資料來進行計算。\n"
            "請嘗試：\n"
            "• 縮小時間範圍\n"
            "• 選擇更長的時間週期\n"
            "• 檢查商品是否有歷史資料"
        ),
        "CALCULATION_ERROR": (
            "❌ 計算錯誤\n\n"
            "指標計算過程中發生錯誤。\n"
            "請檢查：\n"
            "• 參數設定是否合理\n"
            "• 資料完整性"
        ),
        "UNKNOWN_ERROR": (
            "❌ 發生未知錯誤\n\n"
            "請稍後再試，或聯繫管理員。"
        )
    }

    @classmethod
    def format_error(cls, error: Exception) -> str:
        """
        格式化錯誤訊息

        參數：
            error: 異常物件

        回傳：
            用戶友善的錯誤訊息
        """
        error_str = str(error).lower()

        # 根據錯誤訊息內容判斷錯誤類型
        if "login" in error_str or "authentication" in error_str:
            return cls.ERROR_MESSAGES["MT5_LOGIN_FAILED"]
        elif "not connected" in error_str or "connection" in error_str:
            return cls.ERROR_MESSAGES["MT5_NOT_CONNECTED"]
        elif "invalid symbol" in error_str or "symbol" in error_str:
            return cls.ERROR_MESSAGES["INVALID_SYMBOL"]
        elif "timeframe" in error_str:
            return cls.ERROR_MESSAGES["INVALID_TIMEFRAME"]
        elif "insufficient" in error_str or "not enough" in error_str:
            return cls.ERROR_MESSAGES["INSUFFICIENT_DATA"]
        elif "calculation" in error_str or "compute" in error_str:
            return cls.ERROR_MESSAGES["CALCULATION_ERROR"]
        else:
            return cls.ERROR_MESSAGES["UNKNOWN_ERROR"]
```

#### 在 handlers.py 中使用

修改 `message_handler` 函式的錯誤處理部分：

```python
except Exception as e:
    logger.exception(f"處理訊息失敗：{e}")
    from .error_formatter import ErrorFormatter
    friendly_message = ErrorFormatter.format_error(e)
    await status_message.edit_text(friendly_message)
```

#### 成功標準

**手動驗證：**
- [ ] 各種錯誤情況都能顯示友善的訊息
- [ ] 錯誤訊息包含實用的解決建議

---

### 4.2 效能優化

#### 目標
優化 MT5 客戶端連線管理和資料快取。

#### 優化項目

1. **MT5 連線池**：避免重複建立連線
2. **資料快取**：快取最近查詢的資料
3. **非同步處理**：優化長時間運算

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\agent\cache_manager.py`

#### 內容

```python
"""
資料快取管理模組

提供簡單的記憶體快取功能，減少重複的 MT5 查詢。
"""

from typing import Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import hashlib
import json


@dataclass
class CacheEntry:
    """快取項目"""
    key: str
    value: Any
    expires_at: datetime


class CacheManager:
    """簡單的記憶體快取管理器"""

    def __init__(self, default_ttl: int = 300):
        """
        初始化快取管理器

        參數：
            default_ttl: 預設快取時間（秒），預設 5 分鐘
        """
        self._cache: dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl

    def _generate_key(self, **kwargs) -> str:
        """
        生成快取鍵

        參數：
            **kwargs: 用於生成鍵的參數

        回傳：
            快取鍵（MD5 雜湊）
        """
        # 將參數序列化為 JSON 字串
        params_str = json.dumps(kwargs, sort_keys=True)
        # 計算 MD5 雜湊
        return hashlib.md5(params_str.encode()).hexdigest()

    def get(self, **kwargs) -> Optional[Any]:
        """
        取得快取值

        參數：
            **kwargs: 用於查詢的參數

        回傳：
            快取值，如果不存在或已過期則回傳 None
        """
        key = self._generate_key(**kwargs)
        entry = self._cache.get(key)

        if entry is None:
            return None

        # 檢查是否過期
        if datetime.now() > entry.expires_at:
            del self._cache[key]
            return None

        return entry.value

    def set(self, value: Any, ttl: Optional[int] = None, **kwargs) -> None:
        """
        設定快取值

        參數：
            value: 要快取的值
            ttl: 快取時間（秒），如果為 None 則使用預設值
            **kwargs: 用於生成鍵的參數
        """
        key = self._generate_key(**kwargs)
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)

        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            expires_at=expires_at
        )

    def clear(self) -> None:
        """清空所有快取"""
        self._cache.clear()

    def remove_expired(self) -> None:
        """移除所有過期的快取項目"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry.expires_at
        ]
        for key in expired_keys:
            del self._cache[key]


# 全域快取實例
_global_cache = CacheManager()


def get_cache() -> CacheManager:
    """取得全域快取實例"""
    return _global_cache
```

#### 在 tools.py 中使用快取

修改 `get_candles` 工具：

```python
from .cache_manager import get_cache

@tool("get_candles", ...)
async def get_candles(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        symbol = args.get("symbol", "GOLD").upper()
        timeframe = args.get("timeframe", "H1").upper()
        count = int(args.get("count", 100))

        # 檢查快取
        cache = get_cache()
        cached_data = cache.get(
            tool="get_candles",
            symbol=symbol,
            timeframe=timeframe,
            count=count
        )

        if cached_data:
            logger.info(f"使用快取資料：{symbol} {timeframe}")
            return cached_data

        # ... 原有的取得資料邏輯 ...

        # 儲存到快取（5 分鐘）
        cache.set(result, ttl=300,
            tool="get_candles",
            symbol=symbol,
            timeframe=timeframe,
            count=count
        )

        return result
    except Exception as e:
        # ... 錯誤處理 ...
```

#### 成功標準

**手動驗證：**
- [ ] 相同的查詢在快取有效期內會使用快取資料
- [ ] 快取過期後會重新查詢
- [ ] 回應時間明顯改善

---

### 4.3 日誌和監控

#### 目標
完善日誌記錄，方便除錯和監控。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\src\bot\logger_setup.py`

#### 內容

```python
"""
日誌設定模組
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logger(log_dir: str = "logs", debug: bool = False):
    """
    設定全域日誌系統

    參數：
        log_dir: 日誌目錄路徑
        debug: 是否啟用 DEBUG 等級
    """
    # 移除預設處理器
    logger.remove()

    # 建立日誌目錄
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 控制台輸出（INFO 等級）
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
        level="DEBUG" if debug else "INFO",
        colorize=True
    )

    # 一般日誌檔案（INFO 等級）
    logger.add(
        log_path / "bot.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8"
    )

    # 錯誤日誌檔案（ERROR 等級）
    logger.add(
        log_path / "error.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8"
    )

    # DEBUG 日誌檔案（僅在 debug 模式）
    if debug:
        logger.add(
            log_path / "debug.log",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
                "{name}:{function}:{line} - {message}"
            ),
            level="DEBUG",
            rotation="10 MB",
            retention="3 days",
            encoding="utf-8"
        )

    logger.info("日誌系統初始化完成")
```

#### 在 telegram_bot.py 中使用

```python
from .logger_setup import setup_logger

def main():
    """主函式"""
    # 設定日誌
    setup_logger(debug=os.getenv('DEBUG', 'false').lower() == 'true')

    # ... 其餘程式碼 ...
```

#### 成功標準

**手動驗證：**
- [ ] 日誌檔案正確建立在 logs/ 目錄
- [ ] 不同等級的日誌分別記錄
- [ ] 日誌格式清晰易讀

---

### 4.4 部署準備

#### 目標
準備部署所需的文件和腳本。

#### 檔案：`C:\Users\fatfi\works\chip-whisperer\README_TELEGRAM_BOT.md`

#### 內容

```markdown
# Telegram Bot 使用指南

## 概述

本專案整合了 Telegram Bot、Claude Agent SDK 和 MT5，提供自然語言交易助手功能。

## 系統需求

- Python 3.10+
- MetaTrader 5 終端機
- Telegram Bot Token
- Anthropic API Key

## 安裝步驟

### 1. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

編輯 `.env` 檔案，填入以下資訊：

```env
# MT5 設定
MT5_LOGIN=你的MT5帳號
MT5_PASSWORD=你的MT5密碼
MT5_SERVER=你的MT5伺服器

# Telegram Bot
TELEGRAM_BOT_TOKEN=你的Bot Token
TELEGRAM_ADMIN_IDS=你的Telegram User ID

# Claude API
ANTHROPIC_API_KEY=你的Anthropic API Key
```

### 3. 取得 Telegram Bot Token

1. 在 Telegram 中搜尋 `@BotFather`
2. 發送 `/newbot` 指令
3. 按照提示設定 Bot 名稱和用戶名
4. 取得 Bot Token 並填入 `.env` 檔案

### 4. 取得 Anthropic API Key

1. 前往 https://console.anthropic.com/
2. 註冊並登入
3. 在 API Keys 頁面建立新的 API Key
4. 將 API Key 填入 `.env` 檔案

## 啟動 Bot

```bash
py -3.12 scripts/run_bot.py
```

## 使用說明

### 支援的指令

- `/start` - 開始使用
- `/help` - 顯示說明
- `/status` - 檢查系統狀態
- `/account` - 查看帳戶資訊

### 問題範例

- 「取得 GOLD H1 最新 100 根 K 線」
- 「計算 GOLD H1 的 Volume Profile」
- 「SILVER 的 20 期 SMA 是多少？」
- 「幫我分析 GOLD H1 的 RSI」
- 「目前黃金的 H1 成本價位在哪裡？」

## 故障排除

### Bot 無法啟動

1. 檢查 `.env` 檔案是否正確設定
2. 確認 MT5 終端機已啟動
3. 檢查網路連線

### MT5 連線失敗

1. 確認 MT5 帳號、密碼、伺服器設定正確
2. 檢查 MT5 終端機是否正常運作
3. 查看 `logs/error.log` 了解詳細錯誤訊息

### Bot 回應緩慢

1. 檢查網路連線品質
2. 確認 MT5 資料取得正常
3. 考慮調整查詢的資料量

## 開發說明

### 目錄結構

```
src/
├── core/           # MT5 核心模組
├── agent/          # Agent 工具層
│   ├── tools.py           # Agent 工具定義
│   ├── mcp_server.py      # MCP 伺服器
│   └── indicators.py      # 技術指標計算
└── bot/            # Telegram Bot 層
    ├── telegram_bot.py    # Bot 主程式
    ├── handlers.py        # 訊息處理器
    └── config.py          # 設定管理
```

### 新增自訂工具

1. 在 `src/agent/tools.py` 中使用 `@tool` 裝飾器定義新工具
2. 在 `src/agent/mcp_server.py` 中將工具加入伺服器
3. 更新 `get_allowed_tools()` 函式

### 執行測試

```bash
# 執行所有測試
pytest

# 執行特定測試
pytest tests/agent/test_indicators.py -v
```

## 授權

本專案採用 MIT 授權。
```

#### 成功標準

**手動驗證：**
- [ ] README 文件完整清晰
- [ ] 安裝步驟可正常執行
- [ ] 故障排除章節涵蓋常見問題

---

## 驗收標準

### 系統層級驗收

**自動驗證：**
- [ ] 所有單元測試通過：`pytest tests/ -v`
- [ ] 程式碼無語法錯誤
- [ ] 所有依賴套件正確安裝

**手動驗證：**
- [ ] Bot 可正常啟動並連線到 Telegram
- [ ] MT5 連線正常
- [ ] Claude Agent SDK 正常運作
- [ ] 所有指令都能正確回應
- [ ] 自然語言查詢可正確解析並執行
- [ ] 錯誤處理完善，錯誤訊息友善
- [ ] 日誌記錄完整

### 功能驗收

**資料取得：**
- [ ] 可成功取得各種商品的 K 線資料
- [ ] 支援所有時間週期（M1, H1, D1 等）
- [ ] 資料格式正確

**技術指標計算：**
- [ ] Volume Profile 計算正確（POC, VAH, VAL）
- [ ] SMA 計算正確
- [ ] RSI 計算正確
- [ ] 計算結果準確

**Bot 功能：**
- [ ] /start 指令顯示歡迎訊息
- [ ] /help 指令顯示說明
- [ ] /status 指令顯示系統狀態
- [ ] /account 指令顯示帳戶資訊
- [ ] 自然語言查詢正確回應

### 效能驗收

- [ ] 簡單查詢回應時間 < 5 秒
- [ ] 複雜計算回應時間 < 15 秒
- [ ] 相同查詢在快取有效期內 < 1 秒
- [ ] 記憶體使用合理（< 500 MB）

---

## 風險評估

### 技術風險

| 風險                  | 機率 | 影響 | 緩解措施                      |
|-----------------------|------|------|-------------------------------|
| MT5 連線不穩定        | 中   | 高   | 實作重連機制和錯誤處理        |
| Claude API 配額用盡   | 中   | 高   | 監控 API 使用量，設定使用限制 |
| Telegram Bot API 限制 | 低   | 中   | 遵守速率限制，分段發送長訊息  |
| 資料計算錯誤          | 低   | 高   | 完善單元測試，驗證計算邏輯    |

### 營運風險

| 風險           | 機率 | 影響 | 緩解措施                             |
|----------------|------|------|--------------------------------------|
| Bot Token 洩漏 | 低   | 高   | 嚴格管理 .env 檔案，不提交到版本控制 |
| MT5 帳號安全   | 低   | 高   | 使用唯讀帳號，限制操作權限           |
| 伺服器資源不足 | 中   | 中   | 監控資源使用，適時擴充               |

### 建議

1. **測試環境**：先在測試環境完整測試後再部署到正式環境
2. **監控**：設定日誌監控和告警機制
3. **備份**：定期備份設定檔和重要資料
4. **文件**：維護完整的操作手冊和故障排除指南
5. **版本控制**：使用 Git 管理程式碼，標記穩定版本

---

## 後續改進方向

### 短期改進（1-2 週）

1. **增加更多技術指標**
   - MACD
   - Fibonacci Retracement
   - Ichimoku Cloud

2. **改善回應格式**
   - 支援圖表輸出
   - 美化文字格式
   - 支援多語言

3. **增強錯誤處理**
   - 更詳細的錯誤訊息
   - 自動重試機制
   - 錯誤統計和分析

### 中期改進（1-2 月）

1. **資料持久化**
   - 使用資料庫儲存歷史查詢
   - 建立用戶偏好設定
   - 查詢歷史記錄

2. **進階功能**
   - 價格提醒
   - 定期報告
   - 自訂指標組合

3. **效能優化**
   - 分散式快取
   - 非同步任務隊列
   - 資料預載入

### 長期改進（3-6 月）

1. **AI 分析**
   - 市場趨勢預測
   - 風險評估
   - 交易建議

2. **多用戶支援**
   - 用戶認證
   - 權限管理
   - 使用量限制

3. **Web 界面**
   - 建立管理後台
   - 圖表視覺化
   - 歷史查詢管理

---

## 總結

本開發計畫詳細規劃了 Telegram Bot + Claude Agent SDK + MT5 整合系統的實作步驟。透過四個階段的漸進式開發，從環境設定、Agent 工具層建立、Telegram Bot 整合到最終的優化和部署，確保系統穩定可靠。

計畫重點：
- **模組化設計**：各層職責清晰，便於維護和擴展
- **完善測試**：每個階段都有明確的驗收標準
- **錯誤處理**：提供友善的錯誤訊息和完整的日誌
- **文件完整**：包含使用說明和故障排除指南

預計開發時間約 5 個工作天，建議按照計畫順序逐步實作，每完成一個階段後進行測試驗收，確保品質。
