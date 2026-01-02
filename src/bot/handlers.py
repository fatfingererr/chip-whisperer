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


async def crawl_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /crawl_now 指令處理器

    手動觸發一次新聞爬取（僅限管理員）
    """
    chat = update.effective_chat
    user = update.effective_user

    # 忽略私聊
    if chat.type == Chat.PRIVATE:
        logger.debug(f"忽略私聊 /crawl_now 指令（用戶: {user.id}）")
        return

    # 檢查群組和管理員權限
    config: BotConfig = context.bot_data.get('config')
    if not await _check_group_admin(update, context, config):
        return

    logger.info(f"群組 {chat.id} 管理員 {user.id} ({user.username}) 執行 /crawl_now 指令")

    await update.message.reply_text("🔄 正在手動觸發新聞爬取...")

    try:
        # 取得爬蟲調度器（從 Bot 實例）
        crawler_scheduler = context.application.bot_data.get('crawler_scheduler')

        if crawler_scheduler:
            await crawler_scheduler._crawl_and_notify()
            await update.message.reply_text("✅ 爬取完成，請查看上方通知")
        else:
            await update.message.reply_text("❌ 爬蟲未啟動")

    except Exception as e:
        logger.error(f"手動爬取失敗：{e}")
        await update.message.reply_text(f"❌ 爬取失敗：{e}")


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
