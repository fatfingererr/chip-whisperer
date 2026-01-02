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
