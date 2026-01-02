#!/usr/bin/env python3
"""
翻譯效能測試腳本

測試翻譯功能的效能影響。
"""

import time
from src.crawler.translator import NewsTranslator

# 初始化翻譯器
translator = NewsTranslator()

# 測試文本（不同長度）
test_texts = {
    '短文本': 'Gold prices surge',
    '中等文本': 'Gold prices surge amid market volatility. ' * 10,
    '長文本': 'Gold prices surge amid market volatility. ' * 100
}

print("=" * 80)
print("翻譯效能測試")
print("=" * 80)

for name, text in test_texts.items():
    # 測試翻譯速度（5 次取平均）
    times = []
    for i in range(5):
        start = time.time()
        result = translator.translate(text)
        elapsed = time.time() - start
        times.append(elapsed)

    avg_time = sum(times) / len(times)

    print(f"\n{name} ({len(text)} 字元):")
    print(f"  平均翻譯時間: {avg_time:.3f} 秒")
    print(f"  翻譯後長度: {len(result)} 字元")

print("\n" + "=" * 80)
