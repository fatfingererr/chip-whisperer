"""
測試 Agent 名稱匹配邏輯
"""

import sys
from pathlib import Path

# 加入專案路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.agent_manager import AgentManager


def test_match_agent():
    """測試名稱匹配邏輯"""

    # 建立一個簡化的 AgentManager 來測試匹配邏輯
    class TestAgentManager:
        AGENT_NAMES = {
            'arthur': ['arthur', '亞瑟'],
            'max': ['max', '麥克斯'],
            'donna': ['donna', '朵娜']
        }

        def match_agent(self, message: str):
            """根據訊息前 10 個字元匹配 agent"""
            # 提取前 10 個字元，移除空白，轉小寫
            prefix = ''.join(message[:10].split()).lower()
            print(f"原始訊息: {message}")
            print(f"前 10 字元: {message[:10]!r}")
            print(f"處理後的 prefix: {prefix!r}")

            # 檢查每個 agent
            for agent_name, name_variants in self.AGENT_NAMES.items():
                for name in name_variants:
                    if name.lower() in prefix:
                        print(f"匹配成功: {agent_name} (關鍵字: {name})")
                        return agent_name

            print("未匹配到任何 agent")
            return None

    manager = TestAgentManager()

    # 測試案例
    test_cases = [
        "arthur 你今天的任務是?",
        "Arthur 黃金趨勢如何？",
        "ARTHUR 今天有什麼消息？",
        "亞瑟 幫我分析一下",
        "max 可以進場嗎？",
        "Max 今天的交易建議？",
        "麥克斯 現在怎麼樣？",
        "donna 請幫我",
        "Donna 有什麼問題嗎？",
        "朵娜 協助我",
        "這是一個沒有名稱的訊息",
        "hello world"
    ]

    print("=" * 80)
    print("Agent 名稱匹配測試")
    print("=" * 80)

    for i, test_msg in enumerate(test_cases, 1):
        print(f"\n測試 {i}:")
        print("-" * 80)
        result = manager.match_agent(test_msg)
        print(f"結果: {result}")
        print()


if __name__ == "__main__":
    test_match_agent()
