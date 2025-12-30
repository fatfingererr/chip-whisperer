# MT5 Telegram Bot - 快速開始指南

這是一個整合 Telegram Bot、Claude AI 和 MetaTrader 5 的智能交易助手。

## 功能特點

- 自然語言查詢市場數據
- 計算技術指標（Volume Profile、SMA、RSI 等）
- 智能分析和建議
- 支援多種商品和時間週期

## 快速開始

### 1. 安裝依賴

```powershell
pip install -r requirements.txt
```

### 2. 設定環境變數

複製 `.env.example` 為 `.env`：

```powershell
cp .env.example .env
```

編輯 `.env` 檔案，填入以下資訊：

```env
# Telegram Bot Token（從 @BotFather 取得）
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Anthropic API Key（從 https://console.anthropic.com/ 取得）
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# MT5 連線資訊
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=your_broker_server

# 管理員 ID（可選，用逗號分隔）
TELEGRAM_ADMIN_IDS=123456789
```

### 3. 啟動 Bot

```powershell
python scripts/run_bot.py
```

### 4. 開始使用

在 Telegram 中搜尋你的 Bot，傳送 `/start` 開始使用。

## 使用範例

### 基本指令

- `/start` - 顯示歡迎訊息
- `/help` - 顯示詳細說明
- `/status` - 檢查系統狀態

### 自然語言查詢

直接用自然語言提問：

```
幫我查詢黃金最近 100 根 H4 K 線
```

```
計算黃金的 Volume Profile
```

```
黃金的 RSI 是多少？
```

```
給我看看白銀 D1 的 20 日均線
```

## 支援的功能

### 商品代碼
- GOLD, SILVER, EURUSD, GBPUSD, USDJPY 等

### 時間週期
- M1 (1分鐘)
- M5 (5分鐘)
- M15 (15分鐘)
- M30 (30分鐘)
- H1 (1小時)
- H4 (4小時)
- D1 (日線)
- W1 (週線)
- MN1 (月線)

### 技術指標
- Volume Profile（POC、VAH、VAL）
- SMA（簡單移動平均線）
- RSI（相對強弱指標）
- 更多指標持續新增中...

## 測試

測試模組匯入：

```powershell
python scripts/test_imports.py
```

## 疑難排解

### Bot 無法啟動

1. 檢查 `.env` 檔案是否正確設定
2. 確認已安裝所有依賴套件
3. 檢查 Telegram Bot Token 是否有效

### MT5 連線失敗

1. 確認 MT5 終端機正在運行
2. 檢查帳號、密碼和伺服器是否正確
3. 確認 MT5 帳戶狀態正常

### API 錯誤

1. 檢查 Anthropic API Key 是否有效
2. 確認 API 配額未超過限制
3. 檢查網路連線

## 更多資訊

- 實作總結：`thoughts/shared/coding/2025-12-30-telegram-agent-implementation.md`
- 開發計畫：`thoughts/shared/plan/2025-12-30-telegram-agent-implementation-plan.md`

