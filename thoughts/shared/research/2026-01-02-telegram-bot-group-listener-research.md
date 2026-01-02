---
title: Telegram Bot 群組監聽與管理員權限過濾研究
date: 2026-01-02
ticket: N/A
author: Claude Code
tags:
  - telegram-bot
  - group-chat
  - admin-filter
  - breaking-change
status: completed
related_files:
  - src/bot/telegram_bot.py
  - src/bot/handlers.py
  - src/bot/config.py
  - scripts/run_bot.py
  - .env.example
last_updated: 2026-01-02
last_updated_by: Claude Code
---

# Telegram Bot 群組監聽與管理員權限過濾研究

## 研究問題

將 Telegram Bot 修改為**純群組模式**：
1. **完全忽略私聊訊息** - 不回復任何 direct message
2. **只監聽指定群組** - 必須設定 `TELEGRAM_GROUP_IDS`
3. **只響應群組管理員** - 驗證發話者的群組管理員身份

> ⚠️ **破壞式變更**：此修改不向後兼容，將移除原有的私聊模式和 `TELEGRAM_ADMIN_IDS` 機制。

## 摘要

本次修改採用破壞式變更策略，將 Bot 從「私聊優先」改為「純群組模式」：

- **移除** `TELEGRAM_ADMIN_IDS` 環境變數（不再使用）
- **移除** `is_admin()` 方法（不再使用）
- **新增** `TELEGRAM_GROUP_IDS` 環境變數（必要）
- **新增** `is_allowed_group()` 方法
- **修改** 訊息處理邏輯，只處理白名單群組中管理員的訊息

---

## 修改清單

### 需要修改的檔案

| 檔案 | 修改類型 | 說明 |
|------|----------|------|
| `src/bot/config.py` | 重構 | 移除 `admin_ids`，新增 `group_ids` |
| `src/bot/handlers.py` | 重構 | 只處理群組訊息，驗證管理員身份 |
| `src/bot/telegram_bot.py` | 修改 | 過濾器只接收群組訊息 |
| `.env.example` | 修改 | 移除 `ADMIN_IDS`，新增 `GROUP_IDS` |
| `.env` | 修改 | 更新設定 |

---

## 詳細修改方案

### 1. 修改 `src/bot/config.py`

**移除的內容：**
- `telegram_admin_ids: List[int]` 欄位
- `is_admin()` 方法
- `TELEGRAM_ADMIN_IDS` 環境變數解析

**新增的內容：**
- `telegram_group_ids: List[int]` 欄位
- `is_allowed_group()` 方法

```python
"""
Bot 設定管理模組

此模組定義 Bot 的設定資料結構和載入邏輯。
"""

from dataclasses import dataclass
from typing import List
import os
from loguru import logger
from dotenv import load_dotenv


@dataclass
class BotConfig:
    """
    Bot 設定資料類別

    屬性：
        telegram_bot_token: Telegram Bot Token
        telegram_group_ids: 允許的群組 ID 清單（必要）
        anthropic_api_key: Anthropic API Key
        claude_model: Claude 模型名稱
        debug: 是否啟用除錯模式
    """

    # Telegram 設定
    telegram_bot_token: str
    telegram_group_ids: List[int]  # 允許的群組 ID 清單

    # Claude API 設定
    anthropic_api_key: str
    claude_model: str

    # 其他設定
    debug: bool

    @classmethod
    def from_env(cls) -> 'BotConfig':
        """
        從環境變數載入設定

        回傳：
            BotConfig 實例

        例外：
            ValueError: 必要設定缺失時
        """
        # 載入 .env 檔案
        load_dotenv()

        # 讀取必要設定
        telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not telegram_bot_token:
            raise ValueError('未設定 TELEGRAM_BOT_TOKEN 環境變數')

        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            raise ValueError('未設定 ANTHROPIC_API_KEY 環境變數')

        # 讀取群組 ID（必要）
        group_ids_str = os.getenv('TELEGRAM_GROUP_IDS', '')
        if not group_ids_str:
            raise ValueError(
                '未設定 TELEGRAM_GROUP_IDS 環境變數。'
                'Bot 只能在指定群組中運作，請設定至少一個群組 ID。'
            )

        telegram_group_ids = []
        try:
            telegram_group_ids = [
                int(id_str.strip())
                for id_str in group_ids_str.split(',')
                if id_str.strip()
            ]
        except ValueError as e:
            raise ValueError(f'解析 TELEGRAM_GROUP_IDS 失敗：{e}')

        if not telegram_group_ids:
            raise ValueError('TELEGRAM_GROUP_IDS 必須包含至少一個有效的群組 ID')

        logger.info(f'已載入 {len(telegram_group_ids)} 個允許的群組 ID')

        # 讀取其他設定
        claude_model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
        debug = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')

        return cls(
            telegram_bot_token=telegram_bot_token,
            telegram_group_ids=telegram_group_ids,
            anthropic_api_key=anthropic_api_key,
            claude_model=claude_model,
            debug=debug
        )

    def is_allowed_group(self, chat_id: int) -> bool:
        """
        檢查群組是否在允許清單中

        參數：
            chat_id: Telegram Chat ID（群組 ID）

        回傳：
            是否為允許的群組
        """
        return chat_id in self.telegram_group_ids
```

---

### 2. 修改 `src/bot/handlers.py`

**核心邏輯：**
1. 忽略所有私聊訊息（不回應）
2. 忽略不在白名單的群組訊息（不回應）
3. 忽略群組中非管理員的訊息（不回應）
4. 只處理白名單群組中管理員的訊息

```python
"""
訊息處理器模組

此模組定義所有 Telegram Bot 的訊息處理函式。
"""

from telegram import Update, Chat, ChatMember
from telegram.ext import ContextTypes
from loguru import logger
import sys
from pathlib import Path

# 確保可以匯入 agent 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import MT5Agent
from .config import BotConfig


# ============================================================================
# 指令處理器
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    處理 /start 指令

    只在允許的群組中響應管理員。
    """
    chat = update.effective_chat
    user = update.effective_user

    # 忽略私聊
    if chat.type == Chat.PRIVATE:
        logger.debug(f"忽略私聊 /start 指令（用戶: {user.id}）")
        return

    # 檢查群組和管理員權限
    config: BotConfig = context.bot_data.get('config')
    if not await _check_group_admin(update, context, config):
        return

    logger.info(f"群組 {chat.id} 管理員 {user.id} ({user.username}) 執行 /start 指令")

    welcome_message = f"""
你好，{user.first_name}！

我是 MT5 交易助手，可以協助查詢市場數據和計算技術指標。

可用功能：
• 查詢 K 線資料
• 計算 Volume Profile（POC, VAH, VAL）
• 計算技術指標（SMA, RSI 等）
• 取得帳戶資訊

使用方式：
直接用自然語言提出你的問題即可！

範例：
• "幫我查詢黃金最近 100 根 H4 K 線"
• "計算黃金的 Volume Profile"
• "黃金的 RSI 是多少？"

指令列表：
/start - 顯示此歡迎訊息
/help - 顯示詳細說明
/status - 檢查系統狀態

有任何問題隨時告訴我！
"""

    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    處理 /help 指令

    只在允許的群組中響應管理員。
    """
    chat = update.effective_chat
    user = update.effective_user

    # 忽略私聊
    if chat.type == Chat.PRIVATE:
        logger.debug(f"忽略私聊 /help 指令（用戶: {user.id}）")
        return

    # 檢查群組和管理員權限
    config: BotConfig = context.bot_data.get('config')
    if not await _check_group_admin(update, context, config):
        return

    logger.info(f"群組 {chat.id} 管理員 {user.id} ({user.username}) 執行 /help 指令")

    help_message = """
**MT5 交易助手使用說明**

**基本功能：**

1. **查詢 K 線資料**
   範例：
   • "查詢黃金 H1 最近 50 根 K 線"
   • "給我看白銀 D1 的資料"

2. **計算 Volume Profile**
   範例：
   • "計算黃金的 Volume Profile"
   • "幫我看看白銀的 POC 在哪裡"

3. **計算技術指標**
   範例：
   • "計算黃金的 20 日均線"
   • "黃金的 RSI(14) 是多少？"

4. **取得帳戶資訊**
   範例：
   • "我的帳戶資訊"
   • "查詢帳戶餘額"

**支援的商品代碼：**
GOLD, SILVER, EURUSD, GBPUSD, USDJPY 等

**支援的時間週期：**
• M1 - 1 分鐘
• M5 - 5 分鐘
• M15 - 15 分鐘
• M30 - 30 分鐘
• H1 - 1 小時
• H4 - 4 小時
• D1 - 日線
• W1 - 週線
• MN1 - 月線

**提示：**
• 直接用自然語言提問即可
• 可以一次提出多個需求
• 系統會自動選擇適當的工具

如有問題，請聯絡管理員。
"""

    await update.message.reply_text(help_message)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    處理 /status 指令

    只在允許的群組中響應管理員。
    """
    chat = update.effective_chat
    user = update.effective_user

    # 忽略私聊
    if chat.type == Chat.PRIVATE:
        logger.debug(f"忽略私聊 /status 指令（用戶: {user.id}）")
        return

    # 檢查群組和管理員權限
    config: BotConfig = context.bot_data.get('config')
    if not await _check_group_admin(update, context, config):
        return

    logger.info(f"群組 {chat.id} 管理員 {user.id} ({user.username}) 執行 /status 指令")

    try:
        agent = MT5Agent(
            api_key=config.anthropic_api_key,
            model=config.claude_model
        )

        status_message = f"""
系統狀態檢查

✅ Telegram Bot：運作中
✅ Claude Agent：已連線（模型：{config.claude_model}）
✅ MT5 連線：待檢查（需實際查詢時連線）
✅ 群組 ID：{chat.id}

狀態：正常
"""
        await update.message.reply_text(status_message)

    except Exception as e:
        logger.exception("狀態檢查失敗")
        await update.message.reply_text(f"系統狀態異常：{str(e)}")


# ============================================================================
# 訊息處理器
# ============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    處理一般文字訊息

    只處理白名單群組中管理員的訊息。
    私聊訊息和非授權訊息會被靜默忽略。
    """
    user = update.effective_user
    chat = update.effective_chat
    user_message = update.message.text

    # ========================================================================
    # 1. 忽略私聊訊息
    # ========================================================================
    if chat.type == Chat.PRIVATE:
        logger.debug(f"忽略私聊訊息（用戶: {user.id}）")
        return  # 靜默忽略，不回應

    # ========================================================================
    # 2. 忽略非群組訊息（頻道等）
    # ========================================================================
    if chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        logger.debug(f"忽略非群組訊息（類型: {chat.type}）")
        return

    # ========================================================================
    # 3. 檢查群組白名單和管理員權限
    # ========================================================================
    config: BotConfig = context.bot_data.get('config')
    if not config:
        logger.error("Bot 設定未載入")
        return

    if not await _check_group_admin(update, context, config):
        return  # 靜默忽略

    # ========================================================================
    # 4. 記錄並處理訊息
    # ========================================================================
    logger.info(
        f"處理訊息 - 群組: {chat.id} ({chat.title}), "
        f"管理員: {user.id} ({user.username}), "
        f"訊息: {user_message}"
    )

    # 顯示處理中訊息
    processing_message = await update.message.reply_text("正在處理您的請求，請稍候...")

    try:
        # 取得或建立 Agent
        agent = context.bot_data.get('agent')
        if not agent:
            agent = MT5Agent(
                api_key=config.anthropic_api_key,
                model=config.claude_model
            )
            context.bot_data['agent'] = agent

        # 處理訊息
        response = agent.process_message(user_message)

        # 刪除處理中訊息
        await processing_message.delete()

        # 回傳結果（處理長訊息）
        if len(response) <= 4096:
            await update.message.reply_text(response)
        else:
            # 分段傳送
            chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for chunk in chunks:
                await update.message.reply_text(chunk)

        logger.info(f"成功回應群組 {chat.id} 管理員 {user.id}")

    except Exception as e:
        logger.exception(f"處理訊息時發生錯誤：{str(e)}")

        # 刪除處理中訊息
        try:
            await processing_message.delete()
        except:
            pass

        error_message = f"抱歉，處理您的請求時發生錯誤：{str(e)}"
        await update.message.reply_text(error_message)


async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    處理錯誤

    記錄所有錯誤。
    """
    logger.exception(f"更新 {update} 發生錯誤：{context.error}")

    # 只在群組中回應錯誤（且只對管理員）
    if update and update.effective_message and update.effective_chat:
        chat = update.effective_chat
        if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            config: BotConfig = context.bot_data.get('config')
            if config and config.is_allowed_group(chat.id):
                await update.effective_message.reply_text(
                    "抱歉，發生了一個錯誤。請稍後再試或聯絡管理員。"
                )


# ============================================================================
# 輔助函式
# ============================================================================

async def _check_group_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    config: BotConfig
) -> bool:
    """
    檢查是否為允許群組的管理員

    參數：
        update: Telegram Update 物件
        context: Bot Context
        config: Bot 設定

    回傳：
        True 如果是允許群組的管理員，否則 False
    """
    chat = update.effective_chat
    user = update.effective_user

    # 檢查群組白名單
    if not config.is_allowed_group(chat.id):
        logger.debug(
            f"忽略未授權群組訊息 - 群組: {chat.id}, 用戶: {user.id}"
        )
        return False

    # 檢查管理員身份
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in [
            ChatMember.ADMINISTRATOR,
            ChatMember.OWNER
        ]

        if not is_admin:
            logger.debug(
                f"忽略非管理員訊息 - 群組: {chat.id}, "
                f"用戶: {user.id}, 身份: {member.status}"
            )
            return False

        return True

    except Exception as e:
        logger.error(f"檢查群組管理員身份時發生錯誤：{e}")
        return False
```

---

### 3. 修改 `src/bot/telegram_bot.py`

**修改過濾器**：只接收群組訊息

```python
def _register_handlers(self):
    """註冊所有訊息處理器"""

    # 指令處理器（群組中的指令）
    self.application.add_handler(CommandHandler("start", start_command))
    self.application.add_handler(CommandHandler("help", help_command))
    self.application.add_handler(CommandHandler("status", status_command))

    # 訊息處理器：只接收群組中的非指令文字訊息
    self.application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            handle_message
        )
    )

    # 錯誤處理器
    self.application.add_error_handler(handle_error)

    logger.info("所有處理器註冊完成（純群組模式）")
```

---

### 4. 修改 `.env.example`

```bash
# ============================================================================
# MT5 連線設定
# ============================================================================

# MT5 登入帳號（必要）
MT5_LOGIN=12345678

# MT5 登入密碼（必要）
MT5_PASSWORD=your_password

# MT5 伺服器名稱（必要）
MT5_SERVER=YourBroker-Server

# ============================================================================
# Telegram Bot 設定
# ============================================================================

# Telegram Bot Token（必要）
# 從 @BotFather 取得
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# 允許的群組 ID（必要，用逗號分隔）
# Bot 只會在這些群組中運作，並只響應群組管理員的訊息
# 群組 ID 通常是負數，例如：-1001234567890
# 可以透過 @userinfobot 或 @getidsbot 取得群組 ID
TELEGRAM_GROUP_IDS=-1001234567890

# ============================================================================
# Claude API 設定
# ============================================================================

# Anthropic API Key（必要）
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Claude 模型名稱（可選，預設為 claude-sonnet-4-20250514）
CLAUDE_MODEL=claude-sonnet-4-20250514

# ============================================================================
# 其他設定
# ============================================================================

# 除錯模式（可選，預設為 false）
DEBUG=false
```

---

## 訊息處理流程圖

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
│  1. 檢查群組白名單 (TELEGRAM_GROUP_IDS)                      │
│     ❌ 不在白名單 → return（靜默忽略）                       │
│     ✅ 在白名單 → 繼續                                       │
│                                                             │
│  2. 檢查發話者管理員身份 (get_chat_member)                   │
│     ❌ 非管理員 → return（靜默忽略）                         │
│     ✅ 管理員 → 繼續處理                                     │
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

## 環境變數總結

| 變數名稱 | 類型 | 必要性 | 說明 |
|---------|------|--------|------|
| `TELEGRAM_BOT_TOKEN` | string | **必要** | Bot Token |
| `TELEGRAM_GROUP_IDS` | string | **必要** | 允許的群組 ID，逗號分隔 |
| `ANTHROPIC_API_KEY` | string | **必要** | Claude API Key |
| `CLAUDE_MODEL` | string | 可選 | Claude 模型名稱 |
| `DEBUG` | boolean | 可選 | 除錯模式 |

**已移除的變數：**
- ~~`TELEGRAM_ADMIN_IDS`~~ - 不再使用，改為驗證群組管理員身份

---

## 如何取得群組 Chat ID

**方法 1：使用 @userinfobot 或 @getidsbot**

1. 將 Bot 加入群組
2. 在群組中發送任意訊息
3. Bot 會回報群組 ID

**方法 2：透過 Bot 日誌**

1. 暫時修改 `handle_message()` 加入日誌：
   ```python
   logger.info(f"Chat ID: {chat.id}, Title: {chat.title}")
   ```
2. 在群組中發送訊息
3. 查看日誌輸出

**注意事項：**
- 群組 ID 通常是**負數**（如 `-1001234567890`）
- 一般群組升級為超級群組時，ID 會改變

---

## 測試案例

### 測試 1：私聊訊息

- **操作**：在私聊中發送訊息給 Bot
- **預期**：Bot 不回應（靜默忽略）

### 測試 2：未授權群組

- **操作**：在不在 `TELEGRAM_GROUP_IDS` 的群組中發送訊息
- **預期**：Bot 不回應（靜默忽略）

### 測試 3：授權群組 - 非管理員

- **操作**：在授權群組中，以一般成員身份發送訊息
- **預期**：Bot 不回應（靜默忽略）

### 測試 4：授權群組 - 管理員

- **操作**：在授權群組中，以管理員身份發送訊息
- **預期**：Bot 處理訊息並回應

### 測試 5：授權群組 - 群主

- **操作**：在授權群組中，以群主身份發送訊息
- **預期**：Bot 處理訊息並回應

---

## 注意事項

### 1. Bot 權限需求

Bot 必須具有以下權限才能正常運作：
- 被加入群組
- 讀取群組訊息
- 發送群組訊息
- 查詢群組成員資訊（`get_chat_member`）

**建議**：將 Bot 設為群組管理員以確保權限充足。

### 2. API 速率限制

每次訊息都會呼叫 `get_chat_member()` API。如果群組訊息量很大，可能觸發 Telegram API 速率限制。

**優化方案**（未來可考慮）：
- 快取管理員清單
- 使用 `ChatMemberHandler` 監聽管理員變更事件

### 3. 靜默忽略策略

所有非授權訊息都會被**靜默忽略**（不回應），原因：
- 避免在群組中產生雜訊
- 不暴露 Bot 的存在和權限邏輯
- 減少不必要的 API 呼叫

---

## 實作步驟

1. **修改 `src/bot/config.py`**
   - 移除 `telegram_admin_ids` 和 `is_admin()`
   - 新增 `telegram_group_ids` 和 `is_allowed_group()`
   - 修改 `from_env()` 解析邏輯

2. **修改 `src/bot/handlers.py`**
   - 新增 `_check_group_admin()` 輔助函式
   - 修改所有指令處理器加入群組檢查
   - 重寫 `handle_message()` 邏輯

3. **修改 `src/bot/telegram_bot.py`**
   - 修改 `_register_handlers()` 的過濾器

4. **更新 `.env.example` 和 `.env`**
   - 移除 `TELEGRAM_ADMIN_IDS`
   - 新增 `TELEGRAM_GROUP_IDS`

5. **測試**
   - 執行所有測試案例
   - 確認私聊和非授權群組都被靜默忽略

---

**研究完成時間**: 2026-01-02
**預估實作時間**: 1-2 小時
