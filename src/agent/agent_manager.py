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

        # 載入可用的 MT5 商品列表
        self.available_symbols = self._load_available_symbols()

        # 載入所有 agents
        self._load_agents()

        logger.info(f"AgentManager 初始化完成，已載入 {len(self.agents)} 個 agents")

    def _load_available_symbols(self) -> str:
        """
        載入可用的 MT5 商品列表

        回傳：
            商品列表的字串（用於加入 system prompt）
        """
        symbols_file = Path('markets/symbols.txt')

        if not symbols_file.exists():
            logger.warning(f"找不到 symbols.txt 檔案：{symbols_file}")
            return "# 無法載入商品列表"

        try:
            with open(symbols_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取有效的 symbol（非註解行）
            symbols = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # 格式：SYMBOL -> FolderName
                    if '->' in line:
                        symbol = line.split('->')[0].strip()
                        symbols.append(symbol)

            logger.info(f"已載入 {len(symbols)} 個可用商品")

            # 回傳格式化的列表
            symbols_text = "可用的 MT5 商品代碼（必須使用這些精確名稱）：\n"
            symbols_text += ", ".join(sorted(symbols))

            return symbols_text

        except Exception as e:
            logger.error(f"讀取 symbols.txt 失敗：{e}")
            return "# 無法載入商品列表"

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

# 🚨 重要：商品代碼驗證（必須優先執行）

{self.available_symbols}

**常見中文名稱對應**：
- 黃金 → GOLD
- 白銀 → SILVER
- 鋁 → ALUMINIUM（注意：有兩個 I，不是 ALUMINUM）
- 銅 → COPPER
- 鉛 → LEAD
- 鋅 → ZINC
- 鈀金 → PALLADIUM
- 鉑金 → PLATINUM
- 原油 → WTI 或 BRENT
- 比特幣 → BITCOIN
- 以太幣 → ETHEREUM
- Solana → SOLANA

**重要規則**：
1. 在處理任何商品查詢前，先確認商品是否在上述列表中
2. 如果用戶詢問的商品**不在**列表中：
   - 立即回應：「抱歉，MT5 目前沒有提供 [商品名稱] 的數據。」
   - 列出相關的可用商品（如果有）
   - **不要**嘗試調用任何工具
   - **直接結束對話**
3. 使用工具時，symbol 參數必須使用**列表中的精確名稱**（全大寫）

# 工具使用說明

你可以使用以下工具：
1. get_candles - 取得歷史 K 線資料
2. calculate_volume_profile - 計算 Volume Profile（POC, VAH, VAL）
3. calculate_sma - 計算簡單移動平均線
4. calculate_rsi - 計算相對強弱指標
5. get_account_info - 取得帳戶資訊

**重要提醒**：
- 在調用 get_candles 前，請先確認 symbol 參數使用的是 symbols.txt 中的**正確名稱**（全大寫）
- 在使用計算工具前，需要先使用 get_candles 取得資料

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
