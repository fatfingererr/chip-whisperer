# AI Agent 角色設計研究報告

**日期**: 2026-01-02
**研究者**: Claude Code
**專案**: Chip Whisperer - MT5 AI 交易代理

---

## 一、研究背景與目的

### 1.1 需求概述

本研究旨在設計一套完整的 AI 角色系統，使 Telegram Bot 能夠：
- 監聽用戶對話
- 扮演不同角色執行不同任務
- 提供有性格和特性的回覆

### 1.2 專案現況分析

#### 專案結構

```
chip-whisperer/
├── agents/                    # AI 角色定義目錄
│   ├── analysts/             # 分析師角色
│   │   └── Arthur/           # 亞瑟 - 分析師
│   ├── assistants/           # 助理角色
│   │   └── Donna/            # 朵娜 - 助理
│   └── traders/              # 交易員角色
│       └── Max/              # 麥克斯 - 交易員
├── src/
│   ├── agent/                # Agent 核心邏輯
│   │   ├── agent.py          # MT5Agent 類別
│   │   ├── indicators.py     # 技術指標計算
│   │   └── tools.py          # 工具定義
│   ├── bot/                  # Telegram Bot
│   │   ├── telegram_bot.py   # Bot 主程式
│   │   ├── handlers.py       # 訊息處理器
│   │   └── config.py         # Bot 設定
│   ├── core/                 # 核心功能
│   │   ├── data_fetcher.py   # 資料取得
│   │   ├── mt5_client.py     # MT5 客戶端
│   │   └── sqlite_cache.py   # 快取管理
│   └── visualization/        # 視覺化
│       └── vppa_plot.py      # VPPA 圖表
└── scripts/                  # 執行腳本
```

#### 現有功能

1. **MT5 整合**：連接 MetaTrader 5 取得市場資料
2. **技術分析**：Volume Profile (VPPA)、SMA、RSI 等指標
3. **Telegram Bot**：自然語言查詢介面
4. **Claude AI**：使用 Anthropic Claude API 處理對話

---

## 二、角色設計架構

### 2.1 角色概覽

| 角色 | 名稱 | 職責 | 目錄位置 |
|------|------|------|----------|
| 分析師 | Arthur（亞瑟） | 市場分析、技術指標 | `agents/analysts/Arthur/` |
| 交易員 | Max（麥克斯） | 交易策略、風險管理 | `agents/traders/Max/` |
| 助理 | Donna（朵娜） | 帳戶查詢、任務協調 | `agents/assistants/Donna/` |

### 2.2 檔案結構設計

每個角色目錄下包含三個核心檔案：

```
{agent_directory}/
├── persona.md    # 人格設定：個性、說話風格、情緒反應
├── jobs.md       # 任務定義：觸發條件、主要任務、輸出格式
└── routine.md    # 定期任務：排程任務、執行腳本、輸出位置
```

---

## 三、模板設計規範

### 3.1 persona.md 模板結構

```markdown
# {角色名稱} - {職稱}人格設定

## 基本資訊
| 欄位 | 內容 |
|------|------|
| 姓名 | {中英文名稱} |
| 角色 | {職稱} |
| 性別 | {男/女} |
| 人格類型 | {MBTI 類型} |

## 人格特質

### 核心性格
- {特質 1}：{描述}
- {特質 2}：{描述}
- ...

### 說話風格
- {風格描述}

### 口頭禪與慣用語
```yaml
greeting:
  - "{問候語 1}"
  - "{問候語 2}"
{category}:
  - "{用語}"
```

### 情緒反應模式
```yaml
{emotion_name}:
  trigger: "{觸發條件}"
  response: "{回應方式}"
```

## 專業能力

### 核心技能
- {技能 1}
- {技能 2}

## 互動指南

### 回應格式偏好
{格式範例}

### 不會做的事
- {限制 1}
- {限制 2}

## 背景故事
{角色背景描述，供角色扮演時參考}
```

### 3.2 jobs.md 模板結構

```markdown
# {角色名稱} - 任務職責定義

## 角色定位
{簡述角色在團隊中的定位}

## 任務觸發條件

### 主要關鍵字
```yaml
primary_keywords:
  {category}:
    - "{關鍵字}"
```

### 情境判斷規則
```yaml
should_respond:
  - {應處理的情境}
should_not_respond:
  - {不應處理的情境}
```

## 主要任務清單

### 1. {任務名稱}
```yaml
task: {task_id}
description: "{任務描述}"
triggers:
  - "{觸發語句}"
actions:
  - {動作步驟}
output_format: |
  {輸出格式模板}
```

## 回應優先級
```yaml
priority_rules:
  high: [...]
  medium: [...]
  low: [...]
```

## 與其他角色的協作
{協作方式說明}

## 錯誤處理
{錯誤情境的處理方式}
```

### 3.3 routine.md 模板結構

```markdown
# {角色名稱} - 定期任務排程

## 任務總覽
{定期任務概述}

## 定期任務清單

### 1. {任務名稱}
```yaml
task_id: {task_id}
name: "{任務顯示名稱}"
schedule: "{cron 表達式}"  # 例如 "0 8 * * 1-5"
description: "{任務描述}"

execution:
  script: "{執行腳本路徑}"
  steps:
    - name: "{步驟名稱}"
      action: "{動作}"
      {其他參數}

output:
  format: "{輸出格式}"
  destination: "{輸出位置}"
  notification: {true/false}
```

## 任務設定檔結構
```yaml
# config/routines/{agent}.yaml
{設定檔結構}
```

## 手動觸發任務
{手動執行指令}

## 任務依賴關係
{任務間的依賴說明}
```

---

## 四、角色詳細設計

### 4.1 Arthur（亞瑟）- 分析師

#### 人格定位
- **MBTI**：INTJ（策略家）
- **核心特質**：專業嚴謹、邏輯清晰、沉穩內斂
- **說話風格**：專業但不艱澀，像經驗豐富的導師

#### 主要任務
1. Volume Profile 分析
2. 技術指標計算
3. 趨勢研判
4. 支撐壓力分析

#### 定期任務
1. 每日市場晨報（08:00）
2. 關鍵價位突破監控（每 5 分鐘）
3. 週度市場回顧（週五 18:00）
4. 異常波動偵測（每分鐘）
5. VPPA 快取更新（每 4 小時）

### 4.2 Max（麥克斯）- 交易員

#### 人格定位
- **MBTI**：ESTP（企業家）
- **核心特質**：果斷俐落、風險意識強、實戰導向
- **說話風格**：簡潔有力、直擊重點

#### 主要任務
1. 交易機會評估
2. 交易計畫制定
3. 停損停利計算
4. 倉位計算
5. 交易執行確認

#### 定期任務
1. 交易機會掃描（每 2 小時）
2. 持倉監控（每 5 分鐘）
3. 移動停損提醒（每 10 分鐘）
4. 每日交易回顧（22:00）
5. 週度交易總結（週六 20:00）
6. 重大事件前提醒（08:00）

### 4.3 Donna（朵娜）- 助理

#### 人格定位
- **MBTI**：ESFJ（外交官）
- **核心特質**：親切友善、細心周到、耐心傾聽
- **說話風格**：溫和有禮貌、主動詢問

#### 主要任務
1. 帳戶資訊查詢
2. 系統狀態檢查
3. 使用說明
4. 任務分派
5. 日常互動
6. 報告整理

#### 定期任務
1. 每日早安問候（08:00）
2. 每日晚間總結（21:00）
3. 系統健康檢查（每 6 小時）
4. 報告彙整與存檔（23:00）
5. 週度工作回顧（週五 19:00）
6. 定期提醒服務（09:00, 14:00, 17:00）

---

## 五、訊息路由機制

### 5.1 訊息分派邏輯

```
用戶訊息
    │
    ▼
┌─────────────────────────────────┐
│  Donna（預設處理者）             │
│  - 初步接收所有訊息              │
│  - 判斷訊息類型                  │
└─────────────────────────────────┘
    │
    ├─── 分析相關 ──▶ Arthur
    │
    ├─── 交易相關 ──▶ Max
    │
    └─── 其他 ──────▶ Donna 直接處理
```

### 5.2 關鍵字對應表

| 類別 | 關鍵字範例 | 處理者 |
|------|-----------|--------|
| 分析 | 分析、VP、POC、趨勢、指標 | Arthur |
| 交易 | 進場、停損、倉位、策略 | Max |
| 帳戶 | 餘額、保證金、帳戶 | Donna |
| 系統 | 狀態、連線、正常嗎 | Donna |
| 一般 | 你好、謝謝、再見 | Donna |

---

## 六、技術實作建議

### 6.1 Context 載入方式

建議在處理訊息時，根據判斷結果載入對應角色的 Context：

```python
def load_agent_context(agent_name: str) -> dict:
    """載入指定角色的完整 Context"""
    base_path = f"agents/{get_agent_type(agent_name)}/{agent_name}/"

    return {
        "persona": load_markdown(f"{base_path}persona.md"),
        "jobs": load_markdown(f"{base_path}jobs.md"),
        "routine": load_markdown(f"{base_path}routine.md")
    }
```

### 6.2 System Prompt 組合

```python
def build_system_prompt(agent_context: dict) -> str:
    """組合角色的 System Prompt"""
    return f"""
你現在扮演 {agent_context['name']}。

## 人格設定
{agent_context['persona']}

## 任務職責
{agent_context['jobs']}

請根據以上設定回應用戶的訊息。
"""
```

### 6.3 定期任務執行

使用 cron 或 APScheduler 執行定期任務：

```python
# scripts/run_agent_routines.py
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# 載入各角色的 routine 設定
for agent in ['Arthur', 'Max', 'Donna']:
    routine_config = load_routine_config(agent)
    for task in routine_config['tasks']:
        scheduler.add_job(
            func=task['execution']['script'],
            trigger='cron',
            **parse_cron(task['schedule'])
        )

scheduler.start()
```

---

## 七、檔案清單

本研究產出的檔案：

```
agents/
├── analysts/Arthur/
│   ├── persona.md    ✅ 已建立
│   ├── jobs.md       ✅ 已建立
│   └── routine.md    ✅ 已建立
├── assistants/Donna/
│   ├── persona.md    ✅ 已建立
│   ├── jobs.md       ✅ 已建立
│   └── routine.md    ✅ 已建立
└── traders/Max/
    ├── persona.md    ✅ 已建立
    ├── jobs.md       ✅ 已建立
    └── routine.md    ✅ 已建立
```

---

## 八、後續建議

### 8.1 短期實作

1. **訊息路由器**：實作 `MessageRouter` 類別，根據關鍵字分派訊息
2. **Context 載入器**：實作動態載入角色 Context 的功能
3. **System Prompt 組合器**：根據角色設定組合完整的 System Prompt

### 8.2 中期優化

1. **多角色協作**：實作角色間的任務轉交和協作機制
2. **對話記憶**：維護各角色的對話歷史
3. **定期任務框架**：建立統一的定期任務執行框架

### 8.3 長期擴展

1. **角色學習**：根據用戶回饋調整角色行為
2. **新角色擴展**：設計新角色的加入機制
3. **角色個性化**：允許用戶自訂角色特性

---

## 九、總結

本研究設計了一套完整的 AI 角色系統架構，包含：

1. **三個角色定義**：Arthur（分析師）、Max（交易員）、Donna（助理）
2. **統一的模板結構**：persona.md、jobs.md、routine.md
3. **完整的任務定義**：觸發條件、執行動作、輸出格式
4. **定期任務排程**：每個角色的背景任務設計
5. **協作機制**：角色間的任務分派和協作方式

此設計可以讓 Telegram Bot 根據用戶的訊息內容，動態選擇適當的角色進行回覆，提供更有個性和專業性的互動體驗。

---

*報告完成日期：2026-01-02*
*作者：Claude Code*
