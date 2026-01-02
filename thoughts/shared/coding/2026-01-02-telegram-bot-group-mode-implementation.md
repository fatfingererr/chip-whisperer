---
title: Telegram Bot 群組模式實作總結
date: 2026-01-02
ticket: N/A
author: Claude Code
tags:
  - telegram-bot
  - group-mode
  - breaking-change
  - implementation
status: completed
related_files:
  - src/bot/config.py
  - src/bot/handlers.py
  - src/bot/telegram_bot.py
  - .env.example
last_updated: 2026-01-02
last_updated_by: Claude Code
---

# Telegram Bot 群組模式實作總結

## 實作概述

本次實作完成了 Telegram Bot 從「私聊優先模式」到「純群組模式」的破壞式變更。Bot 現在只會在指定的群組中運作，並只響應群組管理員的訊息。

**實作時間**: 2026-01-02
**實作依據**: `thoughts/shared/research/2026-01-02-telegram-bot-group-listener-research.md`

---

## 實作內容

### 1. 修改 `src/bot/config.py`

**移除的內容：**
- `telegram_admin_ids: List[int]` 欄位
- `is_admin(user_id: int)` 方法
- `TELEGRAM_ADMIN_IDS` 環境變數解析邏輯

**新增的內容：**
- `telegram_group_ids: List[int]` 欄位（必要）
- `is_allowed_group(chat_id: int)` 方法
- `TELEGRAM_GROUP_IDS` 環境變數解析（必要設定，缺失時拋出 ValueError）

**核心邏輯：**
- 環境變數 `TELEGRAM_GROUP_IDS` 為必要設定，Bot 啟動時會驗證其存在性
- 支援多個群組 ID，以逗號分隔
- 群組 ID 必須為有效的整數，否則啟動失敗
- 至少需要設定一個群組 ID

---

### 2. 修改 `src/bot/handlers.py`

**新增輔助函式：**
- `_check_group_admin()` - 驗證訊息是否來自允許群組的管理員

**修改所有指令處理器：**
- `start_command()` - 只響應群組中的管理員
- `help_command()` - 只響應群組中的管理員
- `status_command()` - 只響應群組中的管理員

**核心變更：**
所有指令處理器都新增了以下邏輯：
```python
# 忽略私聊
if chat.type == Chat.PRIVATE:
    logger.debug(f"忽略私聊 /xxx 指令（用戶: {user.id}）")
    return

# 檢查群組和管理員權限
config: BotConfig = context.bot_data.get('config')
if not await _check_group_admin(update, context, config):
    return
```

**重寫 `handle_message()` 邏輯：**

訊息處理流程分為四個階段：

1. **忽略私聊訊息**
   - 檢查 `chat.type == Chat.PRIVATE`
   - 直接返回，不做任何回應（靜默忽略）

2. **忽略非群組訊息**
   - 檢查 `chat.type not in [Chat.GROUP, Chat.SUPERGROUP]`
   - 過濾掉頻道等其他類型的訊息

3. **檢查群組白名單和管理員權限**
   - 呼叫 `_check_group_admin()` 驗證
   - 不在白名單 → 靜默忽略
   - 非管理員 → 靜默忽略

4. **處理並回應訊息**
   - 只有通過所有檢查的訊息才會被處理
   - 記錄完整的處理資訊（群組 ID、管理員 ID、訊息內容）

**`_check_group_admin()` 輔助函式邏輯：**

```python
async def _check_group_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    config: BotConfig
) -> bool:
    # 1. 檢查群組白名單
    if not config.is_allowed_group(chat.id):
        return False

    # 2. 檢查管理員身份
    member = await context.bot.get_chat_member(chat.id, user.id)
    is_admin = member.status in [
        ChatMember.ADMINISTRATOR,
        ChatMember.OWNER
    ]

    return is_admin
```

---

### 3. 修改 `src/bot/telegram_bot.py`

**修改過濾器設定：**

原始碼：
```python
MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
```

修改後：
```python
MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
    handle_message
)
```

**效果：**
- 只接收群組訊息（`filters.ChatType.GROUPS`）
- 私聊訊息在進入 handler 前就被過濾掉
- 提升效能，減少不必要的處理

**日誌訊息更新：**
```python
logger.info("所有處理器註冊完成（純群組模式）")
```

---

### 4. 修改 `.env.example`

**移除：**
```bash
# 管理員用戶 ID（可選，用逗號分隔）
# 可以透過 @userinfobot 取得自己的 Telegram User ID
TELEGRAM_ADMIN_IDS=123456789,987654321
```

**新增：**
```bash
# 允許的群組 ID（必要，用逗號分隔）
# Bot 只會在這些群組中運作，並只響應群組管理員的訊息
# 群組 ID 通常是負數，例如：-1001234567890
# 可以透過 @userinfobot 或 @getidsbot 取得群組 ID
TELEGRAM_GROUP_IDS=-1001234567890
```

**重點說明：**
- 標註為「必要」設定
- 說明群組 ID 通常是負數
- 提供取得群組 ID 的方法

---

## 訊息處理流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram 訊息進入                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  telegram_bot.py - MessageHandler                           │
│  過濾器: filters.TEXT & ~filters.COMMAND & filters.GROUPS   │
│                                                             │
│  ❌ 私聊訊息 → 直接過濾（不進入 handler）                    │
│  ❌ 頻道訊息 → 直接過濾                                      │
│  ✅ 群組訊息 → 進入 handler                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  handlers.py::handle_message()                              │
│                                                             │
│  1. 再次檢查是否為私聊（雙重保險）                           │
│     ❌ 私聊 → return（靜默忽略）                             │
│                                                             │
│  2. 檢查群組白名單 (TELEGRAM_GROUP_IDS)                      │
│     ❌ 不在白名單 → return（靜默忽略）                       │
│     ✅ 在白名單 → 繼續                                       │
│                                                             │
│  3. 檢查發話者管理員身份 (get_chat_member)                   │
│     ❌ 非管理員 → return（靜默忽略）                         │
│     ✅ 管理員/群主 → 繼續處理                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  agent.agent::MT5Agent                                      │
│  process_message()                                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  回應至群組                                                  │
│  update.message.reply_text()                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 破壞性變更摘要

### 不再支援的功能

1. **私聊模式**
   - Bot 不再響應任何私聊訊息
   - 私聊 `/start`、`/help`、`/status` 都會被靜默忽略

2. **用戶 ID 授權機制**
   - 移除 `TELEGRAM_ADMIN_IDS` 環境變數
   - 移除 `is_admin()` 方法
   - 不再基於用戶 ID 進行權限控制

### 新增的必要設定

1. **`TELEGRAM_GROUP_IDS`（必要）**
   - Bot 啟動時必須設定此環境變數
   - 至少需要一個有效的群組 ID
   - 多個群組 ID 以逗號分隔

### 新的權限控制機制

- **群組白名單**：只處理指定群組的訊息
- **管理員驗證**：只響應群組管理員和群主的訊息
- **靜默忽略**：所有非授權訊息都不會收到任何回應

---

## 環境變數總結

| 變數名稱 | 類型 | 必要性 | 預設值 | 說明 |
|---------|------|--------|-------|------|
| `TELEGRAM_BOT_TOKEN` | string | **必要** | - | Bot Token |
| `TELEGRAM_GROUP_IDS` | string | **必要** | - | 允許的群組 ID，逗號分隔 |
| `ANTHROPIC_API_KEY` | string | **必要** | - | Claude API Key |
| `CLAUDE_MODEL` | string | 可選 | `claude-sonnet-4-20250514` | Claude 模型名稱 |
| `DEBUG` | boolean | 可選 | `false` | 除錯模式 |

**已移除的變數：**
- ~~`TELEGRAM_ADMIN_IDS`~~ - 不再使用

---

## 實作驗證

### 日誌輸出驗證

**啟動時：**
```
已載入 N 個允許的群組 ID
所有處理器註冊完成（純群組模式）
Telegram Bot 初始化完成
```

**運行時（私聊）：**
```
忽略私聊訊息（用戶: 123456789）
```

**運行時（未授權群組）：**
```
忽略未授權群組訊息 - 群組: -1001111111111, 用戶: 123456789
```

**運行時（非管理員）：**
```
忽略非管理員訊息 - 群組: -1001234567890, 用戶: 123456789, 身份: member
```

**運行時（授權管理員）：**
```
處理訊息 - 群組: -1001234567890 (Test Group), 管理員: 123456789 (username), 訊息: 查詢黃金資料
成功回應群組 -1001234567890 管理員 123456789
```

---

## 使用指南

### 1. 如何取得群組 Chat ID

**方法 1：使用第三方 Bot**
1. 將 `@userinfobot` 或 `@getidsbot` 加入群組
2. 在群組中發送任意訊息
3. Bot 會回報群組 ID

**方法 2：透過 Bot 日誌**
1. 暫時修改 `handle_message()` 加入日誌：
   ```python
   logger.info(f"Chat ID: {chat.id}, Title: {chat.title}")
   ```
2. 在群組中發送訊息
3. 查看日誌輸出，記錄群組 ID
4. 移除臨時日誌程式碼

**注意事項：**
- 群組 ID 通常是**負數**（如 `-1001234567890`）
- 一般群組升級為超級群組時，ID 會改變

### 2. 設定 Bot 權限

Bot 需要以下權限才能正常運作：
- ✅ 被加入群組
- ✅ 讀取群組訊息
- ✅ 發送群組訊息
- ✅ 查詢群組成員資訊（`get_chat_member`）

**建議設定：**
- 將 Bot 設為群組管理員以確保權限充足
- 或確保 Bot 有「查看群組成員」權限

### 3. 設定環境變數

**單一群組：**
```bash
TELEGRAM_GROUP_IDS=-1001234567890
```

**多個群組：**
```bash
TELEGRAM_GROUP_IDS=-1001234567890,-1001111111111,-1002222222222
```

---

## 測試案例

### ✅ 測試 1：私聊訊息
- **操作**：在私聊中發送訊息給 Bot
- **預期**：Bot 不回應（靜默忽略）
- **驗證**：日誌顯示 "忽略私聊訊息"

### ✅ 測試 2：未授權群組
- **操作**：在不在 `TELEGRAM_GROUP_IDS` 的群組中發送訊息
- **預期**：Bot 不回應（靜默忽略）
- **驗證**：日誌顯示 "忽略未授權群組訊息"

### ✅ 測試 3：授權群組 - 非管理員
- **操作**：在授權群組中，以一般成員身份發送訊息
- **預期**：Bot 不回應（靜默忽略）
- **驗證**：日誌顯示 "忽略非管理員訊息"

### ✅ 測試 4：授權群組 - 管理員
- **操作**：在授權群組中，以管理員身份發送訊息
- **預期**：Bot 處理訊息並回應
- **驗證**：日誌顯示 "處理訊息" 和 "成功回應"

### ✅ 測試 5：授權群組 - 群主
- **操作**：在授權群組中，以群主身份發送訊息
- **預期**：Bot 處理訊息並回應
- **驗證**：日誌顯示 "處理訊息" 和 "成功回應"

### ✅ 測試 6：啟動時缺少 TELEGRAM_GROUP_IDS
- **操作**：移除 `TELEGRAM_GROUP_IDS` 環境變數後啟動 Bot
- **預期**：Bot 啟動失敗，拋出 ValueError
- **驗證**：錯誤訊息包含 "未設定 TELEGRAM_GROUP_IDS 環境變數"

---

## 注意事項

### 1. API 速率限制

每次訊息都會呼叫 `get_chat_member()` API 來驗證管理員身份。如果群組訊息量很大，可能觸發 Telegram API 速率限制。

**優化方案（未來可考慮）：**
- 快取管理員清單（設定過期時間）
- 使用 `ChatMemberHandler` 監聽管理員變更事件
- 實作 LRU Cache 減少重複查詢

### 2. 靜默忽略策略

所有非授權訊息都會被**靜默忽略**（不回應），原因：
- ✅ 避免在群組中產生雜訊
- ✅ 不暴露 Bot 的存在和權限邏輯
- ✅ 減少不必要的 API 呼叫
- ✅ 提升用戶體驗（一般成員不會收到「權限不足」的錯誤訊息）

### 3. 雙重檢查機制

雖然 `telegram_bot.py` 的過濾器已經過濾掉私聊訊息，`handle_message()` 中仍然保留了私聊檢查：
- 雙重保險，防止意外情況
- 增強程式碼的防禦性
- 即使過濾器設定錯誤，handler 也能正確處理

### 4. 群組升級問題

當一般群組升級為超級群組時，Chat ID 會改變：
- 需要更新 `TELEGRAM_GROUP_IDS` 環境變數
- 建議使用超級群組（Supergroup）以避免此問題
- 可透過 Bot 日誌查看新的群組 ID

---

## 實作檔案清單

| 檔案路徑 | 修改類型 | 行數變化 | 說明 |
|---------|----------|---------|------|
| `src/bot/config.py` | 重構 | -33 / +34 | 移除 admin_ids，新增 group_ids |
| `src/bot/handlers.py` | 重構 | -75 / +173 | 重寫所有處理器邏輯 |
| `src/bot/telegram_bot.py` | 修改 | -3 / +5 | 修改過濾器設定 |
| `.env.example` | 修改 | -4 / +5 | 更新環境變數範例 |

**總計：**
- 新增程式碼：217 行
- 移除程式碼：115 行
- 淨增加：102 行

---

## 向後相容性

**⚠️ 此為破壞式變更，不向後相容。**

### 遷移步驟

1. **更新環境變數**
   ```bash
   # 移除（如果存在）
   # TELEGRAM_ADMIN_IDS=123456789,987654321

   # 新增（必要）
   TELEGRAM_GROUP_IDS=-1001234567890
   ```

2. **取得群組 ID**
   - 使用 `@userinfobot` 或 `@getidsbot` 取得群組 ID
   - 或查看 Bot 日誌

3. **將 Bot 加入目標群組**
   - 確保 Bot 有適當權限
   - 建議設為群組管理員

4. **重新啟動 Bot**
   ```bash
   python scripts/run_bot.py
   ```

5. **驗證運作**
   - 在群組中發送 `/start` 指令（以管理員身份）
   - 確認 Bot 正確回應

### 如果需要繼續支援私聊

如果有特殊需求需要繼續支援私聊模式，可以：
1. 回退此次變更
2. 或實作混合模式（同時支援私聊和群組）
3. 或維護兩個分支版本

---

## 總結

本次實作成功將 Telegram Bot 轉換為純群組模式，實現了以下目標：

✅ **完全忽略私聊訊息** - 不回復任何 direct message
✅ **只監聽指定群組** - 必須設定 `TELEGRAM_GROUP_IDS`
✅ **只響應群組管理員** - 驗證發話者的群組管理員身份
✅ **靜默忽略策略** - 所有非授權訊息都不會收到回應
✅ **雙重檢查機制** - 過濾器 + handler 雙重保險
✅ **完善的日誌記錄** - 所有行為都有清晰的日誌輸出

### 核心優勢

1. **安全性提升**
   - 明確的群組白名單機制
   - 管理員身份驗證
   - 減少攻擊面（不響應未授權訊息）

2. **使用體驗優化**
   - 靜默忽略避免群組雜訊
   - 只有管理員能操作 Bot
   - 清晰的權限控制

3. **維護性改善**
   - 程式碼結構更清晰
   - 職責分離明確
   - 易於擴展和維護

### 後續可能的改善

1. **效能優化**
   - 實作管理員清單快取
   - 減少 `get_chat_member()` 呼叫次數

2. **功能增強**
   - 支援動態新增/移除群組（不需重啟）
   - 實作群組特定的設定
   - 支援管理員等級權限控制

3. **監控與告警**
   - 實作 metrics 統計
   - 監控 API 速率限制
   - 異常情況告警

---

**實作完成日期**: 2026-01-02
**實作者**: Claude Code
**版本**: 1.0.0
