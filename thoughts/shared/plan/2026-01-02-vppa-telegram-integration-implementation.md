# VPPA Telegram 整合實作計畫

## 概述

本計畫旨在整合現有的 VPPA 計算和視覺化功能到 Telegram Bot 中，使 Agent 能夠透過自然語言指令產生 VPPA 圖表並發送給使用者。同時優化 `get_candles` 函數以支援自動資料回補。

**實作目標：**
1. 更新 `calculate_volume_profile` 工具以產生 VPPA 圖表並發送到 Telegram
2. 更新 `get_candles` 工具以支援自動資料回補
3. 確保向後相容性和完整的錯誤處理

## 現狀分析

### 已存在的核心功能

**VPPA 計算核心** (`src/agent/indicators.py`)
- ✅ `calculate_vppa()`: 完整的 VPPA 計算實作（736-1109 行）
- ✅ 與 PineScript VPPA 指標一致的計算邏輯
- ✅ 支援 Pivot Point 偵測和 Volume Profile 計算

**VPPA 分析腳本** (`scripts/analyze_vppa.py`)
- ✅ 完整的資料更新和回補邏輯（`update_db_to_now`）
- ✅ 資料取得策略（DB 優先，MT5 補充）
- ✅ 支援命令列參數和 JSON 輸出

**視覺化系統** (`src/visualization/vppa_plot.py`)
- ✅ `plot_vppa_chart()`: 完整的 VPPA 圖表繪製（608-766 行）
- ✅ 支援 PNG 輸出（1920x1080 @ 2x）
- ✅ 互動式 Plotly 圖表

**Telegram Bot 整合** (`src/bot/handlers.py`, `src/bot/telegram_bot.py`)
- ✅ `python-telegram-bot>=20.0` 已安裝
- ✅ 支援 `reply_photo()` API
- ✅ 完整的錯誤處理機制

**資料回補機制** (`scripts/backfill_data.py`)
- ✅ 批次回補邏輯（84-265 行）
- ✅ 雙向回補支援（往前或往後）
- ✅ 容錯機制（最多重試 3 次）

### 目前缺少的功能

**Agent 工具整合**
- ❌ `calculate_volume_profile` 工具未實作 VPPA 計算
- ❌ 無圖表產生功能
- ❌ 無 Telegram 圖片發送整合

**自動資料回補**
- ❌ `get_candles` 未整合自動回補邏輯
- ❌ 查詢失敗時無自動重試機制

### 關鍵發現

1. **現有 `calculate_volume_profile` 工具的問題**（`src/agent/tools.py` 118-135 行）：
   - 只支援基礎 Volume Profile（整個資料集）
   - 未實作 VPPA（Pivot Point + Volume Profile）
   - 無視覺化輸出

2. **資料回補策略已完整實作**：
   - `update_db_to_now()` 可直接重用（`scripts/analyze_vppa.py` 92-151 行）
   - `fetch_data()` 實作了 DB 優先策略（`scripts/analyze_vppa.py` 154-207 行）

3. **Telegram 圖片發送 API**：
   - 支援檔案路徑、位元組資料、檔案物件
   - 最大檔案大小 10MB，解析度 10000x10000

## 期望終點狀態

### 功能規格

**使用者體驗**：
```
使用者：「幫我產生黃金 M1 的 VPPA 圖表」
Bot：「收到！正在產生 VPPA 圖表...」
      [發送 VPPA 圖表圖片]
      「GOLD M1 VPPA 分析完成
      • Pivot Points: 15 個
      • 區間數量: 14 個
      • 時間範圍: 2026-01-01 00:00 ~ 2026-01-02 12:00」
```

**自動資料回補**：
```
使用者：「查詢黃金 H1 最近 500 根 K 線」
系統：[檢查 DB] → [發現資料不足] → [自動回補] → [回傳資料]
Bot：「成功取得 GOLD H1 K 線資料，共 500 根
     （已自動補充 150 筆新數據）
     時間範圍：2025-12-15 00:00 ~ 2026-01-02 12:00
     ...」
```

### 驗證標準

#### 自動化驗證
- [ ] 單元測試通過：`pytest tests/test_vppa_integration.py`
- [ ] 工具定義符合 Anthropic SDK 規範
- [ ] 圖表成功產生：PNG 檔案存在且大小合理（< 5MB）
- [ ] 資料回補成功：DB 中存在補充的資料
- [ ] 類型檢查通過：`mypy src/agent/tools.py`
- [ ] Linting 通過：`flake8 src/agent/tools.py`

#### 手動驗證
- [ ] Agent 能正確回應 VPPA 圖表請求
- [ ] 圖表在 Telegram 中正確顯示（1920x1080）
- [ ] POC、VAH、VAL 標註清晰可見
- [ ] 圖表包含正確的商品和時間週期資訊
- [ ] 自動回補後資料完整性檢查
- [ ] 錯誤處理：無效商品代碼、網路錯誤等

**實作註記**：完成本階段所有自動化驗證後，暫停並等待人工確認手動測試成功後再繼續下一階段。

## 不在範圍內的項目

為了避免範圍膨脹，以下功能**不**在本次實作範圍內：

1. **VPPA 參數自訂**：預設使用固定參數（pivot_length=67, price_levels=27），不支援使用者自訂
2. **多商品批次分析**：一次只分析一個商品
3. **歷史 VPPA 快取**：不實作 VPPA 結果快取機制
4. **互動式圖表**：只產生靜態 PNG，不支援 HTML 互動式圖表
5. **自訂視覺化樣式**：使用預設配色和佈局
6. **定時自動回補**：不實作背景定時任務，只在查詢時觸發
7. **分散式回補**：不支援多商品並行回補

## 實作策略

### 核心設計決策

**1. 重用現有邏輯 vs. 重新實作**
   - **決策**：完全重用 `scripts/analyze_vppa.py` 的邏輯
   - **理由**：
     - 已經過測試和驗證
     - 避免重複代碼
     - 確保一致性

**2. 工具設計策略**
   - **方案 A**：新增 `generate_vppa_chart` 工具，保持 `calculate_volume_profile` 不變
   - **方案 B**：擴展 `calculate_volume_profile` 工具支援 VPPA
   - **決策**：採用方案 A（新增工具）
   - **理由**：
     - 向後相容性：不影響現有工具使用
     - 清晰的職責分離：基礎 VP vs. 完整 VPPA
     - 更容易測試和維護

**3. 圖片發送策略**
   - **方案 A**：直接在工具內發送圖片
   - **方案 B**：工具回傳圖片路徑，由 handler 發送
   - **決策**：採用方案 B（回傳路徑）
   - **理由**：
     - 工具職責單一（產生圖表）
     - Handler 統一處理 Telegram API
     - 更容易擴展（例如同時回傳文字和圖片）

**4. 資料回補觸發時機**
   - **決策**：在 `get_candles` 查詢失敗或資料不足時自動觸發
   - **策略**：
     1. 優先查詢 DB
     2. 若 DB 資料不足，先更新到最新（`update_db_to_now`）
     3. 再次查詢 DB
     4. 若仍不足，從 MT5 直接取得

### 技術考量

**效能最佳化**：
- 使用暫存檔避免記憶體溢出（大圖表）
- 圖表產生後立即發送並清理
- DB 查詢使用索引（已有 `idx_candles_symbol_timeframe_time`）

**錯誤處理**：
- MT5 連線錯誤：自動重連（最多 3 次）
- 資料回補失敗：回退到 MT5 直接查詢
- 圖表產生失敗：清理暫存檔並回報錯誤
- Telegram 發送失敗：記錄錯誤但不影響主流程

**日誌記錄**：
- INFO：關鍵步驟（開始回補、圖表產生完成等）
- DEBUG：詳細資訊（查詢參數、資料筆數等）
- WARNING：非致命錯誤（資料不足、重試等）
- ERROR：致命錯誤（連線失敗、檔案錯誤等）

---

## 階段 1：新增 VPPA 圖表產生工具

### 概述

新增 `generate_vppa_chart` 工具到 Agent 工具集，整合現有的 VPPA 分析和視覺化邏輯。

### 需要修改的檔案

#### 1. `src/agent/tools.py`

**修改位置**：第 193 行之後（`TOOLS` 列表末端）

**新增工具定義**：
```python
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
```

**新增執行函式**（在 `execute_tool` 函數中第 220 行後）：
```python
elif tool_name == "generate_vppa_chart":
    return _generate_vppa_chart(tool_input)
```

**新增實作函式**（在檔案末端第 521 行後）：
```python
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
        import tempfile
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
        import os
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
```

**新增 import**（在檔案開頭第 16 行後）：
```python
import tempfile
```

### 成功標準

#### 自動化驗證
- [x] 工具定義已新增到 `TOOLS` 列表
- [x] `execute_tool` 函數已新增對應分支
- [x] `_generate_vppa_chart` 函數實作完成
- [x] `_get_cache_manager` 函數實作完成
- [x] Import 語句已新增
- [x] 程式碼無語法錯誤：`python -m py_compile src/agent/tools.py`

#### 手動驗證
- [ ] 工具能成功產生 VPPA 圖表 PNG 檔案
- [ ] 圖表包含正確的 K 線、Pivot Points 和 Volume Profile
- [ ] 暫存檔案路徑正確回傳
- [ ] 錯誤處理正常（無效商品、時間週期等）
- [ ] 檔案大小檢查正常運作（> 10MB 時拒絕）

**實作註記**：完成所有自動化驗證後，暫停並等待人工確認手動測試成功後再繼續下一階段。

---

## 階段 2：整合 Telegram 圖片發送

### 概述

修改 `handle_message` 函數以支援圖片回傳，當工具回傳包含 `image_path` 的結果時，自動發送圖片到 Telegram。

### 需要修改的檔案

#### 1. `src/bot/handlers.py`

**修改位置**：第 364-376 行（回傳結果部分）

**原始代碼**：
```python
# ====================================================================
# 10. 回傳結果
# ====================================================================
# 刪除處理中訊息
await processing_message.delete()

# 回傳結果（處理長訊息）
if len(response) <= 4096:
    await message.reply_text(response)
else:
    # 分段傳送
    chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
    for chunk in chunks:
        await message.reply_text(chunk)

logger.info(f"成功回應群組 {chat.id} 管理員 {user.id}（Agent: {agent_name}）")
```

**修改為**：
```python
# ====================================================================
# 10. 回傳結果
# ====================================================================
# 刪除處理中訊息
await processing_message.delete()

# 檢查是否有圖片需要發送
image_sent = False
if isinstance(response, dict) and response.get("data", {}).get("image_path"):
    image_path = response["data"]["image_path"]
    image_type = response["data"].get("image_type", "chart")

    logger.info(f"準備發送圖片：{image_path}（類型：{image_type}）")

    try:
        # 建立圖片說明文字
        summary = response["data"].get("summary", {})
        if image_type == "vppa_chart":
            caption = (
                f"📊 {summary.get('symbol', 'N/A')} {summary.get('timeframe', 'N/A')} VPPA 分析\n\n"
                f"⏰ 時間範圍：{summary.get('date_range', {}).get('from', 'N/A')[:16]} ~ "
                f"{summary.get('date_range', {}).get('to', 'N/A')[:16]}\n"
                f"📈 K 線數：{summary.get('total_bars', 'N/A')} 根\n"
                f"📍 Pivot Points：{summary.get('pivot_points', 'N/A')} 個\n"
                f"📦 區間數量：{summary.get('ranges', 'N/A')} 個"
            )
        else:
            caption = response.get("message", "分析結果")

        # 發送圖片
        with open(image_path, 'rb') as photo_file:
            await message.reply_photo(
                photo=photo_file,
                caption=caption
            )

        image_sent = True
        logger.info(f"圖片已發送：{image_path}")

        # 清理暫存檔
        import os
        try:
            os.remove(image_path)
            logger.debug(f"已清理暫存檔：{image_path}")
        except Exception as cleanup_error:
            logger.warning(f"清理暫存檔失敗：{cleanup_error}")

        # 如果有額外的文字說明，也一併發送
        interpretation = response.get("data", {}).get("interpretation")
        if interpretation:
            if len(interpretation) <= 4096:
                await message.reply_text(interpretation)
            else:
                chunks = [interpretation[i:i+4096] for i in range(0, len(interpretation), 4096)]
                for chunk in chunks:
                    await message.reply_text(chunk)

    except Exception as img_error:
        logger.exception(f"發送圖片失敗：{img_error}")
        await message.reply_text(f"圖表已產生但發送失敗：{str(img_error)}")
        image_sent = False

# 如果沒有圖片或圖片發送失敗，發送文字回應
if not image_sent:
    # 提取文字回應（處理 dict 格式）
    if isinstance(response, dict):
        text_response = response.get("data", {}).get("interpretation") or response.get("message", str(response))
    else:
        text_response = str(response)

    # 回傳結果（處理長訊息）
    if len(text_response) <= 4096:
        await message.reply_text(text_response)
    else:
        # 分段傳送
        chunks = [text_response[i:i+4096] for i in range(0, len(text_response), 4096)]
        for chunk in chunks:
            await message.reply_text(chunk)

logger.info(f"成功回應群組 {chat.id} 管理員 {user.id}（Agent: {agent_name}）")
```

**新增 import**（在檔案開頭第 11 行後）：
```python
import os
```

### 成功標準

#### 自動化驗證
- [x] 程式碼無語法錯誤：`python -m py_compile src/bot/handlers.py`
- [x] Import 語句已新增
- [x] 圖片發送邏輯已實作
- [x] 暫存檔清理邏輯已實作

#### 手動驗證
- [ ] Agent 能正確回應 VPPA 圖表請求並發送圖片
- [ ] 圖片在 Telegram 中正確顯示
- [ ] Caption 包含正確的摘要資訊（商品、時間範圍等）
- [ ] Interpretation 文字正確發送
- [ ] 暫存檔案已被清理（不殘留在檔案系統中）
- [ ] 錯誤處理正常（圖片發送失敗時回退到文字）

**實作註記**：完成所有自動化驗證後，暫停並等待人工確認手動測試成功後再繼續下一階段。

---

## 階段 3：優化 `get_candles` 支援自動回補

### 概述

擴展 `get_candles` 工具以支援自動資料回補，當 DB 資料不足時自動觸發更新。

### 需要修改的檔案

#### 1. `src/agent/tools.py`

**修改位置**：`_get_candles` 函數（233-298 行）

**原始代碼**：
```python
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
```

**修改為**：
```python
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
```

### 成功標準

#### 自動化驗證
- [x] 程式碼無語法錯誤：`python -m py_compile src/agent/tools.py`
- [x] 自動回補邏輯已實作
- [x] 錯誤回退邏輯已實作
- [x] 回補統計資訊已加入回傳結果

#### 手動驗證
- [ ] 查詢現有資料時正常回傳（不觸發回補）
- [ ] 查詢不足資料時自動觸發回補
- [ ] 回補後能正確取得所需數量的 K 線
- [ ] 回補失敗時能回退到原始邏輯
- [ ] 回補統計資訊正確顯示（backfilled, backfill_count）

**實作註記**：完成所有自動化驗證後，暫停並等待人工確認手動測試成功後再繼續下一階段。

---

## 階段 4：測試和文件

### 概述

建立完整的測試套件和使用文件，確保功能正確性和可維護性。

### 需要新增的檔案

#### 1. `tests/test_vppa_integration.py`

**新增檔案**：
```python
"""
VPPA 整合測試

測試 VPPA 圖表產生和 Telegram 整合功能。
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 測試環境設定
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
os.environ['TELEGRAM_GROUP_IDS'] = '123456'
os.environ['ANTHROPIC_API_KEY'] = 'test_key'

from src.agent.tools import execute_tool, _generate_vppa_chart, _get_candles


class TestVPPAChartGeneration:
    """測試 VPPA 圖表產生功能"""

    @pytest.fixture
    def mock_mt5_client(self):
        """模擬 MT5 客戶端"""
        with patch('src.agent.tools.get_mt5_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def mock_cache_manager(self):
        """模擬快取管理器"""
        with patch('src.agent.tools._get_cache_manager') as mock:
            cache = MagicMock()
            mock.return_value = cache
            yield cache

    def test_tool_definition_exists(self):
        """測試工具定義存在"""
        from src.agent.tools import TOOLS

        tool_names = [tool['name'] for tool in TOOLS]
        assert 'generate_vppa_chart' in tool_names

    def test_tool_definition_schema(self):
        """測試工具定義符合規範"""
        from src.agent.tools import TOOLS

        vppa_tool = next(t for t in TOOLS if t['name'] == 'generate_vppa_chart')

        assert 'description' in vppa_tool
        assert 'input_schema' in vppa_tool
        assert vppa_tool['input_schema']['type'] == 'object'
        assert 'properties' in vppa_tool['input_schema']
        assert 'required' in vppa_tool['input_schema']

        # 檢查必要參數
        required = vppa_tool['input_schema']['required']
        assert 'symbol' in required
        assert 'timeframe' in required

    @patch('src.agent.tools.plot_vppa_chart')
    @patch('src.agent.tools.calculate_vppa')
    @patch('scripts.analyze_vppa.fetch_data')
    @patch('scripts.analyze_vppa.update_db_to_now')
    def test_generate_vppa_chart_success(
        self,
        mock_update_db,
        mock_fetch_data,
        mock_calculate_vppa,
        mock_plot_chart,
        mock_mt5_client,
        mock_cache_manager
    ):
        """測試成功產生 VPPA 圖表"""
        import pandas as pd

        # 模擬資料
        mock_update_db.return_value = 10

        # 模擬 K 線資料
        df = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=100, freq='1H'),
            'open': [2000 + i for i in range(100)],
            'high': [2005 + i for i in range(100)],
            'low': [1995 + i for i in range(100)],
            'close': [2000 + i for i in range(100)],
            'real_volume': [1000] * 100
        })
        mock_fetch_data.return_value = df

        # 模擬 VPPA 結果
        mock_calculate_vppa.return_value = {
            'metadata': {
                'total_pivot_points': 10,
                'total_ranges': 9
            },
            'pivot_summary': [],
            'pivot_ranges': [],
            'developing_range': None
        }

        # 模擬圖表產生
        mock_plot_chart.return_value = MagicMock()

        # 執行測試
        result = _generate_vppa_chart({
            'symbol': 'GOLD',
            'timeframe': 'M1',
            'count': 100
        })

        # 驗證結果
        assert result['success'] is True
        assert 'image_path' in result['data']
        assert result['data']['image_type'] == 'vppa_chart'
        assert 'summary' in result['data']
        assert result['data']['summary']['symbol'] == 'GOLD'
        assert result['data']['summary']['timeframe'] == 'M1'

        # 驗證函數被調用
        mock_update_db.assert_called_once()
        mock_fetch_data.assert_called_once()
        mock_calculate_vppa.assert_called_once()
        mock_plot_chart.assert_called_once()

    def test_generate_vppa_chart_invalid_timeframe(self, mock_mt5_client, mock_cache_manager):
        """測試無效時間週期"""
        result = _generate_vppa_chart({
            'symbol': 'GOLD',
            'timeframe': 'INVALID',
            'count': 100
        })

        assert result['success'] is False
        assert '無效的時間週期' in result['error']

    @patch('src.agent.tools.plot_vppa_chart')
    @patch('src.agent.tools.calculate_vppa')
    @patch('scripts.analyze_vppa.fetch_data')
    @patch('scripts.analyze_vppa.update_db_to_now')
    def test_generate_vppa_chart_file_too_large(
        self,
        mock_update_db,
        mock_fetch_data,
        mock_calculate_vppa,
        mock_plot_chart,
        mock_mt5_client,
        mock_cache_manager
    ):
        """測試檔案過大處理"""
        import pandas as pd

        # 模擬資料
        mock_update_db.return_value = 0
        df = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=100, freq='1H'),
            'open': [2000] * 100,
            'high': [2005] * 100,
            'low': [1995] * 100,
            'close': [2000] * 100,
            'real_volume': [1000] * 100
        })
        mock_fetch_data.return_value = df

        mock_calculate_vppa.return_value = {
            'metadata': {'total_pivot_points': 10, 'total_ranges': 9},
            'pivot_summary': [],
            'pivot_ranges': [],
            'developing_range': None
        }

        # 模擬產生超大檔案
        with patch('os.path.getsize', return_value=15 * 1024 * 1024):  # 15MB
            result = _generate_vppa_chart({
                'symbol': 'GOLD',
                'timeframe': 'M1',
                'count': 100
            })

        assert result['success'] is False
        assert '檔案過大' in result['error']


class TestGetCandlesWithBackfill:
    """測試 get_candles 自動回補功能"""

    @pytest.fixture
    def mock_mt5_client(self):
        """模擬 MT5 客戶端"""
        with patch('src.agent.tools.get_mt5_client') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def mock_cache_manager(self):
        """模擬快取管理器"""
        with patch('src.agent.tools._get_cache_manager') as mock:
            cache = MagicMock()
            mock.return_value = cache
            yield cache

    @patch('scripts.analyze_vppa.update_db_to_now')
    def test_get_candles_sufficient_data(self, mock_update_db, mock_mt5_client, mock_cache_manager):
        """測試 DB 資料充足時不觸發回補"""
        import pandas as pd

        # 模擬 DB 有足夠資料
        df = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=150, freq='1H'),
            'open': [2000] * 150,
            'high': [2005] * 150,
            'low': [1995] * 150,
            'close': [2000] * 150,
            'real_volume': [1000] * 150
        })
        mock_cache_manager.query_candles.return_value = df

        result = _get_candles({
            'symbol': 'GOLD',
            'timeframe': 'H1',
            'count': 100
        })

        assert result['success'] is True
        assert result['data']['summary']['total_candles'] == 100
        assert result['data']['summary']['backfilled'] is False

        # 驗證未調用回補
        mock_update_db.assert_not_called()

    @patch('scripts.analyze_vppa.update_db_to_now')
    def test_get_candles_triggers_backfill(self, mock_update_db, mock_mt5_client, mock_cache_manager):
        """測試 DB 資料不足時觸發回補"""
        import pandas as pd

        # 第一次查詢：資料不足
        df_insufficient = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=50, freq='1H'),
            'open': [2000] * 50,
            'high': [2005] * 50,
            'low': [1995] * 50,
            'close': [2000] * 50,
            'real_volume': [1000] * 50
        })

        # 第二次查詢：回補後資料充足
        df_sufficient = pd.DataFrame({
            'time': pd.date_range('2026-01-01', periods=150, freq='1H'),
            'open': [2000] * 150,
            'high': [2005] * 150,
            'low': [1995] * 150,
            'close': [2000] * 150,
            'real_volume': [1000] * 150
        })

        mock_cache_manager.query_candles.side_effect = [df_insufficient, df_sufficient]
        mock_update_db.return_value = 100

        result = _get_candles({
            'symbol': 'GOLD',
            'timeframe': 'H1',
            'count': 100
        })

        assert result['success'] is True
        assert result['data']['summary']['total_candles'] == 100
        assert result['data']['summary']['backfilled'] is True
        assert result['data']['summary']['backfill_count'] == 100

        # 驗證調用了回補
        mock_update_db.assert_called_once()

    def test_get_candles_invalid_timeframe(self, mock_mt5_client, mock_cache_manager):
        """測試無效時間週期"""
        result = _get_candles({
            'symbol': 'GOLD',
            'timeframe': 'INVALID',
            'count': 100
        })

        assert result['success'] is False
        assert '無效的時間週期' in result['error']


class TestExecuteTool:
    """測試工具執行器"""

    def test_execute_vppa_chart_tool(self):
        """測試執行 VPPA 圖表工具"""
        with patch('src.agent.tools._generate_vppa_chart') as mock_func:
            mock_func.return_value = {'success': True}

            result = execute_tool('generate_vppa_chart', {'symbol': 'GOLD', 'timeframe': 'M1'})

            assert result['success'] is True
            mock_func.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

#### 2. `docs/vppa_telegram_integration.md`

**新增檔案**：
```markdown
# VPPA Telegram 整合使用指南

## 概述

本文件說明如何使用 Telegram Bot 產生和查看 VPPA（Volume Profile Pivot Anchored）分析圖表。

## 功能介紹

### VPPA 圖表產生

**工具名稱**：`generate_vppa_chart`

**功能**：
- 自動偵測 Pivot High 和 Pivot Low 點
- 為每個 Pivot Point 區間計算 Volume Profile
- 識別 POC（Point of Control）、VAH（Value Area High）、VAL（Value Area Low）
- 產生高解析度 PNG 圖表（1920x1080 @ 2x）
- 自動發送到 Telegram

**支援參數**：
- `symbol`：商品代碼（必填），例如 GOLD、SILVER、EURUSD
- `timeframe`：時間週期（必填），例如 M1、M5、H1、H4、D1
- `count`：K 線數量（選填，預設 2160 根）
- `pivot_length`：Pivot Point 觀察窗口（選填，預設 67）
- `price_levels`：價格分層數量（選填，預設 27）

### 自動資料回補

**工具名稱**：`get_candles`（已擴展）

**新功能**：
- 查詢時自動檢查 DB 資料完整性
- 資料不足時自動觸發回補
- 回補失敗時自動回退到原始邏輯
- 回補統計資訊顯示

## 使用方式

### 產生 VPPA 圖表

**範例 1：基本使用**
```
使用者：「幫我產生黃金 M1 的 VPPA 圖表」
```

Bot 會：
1. 自動補充資料庫到最新
2. 取得 2160 根 M1 K 線
3. 計算 VPPA（pivot_length=67, price_levels=27）
4. 產生圖表並發送

**範例 2：指定 K 線數量**
```
使用者：「產生黃金 H1 VPPA，最近 500 根」
```

**範例 3：多商品分析**
```
使用者：「幫我看白銀 M5 的 VPPA」
```

### 查詢 K 線資料

**範例 1：基本查詢**
```
使用者：「查詢黃金 H1 最近 100 根 K 線」
```

如果 DB 資料不足，Bot 會自動回補並回應：
```
成功取得 GOLD H1 K 線資料，共 100 根（已自動補充 50 筆新數據）
時間範圍：2025-12-28 00:00 ~ 2026-01-02 12:00
...
```

## 圖表解讀

### 視覺元素

**K 線圖**：
- 紅色：上漲
- 綠色：下跌

**Pivot Range 方塊**：
- 灰色半透明矩形標示每個 Pivot Point 區間

**Volume Profile 長條**：
- 藍色長條：該價格層級的成交量
- 深藍色：Value Area 內（67% 成交量）
- 淡藍色：Value Area 外

**POC 線**：
- 紅色實線：Point of Control（成交量最大的價格）
- Naked POC：延伸到最右邊並標註價格和差價

**網格**：
- X 軸：根據時間週期自動調整（M1=1小時, H1=1日）
- Y 軸：根據價格位數自動計算間隔

### 分析要點

**POC（Point of Control）**：
- 成交量最集中的價格
- 市場最認同的價值
- 重要的支撐/壓力位

**VAH/VAL（Value Area High/Low）**：
- 包含 67% 成交量的價格區間
- 突破 VAH/VAL 可能代表趨勢轉變

**Naked POC**：
- 未被後續 Value Area 覆蓋的 POC
- 延伸到最右邊，可能是未來的磁吸價位

## 技術限制

### 檔案大小
- 最大：10MB（Telegram 限制）
- 超過時會拒絕產生並建議減少 K 線數量

### K 線數量
- 建議範圍：500-3000 根
- 過少：Pivot Point 不足，分析意義有限
- 過多：圖表過於複雜，檔案可能過大

### 時間週期
- 支援：M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30, H1, H2, H3, H4, H6, H8, H12, D1, W1, MN1
- 建議：M1-H1（日內分析）、H4-D1（波段分析）

## 常見問題

### Q1：為什麼圖表產生很慢？

A：VPPA 計算涉及大量數值運算，特別是：
- 偵測所有 Pivot Points（左右各 67 根）
- 為每個區間計算 Volume Profile（27 層）
- 產生高解析度圖表（1920x1080 @ 2x）

正常情況下 2160 根 M1 資料需要 10-30 秒。

### Q2：為什麼有時候區間很少？

A：Pivot Point 的偵測取決於：
- `pivot_length`：觀察窗口大小（預設 67）
- 價格波動性：震盪市場會產生更多 Pivot Points

建議：
- 減少 `pivot_length` 可產生更多 Pivot Points
- 增加 K 線數量可包含更多區間

### Q3：如何理解 Naked POC？

A：Naked POC 是指：
- 該 POC 價位未被後續的 Value Area 覆蓋
- 延伸到圖表最右邊
- 可能是未來的支撐/壓力位（磁吸效應）

### Q4：資料回補失敗怎麼辦？

A：系統會自動回退到原始邏輯（從 MT5 直接查詢），不影響主功能。

## 最佳實踐

### 日內交易
- 時間週期：M1, M5, M15
- K 線數量：2160（M1 約 1.5 天）
- 用途：尋找當日關鍵價位

### 波段交易
- 時間週期：H1, H4
- K 線數量：500-1000
- 用途：識別週/月級別的支撐壓力

### 長期分析
- 時間週期：D1, W1
- K 線數量：200-500
- 用途：確認長期趨勢和結構

## 錯誤處理

### 常見錯誤訊息

**「無效的時間週期」**：
- 原因：輸入了不支援的時間週期
- 解決：使用支援的週期（M1, M5, H1, H4, D1 等）

**「圖表檔案過大」**：
- 原因：產生的 PNG 超過 10MB
- 解決：減少 K 線數量或價格層級

**「無法從 MT5 取得數據」**：
- 原因：商品代碼錯誤或 MT5 連線問題
- 解決：檢查商品代碼拼寫，確認 MT5 連線

**「產生 VPPA 圖表失敗」**：
- 原因：可能是記憶體不足或檔案系統錯誤
- 解決：聯絡管理員

## 技術細節

### 計算參數預設值

```python
pivot_length = 67      # Pivot Point 左右觀察窗口
price_levels = 27      # 價格分層數量（Number of Rows）
value_area_pct = 0.67  # Value Area 包含 67% 成交量
volume_ma_length = 14  # 成交量移動平均長度
```

### 圖表規格

- 解析度：1920x1080 @ 2x（實際輸出 3840x2160）
- 格式：PNG
- 配色：紅漲綠跌（符合台灣習慣）
- 時區：自動轉換為本地時區

### 資料回補策略

1. 優先查詢 DB
2. 資料不足時，更新到最新（`update_db_to_now`）
3. 再次查詢 DB
4. 仍不足時，從 MT5 直接取得
5. 失敗時，回退到原始邏輯

## 相關資源

- [VPPA 計算演算法](../thoughts/shared/research/2026-01-02-vppa-calculation-and-data-backfill.md)
- [Telegram Bot 使用說明](./telegram-bot.md)
- [MT5 整合說明](./mt5-integration.md)
```

### 成功標準

#### 自動化驗證
- [x] 測試檔案已建立：`tests/test_vppa_integration.py`
- [ ] 測試能成功執行：`pytest tests/test_vppa_integration.py -v`
- [ ] 所有測試通過
- [x] 文件檔案已建立：`docs/vppa_telegram_integration.md`

#### 手動驗證
- [ ] 測試涵蓋所有關鍵場景（成功、失敗、邊界條件）
- [ ] 文件清晰易懂，包含範例和常見問題
- [ ] 文件中的使用範例經過實際驗證

**實作註記**：完成所有自動化驗證後，暫停並等待人工確認測試通過和文件完整後完成整個實作。

---

## 測試策略

### 單元測試

**測試覆蓋範圍**：
- 工具定義正確性
- 參數驗證
- 成功流程
- 錯誤處理
- 邊界條件

**測試工具**：
- pytest
- unittest.mock
- Coverage.py（目標：> 80%）

### 整合測試

**測試場景**：
1. 端到端：Agent 請求 → 圖表產生 → Telegram 發送
2. 資料回補：DB 不足 → 自動回補 → 資料完整
3. 錯誤恢復：回補失敗 → 回退邏輯 → 仍能取得資料

**手動測試檢查清單**：
- [ ] Agent 能正確理解自然語言請求
- [ ] 圖表在 Telegram 中清晰可見
- [ ] POC、VAH、VAL 標註正確
- [ ] 時區轉換正確（顯示本地時間）
- [ ] 錯誤訊息友善且有幫助

### 效能測試

**基準測試**：
- 2160 根 M1 資料：< 30 秒
- 500 根 H1 資料：< 15 秒
- 圖表檔案大小：< 5MB（通常 1-3MB）

**壓力測試**：
- 最大 K 線數量：5000 根
- 最大價格層級：100 層
- 並發請求：3 個同時進行

## 風險評估

### 高風險項目

**1. 圖表檔案大小超過 Telegram 限制（10MB）**
- **機率**：中
- **影響**：高（功能無法使用）
- **緩解**：
  - 檔案大小檢查（已實作）
  - 錯誤訊息建議減少參數
  - 文件中說明建議範圍

**2. VPPA 計算耗時過長**
- **機率**：中
- **影響**：中（使用者體驗差）
- **緩解**：
  - 顯示「處理中」訊息
  - 預設參數已優化（2160 根約 10-30 秒）
  - 文件中說明預期時間

**3. 自動回補失敗**
- **機率**：低
- **影響**：低（有回退機制）
- **緩解**：
  - 三層回退策略（已實作）
  - 詳細錯誤日誌
  - 不影響主功能

### 中風險項目

**4. MT5 連線不穩定**
- **機率**：低
- **影響**：中（暫時無法取得資料）
- **緩解**：
  - 自動重連機制（`ensure_connected`）
  - 錯誤訊息提示檢查連線
  - DB 快取減少對 MT5 的依賴

**5. 暫存檔清理失敗**
- **機率**：低
- **影響**：低（累積暫存檔）
- **緩解**：
  - Try-except 包裹清理邏輯
  - 日誌記錄清理失敗
  - 使用系統 temp 目錄（自動清理）

### 低風險項目

**6. 記憶體溢出**
- **機率**：極低
- **影響**：高（程式崩潰）
- **緩解**：
  - K 線數量限制（< 5000）
  - 使用檔案儲存而非記憶體
  - 圖表產生後立即釋放

## 效能考量

### 最佳化策略

**1. 資料查詢**：
- DB 優先策略（避免 MT5 網路請求）
- 索引優化（已有 `idx_candles_symbol_timeframe_time`）
- 批次插入（`INSERT OR IGNORE`）

**2. VPPA 計算**：
- 向量化運算（NumPy）
- 避免重複計算（快取中間結果）
- 預設參數已優化（pivot_length=67）

**3. 圖表產生**：
- 使用 shapes 而非 scatter（更高效）
- 合併 POC 線為單一 Trace
- 批量添加 shapes（單次 `update_layout`）

**4. 記憶體管理**：
- 使用暫存檔（`tempfile.NamedTemporaryFile`）
- 圖表產生後立即發送並清理
- 避免在記憶體中保留大型 DataFrame

### 監控指標

**關鍵指標**：
- VPPA 計算時間（目標：< 30 秒）
- 圖表檔案大小（目標：< 5MB）
- DB 查詢時間（目標：< 1 秒）
- 記憶體使用（目標：< 500MB）

**日誌記錄**：
- INFO：關鍵步驟和時間戳
- DEBUG：詳細參數和資料筆數
- WARNING：效能警告（> 30 秒）
- ERROR：失敗和例外

## 向後相容性

### 保證事項

1. **現有工具不受影響**：
   - `calculate_volume_profile` 保持原有行為
   - `get_candles` 向後相容（新增欄位但不破壞）

2. **資料庫 Schema 不變**：
   - 不修改現有表結構
   - 使用現有索引

3. **API 回傳格式**：
   - 新增欄位（`backfilled`, `backfill_count`）
   - 原有欄位保持不變

### 升級路徑

**從舊版本升級**：
1. 無需資料庫遷移
2. 無需修改環境變數
3. 自動使用新功能（向下相容）

## 總結

本實作計畫詳細規劃了 VPPA Telegram 整合的四個階段：

1. **階段 1**：新增 `generate_vppa_chart` 工具
2. **階段 2**：整合 Telegram 圖片發送
3. **階段 3**：優化 `get_candles` 支援自動回補
4. **階段 4**：建立完整的測試和文件

每個階段都包含：
- 清晰的修改範圍和程式碼範例
- 自動化和手動驗證標準
- 暫停點以確保品質

實作完成後，使用者將能夠：
- 透過自然語言請求產生 VPPA 圖表
- 自動取得最新資料（無需手動回補）
- 在 Telegram 中查看高品質的 VPPA 分析圖表

---

**計畫建立日期**：2026-01-02
**計畫建立者**：Claude Sonnet 4.5
**預估實作時間**：4-6 小時（分 4 個階段執行）
