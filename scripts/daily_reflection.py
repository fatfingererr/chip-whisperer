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

        logger.info("自我認知生成完成")

    except Exception as e:
        logger.exception(f"發生錯誤：{e}")
        sys.exit(1)


if __name__ == "__main__":
    # 取得命令列參數
    agent_name = sys.argv[1] if len(sys.argv) > 1 else 'all'

    # 執行
    asyncio.run(main(agent_name))
