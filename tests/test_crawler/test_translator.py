"""
翻譯模組單元測試

測試 NewsTranslator 的核心功能。
"""

import pytest
from src.crawler.translator import NewsTranslator, get_translator


class TestNewsTranslator:
    """NewsTranslator 單元測試"""

    def test_translate_simple_text(self):
        """測試基本翻譯功能"""
        translator = NewsTranslator()
        result = translator.translate("Hello World")

        # 確保有返回值且已翻譯
        assert result
        assert result != "Hello World"
        assert len(result) > 0

    def test_translate_empty_string(self):
        """測試空字串翻譯"""
        translator = NewsTranslator()
        result = translator.translate("")

        # 空字串應返回空字串
        assert result == ""

    def test_translate_whitespace_only(self):
        """測試純空白字串"""
        translator = NewsTranslator()
        result = translator.translate("   ")

        # 純空白應返回原值
        assert result == "   "

    def test_translate_with_fallback(self):
        """測試降級策略"""
        translator = NewsTranslator()

        # 正常翻譯應成功
        result = translator.translate(
            "Gold prices surge amid market volatility",
            fallback_to_original=True
        )

        assert result
        assert len(result) > 0

    def test_get_translator_singleton(self):
        """測試單例模式"""
        translator1 = get_translator()
        translator2 = get_translator()

        # 應該是同一個實例
        assert translator1 is translator2

    def test_translate_long_text(self):
        """測試長文本翻譯"""
        translator = NewsTranslator()

        # 建立一段長文本（但不超過限制）
        long_text = "Gold prices surge. " * 100  # 約 2000 字元

        result = translator.translate(long_text)

        assert result
        assert len(result) > 0

    def test_translate_news_example(self):
        """測試真實新聞範例"""
        translator = NewsTranslator()

        news_examples = [
            "Gold prices surge amid market volatility",
            "Bitcoin breaks resistance level at $100,000",
            "Crude oil futures climb on supply concerns"
        ]

        for news in news_examples:
            result = translator.translate(news)

            # 確保翻譯成功
            assert result
            assert len(result) > 0

            # 應該包含中文字元（簡單檢查）
            assert any('\u4e00' <= char <= '\u9fff' for char in result)


def test_translator_initialization():
    """測試翻譯器初始化"""
    translator = NewsTranslator(
        source_lang='en',
        target_lang='zh-TW',
        max_retries=5,
        base_delay=0.5,
        max_delay=5.0
    )

    assert translator.source_lang == 'en'
    assert translator.target_lang == 'zh-TW'
    assert translator.max_retries == 5
    assert translator.base_delay == 0.5
    assert translator.max_delay == 5.0
