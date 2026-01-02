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
