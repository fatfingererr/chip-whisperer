---
title: Agent Telegram 執行緒監聽器設計研究
date: 2026-01-02
author: Claude Code (codebase-researcher)
tags: [research, agents, telegram, threading, design]
status: completed
related_files:
  - agents/analysts/Arthur/persona.md
  - agents/analysts/Arthur/jobs.md
  - agents/analysts/Arthur/routine.md
  - agents/traders/Max/persona.md
  - agents/traders/Max/jobs.md
  - agents/traders/Max/routine.md
  - agents/assistants/Donna/persona.md
  - agents/assistants/Donna/jobs.md
  - agents/assistants/Donna/routine.md
  - src/bot/telegram_bot.py
  - src/bot/handlers.py
  - src/bot/config.py
  - src/agent/agent.py
  - scripts/run_bot.py
  - .env.example
last_updated: 2026-01-02T14:30:00+08:00
last_updated_by: Claude Code
---

# Agent Telegram 執行緒監聽器設計研究

## 研究問題

分析如何在 `run_bot` 啟動時，讓 `agents` 目錄下三個角色（analysts、traders、assistants）的所有 agent 各起一個執行緒監聽 Telegram 訊息，並實現以下功能：

1. **訊息接受機制**：當收到 admin 的訊息，且訊息前 10 個字元（無論大小寫、空白分隔）包含自己的名字就接受，然後用 Claude Agent SDK 去回答
2. **每日自我認知記錄**：每個 agent 在 UTC+8 新的一天時，在 `logs/yyyymmdd/` 底下建立 `<agent 全小寫名字>.log`，並讀取自己的 `job.md`、`persona.md`、`routine.md`，輸出 300 中文字的自我認知
3. **記憶參考機制**：若已有當日 log 檔，從 Telegram 收到的問題需加上該 log 全文作為本日記憶參考來回答

## 摘要

經過對代碼庫的深入分析，目前系統具備以下基礎設施：

1. **Agents 結構**：已建立三個角色目錄（analysts、traders、assistants），每個角色下有一個 agent（Arthur、Max、Donna），每個 agent 都有完整的 `persona.md`、`jobs.md`、`routine.md` 配置檔
2. **Telegram Bot 基礎**：已有基本的 Telegram bot 框架，使用 `python-telegram-bot` 庫（v20.0+），支援群組模式和管理員權限驗證
3. **Claude Agent SDK**：已整合 Anthropic Claude SDK（v0.18.0+），使用 `anthropic.Anthropic` 客戶端和工具調用機制
4. **非同步支援**：系統已使用 `async/await` 架構，具備 `aiohttp` 和 `AsyncIOScheduler` 支援
5. **日誌系統**：使用 `loguru` 管理日誌，目前日誌輸出到 `logs/YYYY-MM-DD.log`

然而，**目前系統尚未實現**多 agent 執行緒監聽和個別 agent 的自我認知記錄機制。現有的 bot 僅使用單一 `MT5Agent` 實例處理所有訊息，沒有依照 agent 名稱分派或多執行緒架構。

## 詳細研究結果

### 1. 現有 Agents 目錄結構

**LOCATOR MODE：找到 agents 的組織結構**

```
agents/
├── analysts/
│   └── Arthur/
│       ├── persona.md      # 人格設定
│       ├── jobs.md         # 任務職責定義
│       └── routine.md      # 定期任務排程
├── traders/
│   └── Max/
│       ├── persona.md
│       ├── jobs.md
│       └── routine.md
└── assistants/
    └── Donna/
        ├── persona.md
        ├── jobs.md
        └── routine.md
```

**檔案位置**：
- `C:\Users\fatfi\works\chip-whisperer\agents\analysts\Arthur\`
- `C:\Users\fatfi\works\chip-whisperer\agents\traders\Max\`
- `C:\Users\fatfi\works\chip-whisperer\agents\assistants\Donna\`

**三個角色（Roles）**：
1. **analysts**（分析師）：Arthur 負責市場分析、技術指標、趨勢研判
2. **traders**（交易員）：Max 負責交易策略、進出場執行、風險管理
3. **assistants**（助理）：Donna 負責帳戶查詢、一般問答、任務分派

每個 agent 的配置檔案格式：
- **persona.md**：包含基本資訊、人格特質、說話風格、口頭禪、情緒反應模式、專業能力、背景故事
- **jobs.md**：包含角色定位、任務觸發條件、主要任務清單、回應優先級、與其他角色的協作、錯誤處理
- **routine.md**：包含定期任務清單（使用 cron 格式的 schedule）、任務執行腳本路徑、報告模板、手動觸發指令

### 2. 現有 Bot 啟動邏輯

**ANALYZER MODE：理解 run_bot 的啟動流程**

**主啟動腳本**：`C:\Users\fatfi\works\chip-whisperer\scripts\run_bot.py`

```python
def main():
    # 1. 載入設定（從環境變數）
    config = BotConfig.from_env()

    # 2. 設定日誌系統
    setup_logging(debug=config.debug)

    # 3. 建立並啟動 Bot
    bot = create_bot(config)

    # 4. 啟動 Bot（polling 模式）
    bot.run()
```

**Bot 建立流程**（`src/bot/telegram_bot.py`）：

```python
class TelegramBot:
    def __init__(self, config: BotConfig):
        # 1. 建立 Telegram Application
        self.application = Application.builder().token(config.telegram_bot_token).build()

        # 2. 註冊處理器
        self._register_handlers()

        # 3. 初始化爬蟲調度器（使用 AsyncIOScheduler）
        self.crawler_scheduler = CrawlerScheduler(config, self.application)
```

**關鍵觀察**：
- Bot 使用 `Application.run_polling()` 進入主事件循環
- 已有 `AsyncIOScheduler` 用於爬蟲定時任務
- 回調機制：`post_init` 在啟動後執行，`post_shutdown` 在關閉前執行
- 目前**沒有**為個別 agent 建立執行緒或任務的機制

### 3. 現有 Telegram 整合方式

**ANALYZER MODE：分析訊息處理流程**

**訊息處理器註冊**（`src/bot/telegram_bot.py:74-97`）：

```python
def _register_handlers(self):
    # 指令處理器
    self.application.add_handler(CommandHandler("start", start_command))
    self.application.add_handler(CommandHandler("help", help_command))
    self.application.add_handler(CommandHandler("status", status_command))
    self.application.add_handler(CommandHandler("crawl_now", crawl_now_command))

    # 訊息處理器：只接收群組中的非指令文字訊息
    self.application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            handle_message
        )
    )

    # 錯誤處理器
    self.application.add_error_handler(handle_error)
```

**訊息處理邏輯**（`src/bot/handlers.py:232-318`）：

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. 忽略私聊訊息
    if chat.type == Chat.PRIVATE:
        return

    # 2. 檢查群組白名單和管理員權限
    if not await _check_group_admin(update, context, config):
        return

    # 3. 使用單一 MT5Agent 處理
    agent = context.bot_data.get('agent')
    if not agent:
        agent = MT5Agent(api_key=config.anthropic_api_key, model=config.claude_model)
        context.bot_data['agent'] = agent

    # 4. 處理訊息並回應
    response = agent.process_message(user_message)
    await update.message.reply_text(response)
```

**權限檢查機制**（`src/bot/handlers.py:343-388`）：

```python
async def _check_group_admin(update, context, config) -> bool:
    # 1. 檢查群組是否在白名單
    if not config.is_allowed_group(chat.id):
        return False

    # 2. 檢查是否為管理員
    member = await context.bot.get_chat_member(chat.id, user.id)
    is_admin = member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    return is_admin
```

**關鍵發現**：
- 目前僅有**單一訊息處理器** `handle_message`
- 使用**共用的 MT5Agent 實例**處理所有訊息
- 已實現 **admin 權限驗證**機制
- **尚未實現**依照 agent 名稱分派訊息的邏輯

### 4. 現有 Claude Agent SDK 使用情況

**ANALYZER MODE：檢視 Claude SDK 整合**

**Agent 類別**（`src/agent/agent.py`）：

```python
class MT5Agent:
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.conversation_history = []

    def process_message(self, user_message: str, system_prompt: str = None) -> str:
        # 1. 建立訊息
        messages = [{"role": "user", "content": user_message}]

        # 2. 呼叫 Claude API（支援工具調用循環）
        while turn_count < max_turns:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16384,
                system=system_prompt,
                tools=TOOLS,
                messages=messages
            )

            # 3. 處理工具調用
            if response.stop_reason == "tool_use":
                # 執行工具並繼續對話
                ...
            else:
                # 回傳文字回應
                return self._extract_text_response(response)
```

**SDK 版本**（`requirements.txt:27`）：
```
anthropic>=0.18.0
```

**關鍵觀察**：
- 使用 **Anthropic Python SDK**（非 Agent SDK）
- 使用 **`messages.create()`** API 和工具調用（tool use）機制
- 支援 **多輪對話**和 **工具執行循環**
- 每個 agent 實例可以有**獨立的 system_prompt** 和對話歷史

### 5. Agent 配置檔案格式

**PATTERN MODE：分析 persona、jobs、routine 的內容結構**

#### 5.1 persona.md 格式

**Arthur 範例**（`agents/analysts/Arthur/persona.md`）：

```markdown
# Arthur（亞瑟）- 分析師人格設定

## 基本資訊
| 欄位 | 內容 |
|------|------|
| 姓名 | Arthur（亞瑟） |
| 角色 | 資深市場分析師 |
| 性別 | 男 |
| 人格類型 | INTJ（策略家） |

## 人格特質
### 核心性格
- **專業嚴謹**：對數據和分析有極高的精準度要求
- ...

### 說話風格
- 使用專業但不艱澀的語言
- ...

### 口頭禪與慣用語
```yaml
greeting:
  - "你好，有什麼需要分析的嗎？"
  ...
```

## 專業能力
### 核心技能
- **量價分析**：專精 Volume Profile、VPPA、成交量分析
- ...

## 互動指南
### 回應格式偏好
...
```

**共同特徵**：
- 使用 Markdown 格式
- 包含 YAML 內嵌區塊定義對話模板
- 詳細的人格描述和說話風格
- 300-500 行的完整人格設定

#### 5.2 jobs.md 格式

**Max 範例**（`agents/traders/Max/jobs.md`）：

```markdown
# Max（麥克斯）- 任務職責定義

## 角色定位
Max 是團隊中的**交易執行專家**...

## 任務觸發條件
### 主要關鍵字
```yaml
primary_keywords:
  trading_action:
    - "進場"
    - "出場"
    ...
```

## 主要任務清單
### 1. 交易機會評估
```yaml
task: trade_opportunity_assessment
triggers:
  - "可以進場嗎"
  ...
actions:
  - 取得 Arthur 的分析結果
  ...
output_format: |
  ## 交易機會評估
  ...
```

## 與其他角色的協作
...
```

**關鍵元素**：
- **關鍵字列表**：用於判斷是否應接手處理該訊息
- **任務定義**：包含 triggers、actions、output_format
- **協作規則**：定義與其他 agent 的轉介機制

#### 5.3 routine.md 格式

**Donna 範例**（`agents/assistants/Donna/routine.md`）：

```markdown
# Donna（朵娜）- 定期任務排程

## 定期任務清單
### 1. 每日早安問候
```yaml
task_id: daily_greeting
schedule: "0 8 * * 1-5"  # 週一至週五 08:00
execution:
  script: "scripts/routines/donna_daily_greeting.py"
  steps:
    - name: "取得帳戶概況"
      action: "fetch_account_summary"
    ...
```

## 手動觸發任務
```bash
python scripts/routines/donna_daily_greeting.py --manual
```
```

**排程格式**：
- 使用 **Cron 表達式**（與 APScheduler 相容）
- 定義執行腳本路徑（目前這些腳本**尚未建立**）
- 包含任務步驟和輸出模板

### 6. 現有日誌管理機制

**ANALYZER MODE：檢視日誌系統**

**日誌設定**（`scripts/run_bot.py:30-64`）：

```python
def setup_logging(debug: bool = False):
    # 1. 移除預設處理器
    logger.remove()

    # 2. 控制台輸出
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | ...",
        level=log_level,
        colorize=True
    )

    # 3. 檔案輸出
    logger.add(
        "logs/{time:YYYY-MM-DD}.log",
        rotation="00:00",  # 每天午夜輪換
        retention="30 days",
        level=log_level,
        encoding="utf-8"
    )
```

**當前日誌結構**：
```
logs/
└── 2026-01-02.log  # 所有 bot 活動的統一日誌
```

**所需的日誌結構**（根據需求）：
```
logs/
└── 20260102/       # UTC+8 日期目錄
    ├── arthur.log  # Arthur 的自我認知 + 互動記錄
    ├── max.log     # Max 的自我認知 + 互動記錄
    └── donna.log   # Donna 的自我認知 + 互動記錄
```

**時區處理**：
- 目前 bot 已有台灣時區處理範例（`telegram_bot.py:126`）：
  ```python
  import pytz
  taiwan_tz = pytz.timezone('Asia/Taipei')
  now = datetime.now(taiwan_tz)
  ```

### 7. 相關配置檔案

**DOCUMENTATION MODE：環境變數和設定**

**環境變數配置**（`.env.example`）：

```bash
# Telegram Bot 設定
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_GROUP_IDS=-1001234567890  # 允許的群組 ID（逗號分隔）

# Claude API 設定
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
CLAUDE_MODEL=claude-sonnet-4-5-20250929  # 可選

# 除錯模式
DEBUG=false
```

**Bot 設定類別**（`src/bot/config.py`）：

```python
@dataclass
class BotConfig:
    telegram_bot_token: str
    telegram_group_ids: List[int]  # 允許的群組 ID 清單
    anthropic_api_key: str
    claude_model: str
    debug: bool

    @classmethod
    def from_env(cls) -> 'BotConfig':
        # 從環境變數載入設定
        ...

    def is_allowed_group(self, chat_id: int) -> bool:
        # 檢查群組是否在允許清單中
        return chat_id in self.telegram_group_ids
```

**關鍵發現**：
- **群組白名單**：已支援多個群組 ID
- **Admin 驗證**：已在 `_check_group_admin()` 實現
- **尚未定義** agent 特定的配置（如 admin user IDs）

### 8. 現有 Threading/Async 處理機制

**PATTERN MODE：檢視並行處理架構**

**Async 架構**：
- Telegram bot 使用 **`async/await`** 架構（`python-telegram-bot` v20+）
- 所有 handler 都是 `async` 函數
- 使用 `Application.run_polling()` 啟動事件循環

**APScheduler 使用範例**（`src/crawler/scheduler.py`）：

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

class CrawlerScheduler:
    def __init__(self, config, telegram_app):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        # 新增定時任務
        self.scheduler.add_job(
            self._crawl_and_notify,
            trigger=IntervalTrigger(minutes=interval),
            id='news_crawler',
            replace_existing=True
        )
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()
```

**Threading 支援**：
- `requirements.txt` 包含 `aiohttp>=3.9.0` 用於非同步 HTTP
- Python 標準庫 `threading` 和 `asyncio` 可用
- 未發現現有的執行緒池或背景任務管理

**關鍵觀察**：
- 系統已使用 **AsyncIOScheduler**，可用於實現 agent 的定期任務
- 可以為每個 agent 建立**獨立的 async task** 而非傳統執行緒
- Telegram bot 的事件循環可以整合多個並行任務

## 架構分析：如何實現需求

### 需求 1：訊息接受機制

**當前問題**：
- 單一 `handle_message()` 處理所有訊息
- 沒有依照 agent 名稱分派的邏輯

**實現方案**：
1. **訊息路由器**：修改 `handle_message()` 加入名稱匹配邏輯
   ```python
   async def handle_message(update, context):
       message_text = update.message.text

       # 提取前 10 個字元（忽略大小寫和空白）
       prefix = ''.join(message_text[:10].split()).lower()

       # 檢查匹配的 agent
       agent_name = None
       if 'arthur' in prefix or '亞瑟' in prefix:
           agent_name = 'arthur'
       elif 'max' in prefix or '麥克斯' in prefix:
           agent_name = 'max'
       elif 'donna' in prefix or '朵娜' in prefix:
           agent_name = 'donna'

       if agent_name:
           # 獲取對應的 agent 實例
           agent_instance = context.bot_data.get(f'agent_{agent_name}')
           # 處理訊息
           ...
   ```

2. **Agent 實例管理**：在 bot 初始化時為每個 agent 建立獨立實例
   ```python
   class TelegramBot:
       def __init__(self, config):
           # 為每個 agent 建立實例
           self.agents = {
               'arthur': self._create_agent('arthur'),
               'max': self._create_agent('max'),
               'donna': self._create_agent('donna')
           }

       def _create_agent(self, name):
           # 讀取 persona.md、jobs.md 建立 system prompt
           system_prompt = self._build_system_prompt(name)
           return MT5Agent(
               api_key=self.config.anthropic_api_key,
               model=self.config.claude_model
           )
   ```

### 需求 2：每日自我認知記錄

**實現方案**：
1. **日期檢查任務**：使用 APScheduler 在每天 00:00 (UTC+8) 觸發
   ```python
   def start(self):
       # 為每個 agent 設定每日任務
       for agent_name in ['arthur', 'max', 'donna']:
           self.scheduler.add_job(
               self._daily_self_reflection,
               args=[agent_name],
               trigger=CronTrigger(hour=0, minute=0, timezone='Asia/Taipei'),
               id=f'{agent_name}_daily_reflection'
           )
   ```

2. **自我認知生成**：
   ```python
   async def _daily_self_reflection(self, agent_name):
       # 1. 讀取配置檔案
       persona = read_file(f'agents/{role}/{agent_name}/persona.md')
       jobs = read_file(f'agents/{role}/{agent_name}/jobs.md')
       routine = read_file(f'agents/{role}/{agent_name}/routine.md')

       # 2. 建立 prompt
       prompt = f"""
       請根據以下資訊，用 300 字繁體中文撰寫你的自我認知：

       你的人格設定：
       {persona}

       你的任務職責：
       {jobs}

       你的定期任務：
       {routine}

       今天是 {date}，請描述你對自己角色的理解、今日的工作重點和心態。
       """

       # 3. 呼叫 Claude 生成
       agent = self.agents[agent_name]
       reflection = agent.process_message(prompt)

       # 4. 寫入日誌
       log_path = f'logs/{yyyymmdd}/{agent_name}.log'
       write_log(log_path, f"=== {date} 自我認知 ===\n{reflection}\n\n")
   ```

### 需求 3：記憶參考機制

**實現方案**：
1. **檢查當日 log 檔**：
   ```python
   async def handle_agent_message(self, agent_name, user_message):
       # 1. 檢查當日 log
       today = datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y%m%d')
       log_path = f'logs/{today}/{agent_name}.log'

       daily_memory = ""
       if os.path.exists(log_path):
           with open(log_path, 'r', encoding='utf-8') as f:
               daily_memory = f.read()

       # 2. 將記憶加入訊息
       if daily_memory:
           enhanced_message = f"{user_message}\n\n[本日記憶參考]\n{daily_memory}"
       else:
           enhanced_message = user_message

       # 3. 處理訊息
       agent = self.agents[agent_name]
       response = agent.process_message(enhanced_message)

       # 4. 記錄互動到 log
       append_log(log_path, f"\n[{timestamp}] 用戶: {user_message}\n回應: {response}\n")
   ```

## 程式碼參考

### 關鍵檔案位置和行號

1. **Bot 啟動入口**：`C:\Users\fatfi\works\chip-whisperer\scripts\run_bot.py:67-92`
   - 主函數負責載入設定、初始化並啟動 bot

2. **Bot 類別定義**：`C:\Users\fatfi\works\chip-whisperer\src\bot\telegram_bot.py:33-243`
   - `TelegramBot.__init__()` - 初始化 bot 和處理器（40-72）
   - `TelegramBot._register_handlers()` - 註冊訊息處理器（74-97）
   - `TelegramBot._post_init()` - Bot 啟動後回調（99-117）

3. **訊息處理邏輯**：`C:\Users\fatfi\works\chip-whisperer\src\bot\handlers.py:232-318`
   - `handle_message()` - 主訊息處理函數
   - `_check_group_admin()` - 管理員權限檢查（343-388）

4. **Claude Agent**：`C:\Users\fatfi\works\chip-whisperer\src\agent\agent.py:17-200`
   - `MT5Agent.process_message()` - 處理訊息的主方法（51-177）

5. **APScheduler 使用範例**：`C:\Users\fatfi\works\chip-whisperer\src\crawler\scheduler.py:18-133`
   - `CrawlerScheduler` 展示如何整合定時任務到 Telegram bot

6. **Agent 配置檔案**：
   - Arthur: `C:\Users\fatfi\works\chip-whisperer\agents\analysts\Arthur\*.md`
   - Max: `C:\Users\fatfi\works\chip-whisperer\agents\traders\Max\*.md`
   - Donna: `C:\Users\fatfi\works\chip-whisperer\agents\assistants\Donna\*.md`

### 配置檔案組織

**agents 目錄映射**：
```python
AGENT_ROLES = {
    'arthur': 'analysts',
    'max': 'traders',
    'donna': 'assistants'
}

def get_agent_path(agent_name: str, file_type: str) -> str:
    """
    取得 agent 配置檔案路徑

    Args:
        agent_name: 'arthur', 'max', 或 'donna'
        file_type: 'persona', 'jobs', 或 'routine'

    Returns:
        完整檔案路徑
    """
    role = AGENT_ROLES[agent_name.lower()]
    agent_name_cap = agent_name.capitalize()
    return f'agents/{role}/{agent_name_cap}/{file_type}.md'
```

## 歷史脈絡

### 現有設計決策

1. **群組模式優先**：Bot 設計為只在群組中運作，忽略私聊（`handlers.py:246`）
2. **管理員限制**：只響應群組管理員的訊息（`handlers.py:265`）
3. **單一 Agent 模式**：目前使用共用的 `MT5Agent` 實例
4. **工具導向**：Agent 透過工具調用（tool use）執行 MT5 操作
5. **非同步優先**：全面使用 async/await 架構

### 系統演進軌跡

1. **初期**：基本 MT5 連線和資料查詢
2. **Bot 整合**：加入 Telegram bot 和 Claude Agent SDK
3. **爬蟲功能**：整合定時新聞爬蟲（使用 APScheduler）
4. **Agent 人格化**（當前階段）：建立 persona/jobs/routine 配置檔，但尚未實現多 agent 架構

## 相關研究

### Agent 設計模式

**三個 agent 的分工**（基於 jobs.md 分析）：

1. **Arthur（分析師）**：
   - 關鍵字：分析、研究、Volume Profile、技術指標、趨勢、支撐壓力
   - 輸出：分析報告、指標計算結果
   - 協作：向 Max 提供分析結果

2. **Max（交易員）**：
   - 關鍵字：進場、出場、停損、停利、倉位、策略、風險
   - 輸出：交易建議、風險評估
   - 協作：依賴 Arthur 的分析，向 Donna 要求帳戶資訊

3. **Donna（助理）**：
   - 關鍵字：帳戶、餘額、系統、狀態、幫忙、查詢
   - 輸出：帳戶資訊、系統狀態、任務轉介
   - 協作：預設處理者，負責轉介給 Arthur 或 Max

**角色互動流程**：
```
用戶問題
    ↓
Donna（預設接收）
    ├→ 技術分析？ → Arthur → 分析結果
    ├→ 交易建議？ → Max（參考 Arthur 分析）→ 交易計畫
    └→ 一般查詢？ → Donna 直接回答
```

### 定期任務規劃

**Arthur 的 routine**（`agents/analysts/Arthur/routine.md`）：
- 每日晨報（08:00）
- 價位監控（每 5 分鐘）
- 週度回顧（週五 18:00）
- 異常波動偵測（每分鐘）
- VPPA 快取更新（每 4 小時）

**Max 的 routine**（`agents/traders/Max/routine.md`）：
- 交易機會掃描（每 2 小時）
- 持倉監控（每 5 分鐘）
- 移動停損提醒（每 10 分鐘）
- 每日交易回顧（22:00）
- 重大事件提醒（每日 08:00）

**Donna 的 routine**（`agents/assistants/Donna/routine.md`）：
- 每日早安問候（08:00）
- 每日晚間總結（21:00）
- 系統健康檢查（每 6 小時）
- 報告彙整存檔（23:00）
- 週度工作回顧（週五 19:00）

## 開放問題

1. **執行緒 vs Async Task**：
   - 需求提到「起一個 thread」，但現有架構使用 async
   - 建議：使用 `asyncio.create_task()` 而非傳統執行緒，更符合現有架構

2. **Admin 識別**：
   - 需求提到「admin 的訊息」
   - 目前系統檢查「群組管理員」（Telegram 角色）
   - 是否需要額外的白名單機制？還是沿用現有的群組管理員檢查？

3. **名稱匹配策略**：
   - 需求：「前 10 個字元包含名字（無論大小寫、空白分隔）」
   - 中英文名稱都要支援嗎？（Arthur/亞瑟、Max/麥克斯、Donna/朵娜）
   - 部分匹配還是完全匹配？

4. **記憶管理策略**：
   - 每日 log 檔會持續累積對話記錄
   - 是否需要限制記憶長度以避免 token 超限？
   - 如何處理跨日的對話連續性？

5. **System Prompt 建構**：
   - persona.md、jobs.md 內容很長（500+ 行）
   - 是否需要摘要或只提取關鍵部分？
   - 如何平衡人格完整性和 token 使用效率？

6. **錯誤處理和恢復**：
   - Agent 任務失敗時如何處理？
   - 是否需要將錯誤記錄到 agent 的 log 檔？
   - 定期任務失敗是否需要重試機制？

7. **多 Agent 衝突**：
   - 如果訊息同時匹配多個 agent 名稱怎麼辦？
   - 是否需要優先級機制？

## 結論

現有系統已具備實現需求的基礎設施：
- ✅ Telegram bot 框架
- ✅ Claude Agent SDK 整合
- ✅ Async/非同步架構
- ✅ APScheduler 定時任務支援
- ✅ Agent 配置檔案（persona/jobs/routine）
- ✅ 管理員權限驗證

但需要新增的核心功能：
- ❌ 多 agent 實例管理
- ❌ 基於名稱的訊息路由
- ❌ 每日自我認知生成
- ❌ 記憶參考機制
- ❌ 個別 agent 的 log 管理
- ❌ 定期任務的實際腳本

建議的實現路徑：
1. 擴展 `TelegramBot` 類別，為每個 agent 建立獨立實例
2. 修改 `handle_message()` 加入名稱匹配和路由邏輯
3. 建立 `AgentManager` 類別管理 agent 生命週期和任務
4. 實現每日自我認知任務（使用 APScheduler）
5. 修改日誌結構為按日期和 agent 分類
6. 整合記憶參考機制到訊息處理流程

---

**研究完成日期**：2026-01-02
**研究者**：Claude Code (codebase-researcher)
**文件版本**：1.0
