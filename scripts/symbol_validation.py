"""
測試商品代碼驗證功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.agent_manager import AgentManager
from dotenv import load_dotenv
import os

load_dotenv()

# 建立 AgentManager
api_key = os.getenv('ANTHROPIC_API_KEY')
model = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')

manager = AgentManager(api_key=api_key, model=model)

print("=" * 80)
print("商品代碼驗證測試")
print("=" * 80)

# 檢查載入的商品列表
print("\n已載入的商品列表：")
print(manager.available_symbols)

# 測試 system prompt 是否包含商品列表
print("\n" + "=" * 80)
print("System Prompt 中的商品驗證部分：")
print("=" * 80)

arthur = manager.get_agent('arthur')
if arthur and hasattr(arthur, 'default_system_prompt'):
    # 提取商品驗證相關部分
    prompt = arthur.default_system_prompt
    start_idx = prompt.find('# 🚨 重要：商品代碼驗證')
    end_idx = prompt.find('# 工具使用說明')

    if start_idx != -1 and end_idx != -1:
        validation_section = prompt[start_idx:end_idx]
        print(validation_section)
    else:
        print("找不到商品驗證部分")
else:
    print("無法取得 Arthur 的 system prompt")

print("\n" + "=" * 80)
print("測試完成")
print("=" * 80)
