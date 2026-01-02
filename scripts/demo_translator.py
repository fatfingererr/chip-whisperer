#!/usr/bin/env python3
"""
翻譯器手動測試腳本

測試 deep-translator 翻譯英文新聞為繁體中文。
"""

from src.crawler.translator import NewsTranslator

# 初始化翻譯器
translator = NewsTranslator()

# 測試文本
news_texts = [
    "Gold prices surge amid market volatility",
    "Bitcoin breaks resistance level at $100,000",
    "Crude oil futures climb on supply concerns",
    "Silver prices hit new yearly highs",
    "Copper demand rises in China"
]

print("=" * 70)
print("翻譯器測試結果")
print("=" * 70)

# 翻譯並顯示結果
for i, text in enumerate(news_texts, 1):
    try:
        translated = translator.translate(text)
        print(f"\n{i}. 原文：{text}")
        print(f"   譯文：{translated}")
    except Exception as e:
        print(f"\n{i}. 原文：{text}")
        print(f"   錯誤：{e}")

print("\n" + "=" * 70)
