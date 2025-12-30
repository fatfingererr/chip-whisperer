"""
Agent 自訂工具定義

此模組定義所有 Claude Agent 可調用的工具，
封裝 src/core 模組的功能和技術指標計算。
"""

from typing import Any, Dict, List
from loguru import logger
import pandas as pd
import json
import os
import sys
from pathlib import Path

# 確保可以匯入 core 模組
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
# 工具定義（Anthropic SDK 格式）
# ============================================================================

TOOLS = [
    {
        "name": "get_candles",
        "description": "取得指定商品和時間週期的 K 線資料。可用於查詢歷史價格數據。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "商品代碼，例如 'GOLD', 'SILVER', 'EURUSD' 等"
                },
                "timeframe": {
                    "type": "string",
                    "description": "時間週期，例如 'H1'（1小時）, 'H4'（4小時）, 'D1'（日線）"
                },
                "count": {
                    "type": "integer",
                    "description": "要取得的 K 線數量（預設 100 根）",
                    "default": 100
                }
            },
            "required": ["symbol", "timeframe"]
        }
    },
    {
        "name": "calculate_volume_profile",
        "description": "計算 Volume Profile 技術指標，包含 POC（最大成交量價位）、VAH（價值區域高點）、VAL（價值區域低點）。需要先使用 get_candles 取得 K 線資料。",
        "input_schema": {
            "type": "object",
            "properties": {
                "candles_json": {
                    "type": "string",
                    "description": "JSON 格式的 K 線資料字串（由 get_candles 工具提供）"
                },
                "price_bins": {
                    "type": "integer",
                    "description": "價格區間數量（預設 100）",
                    "default": 100
                }
            },
            "required": ["candles_json"]
        }
    },
    {
        "name": "calculate_sma",
        "description": "計算簡單移動平均線（SMA）。需要先使用 get_candles 取得 K 線資料。",
        "input_schema": {
            "type": "object",
            "properties": {
                "candles_json": {
                    "type": "string",
                    "description": "JSON 格式的 K 線資料字串"
                },
                "window": {
                    "type": "integer",
                    "description": "移動平均視窗大小（預設 20）",
                    "default": 20
                },
                "column": {
                    "type": "string",
                    "description": "計算欄位（預設 'close'）",
                    "default": "close"
                }
            },
            "required": ["candles_json"]
        }
    },
    {
        "name": "calculate_rsi",
        "description": "計算相對強弱指標（RSI），用於判斷超買超賣。需要先使用 get_candles 取得 K 線資料。",
        "input_schema": {
            "type": "object",
            "properties": {
                "candles_json": {
                    "type": "string",
                    "description": "JSON 格式的 K 線資料字串"
                },
                "window": {
                    "type": "integer",
                    "description": "RSI 視窗大小（預設 14）",
                    "default": 14
                },
                "column": {
                    "type": "string",
                    "description": "計算欄位（預設 'close'）",
                    "default": "close"
                }
            },
            "required": ["candles_json"]
        }
    },
    {
        "name": "get_account_info",
        "description": "取得 MT5 帳戶資訊，包含餘額、淨值、保證金等。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# ============================================================================
# 工具執行函式
# ============================================================================

def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    執行指定的工具

    參數：
        tool_name: 工具名稱
        tool_input: 工具輸入參數

    回傳：
        工具執行結果字典
    """
    try:
        if tool_name == "get_candles":
            return _get_candles(tool_input)
        elif tool_name == "calculate_volume_profile":
            return _calculate_volume_profile(tool_input)
        elif tool_name == "calculate_sma":
            return _calculate_sma(tool_input)
        elif tool_name == "calculate_rsi":
            return _calculate_rsi(tool_input)
        elif tool_name == "get_account_info":
            return _get_account_info(tool_input)
        else:
            return {
                "error": f"未知的工具：{tool_name}"
            }
    except Exception as e:
        logger.exception(f"工具執行失敗：{tool_name}")
        return {
            "error": f"工具執行錯誤：{str(e)}"
        }


def _get_candles(args: Dict[str, Any]) -> Dict[str, Any]:
    """取得 K 線資料"""
    try:
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

        # 將 DataFrame 轉換為可序列化的格式
        # 需要處理時間欄位
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
                "from": str(df['time'].min()) if 'time' in df.columns else "N/A",
                "to": str(df['time'].max()) if 'time' in df.columns else "N/A"
            },
            "price_range": {
                "high": float(df['high'].max()),
                "low": float(df['low'].min()),
                "latest_close": float(df['close'].iloc[-1])
            },
            "total_volume": float(df['real_volume'].sum())
        }

        result = {
            "success": True,
            "message": f"成功取得 {symbol} {timeframe} K 線資料，共 {len(df)} 根",
            "data": {
                "candles_json": candles_json,
                "summary": summary
            }
        }

        logger.info(f"成功取得 {len(df)} 根 K 線")
        return result

    except Exception as e:
        logger.exception("取得 K 線資料失敗")
        return {
            "success": False,
            "error": f"取得 K 線資料失敗：{str(e)}"
        }


def _calculate_volume_profile(args: Dict[str, Any]) -> Dict[str, Any]:
    """計算 Volume Profile"""
    try:
        candles_json = args.get("candles_json")
        price_bins = int(args.get("price_bins", 100))

        logger.info(f"工具調用：calculate_volume_profile(price_bins={price_bins})")

        # 解析 K 線資料
        candles_list = json.loads(candles_json)
        df = pd.DataFrame(candles_list)

        # 計算 Volume Profile
        profile_df, metrics = calculate_volume_profile(df, price_bins)

        result = {
            "success": True,
            "message": "Volume Profile 計算完成",
            "data": {
                "metrics": metrics,
                "interpretation": f"""
Volume Profile 分析結果：

關鍵價位：
• POC (Point of Control): {metrics['poc_price']:.2f}
  - 成交量最大的價位，是市場最認同的價格
  - 成交量：{metrics['poc_volume']:.0f}

• VAH (Value Area High): {metrics['vah']:.2f}
  - 價值區域上界，70% 成交量的高點

• VAL (Value Area Low): {metrics['val']:.2f}
  - 價值區域下界，70% 成交量的低點

• Value Area 範圍: {metrics['vah'] - metrics['val']:.2f} 點
  - 涵蓋 {metrics['value_area_percentage']:.1f}% 的成交量

總成交量：{metrics['total_volume']:.0f}
"""
            }
        }

        logger.info("Volume Profile 計算成功")
        return result

    except Exception as e:
        logger.exception("計算 Volume Profile 失敗")
        return {
            "success": False,
            "error": f"計算 Volume Profile 失敗：{str(e)}"
        }


def _calculate_sma(args: Dict[str, Any]) -> Dict[str, Any]:
    """計算 SMA"""
    try:
        candles_json = args.get("candles_json")
        window = int(args.get("window", 20))
        column = args.get("column", "close")

        logger.info(f"工具調用：calculate_sma(window={window}, column={column})")

        # 解析 K 線資料
        candles_list = json.loads(candles_json)
        df = pd.DataFrame(candles_list)

        # 計算 SMA
        sma = calculate_sma(df, window, column)

        # 取得最新值
        latest_sma = float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None
        latest_price = float(df[column].iloc[-1])

        # 判斷趨勢
        if latest_sma:
            if latest_price > latest_sma:
                trend = "價格在均線之上（多頭）"
            elif latest_price < latest_sma:
                trend = "價格在均線之下（空頭）"
            else:
                trend = "價格在均線上（中性）"
        else:
            trend = "N/A"

        result = {
            "success": True,
            "message": f"SMA({window}) 計算完成",
            "data": {
                "window": window,
                "column": column,
                "latest_sma": latest_sma,
                "latest_price": latest_price,
                "trend": trend,
                "interpretation": f"""
SMA({window}) 分析結果：

• 最新 SMA 值：{latest_sma:.2f if latest_sma else 'N/A'}
• 最新價格：{latest_price:.2f}
• 趨勢判斷：{trend}
"""
            }
        }

        logger.info("SMA 計算成功")
        return result

    except Exception as e:
        logger.exception("計算 SMA 失敗")
        return {
            "success": False,
            "error": f"計算 SMA 失敗：{str(e)}"
        }


def _calculate_rsi(args: Dict[str, Any]) -> Dict[str, Any]:
    """計算 RSI"""
    try:
        candles_json = args.get("candles_json")
        window = int(args.get("window", 14))
        column = args.get("column", "close")

        logger.info(f"工具調用：calculate_rsi(window={window}, column={column})")

        # 解析 K 線資料
        candles_list = json.loads(candles_json)
        df = pd.DataFrame(candles_list)

        # 計算 RSI
        rsi = calculate_rsi(df, window, column)

        # 取得最新值
        latest_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

        # 判斷超買超賣
        if latest_rsi:
            if latest_rsi > 70:
                status = "超買區域（RSI > 70）"
                suggestion = "市場可能過熱，注意回調風險"
            elif latest_rsi < 30:
                status = "超賣區域（RSI < 30）"
                suggestion = "市場可能超賣，注意反彈機會"
            else:
                status = "中性區域（30 ≤ RSI ≤ 70）"
                suggestion = "市場處於正常範圍"
        else:
            status = "N/A"
            suggestion = "資料不足"

        result = {
            "success": True,
            "message": f"RSI({window}) 計算完成",
            "data": {
                "window": window,
                "column": column,
                "latest_rsi": latest_rsi,
                "status": status,
                "interpretation": f"""
RSI({window}) 分析結果：

• 最新 RSI 值：{latest_rsi:.2f if latest_rsi else 'N/A'}
• 狀態：{status}
• 建議：{suggestion}
"""
            }
        }

        logger.info("RSI 計算成功")
        return result

    except Exception as e:
        logger.exception("計算 RSI 失敗")
        return {
            "success": False,
            "error": f"計算 RSI 失敗：{str(e)}"
        }


def _get_account_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """取得帳戶資訊"""
    try:
        logger.info("工具調用：get_account_info()")

        # 取得 MT5 客戶端
        client = get_mt5_client()

        # 取得帳戶資訊
        account_info = client.get_account_info()

        if account_info:
            result = {
                "success": True,
                "message": "成功取得帳戶資訊",
                "data": {
                    "account_info": account_info,
                    "summary": f"""
MT5 帳戶資訊：

• 帳號：{account_info.get('login', 'N/A')}
• 伺服器：{account_info.get('server', 'N/A')}
• 餘額：{account_info.get('balance', 0):.2f}
• 淨值：{account_info.get('equity', 0):.2f}
• 保證金：{account_info.get('margin', 0):.2f}
• 可用保證金：{account_info.get('margin_free', 0):.2f}
"""
                }
            }
        else:
            result = {
                "success": False,
                "error": "無法取得帳戶資訊"
            }

        return result

    except Exception as e:
        logger.exception("取得帳戶資訊失敗")
        return {
            "success": False,
            "error": f"取得帳戶資訊失敗：{str(e)}"
        }
