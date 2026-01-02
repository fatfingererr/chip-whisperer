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
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import tempfile

# 確保可以匯入 core 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import MT5Config, ChipWhispererMT5Client, HistoricalDataFetcher
from core.sqlite_cache import SQLiteCacheManager
from .indicators import (
    calculate_volume_profile,
    calculate_sma,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_vppa
)
from visualization import plot_vppa_chart


# ============================================================================
# MT5 時間週期對應表
# ============================================================================

TIMEFRAME_MAP = {
    'M1': mt5.TIMEFRAME_M1, 'M2': mt5.TIMEFRAME_M2, 'M3': mt5.TIMEFRAME_M3,
    'M4': mt5.TIMEFRAME_M4, 'M5': mt5.TIMEFRAME_M5, 'M6': mt5.TIMEFRAME_M6,
    'M10': mt5.TIMEFRAME_M10, 'M12': mt5.TIMEFRAME_M12, 'M15': mt5.TIMEFRAME_M15,
    'M20': mt5.TIMEFRAME_M20, 'M30': mt5.TIMEFRAME_M30,
    'H1': mt5.TIMEFRAME_H1, 'H2': mt5.TIMEFRAME_H2, 'H3': mt5.TIMEFRAME_H3,
    'H4': mt5.TIMEFRAME_H4, 'H6': mt5.TIMEFRAME_H6, 'H8': mt5.TIMEFRAME_H8,
    'H12': mt5.TIMEFRAME_H12, 'D1': mt5.TIMEFRAME_D1,
    'W1': mt5.TIMEFRAME_W1, 'MN1': mt5.TIMEFRAME_MN1,
}

TIMEFRAME_MINUTES = {
    'M1': 1, 'M2': 2, 'M3': 3, 'M4': 4, 'M5': 5, 'M6': 6,
    'M10': 10, 'M12': 12, 'M15': 15, 'M20': 20, 'M30': 30,
    'H1': 60, 'H2': 120, 'H3': 180, 'H4': 240, 'H6': 360, 'H8': 480, 'H12': 720,
    'D1': 1440, 'W1': 10080, 'MN1': 43200,
}


# ============================================================================
# MT5 連線管理
# ============================================================================

# 全域實例（單例模式）
_mt5_client = None
_mt5_config = None
_cache_manager = None


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
    },
    {
        "name": "generate_vppa_chart",
        "description": (
            "產生 VPPA (Volume Profile Pivot Anchored) 圖表並儲存為 PNG 圖片。"
            "VPPA 會自動偵測 Pivot High/Low 點，並為每個區間計算 Volume Profile。"
            "適合用於分析關鍵價格區間的成交量分佈。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "商品代碼，例如 'GOLD', 'SILVER', 'EURUSD' 等"
                },
                "timeframe": {
                    "type": "string",
                    "description": "時間週期，例如 'M1', 'M5', 'H1', 'H4', 'D1' 等"
                },
                "count": {
                    "type": "integer",
                    "description": "K 線數量（預設 2160 根，約 1.5 天的 M1 數據）",
                    "default": 2160
                },
                "pivot_length": {
                    "type": "integer",
                    "description": "Pivot Point 左右觀察窗口（預設 67）",
                    "default": 67
                },
                "price_levels": {
                    "type": "integer",
                    "description": "價格分層數量/Number of Rows（預設 27）",
                    "default": 27
                }
            },
            "required": ["symbol", "timeframe"]
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
        elif tool_name == "generate_vppa_chart":
            return _generate_vppa_chart(tool_input)
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
    """
    取得 K 線資料（支援自動回補）

    此函數實作智慧資料取得策略：
    1. 優先從 DB 查詢
    2. 若 DB 資料不足，自動更新到最新（update_db_to_now）
    3. 再次查詢 DB
    4. 若仍不足，從 MT5 直接取得

    參數：
        args: 工具輸入參數

    回傳：
        包含 K 線資料和摘要的字典
    """
    try:
        symbol = args.get("symbol", "GOLD").upper()
        timeframe = args.get("timeframe", "H1").upper()
        count = int(args.get("count", 100))

        logger.info(f"工具調用：get_candles(symbol={symbol}, timeframe={timeframe}, count={count})")

        # 驗證時間週期
        if timeframe not in TIMEFRAME_MAP:
            return {
                "success": False,
                "error": f"無效的時間週期：{timeframe}，支援的週期：{', '.join(TIMEFRAME_MAP.keys())}"
            }

        # 取得 MT5 客戶端和快取管理器
        client = get_mt5_client()
        cache = _get_cache_manager()

        # 記錄是否進行了回補
        backfilled = False
        backfill_count = 0

        # 策略 1：優先從 DB 查詢
        logger.info("嘗試從 DB 查詢資料")
        tf_minutes = TIMEFRAME_MINUTES[timeframe]
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=tf_minutes * count * 2)

        df = cache.query_candles(symbol, timeframe, start_time, end_time)

        if df is not None and len(df) >= count:
            logger.info(f"DB 資料充足，取得 {len(df)} 筆")
            df = df.sort_values('time', ascending=True).tail(count).reset_index(drop=True)
        else:
            # 策略 2：DB 資料不足，嘗試自動回補
            existing_count = len(df) if df is not None else 0
            logger.info(f"DB 資料不足（{existing_count}/{count}），觸發自動回補")

            try:
                # 2.1 更新到最新
                from scripts.analyze_vppa import update_db_to_now
                backfill_count = update_db_to_now(symbol, timeframe, cache, client)
                logger.info(f"已補充 {backfill_count} 筆新資料")
                backfilled = True

                # 2.2 再次查詢 DB
                df = cache.query_candles(symbol, timeframe, start_time, end_time)

                if df is not None and len(df) >= count:
                    logger.info(f"回補後 DB 資料充足，取得 {len(df)} 筆")
                    df = df.sort_values('time', ascending=True).tail(count).reset_index(drop=True)
                else:
                    # 策略 3：仍不足，從 MT5 直接取得
                    logger.info(f"回補後仍不足（{len(df) if df is not None else 0}/{count}），從 MT5 直接取得")

                    tf_constant = TIMEFRAME_MAP[timeframe]
                    rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, count)

                    if rates is None or len(rates) == 0:
                        raise RuntimeError(f"無法從 MT5 取得 {symbol} {timeframe} 數據")

                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

                    # 保存到 DB
                    inserted = cache.insert_candles(df, symbol, timeframe)
                    logger.info(f"從 MT5 取得並保存 {inserted} 筆數據")
                    backfilled = True
                    backfill_count += inserted

                    df = df.sort_values('time', ascending=True).reset_index(drop=True)

            except Exception as backfill_error:
                logger.error(f"自動回補失敗：{backfill_error}")
                # 回退：使用 HistoricalDataFetcher（原始邏輯）
                logger.info("回退到原始查詢邏輯")
                fetcher = HistoricalDataFetcher(client)
                df = fetcher.get_candles_latest(
                    symbol=symbol,
                    timeframe=timeframe,
                    count=count
                )

        # 將 DataFrame 轉換為可序列化的格式
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
            "total_volume": float(df['real_volume'].sum()),
            "backfilled": backfilled,
            "backfill_count": backfill_count
        }

        # 組裝訊息
        message = f"成功取得 {symbol} {timeframe} K 線資料，共 {len(df)} 根"
        if backfilled and backfill_count > 0:
            message += f"（已自動補充 {backfill_count} 筆新數據）"

        result = {
            "success": True,
            "message": message,
            "data": {
                "candles_json": candles_json,
                "summary": summary
            }
        }

        logger.info(f"成功取得 {len(df)} 根 K 線（回補：{backfilled}，新增：{backfill_count}）")
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


def _generate_vppa_chart(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    產生 VPPA 圖表並儲存為 PNG

    此函數整合了 analyze_vppa 和 plot_vppa_chart 的功能，
    產生完整的 VPPA 分析圖表。

    參數：
        args: 工具輸入參數

    回傳：
        包含圖片路徑和分析摘要的字典
    """
    try:
        # 1. 解析參數
        symbol = args.get("symbol", "GOLD").upper()
        timeframe = args.get("timeframe", "M1").upper()
        count = int(args.get("count", 2160))
        pivot_length = int(args.get("pivot_length", 67))
        price_levels = int(args.get("price_levels", 27))

        logger.info(
            f"工具調用：generate_vppa_chart("
            f"symbol={symbol}, timeframe={timeframe}, count={count}, "
            f"pivot_length={pivot_length}, price_levels={price_levels})"
        )

        # 2. 驗證參數
        if timeframe not in TIMEFRAME_MAP:
            return {
                "success": False,
                "error": f"無效的時間週期：{timeframe}，支援的週期：{', '.join(TIMEFRAME_MAP.keys())}"
            }

        # 3. 取得 MT5 客戶端和快取管理器
        client = get_mt5_client()
        cache = _get_cache_manager()

        # 4. 執行 VPPA 分析（重用 analyze_vppa 邏輯）
        logger.info("步驟 1/4：執行 VPPA 分析")

        # 4.1 補充 DB 到最新
        from scripts.analyze_vppa import update_db_to_now
        new_count = update_db_to_now(symbol, timeframe, cache, client)
        logger.info(f"補充了 {new_count} 筆新數據")

        # 4.2 取得 K 線數據
        from scripts.analyze_vppa import fetch_data
        df = fetch_data(symbol, timeframe, count, cache, client)
        logger.info(f"取得 {len(df)} 筆 K 線數據")

        # 4.3 計算成交量移動平均
        df['volume_ma'] = df['real_volume'].rolling(window=14).mean()

        # 4.4 計算 VPPA
        df_indexed = df.set_index('time')
        vppa_result = calculate_vppa(
            df_indexed,
            pivot_length=pivot_length,
            price_levels=price_levels,
            value_area_pct=0.67
        )

        logger.info(
            f"VPPA 計算完成：{vppa_result['metadata']['total_pivot_points']} 個 Pivot Points，"
            f"{vppa_result['metadata']['total_ranges']} 個區間"
        )

        # 5. 整理 VPPA JSON 格式（與 analyze_vppa.py 一致）
        logger.info("步驟 2/4：整理分析結果")

        output = {
            'symbol': symbol,
            'timeframe': timeframe,
            'analysis_time': datetime.now(timezone.utc).isoformat(),
            'parameters': {
                'count': count,
                'pivot_length': pivot_length,
                'price_levels': price_levels,
                'value_area_pct': 0.67,
                'volume_ma_length': 14
            },
            'data_range': {
                'start_time': df['time'].min().isoformat(),
                'end_time': df['time'].max().isoformat(),
                'total_bars': len(df)
            },
            'summary': {
                'total_pivot_points': vppa_result['metadata']['total_pivot_points'],
                'total_ranges': vppa_result['metadata']['total_ranges'],
                'has_developing_range': vppa_result['developing_range'] is not None,
                'volume_stats': {
                    'latest_volume_ma': float(df['volume_ma'].iloc[-1]) if not pd.isna(df['volume_ma'].iloc[-1]) else None,
                    'avg_volume': float(df['real_volume'].mean()),
                    'total_volume': float(df['real_volume'].sum())
                }
            },
            'pivot_points': vppa_result['pivot_summary'],
            'pivot_ranges': [],
            'developing_range': None
        }

        # 整理區間資料（簡化版，只保留必要欄位）
        for i, range_data in enumerate(vppa_result['pivot_ranges']):
            range_output = {
                'range_id': i,
                'start_idx': range_data['start_idx'],
                'end_idx': range_data['end_idx'],
                'start_time': range_data['start_time'],
                'end_time': range_data['end_time'],
                'bar_count': range_data['bar_count'],
                'pivot_type': range_data['pivot_type'],
                'pivot_price': range_data['pivot_price'],
                'price_info': {
                    'highest': range_data['price_highest'],
                    'lowest': range_data['price_lowest'],
                    'range': range_data['price_range'],
                    'step': range_data['price_step']
                },
                'poc': range_data['poc'],
                'value_area': {
                    'vah': range_data['vah'],
                    'val': range_data['val'],
                    'width': range_data['value_area_width'],
                    'volume': range_data['value_area_volume'],
                    'pct': range_data['value_area_pct']
                },
                'volume_info': {
                    'total': range_data['total_volume'],
                    'avg_per_bar': range_data['avg_volume_per_bar']
                },
                'volume_profile': {
                    'levels': len(range_data['volume_profile']),
                    'price_centers': range_data['price_centers'],
                    'volumes': range_data['volume_profile']
                }
            }
            output['pivot_ranges'].append(range_output)

        # 處理發展中的區間
        if vppa_result['developing_range']:
            dev = vppa_result['developing_range']
            output['developing_range'] = {
                'start_idx': dev['start_idx'],
                'end_idx': dev['end_idx'],
                'start_time': dev['start_time'],
                'end_time': dev['end_time'],
                'bar_count': dev['bar_count'],
                'is_developing': True,
                'price_info': {
                    'highest': dev['price_highest'],
                    'lowest': dev['price_lowest'],
                    'range': dev['price_range'],
                    'step': dev['price_step']
                },
                'poc': dev['poc'],
                'value_area': {
                    'vah': dev['vah'],
                    'val': dev['val'],
                    'width': dev['value_area_width'],
                    'volume': dev['value_area_volume'],
                    'pct': dev['value_area_pct']
                },
                'volume_info': {
                    'total': dev['total_volume'],
                    'avg_per_bar': dev['avg_volume_per_bar']
                },
                'volume_profile': {
                    'levels': len(dev['volume_profile']),
                    'price_centers': dev['price_centers'],
                    'volumes': dev['volume_profile']
                }
            }

        # 6. 產生圖表
        logger.info("步驟 3/4：產生 VPPA 圖表")

        # 建立暫存檔案
        with tempfile.NamedTemporaryFile(
            suffix='.png',
            prefix=f'vppa_{symbol}_{timeframe}_',
            delete=False
        ) as tmp:
            output_path = tmp.name

        logger.info(f"圖表輸出路徑：{output_path}")

        # 繪製圖表
        fig = plot_vppa_chart(
            vppa_json=output,
            candles_df=df,
            output_path=output_path,
            show_pivot_points=True,
            show_developing=True,
            width=1920,
            height=1080
        )

        logger.info("圖表產生完成")

        # 7. 檢查檔案大小
        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)

        if file_size_mb > 10:
            logger.warning(f"圖表檔案過大：{file_size_mb:.2f} MB（超過 Telegram 10MB 限制）")
            os.remove(output_path)
            return {
                "success": False,
                "error": f"圖表檔案過大（{file_size_mb:.2f} MB），請減少 K 線數量或價格層級"
            }

        logger.info(f"圖表檔案大小：{file_size_mb:.2f} MB")

        # 8. 組裝回傳結果
        logger.info("步驟 4/4：組裝回傳結果")

        result = {
            "success": True,
            "message": f"{symbol} {timeframe} VPPA 圖表已產生",
            "data": {
                "image_path": output_path,
                "image_type": "vppa_chart",  # 標記為 VPPA 圖表
                "summary": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "total_bars": len(df),
                    "date_range": {
                        "from": str(df['time'].min()),
                        "to": str(df['time'].max())
                    },
                    "pivot_points": output['summary']['total_pivot_points'],
                    "ranges": output['summary']['total_ranges'],
                    "has_developing": output['summary']['has_developing_range']
                },
                "interpretation": f"""
VPPA 分析完成！

商品：{symbol} {timeframe}
時間範圍：{df['time'].min().strftime('%Y-%m-%d %H:%M')} ~ {df['time'].max().strftime('%Y-%m-%d %H:%M')}
總 K 線數：{len(df)} 根

Pivot Points：{output['summary']['total_pivot_points']} 個
區間數量：{output['summary']['total_ranges']} 個
發展中區間：{'是' if output['summary']['has_developing_range'] else '否'}

圖表已產生，請參考上方圖片查看詳細的 Volume Profile 分佈。
"""
            }
        }

        logger.info("VPPA 圖表產生成功")
        return result

    except Exception as e:
        logger.exception("產生 VPPA 圖表失敗")
        return {
            "success": False,
            "error": f"產生 VPPA 圖表失敗：{str(e)}"
        }


def _get_cache_manager() -> SQLiteCacheManager:
    """
    取得 SQLite 快取管理器單例

    回傳：
        SQLiteCacheManager 實例
    """
    global _cache_manager

    if _cache_manager is None:
        logger.info("初始化 SQLite 快取管理器")
        db_path = os.getenv("CANDLES_DB_PATH", "data/candles.db")
        _cache_manager = SQLiteCacheManager(db_path)

    return _cache_manager
