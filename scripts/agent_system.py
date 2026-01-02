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

        logger.info("測試通過：AgentManager 成功載入所有 agents")
        return agent_manager

    except Exception as e:
        logger.error(f"測試失敗：{e}")
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
            logger.info(f"  訊息「{message}」 -> {result or '無匹配'}")

        logger.info("測試通過：所有名稱匹配測試正確")

    except Exception as e:
        logger.error(f"測試失敗：{e}")
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
        logger.info("  成功追加內容到 arthur 日誌")

        # 測試讀取
        memory = agent_manager.read_daily_memory('arthur')
        assert test_content in memory, "讀取的記憶應包含寫入的內容"
        logger.info(f"  成功讀取 arthur 記憶：{len(memory)} 字元")

        # 測試追加
        additional_content = "這是追加的內容\n"
        agent_manager.append_to_daily_log('arthur', additional_content)
        memory = agent_manager.read_daily_memory('arthur')
        assert additional_content in memory, "讀取的記憶應包含追加的內容"
        logger.info("  成功追加額外內容到 arthur 日誌")

        # 測試不存在的記憶
        memory = agent_manager.read_daily_memory('nonexistent_agent')
        assert memory == '', "不存在的 agent 應回傳空字串"
        logger.info("  不存在的 agent 正確回傳空記憶")

        logger.info("測試通過：所有記憶操作正確")

    except Exception as e:
        logger.error(f"測試失敗：{e}")
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
        logger.info(f"  日誌檔案已生成：{log_path}")

        # 檢查內容
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert '自我認知' in content, "日誌內容應包含「自我認知」"
        assert len(content) > 100, "自我認知內容應超過 100 字元"
        logger.info(f"  自我認知內容正確：{len(content)} 字元")

        logger.info("測試通過：自我認知生成正確")

    except Exception as e:
        logger.error(f"測試失敗：{e}")
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
            logger.info(f"  已整合記憶：{len(daily_memory)} 字元")
        else:
            enhanced_message = test_message
            logger.info("  arthur 沒有本日記憶")

        # 處理訊息
        system_prompt = getattr(agent, 'default_system_prompt', None)
        logger.info("  正在處理訊息...")
        response = agent.process_message(enhanced_message, system_prompt=system_prompt)

        assert len(response) > 0, "回應不應為空"
        logger.info(f"  收到回應：{len(response)} 字元")
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
        logger.info("  已記錄互動到日誌")

        logger.info("測試通過：訊息處理流程正確")

    except Exception as e:
        logger.error(f"測試失敗：{e}")
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
        logger.info("所有測試通過！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("=" * 60)
        logger.error("測試失敗")
        logger.error("=" * 60)
        logger.exception(e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
