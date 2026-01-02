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
