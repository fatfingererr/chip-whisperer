# Agent Telegram 執行緒監聽器實作計劃

## 概述

本計劃旨在實現多 Agent 執行緒監聽機制，讓 `agents` 目錄下三個角色（analysts、traders、assistants）的所有 agent 各自監聽 Telegram 訊息、生成每日自我認知，並透過記憶參考機制提供更智慧的回應。

## 當前狀態分析

### 已具備的基礎設施

**優勢**：
- ✅ Telegram bot 框架（`python-telegram-bot` v20+）
- ✅ Claude Anthropic SDK 整合（`anthropic` v0.18.0+）
- ✅ 完整的 async/await 架構
- ✅ APScheduler 定時任務支援（AsyncIOScheduler）
- ✅ Agent 配置檔案（persona.md、jobs.md、routine.md）
- ✅ 管理員權限驗證機制（`_check_group_admin()`）
- ✅ 日誌系統（loguru）
- ✅ 時區處理範例（UTC+8 / Asia/Taipei）

**限制**：
- ❌ 目前僅使用單一 `MT5Agent` 實例處理所有訊息
- ❌ 沒有基於 agent 名稱的訊息路由機制
- ❌ 沒有每日自我認知生成功能
- ❌ 沒有記憶整合機制
- ❌ 日誌結構不支援個別 agent 的日誌分類

### 關鍵發現

從研究文檔中，我們了解到：

1. **Agent 目錄結構**：
   ```
   agents/
   ├── analysts/Arthur/    # 分析師
   ├── traders/Max/        # 交易員
   └── assistants/Donna/   # 助理
   ```

2. **現有訊息處理流程**（`src/bot/handlers.py:232-318`）：
   - 單一處理器 `handle_message()` 處理所有訊息
   - 使用共用的 `MT5Agent` 實例
   - 已實現 admin 權限驗證

3. **APScheduler 使用範例**（`src/crawler/scheduler.py`）：
   - 已在 `CrawlerScheduler` 中成功整合定時任務
   - 使用 `AsyncIOScheduler` 和 `CronTrigger`/`IntervalTrigger`

4. **Bot 啟動流程**（`src/bot/telegram_bot.py`）：
   - `_post_init()` 回調在 bot 啟動後執行（99-117 行）
   - `_post_shutdown()` 回調在 bot 關閉前執行（164-178 行）

## 理想的最終狀態

### 架構目標

**多 Agent 實例管理**：
- 每個 agent（Arthur、Max、Donna）有獨立的實例
- 每個實例載入自己的 persona.md、jobs.md、routine.md
- 獨立的對話歷史和 system prompt

**訊息路由機制**：
- 訊息前 10 個字元（忽略大小寫、空白）匹配 agent 名稱
- 支援中英文名稱（Arthur/亞瑟、Max/麥克斯、Donna/朵娜）
- 匹配成功則路由到對應的 agent 處理

**每日自我認知**：
- 每天 00:00 (UTC+8) 自動觸發
- 讀取 persona.md、jobs.md、routine.md
- 使用 Claude 生成 300 中文字的自我認知
- 寫入 `logs/yyyymmdd/<agent 名稱>.log`

**記憶整合**：
- 回答問題前檢查當日 log 檔
- 若存在，將 log 全文附加到提示詞作為「本日記憶參考」
- 互動記錄也追加到 log 檔

**日誌結構**：
```
logs/
├── 20260102/          # UTC+8 日期目錄
│   ├── arthur.log     # Arthur 的自我認知 + 互動記錄
│   ├── max.log        # Max 的自我認知 + 互動記錄
│   └── donna.log      # Donna 的自我認知 + 互動記錄
├── 20260103/
│   └── ...
└── 2026-01-02.log     # 系統日誌（保持不變）
```

## 我們不做什麼

為避免範圍蔓延，以下項目**明確排除**在本次實作之外：

- ❌ 不實現傳統執行緒（使用 async task 代替）
- ❌ 不修改現有的系統日誌結構（`logs/YYYY-MM-DD.log`）
- ❌ 不實現 routine.md 中定義的定期任務腳本（本次僅實現自我認知生成）
- ❌ 不實現跨 agent 的任務轉介機制（暫時）
- ❌ 不實現 agent 間的協作通訊（暫時）
- ❌ 不修改現有的指令處理器（`/start`、`/help`、`/status`、`/crawl_now`）
- ❌ 不新增額外的環境變數或配置項目（除非必要）

## 實作方法

### 核心策略

1. **Agent 實例管理**：建立 `AgentManager` 類別統一管理所有 agent 實例
2. **訊息路由**：在 `handle_message()` 加入名稱匹配邏輯
3. **定時任務整合**：使用 `AsyncIOScheduler` 整合每日自我認知任務
4. **記憶管理**：在訊息處理流程中整合記憶讀取和追加邏輯

### 技術選型

- **並行模型**：使用 `asyncio.create_task()` 而非傳統執行緒（與現有架構一致）
- **調度器**：使用 `APScheduler` 的 `AsyncIOScheduler`（已有成功案例）
- **時區處理**：使用 `pytz.timezone('Asia/Taipei')`（已在代碼中使用）
- **日誌格式**：使用標準文字檔，UTF-8 編碼

---

## 階段一：建立 Agent 管理器

### 概述

建立 `AgentManager` 類別，負責載入和管理所有 agent 實例，包括讀取配置檔案、建立獨立的 system prompt、管理日誌路徑等。

### 需要修改的檔案

#### 1. 新增 `src/agent/agent_manager.py`

**檔案路徑**：`C:\Users\fatfi\works\chip-whisperer\src\agent\agent_manager.py`

**說明**：這是核心的 Agent 管理器，負責載入所有 agent 配置、建立實例、管理日誌路徑。

**完整程式碼**：

```python
"""
Agent 管理器模組

負責載入和管理所有 agent 實例，包括配置讀取、實例化、日誌管理等。
"""

from typing import Dict, Optional, Tuple
from pathlib import Path
from loguru import logger
from datetime import datetime
import pytz
import os

from .agent import MT5Agent


class AgentManager:
    """
    Agent 管理器

    統一管理所有 agent 實例的生命週期和資源。
    """

    # Agent 角色映射
    AGENT_ROLES = {
        'arthur': 'analysts',
        'max': 'traders',
        'donna': 'assistants'
    }

    # Agent 中英文名稱映射
    AGENT_NAMES = {
        'arthur': ['arthur', '亞瑟'],
        'max': ['max', '麥克斯'],
        'donna': ['donna', '朵娜']
    }

    def __init__(self, api_key: str, model: str, agents_base_dir: str = 'agents'):
        """
        初始化 Agent 管理器

        參數：
            api_key: Anthropic API Key
            model: Claude 模型名稱
            agents_base_dir: agents 目錄路徑（預設為 'agents'）
        """
        self.api_key = api_key
        self.model = model
        self.agents_base_dir = Path(agents_base_dir)
        self.agents: Dict[str, MT5Agent] = {}
        self.agent_configs: Dict[str, Dict[str, str]] = {}

        # 台灣時區
        self.taiwan_tz = pytz.timezone('Asia/Taipei')

        # 載入所有 agents
        self._load_agents()

        logger.info(f"AgentManager 初始化完成，已載入 {len(self.agents)} 個 agents")

    def _load_agents(self):
        """載入所有 agent 實例"""
        for agent_name, role in self.AGENT_ROLES.items():
            try:
                # 讀取配置檔案
                config = self._load_agent_config(agent_name, role)
                self.agent_configs[agent_name] = config

                # 建立 system prompt
                system_prompt = self._build_system_prompt(config)

                # 建立 agent 實例（暫存 system_prompt 到實例中）
                agent = MT5Agent(api_key=self.api_key, model=self.model)
                agent.default_system_prompt = system_prompt  # 新增屬性

                self.agents[agent_name] = agent

                logger.info(f"已載入 agent：{agent_name} ({role})")

            except Exception as e:
                logger.error(f"載入 agent {agent_name} 失敗：{e}")

    def _load_agent_config(self, agent_name: str, role: str) -> Dict[str, str]:
        """
        讀取 agent 的配置檔案

        參數：
            agent_name: agent 名稱（小寫）
            role: 角色目錄名稱

        回傳：
            包含 persona、jobs、routine 內容的字典
        """
        agent_name_cap = agent_name.capitalize()
        agent_dir = self.agents_base_dir / role / agent_name_cap

        config = {}

        # 讀取 persona.md
        persona_path = agent_dir / 'persona.md'
        if persona_path.exists():
            with open(persona_path, 'r', encoding='utf-8') as f:
                config['persona'] = f.read()
        else:
            logger.warning(f"找不到 {agent_name} 的 persona.md")
            config['persona'] = ''

        # 讀取 jobs.md
        jobs_path = agent_dir / 'jobs.md'
        if jobs_path.exists():
            with open(jobs_path, 'r', encoding='utf-8') as f:
                config['jobs'] = f.read()
        else:
            logger.warning(f"找不到 {agent_name} 的 jobs.md")
            config['jobs'] = ''

        # 讀取 routine.md
        routine_path = agent_dir / 'routine.md'
        if routine_path.exists():
            with open(routine_path, 'r', encoding='utf-8') as f:
                config['routine'] = f.read()
        else:
            logger.warning(f"找不到 {agent_name} 的 routine.md")
            config['routine'] = ''

        return config

    def _build_system_prompt(self, config: Dict[str, str]) -> str:
        """
        建立 agent 的 system prompt

        參數：
            config: agent 配置（persona、jobs、routine）

        回傳：
            完整的 system prompt
        """
        system_prompt = f"""你是一個專業的 MT5 交易助手團隊成員。

# 你的人格設定

{config['persona']}

# 你的任務職責

{config['jobs']}

# 你的定期任務

{config['routine']}

# 工具使用說明

你可以使用以下工具：
1. get_candles - 取得歷史 K 線資料
2. calculate_volume_profile - 計算 Volume Profile（POC, VAH, VAL）
3. calculate_sma - 計算簡單移動平均線
4. calculate_rsi - 計算相對強弱指標
5. get_account_info - 取得帳戶資訊

請根據用戶的需求，自動選擇並調用適當的工具。在使用計算工具前，需要先使用 get_candles 取得資料。

# 回答規範

請遵循以下規範：
- 使用繁體中文回答
- 保持你的人格特質和說話風格
- 根據你的任務職責範圍回答問題
- 清晰解釋分析結果
- 提供實用的交易見解
- 保持專業和友善的語氣
"""
        return system_prompt

    def match_agent(self, message: str) -> Optional[str]:
        """
        根據訊息前 10 個字元匹配 agent

        參數：
            message: 用戶訊息

        回傳：
            匹配的 agent 名稱（小寫），若無匹配則回傳 None
        """
        # 提取前 10 個字元，移除空白，轉小寫
        prefix = ''.join(message[:10].split()).lower()

        # 檢查每個 agent
        for agent_name, name_variants in self.AGENT_NAMES.items():
            for name in name_variants:
                if name.lower() in prefix:
                    logger.debug(f"訊息匹配到 agent：{agent_name}")
                    return agent_name

        logger.debug("訊息未匹配到任何 agent")
        return None

    def get_agent(self, agent_name: str) -> Optional[MT5Agent]:
        """
        取得指定的 agent 實例

        參數：
            agent_name: agent 名稱（小寫）

        回傳：
            MT5Agent 實例，若不存在則回傳 None
        """
        return self.agents.get(agent_name)

    def get_daily_log_path(self, agent_name: str) -> Path:
        """
        取得指定 agent 的當日日誌路徑

        參數：
            agent_name: agent 名稱（小寫）

        回傳：
            日誌檔案的完整路徑
        """
        # 取得台灣時區的當前日期
        now = datetime.now(self.taiwan_tz)
        date_str = now.strftime('%Y%m%d')

        # 建立日誌目錄
        log_dir = Path('logs') / date_str
        log_dir.mkdir(parents=True, exist_ok=True)

        # 回傳日誌檔案路徑
        return log_dir / f'{agent_name}.log'

    def read_daily_memory(self, agent_name: str) -> str:
        """
        讀取指定 agent 的當日記憶

        參數：
            agent_name: agent 名稱（小寫）

        回傳：
            當日記憶內容，若檔案不存在則回傳空字串
        """
        log_path = self.get_daily_log_path(agent_name)

        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.debug(f"已讀取 {agent_name} 的當日記憶：{len(content)} 字元")
                return content
            except Exception as e:
                logger.error(f"讀取 {agent_name} 當日記憶失敗：{e}")
                return ''
        else:
            logger.debug(f"{agent_name} 的當日記憶檔案不存在")
            return ''

    def append_to_daily_log(self, agent_name: str, content: str):
        """
        追加內容到指定 agent 的當日日誌

        參數：
            agent_name: agent 名稱（小寫）
            content: 要追加的內容
        """
        log_path = self.get_daily_log_path(agent_name)

        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(content)
            logger.debug(f"已追加內容到 {agent_name} 的當日日誌")
        except Exception as e:
            logger.error(f"追加內容到 {agent_name} 當日日誌失敗：{e}")

    def get_all_agent_names(self) -> list:
        """
        取得所有 agent 名稱

        回傳：
            agent 名稱列表（小寫）
        """
        return list(self.agents.keys())
```

### 成功標準

#### 自動化驗證：

- [ ] `src/agent/agent_manager.py` 檔案建立成功
- [ ] Python 語法檢查通過：`python -m py_compile src/agent/agent_manager.py`
- [ ] 匯入測試通過：`python -c "from src.agent.agent_manager import AgentManager; print('OK')"`

#### 手動驗證：

- [ ] 啟動 bot 時，`AgentManager` 成功載入三個 agents（Arthur、Max、Donna）
- [ ] 日誌中顯示「AgentManager 初始化完成，已載入 3 個 agents」
- [ ] 日誌中顯示每個 agent 的載入訊息（「已載入 agent：arthur (analysts)」等）
- [ ] 沒有出現找不到配置檔案的警告

**實作注意事項**：完成此階段的所有自動化驗證後，暫停並等待手動驗證確認成功，然後再進入階段二。

---

## 階段二：整合 Agent 管理器到 Bot

### 概述

將 `AgentManager` 整合到 `TelegramBot` 中，修改訊息處理流程以支援多 agent 路由。

### 需要修改的檔案

#### 1. 修改 `src/bot/telegram_bot.py`

**檔案路徑**：`C:\Users\fatfi\works\chip-whisperer\src\bot\telegram_bot.py`

**修改點 1**：在檔案頂部新增匯入

```python
# 在現有的匯入之後新增
from src.agent.agent_manager import AgentManager
```

**修改點 2**：修改 `__init__()` 方法（40-72 行）

**原始程式碼**：
```python
def __init__(self, config: BotConfig):
    """
    初始化 Bot

    參數：
        config: Bot 設定
    """
    self.config = config

    # 建立 Application
    self.application = (
        Application.builder()
        .token(config.telegram_bot_token)
        .build()
    )

    # 儲存設定到 bot_data
    self.application.bot_data['config'] = config

    # 註冊處理器
    self._register_handlers()

    # 新增：初始化爬蟲調度器
    crawler_config = CrawlerConfig.from_env()
    self.crawler_scheduler = CrawlerScheduler(
        config=crawler_config,
        telegram_app=self.application
    )

    # 新增：儲存到 bot_data，供指令處理器使用
    self.application.bot_data['crawler_scheduler'] = self.crawler_scheduler

    logger.info("Telegram Bot 初始化完成")
```

**新程式碼**：
```python
def __init__(self, config: BotConfig):
    """
    初始化 Bot

    參數：
        config: Bot 設定
    """
    self.config = config

    # 建立 Application
    self.application = (
        Application.builder()
        .token(config.telegram_bot_token)
        .build()
    )

    # 儲存設定到 bot_data
    self.application.bot_data['config'] = config

    # 註冊處理器
    self._register_handlers()

    # 新增：初始化 AgentManager
    self.agent_manager = AgentManager(
        api_key=config.anthropic_api_key,
        model=config.claude_model
    )
    self.application.bot_data['agent_manager'] = self.agent_manager

    # 新增：初始化爬蟲調度器
    crawler_config = CrawlerConfig.from_env()
    self.crawler_scheduler = CrawlerScheduler(
        config=crawler_config,
        telegram_app=self.application
    )

    # 新增：儲存到 bot_data，供指令處理器使用
    self.application.bot_data['crawler_scheduler'] = self.crawler_scheduler

    logger.info("Telegram Bot 初始化完成")
```

#### 2. 修改 `src/bot/handlers.py`

**檔案路徑**：`C:\Users\fatfi\works\chip-whisperer\src\bot\handlers.py`

**修改點**：完全重寫 `handle_message()` 函數（232-318 行）

**原始程式碼**：
```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    處理一般文字訊息

    只處理白名單群組中管理員的訊息。
    私聊訊息和非授權訊息會被靜默忽略。
    """
    user = update.effective_user
    chat = update.effective_chat
    user_message = update.message.text

    # 1. 忽略私聊訊息
    if chat.type == Chat.PRIVATE:
        logger.debug(f"忽略私聊訊息（用戶: {user.id}）")
        return

    # 2. 忽略非群組訊息（頻道等）
    if chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        logger.debug(f"忽略非群組訊息（類型: {chat.type}）")
        return

    # 3. 檢查群組白名單和管理員權限
    config: BotConfig = context.bot_data.get('config')
    if not config:
        logger.error("Bot 設定未載入")
        return

    if not await _check_group_admin(update, context, config):
        return

    # 4. 記錄並處理訊息
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
```

**新程式碼**：
```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    處理一般文字訊息

    只處理白名單群組中管理員的訊息。
    使用 AgentManager 根據訊息內容路由到對應的 agent。
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
    # 4. 取得 AgentManager
    # ========================================================================
    from src.agent.agent_manager import AgentManager
    agent_manager: AgentManager = context.bot_data.get('agent_manager')
    if not agent_manager:
        logger.error("AgentManager 未初始化")
        await update.message.reply_text("系統錯誤：Agent 管理器未初始化")
        return

    # ========================================================================
    # 5. 匹配 Agent
    # ========================================================================
    agent_name = agent_manager.match_agent(user_message)

    if not agent_name:
        logger.debug(f"訊息未匹配到任何 agent，忽略：{user_message[:50]}")
        return  # 靜默忽略未匹配的訊息

    # ========================================================================
    # 6. 記錄並處理訊息
    # ========================================================================
    logger.info(
        f"處理訊息 - 群組: {chat.id} ({chat.title}), "
        f"管理員: {user.id} ({user.username}), "
        f"Agent: {agent_name}, "
        f"訊息: {user_message}"
    )

    # 顯示處理中訊息
    processing_message = await update.message.reply_text(
        f"收到！{agent_name.capitalize()} 正在處理您的請求..."
    )

    try:
        # 取得 agent 實例
        agent = agent_manager.get_agent(agent_name)
        if not agent:
            logger.error(f"找不到 agent：{agent_name}")
            await processing_message.delete()
            await update.message.reply_text(f"系統錯誤：找不到 {agent_name}")
            return

        # ====================================================================
        # 7. 整合記憶參考
        # ====================================================================
        daily_memory = agent_manager.read_daily_memory(agent_name)

        # 建立增強的訊息（若有記憶則附加）
        if daily_memory:
            enhanced_message = f"{user_message}\n\n[本日記憶參考]\n{daily_memory}"
            logger.debug(f"已整合 {agent_name} 的記憶：{len(daily_memory)} 字元")
        else:
            enhanced_message = user_message
            logger.debug(f"{agent_name} 沒有本日記憶")

        # 取得 system prompt（從 agent 的 default_system_prompt 屬性）
        system_prompt = getattr(agent, 'default_system_prompt', None)

        # ====================================================================
        # 8. 處理訊息
        # ====================================================================
        response = agent.process_message(
            enhanced_message,
            system_prompt=system_prompt
        )

        # ====================================================================
        # 9. 記錄互動到日誌
        # ====================================================================
        from datetime import datetime
        import pytz
        taiwan_tz = pytz.timezone('Asia/Taipei')
        timestamp = datetime.now(taiwan_tz).strftime('%Y-%m-%d %H:%M:%S')

        interaction_log = f"""
[{timestamp}] 用戶 {user.username} ({user.id}): {user_message}
回應: {response}

"""
        agent_manager.append_to_daily_log(agent_name, interaction_log)

        # ====================================================================
        # 10. 回傳結果
        # ====================================================================
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

        logger.info(f"成功回應群組 {chat.id} 管理員 {user.id}（Agent: {agent_name}）")

    except Exception as e:
        logger.exception(f"處理訊息時發生錯誤：{str(e)}")

        # 刪除處理中訊息
        try:
            await processing_message.delete()
        except:
            pass

        error_message = f"抱歉，{agent_name.capitalize()} 處理您的請求時發生錯誤：{str(e)}"
        await update.message.reply_text(error_message)
```

### 成功標準

#### 自動化驗證：

- [ ] `src/bot/telegram_bot.py` 修改完成
- [ ] `src/bot/handlers.py` 修改完成
- [ ] Python 語法檢查通過：`python -m py_compile src/bot/telegram_bot.py`
- [ ] Python 語法檢查通過：`python -m py_compile src/bot/handlers.py`
- [ ] Bot 啟動成功：`python scripts/run_bot.py`（不中斷）

#### 手動驗證：

- [ ] 在 Telegram 群組發送「Arthur 黃金趨勢如何」，Arthur 成功回應
- [ ] 在 Telegram 群組發送「Max 可以進場嗎」，Max 成功回應
- [ ] 在 Telegram 群組發送「Donna 帳戶餘額」，Donna 成功回應
- [ ] 發送不包含 agent 名稱的訊息（如「你好」），bot 靜默忽略（不回應）
- [ ] 發送包含中文名稱的訊息（如「亞瑟 分析一下」），Arthur 成功回應
- [ ] 日誌中顯示正確的 agent 匹配和處理訊息（「Agent: arthur」等）

**實作注意事項**：完成此階段的所有自動化驗證後，暫停並等待手動驗證確認成功，然後再進入階段三。

---

## 階段三：實現每日自我認知生成

### 概述

建立 `AgentScheduler` 類別，使用 APScheduler 在每天 00:00 (UTC+8) 自動為每個 agent 生成自我認知並寫入日誌。

### 需要修改的檔案

#### 1. 新增 `src/agent/agent_scheduler.py`

**檔案路徑**：`C:\Users\fatfi\works\chip-whisperer\src\agent\agent_scheduler.py`

**說明**：Agent 定時任務管理器，負責每日自我認知生成。

**完整程式碼**：

```python
"""
Agent 定時任務管理器

負責管理 agent 的定期任務，如每日自我認知生成。
"""

from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from datetime import datetime
import pytz

from .agent_manager import AgentManager


class AgentScheduler:
    """
    Agent 定時任務管理器

    使用 APScheduler 管理 agent 的定期任務。
    """

    def __init__(self, agent_manager: AgentManager):
        """
        初始化調度器

        參數:
            agent_manager: AgentManager 實例
        """
        self.agent_manager = agent_manager
        self.scheduler = AsyncIOScheduler(timezone='Asia/Taipei')
        self.taiwan_tz = pytz.timezone('Asia/Taipei')

        logger.info("AgentScheduler 初始化完成")

    async def _generate_daily_self_reflection(self, agent_name: str):
        """
        生成指定 agent 的每日自我認知

        參數:
            agent_name: agent 名稱（小寫）
        """
        try:
            logger.info(f"開始生成 {agent_name} 的每日自我認知")

            # 取得 agent 實例和配置
            agent = self.agent_manager.get_agent(agent_name)
            if not agent:
                logger.error(f"找不到 agent：{agent_name}")
                return

            config = self.agent_manager.agent_configs.get(agent_name)
            if not config:
                logger.error(f"找不到 {agent_name} 的配置")
                return

            # 取得當前日期
            now = datetime.now(self.taiwan_tz)
            date_str = now.strftime('%Y年%m月%d日')

            # 建立自我認知提示詞
            prompt = f"""今天是 {date_str}，這是新的一天的開始。

請根據以下資訊，用繁體中文撰寫你的自我認知（約 300 字）：

## 你的人格設定

{config['persona']}

## 你的任務職責

{config['jobs']}

## 你的定期任務

{config['routine']}

---

請描述：
1. 你對自己角色的理解
2. 今日的工作重點和目標
3. 你的心態和準備

請用第一人稱撰寫，展現你的人格特質。
"""

            # 使用 agent 生成自我認知（不使用 default_system_prompt）
            reflection = agent.process_message(prompt, system_prompt="你是一個專業的 MT5 交易團隊成員，正在撰寫你的每日自我認知。")

            # 建立日誌內容
            log_content = f"""{'='*60}
{date_str} 自我認知
{'='*60}

{reflection}

{'='*60}

"""

            # 寫入日誌（覆蓋模式，因為這是當日第一筆記錄）
            log_path = self.agent_manager.get_daily_log_path(agent_name)

            # 檢查檔案是否已存在（避免重複生成）
            if log_path.exists():
                logger.warning(f"{agent_name} 的當日自我認知已存在，跳過生成")
                return

            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(log_content)

            logger.info(f"{agent_name} 的每日自我認知已生成並寫入：{log_path}")

        except Exception as e:
            logger.exception(f"生成 {agent_name} 每日自我認知失敗：{e}")

    def start(self):
        """
        啟動定時任務
        """
        # 為每個 agent 設定每日任務
        for agent_name in self.agent_manager.get_all_agent_names():
            self.scheduler.add_job(
                self._generate_daily_self_reflection,
                args=[agent_name],
                trigger=CronTrigger(hour=0, minute=0, timezone=self.taiwan_tz),
                id=f'{agent_name}_daily_reflection',
                name=f'{agent_name.capitalize()} 每日自我認知',
                replace_existing=True
            )

            logger.info(f"已設定 {agent_name} 的每日自我認知任務（每天 00:00 UTC+8）")

        # 啟動調度器
        self.scheduler.start()
        logger.info("AgentScheduler 已啟動")

    def stop(self):
        """
        停止定時任務
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("AgentScheduler 已停止")

    async def trigger_self_reflection_now(self, agent_name: str):
        """
        手動觸發指定 agent 的自我認知生成（用於測試）

        參數:
            agent_name: agent 名稱（小寫）
        """
        logger.info(f"手動觸發 {agent_name} 的自我認知生成")
        await self._generate_daily_self_reflection(agent_name)
```

#### 2. 修改 `src/bot/telegram_bot.py`

**修改點 1**：在檔案頂部新增匯入

```python
# 在現有的匯入之後新增
from src.agent.agent_scheduler import AgentScheduler
```

**修改點 2**：修改 `__init__()` 方法

在初始化 `AgentManager` 之後新增：

```python
# 新增：初始化 AgentScheduler
self.agent_scheduler = AgentScheduler(agent_manager=self.agent_manager)
self.application.bot_data['agent_scheduler'] = self.agent_scheduler
```

**修改點 3**：修改 `_post_init()` 方法（99-117 行）

**原始程式碼**：
```python
async def _post_init(self, application: Application):
    """
    初始化後回調

    在 Bot 啟動後執行的初始化任務。
    """
    logger.info("Bot 啟動後初始化...")

    # 取得 Bot 資訊
    bot = await application.bot.get_me()
    logger.info(f"Bot 用戶名：@{bot.username}")
    logger.info(f"Bot ID：{bot.id}")

    # 發送開張訊息到所有配置的群組
    await self._send_startup_message(application)

    # 新增：啟動爬蟲定時任務
    self.crawler_scheduler.start()
    logger.info("爬蟲定時任務已整合到 Bot 生命週期")
```

**新程式碼**：
```python
async def _post_init(self, application: Application):
    """
    初始化後回調

    在 Bot 啟動後執行的初始化任務。
    """
    logger.info("Bot 啟動後初始化...")

    # 取得 Bot 資訊
    bot = await application.bot.get_me()
    logger.info(f"Bot 用戶名：@{bot.username}")
    logger.info(f"Bot ID：{bot.id}")

    # 發送開張訊息到所有配置的群組
    await self._send_startup_message(application)

    # 新增：啟動爬蟲定時任務
    self.crawler_scheduler.start()
    logger.info("爬蟲定時任務已整合到 Bot 生命週期")

    # 新增：啟動 Agent 定時任務
    self.agent_scheduler.start()
    logger.info("Agent 定時任務已整合到 Bot 生命週期")
```

**修改點 4**：修改 `_post_shutdown()` 方法（164-178 行）

**原始程式碼**：
```python
async def _post_shutdown(self, application: Application):
    """
    關閉後回調

    在 Bot 關閉前執行的清理任務。
    """
    logger.info("Bot 正在關閉...")

    # 發送關閉訊息到所有配置的群組
    await self._send_shutdown_message(application)

    # 新增：停止爬蟲定時任務
    self.crawler_scheduler.stop()
    logger.info("爬蟲定時任務已停止")
```

**新程式碼**：
```python
async def _post_shutdown(self, application: Application):
    """
    關閉後回調

    在 Bot 關閉前執行的清理任務。
    """
    logger.info("Bot 正在關閉...")

    # 發送關閉訊息到所有配置的群組
    await self._send_shutdown_message(application)

    # 新增：停止爬蟲定時任務
    self.crawler_scheduler.stop()
    logger.info("爬蟲定時任務已停止")

    # 新增：停止 Agent 定時任務
    self.agent_scheduler.stop()
    logger.info("Agent 定時任務已停止")
```

#### 3. 新增測試腳本 `scripts/test_daily_reflection.py`

**檔案路徑**：`C:\Users\fatfi\works\chip-whisperer\scripts\test_daily_reflection.py`

**說明**：手動觸發自我認知生成的測試腳本。

**完整程式碼**：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試 Agent 每日自我認知生成

此腳本用於手動觸發 agent 的自我認知生成，不需要等到午夜 00:00。

使用方式：
    python scripts/test_daily_reflection.py [agent_name]

範例：
    python scripts/test_daily_reflection.py arthur
    python scripts/test_daily_reflection.py max
    python scripts/test_daily_reflection.py donna
    python scripts/test_daily_reflection.py all
"""

import sys
import asyncio
from pathlib import Path

# 確保可以匯入 src 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.bot.config import BotConfig
from src.agent.agent_manager import AgentManager
from src.agent.agent_scheduler import AgentScheduler


async def main(agent_name: str = 'all'):
    """
    主函式

    參數：
        agent_name: 要生成自我認知的 agent 名稱（arthur/max/donna/all）
    """
    try:
        # 載入設定
        logger.info("載入 Bot 設定...")
        config = BotConfig.from_env()

        # 初始化 AgentManager
        logger.info("初始化 AgentManager...")
        agent_manager = AgentManager(
            api_key=config.anthropic_api_key,
            model=config.claude_model
        )

        # 初始化 AgentScheduler
        logger.info("初始化 AgentScheduler...")
        agent_scheduler = AgentScheduler(agent_manager=agent_manager)

        # 觸發自我認知生成
        if agent_name == 'all':
            logger.info("為所有 agents 生成自我認知...")
            for name in agent_manager.get_all_agent_names():
                await agent_scheduler.trigger_self_reflection_now(name)
        else:
            if agent_name not in agent_manager.get_all_agent_names():
                logger.error(f"找不到 agent：{agent_name}")
                logger.info(f"可用的 agents：{', '.join(agent_manager.get_all_agent_names())}")
                sys.exit(1)

            logger.info(f"為 {agent_name} 生成自我認知...")
            await agent_scheduler.trigger_self_reflection_now(agent_name)

        logger.info("✅ 自我認知生成完成")

    except Exception as e:
        logger.exception(f"發生錯誤：{e}")
        sys.exit(1)


if __name__ == "__main__":
    # 取得命令列參數
    agent_name = sys.argv[1] if len(sys.argv) > 1 else 'all'

    # 執行
    asyncio.run(main(agent_name))
```

### 成功標準

#### 自動化驗證：

- [ ] `src/agent/agent_scheduler.py` 檔案建立成功
- [ ] `scripts/test_daily_reflection.py` 檔案建立成功
- [ ] `src/bot/telegram_bot.py` 修改完成
- [ ] Python 語法檢查通過：`python -m py_compile src/agent/agent_scheduler.py`
- [ ] Python 語法檢查通過：`python -m py_compile scripts/test_daily_reflection.py`
- [ ] Python 語法檢查通過：`python -m py_compile src/bot/telegram_bot.py`
- [ ] 測試腳本執行成功：`python scripts/test_daily_reflection.py all`
- [ ] 日誌檔案生成成功：檢查 `logs/20260102/arthur.log`、`logs/20260102/max.log`、`logs/20260102/donna.log` 存在

#### 手動驗證：

- [ ] 開啟 `logs/20260102/arthur.log`，內容包含「自我認知」標題和約 300 字的繁體中文內容
- [ ] 開啟 `logs/20260102/max.log`，內容包含「自我認知」標題和約 300 字的繁體中文內容
- [ ] 開啟 `logs/20260102/donna.log`，內容包含「自我認知」標題和約 300 字的繁體中文內容
- [ ] 自我認知內容展現各 agent 的人格特質（Arthur 專業嚴謹、Max 行動導向、Donna 親切友善）
- [ ] 日誌中顯示「AgentScheduler 已啟動」
- [ ] 日誌中顯示每個 agent 的定時任務設定訊息
- [ ] Bot 啟動時，AgentScheduler 成功整合到生命週期

**實作注意事項**：完成此階段的所有自動化驗證後，暫停並等待手動驗證確認成功，然後再進入階段四。

---

## 階段四：整合測試與文檔

### 概述

建立端到端測試腳本，驗證整個系統的功能，並撰寫使用文檔。

### 需要修改的檔案

#### 1. 新增 `scripts/test_agent_system.py`

**檔案路徑**：`C:\Users\fatfi\works\chip-whisperer\scripts\test_agent_system.py`

**說明**：完整的端到端測試腳本。

**完整程式碼**：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent 系統端到端測試

測試項目：
1. AgentManager 初始化
2. Agent 名稱匹配
3. 記憶讀取和追加
4. 每日自我認知生成
5. 訊息處理流程

使用方式：
    python scripts/test_agent_system.py
"""

import sys
import asyncio
from pathlib import Path

# 確保可以匯入 src 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.bot.config import BotConfig
from src.agent.agent_manager import AgentManager
from src.agent.agent_scheduler import AgentScheduler


def test_agent_manager_initialization():
    """測試 1：AgentManager 初始化"""
    logger.info("=" * 60)
    logger.info("測試 1：AgentManager 初始化")
    logger.info("=" * 60)

    try:
        config = BotConfig.from_env()
        agent_manager = AgentManager(
            api_key=config.anthropic_api_key,
            model=config.claude_model
        )

        # 檢查是否載入了 3 個 agents
        assert len(agent_manager.agents) == 3, f"應載入 3 個 agents，實際載入了 {len(agent_manager.agents)} 個"

        # 檢查每個 agent 是否存在
        for agent_name in ['arthur', 'max', 'donna']:
            assert agent_name in agent_manager.agents, f"找不到 agent：{agent_name}"
            assert agent_manager.agent_configs.get(agent_name), f"找不到 {agent_name} 的配置"

        logger.info("✅ 測試通過：AgentManager 成功載入所有 agents")
        return agent_manager

    except Exception as e:
        logger.error(f"❌ 測試失敗：{e}")
        raise


def test_agent_name_matching(agent_manager: AgentManager):
    """測試 2：Agent 名稱匹配"""
    logger.info("=" * 60)
    logger.info("測試 2：Agent 名稱匹配")
    logger.info("=" * 60)

    test_cases = [
        ("Arthur 黃金趨勢如何", "arthur"),
        ("arthur 分析一下", "arthur"),
        ("亞瑟 幫我看看", "arthur"),
        ("Max 可以進場嗎", "max"),
        ("max 風險如何", "max"),
        ("麥克斯 停損在哪", "max"),
        ("Donna 帳戶餘額", "donna"),
        ("donna 查詢一下", "donna"),
        ("朵娜 系統狀態", "donna"),
        ("你好", None),  # 不應匹配
        ("今天天氣如何", None),  # 不應匹配
    ]

    try:
        for message, expected in test_cases:
            result = agent_manager.match_agent(message)
            assert result == expected, f"訊息「{message}」應匹配 {expected}，實際匹配 {result}"
            logger.info(f"  ✓ 「{message}」 -> {result or '無匹配'}")

        logger.info("✅ 測試通過：所有名稱匹配測試正確")

    except Exception as e:
        logger.error(f"❌ 測試失敗：{e}")
        raise


def test_memory_operations(agent_manager: AgentManager):
    """測試 3：記憶讀取和追加"""
    logger.info("=" * 60)
    logger.info("測試 3：記憶讀取和追加")
    logger.info("=" * 60)

    try:
        # 測試寫入
        test_content = "測試記憶內容\n這是第一行\n這是第二行\n"
        agent_manager.append_to_daily_log('arthur', test_content)
        logger.info("  ✓ 成功追加內容到 arthur 日誌")

        # 測試讀取
        memory = agent_manager.read_daily_memory('arthur')
        assert test_content in memory, "讀取的記憶應包含寫入的內容"
        logger.info(f"  ✓ 成功讀取 arthur 記憶：{len(memory)} 字元")

        # 測試追加
        additional_content = "這是追加的內容\n"
        agent_manager.append_to_daily_log('arthur', additional_content)
        memory = agent_manager.read_daily_memory('arthur')
        assert additional_content in memory, "讀取的記憶應包含追加的內容"
        logger.info("  ✓ 成功追加額外內容到 arthur 日誌")

        # 測試不存在的記憶
        memory = agent_manager.read_daily_memory('nonexistent_agent')
        assert memory == '', "不存在的 agent 應回傳空字串"
        logger.info("  ✓ 不存在的 agent 正確回傳空記憶")

        logger.info("✅ 測試通過：所有記憶操作正確")

    except Exception as e:
        logger.error(f"❌ 測試失敗：{e}")
        raise


async def test_daily_self_reflection(agent_manager: AgentManager):
    """測試 4：每日自我認知生成"""
    logger.info("=" * 60)
    logger.info("測試 4：每日自我認知生成")
    logger.info("=" * 60)

    try:
        # 初始化 AgentScheduler
        agent_scheduler = AgentScheduler(agent_manager=agent_manager)

        # 為 arthur 生成自我認知
        logger.info("  正在生成 arthur 的自我認知...")
        await agent_scheduler.trigger_self_reflection_now('arthur')

        # 檢查日誌檔案
        log_path = agent_manager.get_daily_log_path('arthur')
        assert log_path.exists(), f"日誌檔案應存在：{log_path}"
        logger.info(f"  ✓ 日誌檔案已生成：{log_path}")

        # 檢查內容
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert '自我認知' in content, "日誌內容應包含「自我認知」"
        assert len(content) > 100, "自我認知內容應超過 100 字元"
        logger.info(f"  ✓ 自我認知內容正確：{len(content)} 字元")

        logger.info("✅ 測試通過：自我認知生成正確")

    except Exception as e:
        logger.error(f"❌ 測試失敗：{e}")
        raise


async def test_message_processing(agent_manager: AgentManager):
    """測試 5：訊息處理流程"""
    logger.info("=" * 60)
    logger.info("測試 5：訊息處理流程")
    logger.info("=" * 60)

    try:
        # 取得 arthur agent
        agent = agent_manager.get_agent('arthur')
        assert agent is not None, "應能取得 arthur agent"

        # 準備測試訊息
        test_message = "請簡單介紹一下你自己"

        # 整合記憶
        daily_memory = agent_manager.read_daily_memory('arthur')
        if daily_memory:
            enhanced_message = f"{test_message}\n\n[本日記憶參考]\n{daily_memory}"
            logger.info(f"  ✓ 已整合記憶：{len(daily_memory)} 字元")
        else:
            enhanced_message = test_message
            logger.info("  ℹ arthur 沒有本日記憶")

        # 處理訊息
        system_prompt = getattr(agent, 'default_system_prompt', None)
        logger.info("  正在處理訊息...")
        response = agent.process_message(enhanced_message, system_prompt=system_prompt)

        assert len(response) > 0, "回應不應為空"
        logger.info(f"  ✓ 收到回應：{len(response)} 字元")
        logger.info(f"  回應內容（前 200 字元）：{response[:200]}...")

        # 記錄互動
        from datetime import datetime
        import pytz
        taiwan_tz = pytz.timezone('Asia/Taipei')
        timestamp = datetime.now(taiwan_tz).strftime('%Y-%m-%d %H:%M:%S')

        interaction_log = f"""
[{timestamp}] 測試用戶: {test_message}
回應: {response}

"""
        agent_manager.append_to_daily_log('arthur', interaction_log)
        logger.info("  ✓ 已記錄互動到日誌")

        logger.info("✅ 測試通過：訊息處理流程正確")

    except Exception as e:
        logger.error(f"❌ 測試失敗：{e}")
        raise


async def main():
    """主函式"""
    logger.info("開始 Agent 系統端到端測試")
    logger.info("=" * 60)

    try:
        # 測試 1：AgentManager 初始化
        agent_manager = test_agent_manager_initialization()

        # 測試 2：Agent 名稱匹配
        test_agent_name_matching(agent_manager)

        # 測試 3：記憶操作
        test_memory_operations(agent_manager)

        # 測試 4：每日自我認知生成
        await test_daily_self_reflection(agent_manager)

        # 測試 5：訊息處理流程
        await test_message_processing(agent_manager)

        logger.info("=" * 60)
        logger.info("🎉 所有測試通過！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("=" * 60)
        logger.error("💥 測試失敗")
        logger.error("=" * 60)
        logger.exception(e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
```

#### 2. 新增使用文檔 `docs/agent_system_usage.md`

**檔案路徑**：`C:\Users\fatfi\works\chip-whisperer\docs\agent_system_usage.md`

**說明**：Agent 系統使用文檔。

**完整內容**：

```markdown
# Agent 系統使用文檔

## 概述

本系統實現了多 Agent 執行緒監聽機制，包含三個 AI Agents：

- **Arthur（亞瑟）**：資深市場分析師，負責技術分析和趨勢研判
- **Max（麥克斯）**：交易執行專家，負責交易策略和風險管理
- **Donna（朵娜）**：專業助理，負責帳戶查詢和任務分派

## 核心功能

### 1. 訊息路由機制

當您在 Telegram 群組中發送訊息時，系統會根據訊息的**前 10 個字元**（忽略大小寫和空白）匹配 Agent 名稱。

**支援的名稱**：
- **Arthur**：`arthur`、`Arthur`、`亞瑟`
- **Max**：`max`、`Max`、`麥克斯`
- **Donna**：`donna`、`Donna`、`朵娜`

**範例**：
```
✅ "Arthur 黃金趨勢如何？" → Arthur 回應
✅ "arthur 分析一下白銀" → Arthur 回應
✅ "亞瑟 幫我看看" → Arthur 回應

✅ "Max 可以進場嗎？" → Max 回應
✅ "max 風險評估" → Max 回應
✅ "麥克斯 停損在哪" → Max 回應

✅ "Donna 帳戶餘額" → Donna 回應
✅ "donna 查詢一下" → Donna 回應
✅ "朵娜 系統狀態" → Donna 回應

❌ "你好" → 無回應（未匹配任何 Agent）
❌ "今天天氣如何" → 無回應
```

### 2. 每日自我認知

每天午夜 00:00（UTC+8），每個 Agent 會自動：

1. 讀取自己的 `persona.md`、`jobs.md`、`routine.md`
2. 使用 Claude 生成約 300 字的繁體中文自我認知
3. 寫入 `logs/yyyymmdd/<agent 名稱>.log`

**日誌結構**：
```
logs/
├── 20260102/
│   ├── arthur.log   # Arthur 的自我認知 + 互動記錄
│   ├── max.log      # Max 的自我認知 + 互動記錄
│   └── donna.log    # Donna 的自我認知 + 互動記錄
├── 20260103/
│   └── ...
```

**手動觸發**（測試用）：
```bash
# 為所有 agents 生成自我認知
python scripts/test_daily_reflection.py all

# 為特定 agent 生成
python scripts/test_daily_reflection.py arthur
python scripts/test_daily_reflection.py max
python scripts/test_daily_reflection.py donna
```

### 3. 記憶參考機制

當 Agent 回答問題時，會自動：

1. 檢查當日日誌檔案（`logs/yyyymmdd/<agent 名稱>.log`）
2. 若存在，將完整內容附加到提示詞作為「本日記憶參考」
3. 回答後，將互動記錄追加到日誌檔案

**範例流程**：
```
用戶："Arthur 黃金趨勢如何？"
↓
系統檢查：logs/20260102/arthur.log 是否存在
↓
若存在：將完整日誌內容附加到提示詞
↓
Arthur 基於記憶和當前問題回答
↓
系統記錄互動到 logs/20260102/arthur.log
```

## 系統架構

### 核心模組

#### AgentManager (`src/agent/agent_manager.py`)

負責管理所有 Agent 實例：

- 載入 Agent 配置檔案（persona、jobs、routine）
- 建立獨立的 system prompt
- 名稱匹配路由
- 記憶讀取和追加
- 日誌路徑管理

**主要方法**：
```python
agent_manager.match_agent(message)          # 匹配 Agent
agent_manager.get_agent(agent_name)         # 取得 Agent 實例
agent_manager.read_daily_memory(agent_name) # 讀取記憶
agent_manager.append_to_daily_log(...)      # 追加日誌
agent_manager.get_daily_log_path(...)       # 取得日誌路徑
```

#### AgentScheduler (`src/agent/agent_scheduler.py`)

負責管理定期任務：

- 每日自我認知生成（00:00 UTC+8）
- 使用 APScheduler 的 AsyncIOScheduler
- 支援手動觸發（測試用）

**主要方法**：
```python
agent_scheduler.start()                              # 啟動調度器
agent_scheduler.stop()                               # 停止調度器
agent_scheduler.trigger_self_reflection_now(agent)   # 手動觸發
```

### 訊息處理流程

```
Telegram 訊息
    ↓
檢查權限（群組白名單 + 管理員）
    ↓
匹配 Agent 名稱（前 10 個字元）
    ↓
取得 Agent 實例
    ↓
讀取當日記憶
    ↓
整合記憶到提示詞
    ↓
調用 Claude API 處理
    ↓
回傳結果給用戶
    ↓
記錄互動到日誌
```

## 測試與驗證

### 端到端測試

執行完整的系統測試：

```bash
python scripts/test_agent_system.py
```

測試項目：
1. AgentManager 初始化
2. Agent 名稱匹配
3. 記憶讀取和追加
4. 每日自我認知生成
5. 訊息處理流程

### 單獨測試

#### 測試自我認知生成
```bash
python scripts/test_daily_reflection.py all
```

#### 測試 Bot 啟動
```bash
python scripts/run_bot.py
```

檢查日誌中是否顯示：
- `AgentManager 初始化完成，已載入 3 個 agents`
- `AgentScheduler 已啟動`
- `已設定 arthur 的每日自我認知任務（每天 00:00 UTC+8）`

## 日誌和除錯

### 系統日誌

位置：`logs/YYYY-MM-DD.log`

包含所有系統運行日誌（bot 啟動、訊息處理、錯誤等）

### Agent 日誌

位置：`logs/yyyymmdd/<agent 名稱>.log`

包含：
- 每日自我認知（00:00 生成）
- 所有互動記錄（時間戳記 + 問題 + 回應）

**範例**：
```
============================================================
2026年01月02日 自我認知
============================================================

今天是新的一天，我是 Arthur，團隊中的資深市場分析師...

============================================================

[2026-01-02 10:30:15] 用戶 user123 (12345): Arthur 黃金趨勢如何？
回應: 讓我為你分析一下黃金目前的趨勢...

[2026-01-02 14:20:30] 用戶 user456 (67890): arthur 白銀支撐在哪
回應: 根據 Volume Profile 的分布，白銀目前的關鍵支撐位在...
```

### 除錯模式

啟用除錯模式以查看詳細日誌：

```bash
# 設定環境變數
export DEBUG=true

# 或在 .env 檔案中
DEBUG=true

# 啟動 bot
python scripts/run_bot.py
```

## 常見問題

### Q1：訊息沒有得到回應？

**檢查清單**：
- ✓ 訊息是否在允許的群組中？
- ✓ 發送者是否為群組管理員？
- ✓ 訊息前 10 個字元是否包含 Agent 名稱？
- ✓ 名稱拼寫是否正確？（大小寫不敏感）

**範例**：
```
❌ "黃金趨勢如何？" → 沒有 Agent 名稱
✅ "Arthur 黃金趨勢如何？" → 正確

❌ "Artur 分析一下" → 拼寫錯誤
✅ "Arthur 分析一下" → 正確
```

### Q2：如何查看 Agent 的記憶？

直接開啟對應的日誌檔案：

```bash
# 今天的日期（UTC+8）
cat logs/20260102/arthur.log
cat logs/20260102/max.log
cat logs/20260102/donna.log
```

### Q3：記憶會跨日保留嗎？

**不會**。每個 Agent 的記憶只保留在當日的日誌檔案中。

- 新的一天（00:00 UTC+8）會建立新的日誌檔案
- 自我認知會重新生成
- 互動記錄從零開始累積

舊的日誌檔案會保留在歷史目錄中（如 `logs/20260101/`），但不會被載入到記憶中。

### Q4：如何修改 Agent 的人格或任務？

編輯對應的配置檔案：

```bash
# Arthur 的配置
agents/analysts/Arthur/persona.md   # 人格設定
agents/analysts/Arthur/jobs.md      # 任務職責
agents/analysts/Arthur/routine.md   # 定期任務

# Max 的配置
agents/traders/Max/persona.md
agents/traders/Max/jobs.md
agents/traders/Max/routine.md

# Donna 的配置
agents/assistants/Donna/persona.md
agents/assistants/Donna/jobs.md
agents/assistants/Donna/routine.md
```

修改後**重啟 bot** 即可生效：
```bash
# 停止 bot（Ctrl+C）
# 重新啟動
python scripts/run_bot.py
```

### Q5：自我認知生成失敗怎麼辦？

**檢查**：
- ✓ Anthropic API Key 是否正確？
- ✓ 網路連線是否正常？
- ✓ 日誌檔案權限是否正確？

**手動觸發測試**：
```bash
python scripts/test_daily_reflection.py arthur
```

查看日誌中的錯誤訊息：
```bash
tail -f logs/2026-01-02.log
```

### Q6：記憶太長會影響效能嗎？

**可能會**。目前系統會將整個日誌檔案內容附加到提示詞中。

**緩解策略**（未來改進）：
- 限制記憶長度（僅保留最近 N 條互動）
- 使用摘要機制壓縮歷史記憶
- 智能選擇相關記憶

**當前建議**：
- 每日記憶會在午夜重置，通常不會過長
- 若單日互動非常頻繁，可能需要監控 token 使用量

## 技術細節

### 時區處理

系統使用 **Asia/Taipei (UTC+8)** 時區：

```python
import pytz
taiwan_tz = pytz.timezone('Asia/Taipei')
now = datetime.now(taiwan_tz)
```

所有時間戳記和日誌檔名都基於 UTC+8。

### APScheduler 整合

使用 `AsyncIOScheduler` 管理定期任務：

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone='Asia/Taipei')
scheduler.add_job(
    func=generate_self_reflection,
    trigger=CronTrigger(hour=0, minute=0),
    id='agent_daily_reflection'
)
scheduler.start()
```

### 記憶整合範例

```python
# 原始訊息
user_message = "Arthur 黃金趨勢如何？"

# 讀取記憶
daily_memory = agent_manager.read_daily_memory('arthur')

# 整合記憶
if daily_memory:
    enhanced_message = f"{user_message}\n\n[本日記憶參考]\n{daily_memory}"
else:
    enhanced_message = user_message

# 處理訊息
response = agent.process_message(enhanced_message, system_prompt=system_prompt)
```

## 維護和監控

### 日誌清理

系統日誌會自動輪換和清理（保留 30 天）：

```python
logger.add(
    "logs/{time:YYYY-MM-DD}.log",
    rotation="00:00",      # 每天午夜輪換
    retention="30 days"    # 保留 30 天
)
```

Agent 日誌需要手動清理：

```bash
# 刪除 30 天前的 Agent 日誌
find logs/ -type d -name "202*" -mtime +30 -exec rm -rf {} \;
```

### 效能監控

關注以下指標：

- **API 調用次數**：每次訊息處理都會調用 Claude API
- **日誌檔案大小**：記憶過長可能影響效能
- **回應時間**：正常應在 5-10 秒內

### 錯誤追蹤

所有錯誤都會記錄到系統日誌：

```bash
# 即時查看錯誤
tail -f logs/2026-01-02.log | grep ERROR

# 搜尋特定錯誤
grep "AgentManager" logs/2026-01-02.log
grep "處理訊息時發生錯誤" logs/2026-01-02.log
```

---

**版本**：1.0
**最後更新**：2026-01-02
**維護者**：Claude Code
```

### 成功標準

#### 自動化驗證：

- [ ] `scripts/test_agent_system.py` 檔案建立成功
- [ ] `docs/agent_system_usage.md` 檔案建立成功
- [ ] Python 語法檢查通過：`python -m py_compile scripts/test_agent_system.py`
- [ ] 端到端測試執行成功：`python scripts/test_agent_system.py`
- [ ] 所有測試項目通過（共 5 項）

#### 手動驗證：

- [ ] 在 Telegram 群組完整測試一次對話流程（發送訊息給 Arthur、Max、Donna）
- [ ] 檢查日誌檔案中的互動記錄格式正確
- [ ] 第二次向同一 Agent 發送訊息時，確認記憶已整合（回應中參考前次對話）
- [ ] 查看使用文檔，確認內容完整且清晰
- [ ] 使用文檔中的範例都能正常執行

**實作注意事項**：完成此階段後，整個專案即完成。

---

## 測試策略

### 單元測試

**測試範圍**：
- `AgentManager` 的名稱匹配邏輯
- 記憶讀取和追加功能
- 日誌路徑生成

**測試方法**：
使用 `scripts/test_agent_system.py` 中的獨立測試函數

### 整合測試

**測試範圍**：
- Bot 啟動和 AgentManager 初始化
- 訊息處理流程（路由 → 記憶整合 → 處理 → 記錄）
- 定時任務觸發

**測試方法**：
1. 啟動 bot：`python scripts/run_bot.py`
2. 在 Telegram 群組發送測試訊息
3. 檢查日誌檔案和回應

### 端到端測試

**測試流程**：
```bash
# 1. 生成自我認知
python scripts/test_daily_reflection.py all

# 2. 檢查日誌檔案
ls -la logs/20260102/

# 3. 執行系統測試
python scripts/test_agent_system.py

# 4. 啟動 bot
python scripts/run_bot.py

# 5. Telegram 測試
# 在群組發送：「Arthur 黃金趨勢如何？」
# 在群組發送：「Max 風險評估」
# 在群組發送：「Donna 帳戶餘額」

# 6. 檢查互動記錄
cat logs/20260102/arthur.log
cat logs/20260102/max.log
cat logs/20260102/donna.log
```

### 效能測試

**測試項目**：
- 冷啟動時間（Bot 啟動到準備就緒）
- 訊息回應時間（收到訊息到回傳結果）
- 記憶載入時間（讀取大型日誌檔案）

**預期指標**：
- 冷啟動：< 10 秒
- 訊息回應：< 10 秒（不含 API 延遲）
- 記憶載入：< 1 秒（日誌檔案 < 100KB）

### 錯誤處理測試

**測試場景**：
- 配置檔案缺失或格式錯誤
- Anthropic API 錯誤或超時
- 日誌檔案權限錯誤
- 訊息格式異常

**驗證方法**：
檢查錯誤是否被正確捕獲並記錄到日誌，且不會導致 bot 崩潰。

---

## 效能考量

### API 調用優化

**問題**：每次訊息處理都會調用 Claude API

**優化策略**（未來）：
- 實現對話歷史快取
- 批次處理多個訊息
- 使用較小的模型處理簡單查詢

### 記憶管理

**問題**：完整日誌檔案可能很大，影響 token 使用

**當前策略**：
- 每日重置記憶（午夜建立新檔案）
- 使用文字檔案而非資料庫（簡化管理）

**未來優化**：
- 限制記憶長度（保留最近 N 條）
- 使用向量資料庫進行語意搜尋
- 智能摘要歷史記憶

### 並行處理

**當前架構**：
- 使用 async/await 而非傳統執行緒
- 所有 handlers 都是非阻塞的
- APScheduler 使用 AsyncIOScheduler

**優勢**：
- 更好的資源利用率
- 更容易管理
- 與 python-telegram-bot 完美整合

---

## 遷移注意事項

### 從舊系統遷移

如果您之前使用單一 Agent 模式，遷移步驟：

1. **備份現有配置**：
   ```bash
   cp -r agents agents.backup
   ```

2. **更新代碼**：
   按照本計劃逐階段實作

3. **測試新系統**：
   ```bash
   python scripts/test_agent_system.py
   ```

4. **平滑切換**：
   - 可以先在測試環境驗證
   - 確認無誤後再部署到生產環境

### 設定檔案無變更

本實作**不需要修改環境變數**或新增配置項目，完全使用現有的：
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_GROUP_IDS`
- `ANTHROPIC_API_KEY`
- `CLAUDE_MODEL`
- `DEBUG`

---

## 已知限制

### 1. 名稱匹配限制

- 僅檢查訊息前 10 個字元
- 若訊息前面有大量空白或符號可能影響匹配
- 不支援模糊匹配（必須精確包含名稱）

### 2. 記憶限制

- 每日記憶會在午夜重置，無法跨日保留
- 完整載入日誌檔案，可能受 token 限制影響
- 不支援選擇性記憶載入

### 3. 並行限制

- 同一 Agent 同時處理多個訊息時，可能會有對話歷史混淆
- 目前未實現訊息佇列或鎖定機制

### 4. 錯誤恢復

- 自我認知生成失敗不會自動重試
- 需要手動觸發或等待隔天

---

## 未來改進方向

### 短期（1-2 週）

- [ ] 實現訊息佇列，避免並行衝突
- [ ] 新增記憶摘要機制，減少 token 使用
- [ ] 實現自我認知生成失敗的重試機制
- [ ] 新增更多測試案例

### 中期（1-2 月）

- [ ] 實現 routine.md 中定義的其他定期任務
- [ ] 新增 Agent 間的協作通訊機制
- [ ] 實現智能任務轉介（Donna → Arthur/Max）
- [ ] 新增效能監控和儀表板

### 長期（3-6 月）

- [ ] 使用向量資料庫實現長期記憶
- [ ] 實現跨日記憶參考（基於相似度搜尋）
- [ ] 新增更多 Agents 和角色
- [ ] 實現 Agent 自我學習和改進機制

---

## 參考資料

### 相關文檔

- 研究文檔：`thoughts/shared/research/2026-01-02-agent-telegram-thread-listener-design.md`
- 使用文檔：`docs/agent_system_usage.md`

### 相關代碼

- Bot 主程式：`src/bot/telegram_bot.py`
- 訊息處理器：`src/bot/handlers.py`
- Agent 類別：`src/agent/agent.py`
- Agent 管理器：`src/agent/agent_manager.py`（新增）
- Agent 調度器：`src/agent/agent_scheduler.py`（新增）
- 爬蟲調度器範例：`src/crawler/scheduler.py`

### Agent 配置

- Arthur：`agents/analysts/Arthur/*.md`
- Max：`agents/traders/Max/*.md`
- Donna：`agents/assistants/Donna/*.md`

---

**計劃版本**：1.0
**建立日期**：2026-01-02
**計劃者**：Claude Code (implementation-planner)
**預估完成時間**：4-6 小時（分 4 個階段）
