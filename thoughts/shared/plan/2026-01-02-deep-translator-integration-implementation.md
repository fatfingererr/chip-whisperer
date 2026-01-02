---
title: deep-translator 整合實作計畫
date: 2026-01-02
author: Claude Code
tags:
  - deep-translator
  - translation
  - implementation-plan
  - telegram-bot
  - news-crawler
status: completed
related_research: thoughts/shared/research/2026-01-02-deep-translator-integration-research.md
estimated_time: 2-3 小時
priority: medium
---

# deep-translator 整合實作計畫

## 概述

本計畫將整合 deep-translator 套件的 GoogleTranslator，實現商品新聞爬蟲系統的翻譯功能。核心目標是在發送 Telegram 訊息時將英文新聞翻譯成繁體中文（zh-TW），同時保持檔案保存的英文原文不變。

## 當前狀態分析

### 現有架構

**Telegram 訊息發送流程**：
- **檔案**：`src/crawler/scheduler.py`
- **關鍵方法**：
  - `_crawl_and_notify()`（第 43-56 行）：爬取新聞並發送通知
  - `_send_telegram_notifications()`（第 58-80 行）：發送 Telegram 通知
  - `_format_news_message()`（第 82-125 行）：格式化新聞訊息

**新聞資料結構**：
```python
{
    'commodity': 'Gold',      # 商品名稱
    'news_id': 1,             # 新聞 ID
    'text': '...',            # 完整文本（英文）
    'time': '2026-01-02...'   # 時間戳
}
```

**關鍵發現**：
- 訊息格式化在 `_format_news_message()` 方法中完成
- `text` 欄位目前是英文原文，這是翻譯的目標
- 檔案保存在 `news_crawler.py` 中完成，與 Telegram 發送流程獨立

### 缺少的功能

1. **翻譯模組**：沒有翻譯相關的程式碼
2. **翻譯配置**：`config.py` 中沒有翻譯相關配置
3. **錯誤處理**：沒有翻譯失敗的降級策略
4. **依賴套件**：`requirements.txt` 中沒有 deep-translator

## 期望的最終狀態

### 功能目標

1. ✅ **Telegram 訊息翻譯為繁體中文**
   - 英文新聞自動翻譯成繁體中文（zh-TW）
   - 翻譯失敗時自動降級回英文原文
   - 不阻塞 Telegram 通知流程

2. ✅ **檔案保存維持英文原文**
   - 保存到 `markets/` 目錄的檔案仍為英文
   - 不影響現有的檔案結構

3. ✅ **可配置的翻譯功能**
   - 可透過環境變數啟用/停用翻譯
   - 可配置目標語言、重試次數等參數

4. ✅ **穩健的錯誤處理**
   - 速率限制時自動重試（指數退避）
   - 網路錯誤時自動重試
   - 重試失敗後降級回原文

### 驗證標準

**自動化驗證**：
- [ ] `pip install -r requirements.txt` 成功安裝 deep-translator
- [ ] `python -m pytest tests/test_crawler/test_translator.py` 單元測試通過
- [ ] `python -c "from src.crawler.translator import NewsTranslator"` 模組匯入成功
- [ ] 環境變數配置正確載入（檢查 config.py）

**手動驗證**：
- [ ] 啟動 Bot 後觸發 `/crawl_now`，Telegram 收到繁體中文訊息
- [ ] 檢查 `markets/` 目錄下的檔案仍為英文原文
- [ ] 停用翻譯功能（`CRAWLER_ENABLE_TRANSLATION=false`），Telegram 收到英文訊息
- [ ] 模擬網路錯誤（斷網），Bot 降級發送英文訊息而不崩潰
- [ ] 長文本（超過 3000 字元）正確截斷後翻譯

## 我們不做的事情

明確排除以下範圍，避免範圍蔓延：

1. ❌ **不翻譯保存的檔案**：檔案內容維持英文
2. ❌ **不實作翻譯緩存**：初期不需要緩存機制（可作為未來優化）
3. ❌ **不建立專業術語字典**：直接使用 Google Translate（未來可優化）
4. ❌ **不支援多語言翻譯**：只支援繁體中文（zh-TW）
5. ❌ **不實作長文本分段翻譯**：初期使用簡單截斷（未來可優化）
6. ❌ **不整合其他翻譯 API**：只使用 deep-translator GoogleTranslator

## 實作方法

### 架構設計

**新增檔案**：
- `src/crawler/translator.py`：翻譯模組

**修改檔案**：
- `src/crawler/config.py`：新增翻譯配置
- `src/crawler/scheduler.py`：整合翻譯功能
- `requirements.txt`：新增 deep-translator 依賴
- `.env.example`：新增翻譯環境變數範例

**翻譯流程**：
```
新聞爬取 -> 保存檔案（英文）-> 格式化訊息時翻譯 -> 發送 Telegram（中文）
```

**插入點**：`scheduler.py` 的 `_format_news_message()` 方法

---

## 階段一：基礎翻譯模組

### 概述

建立 `src/crawler/translator.py` 翻譯模組，實作核心翻譯功能、重試機制和錯誤處理。

### 需要創建的檔案

#### 1. `src/crawler/translator.py`

**檔案位置**：`C:\Users\fatfi\works\chip-whisperer\src\crawler\translator.py`

**實作內容**：

```python
"""
新聞翻譯模組

使用 deep-translator GoogleTranslator 將英文新聞翻譯為繁體中文。

主要功能：
- 英文到繁體中文（zh-TW）翻譯
- 指數退避重試機制（處理速率限制和網路錯誤）
- 降級策略（翻譯失敗時返回原文）
- 單例模式全域翻譯器實例
"""

from typing import Optional
import time
import random
from loguru import logger
from deep_translator import GoogleTranslator
from deep_translator.exceptions import (
    TooManyRequests,
    RequestError,
    NotValidLength,
    TranslationNotFound
)


class NewsTranslator:
    """
    新聞翻譯器

    使用 Google Translate（透過 deep-translator）翻譯新聞為繁體中文。

    功能：
    - 自動偵測來源語言（通常為英文）
    - 翻譯為繁體中文（zh-TW）
    - 速率限制和網路錯誤自動重試
    - 翻譯失敗時可選擇降級回原文
    """

    def __init__(
        self,
        source_lang: str = 'auto',
        target_lang: str = 'zh-TW',
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0
    ):
        """
        初始化翻譯器

        參數:
            source_lang: 來源語言（預設 'auto' 自動檢測）
            target_lang: 目標語言（預設 'zh-TW' 繁體中文）
            max_retries: 最大重試次數（預設 3）
            base_delay: 初始重試延遲（秒，預設 1.0）
            max_delay: 最大重試延遲（秒，預設 10.0）
        """
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

        # 初始化翻譯器
        self.translator = GoogleTranslator(
            source=source_lang,
            target=target_lang
        )

        logger.info(f"翻譯器初始化完成：{source_lang} -> {target_lang}")

    def translate(self, text: str, fallback_to_original: bool = True) -> str:
        """
        翻譯文本

        參數:
            text: 要翻譯的文本（英文）
            fallback_to_original: 失敗時是否降級回原文（預設 True）

        回傳:
            翻譯後的文本（繁體中文），失敗時返回原文（若 fallback_to_original=True）

        範例:
            >>> translator = NewsTranslator()
            >>> result = translator.translate("Gold prices surge")
            >>> print(result)
            黃金價格飆升
        """
        if not text or not text.strip():
            return text

        # 執行翻譯（帶重試機制）
        try:
            translated = self._translate_with_retry(text)
            logger.debug(f"翻譯成功：{text[:50]}... -> {translated[:50]}...")
            return translated

        except Exception as e:
            logger.error(f"翻譯失敗：{e}")

            if fallback_to_original:
                logger.warning("降級回英文原文")
                return text
            else:
                raise

    def _translate_with_retry(self, text: str) -> str:
        """
        使用指數退避重試機制翻譯

        參數:
            text: 要翻譯的文本

        回傳:
            翻譯後的文本

        例外:
            TooManyRequests: 超過速率限制且重試失敗
            RequestError: 請求錯誤且重試失敗
            NotValidLength: 文本長度無效（不重試）
            TranslationNotFound: 翻譯未找到（不重試）
            Exception: 其他未知錯誤
        """
        for attempt in range(self.max_retries + 1):
            try:
                # 執行翻譯
                translated = self.translator.translate(text)

                if attempt > 0:
                    logger.info(f"翻譯成功（重試 {attempt} 次後）")

                return translated

            except TooManyRequests:
                if attempt == self.max_retries:
                    logger.error(f"翻譯速率限制，重試 {self.max_retries} 次後仍失敗")
                    raise

                # 計算延遲（指數退避 + 隨機抖動）
                delay = self._calculate_backoff_delay(attempt)
                logger.warning(
                    f"翻譯速率限制，{delay:.2f} 秒後重試 "
                    f"（第 {attempt + 1}/{self.max_retries} 次）"
                )
                time.sleep(delay)

            except RequestError as e:
                if attempt == self.max_retries:
                    logger.error(f"翻譯請求錯誤（{e}），重試 {self.max_retries} 次後仍失敗")
                    raise

                delay = self._calculate_backoff_delay(attempt)
                logger.warning(
                    f"翻譯請求錯誤（{e}），{delay:.2f} 秒後重試 "
                    f"（第 {attempt + 1}/{self.max_retries} 次）"
                )
                time.sleep(delay)

            except NotValidLength as e:
                # 文本長度無效，不重試
                logger.error(f"文本長度無效：{e}")
                raise

            except TranslationNotFound as e:
                # 翻譯未找到，不重試
                logger.error(f"翻譯未找到：{e}")
                raise

            except Exception as e:
                # 未知錯誤，記錄並拋出
                logger.error(f"翻譯發生未知錯誤：{e}")
                raise

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        計算指數退避延遲時間

        使用公式：delay = min(base_delay * (2 ^ attempt), max_delay) * jitter
        其中 jitter 為 0.5 ~ 1.5 之間的隨機數

        參數:
            attempt: 當前重試次數（從 0 開始）

        回傳:
            延遲時間（秒）

        範例:
            attempt=0: 1.0 * (2^0) * jitter = 0.5~1.5 秒
            attempt=1: 1.0 * (2^1) * jitter = 1.0~3.0 秒
            attempt=2: 1.0 * (2^2) * jitter = 2.0~6.0 秒
        """
        # 指數退避：delay = base_delay * (2 ^ attempt)
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)

        # 添加隨機抖動（0.5 ~ 1.5 倍）
        jitter = 0.5 + random.random()
        delay = delay * jitter

        return delay


# 全域翻譯器實例（單例模式）
_global_translator: Optional[NewsTranslator] = None


def get_translator(
    target_lang: str = 'zh-TW',
    max_retries: int = 3,
    **kwargs
) -> NewsTranslator:
    """
    取得全域翻譯器實例（單例模式）

    參數:
        target_lang: 目標語言（預設 zh-TW）
        max_retries: 最大重試次數（預設 3）
        **kwargs: 其他 NewsTranslator 參數

    回傳:
        NewsTranslator 實例

    範例:
        >>> translator = get_translator()
        >>> result = translator.translate("Hello World")
        >>> print(result)
        你好世界
    """
    global _global_translator

    if _global_translator is None:
        _global_translator = NewsTranslator(
            target_lang=target_lang,
            max_retries=max_retries,
            **kwargs
        )

    return _global_translator
```

### 實作步驟

**步驟 1：更新依賴套件**

修改 `requirements.txt`，新增 deep-translator：

```bash
# 新聞爬蟲相關
httpx>=0.25.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
APScheduler>=3.10.0
selenium>=4.15.0
webdriver-manager>=4.0.0

# 翻譯功能
deep-translator>=1.11.0
```

**步驟 2：安裝依賴**

```bash
pip install deep-translator>=1.11.0
```

**步驟 3：建立翻譯模組檔案**

建立 `src/crawler/translator.py` 檔案，複製上述完整程式碼。

**步驟 4：驗證模組匯入**

```bash
python -c "from src.crawler.translator import NewsTranslator, get_translator; print('模組匯入成功')"
```

### 測試方式

**單元測試腳本**：

建立 `tests/test_crawler/test_translator.py`：

```python
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
```

**手動測試腳本**：

建立 `scripts/test_translator.py`：

```python
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
```

執行測試：

```bash
# 單元測試
python -m pytest tests/test_crawler/test_translator.py -v

# 手動測試
python scripts/test_translator.py
```

### 成功標準

#### 自動化驗證

- [ ] `pip install deep-translator>=1.11.0` 安裝成功
- [ ] `python -c "from src.crawler.translator import NewsTranslator"` 匯入成功
- [ ] `python -m pytest tests/test_crawler/test_translator.py` 所有測試通過
- [ ] 翻譯器能正確初始化並設定參數
- [ ] 單例模式 `get_translator()` 返回同一實例

#### 手動驗證

- [ ] 執行 `python scripts/test_translator.py` 看到繁體中文翻譯結果
- [ ] 翻譯結果為繁體字（如「台灣」而非「台湾」）
- [ ] 空字串和純空白字串返回原值
- [ ] 長文本（2000+ 字元）翻譯成功
- [ ] 翻譯結果包含中文字元（視覺檢查）

**完成此階段後，請暫停並確認測試通過後再繼續。**

---

## 階段二：配置管理

### 概述

修改 `config.py` 和 `.env.example`，新增翻譯相關配置選項，使翻譯功能可透過環境變數控制。

### 需要修改的檔案

#### 1. `src/crawler/config.py`

**修改位置**：在 `CrawlerConfig` 類別中新增翻譯配置欄位

**修改後的完整程式碼**：

```python
"""
爬蟲配置模組

管理爬蟲相關的配置參數。
"""

from dataclasses import dataclass
from typing import List
import os
from dotenv import load_dotenv


@dataclass
class CrawlerConfig:
    """
    爬蟲配置資料類別

    屬性:
        target_url: 目標網站 URL
        crawl_interval_minutes: 爬取間隔（分鐘）
        interval_jitter_seconds: 間隔隨機化範圍（秒）
        markets_dir: markets 目錄路徑
        enabled: 是否啟用爬蟲
        telegram_notify_groups: 要通知的 Telegram 群組 ID 列表
        enable_translation: 是否啟用新聞翻譯
        translation_target_lang: 翻譯目標語言
        translation_max_retries: 翻譯最大重試次數
    """

    target_url: str
    crawl_interval_minutes: int
    interval_jitter_seconds: int
    markets_dir: str
    enabled: bool
    telegram_notify_groups: List[int]

    # 翻譯相關配置
    enable_translation: bool
    translation_target_lang: str
    translation_max_retries: int

    @classmethod
    def from_env(cls) -> 'CrawlerConfig':
        """
        從環境變數載入配置

        回傳:
            CrawlerConfig 實例
        """
        load_dotenv()

        return cls(
            target_url=os.getenv(
                'CRAWLER_TARGET_URL',
                'https://tradingeconomics.com/stream?c=commodity'
            ),
            crawl_interval_minutes=int(os.getenv('CRAWLER_INTERVAL_MINUTES', '5')),
            interval_jitter_seconds=int(os.getenv('CRAWLER_JITTER_SECONDS', '15')),
            markets_dir=os.getenv('MARKETS_DIR', 'markets'),
            enabled=os.getenv('CRAWLER_ENABLED', 'true').lower() in ('true', '1', 'yes'),
            telegram_notify_groups=[
                int(gid.strip())
                for gid in os.getenv('CRAWLER_NOTIFY_GROUPS', '').split(',')
                if gid.strip()
            ],

            # 翻譯配置
            enable_translation=os.getenv('CRAWLER_ENABLE_TRANSLATION', 'true').lower() in ('true', '1', 'yes'),
            translation_target_lang=os.getenv('CRAWLER_TRANSLATION_TARGET_LANG', 'zh-TW'),
            translation_max_retries=int(os.getenv('CRAWLER_TRANSLATION_MAX_RETRIES', '3')),
        )
```

#### 2. `.env.example`

**修改位置**：在「商品新聞爬蟲設定」區塊後新增翻譯設定

**新增內容**：

```bash
# 要通知的 Telegram 群組 ID（可選，用逗號分隔）
# 若不設定則只保存到檔案，不發送通知
# 建議使用與 TELEGRAM_GROUP_IDS 相同的值
CRAWLER_NOTIFY_GROUPS=

# ============================================================================
# 商品新聞翻譯設定
# ============================================================================

# 是否啟用新聞翻譯（可選，預設為 true）
# 啟用後，發送到 Telegram 的訊息會自動翻譯為繁體中文
# 檔案保存仍為英文原文
CRAWLER_ENABLE_TRANSLATION=true

# 翻譯目標語言（可選，預設為 zh-TW 繁體中文）
# 支援的語言代碼：
#   zh-TW: 繁體中文（台灣）- 推薦
#   zh-CN: 簡體中文（中國）
#   ja: 日文
#   ko: 韓文
CRAWLER_TRANSLATION_TARGET_LANG=zh-TW

# 翻譯最大重試次數（可選，預設為 3）
# 當翻譯因速率限制或網路錯誤失敗時，會自動重試
# 重試採用指數退避策略（1秒、2秒、4秒...）
CRAWLER_TRANSLATION_MAX_RETRIES=3
```

### 實作步驟

**步驟 1：修改 config.py**

1. 在 `CrawlerConfig` 類別中新增三個欄位：
   - `enable_translation: bool`
   - `translation_target_lang: str`
   - `translation_max_retries: int`

2. 在 `from_env()` 方法中新增對應的環境變數讀取邏輯

**步驟 2：更新 .env.example**

在檔案末尾新增「商品新聞翻譯設定」區塊，包含詳細的註解說明。

**步驟 3：（可選）更新本地 .env 檔案**

如果有本地 `.env` 檔案，同步新增翻譯配置：

```bash
CRAWLER_ENABLE_TRANSLATION=true
CRAWLER_TRANSLATION_TARGET_LANG=zh-TW
CRAWLER_TRANSLATION_MAX_RETRIES=3
```

### 測試方式

**配置載入測試腳本**：

建立 `scripts/test_config.py`：

```python
#!/usr/bin/env python3
"""
配置載入測試腳本

測試翻譯配置是否正確從環境變數載入。
"""

import os
from dotenv import load_dotenv
from src.crawler.config import CrawlerConfig

# 載入 .env
load_dotenv()

# 載入配置
config = CrawlerConfig.from_env()

print("=" * 70)
print("爬蟲配置載入結果")
print("=" * 70)

# 顯示原有配置
print("\n【原有配置】")
print(f"目標 URL: {config.target_url}")
print(f"爬取間隔: {config.crawl_interval_minutes} 分鐘")
print(f"爬蟲啟用: {config.enabled}")
print(f"通知群組: {config.telegram_notify_groups}")

# 顯示翻譯配置
print("\n【翻譯配置】")
print(f"啟用翻譯: {config.enable_translation}")
print(f"目標語言: {config.translation_target_lang}")
print(f"重試次數: {config.translation_max_retries}")

# 驗證預設值
print("\n【驗證結果】")
errors = []

if not isinstance(config.enable_translation, bool):
    errors.append("enable_translation 應為 bool 類型")

if config.translation_target_lang not in ['zh-TW', 'zh-CN', 'ja', 'ko', 'en']:
    errors.append(f"translation_target_lang 值異常: {config.translation_target_lang}")

if not isinstance(config.translation_max_retries, int) or config.translation_max_retries < 0:
    errors.append("translation_max_retries 應為非負整數")

if errors:
    print("❌ 配置驗證失敗：")
    for error in errors:
        print(f"   - {error}")
else:
    print("✅ 配置載入成功，所有欄位類型正確")

print("\n" + "=" * 70)
```

執行測試：

```bash
python scripts/test_config.py
```

### 成功標準

#### 自動化驗證

- [ ] `python scripts/test_config.py` 顯示「配置載入成功」
- [ ] `enable_translation` 為 `bool` 類型
- [ ] `translation_target_lang` 預設為 `'zh-TW'`
- [ ] `translation_max_retries` 為 `int` 類型且 >= 0
- [ ] 環境變數未設定時使用正確的預設值

#### 手動驗證

- [ ] 設定 `CRAWLER_ENABLE_TRANSLATION=false`，配置載入後為 `False`
- [ ] 設定 `CRAWLER_TRANSLATION_TARGET_LANG=ja`，配置載入後為 `'ja'`
- [ ] 設定 `CRAWLER_TRANSLATION_MAX_RETRIES=5`，配置載入後為 `5`
- [ ] `.env.example` 包含完整的翻譯配置註解

**完成此階段後，請暫停並確認測試通過後再繼續。**

---

## 階段三：整合到 scheduler.py

### 概述

修改 `scheduler.py` 的 `_format_news_message()` 方法，整合翻譯功能。根據配置決定是否翻譯新聞文本。

### 需要修改的檔案

#### 1. `src/crawler/scheduler.py`

**修改位置 1**：檔案頂部新增導入

在第 14 行後新增：

```python
from .config import CrawlerConfig
from .news_crawler import NewsCrawler
from .translator import get_translator  # 新增
```

**修改位置 2**：`_format_news_message()` 方法（第 82-125 行）

**修改後的完整方法**：

```python
def _format_news_message(self, news: dict) -> str:
    """
    格式化新聞訊息

    參數:
        news: 新聞資料

    回傳:
        格式化後的 Markdown 訊息
    """
    commodity = news['commodity']
    news_id = news['news_id']
    text = news['text']  # 英文原文
    time = news.get('time', 'N/A')

    # ========== 新增：根據配置決定是否翻譯 ==========
    if self.config.enable_translation:
        try:
            # 取得翻譯器實例
            translator = get_translator(
                target_lang=self.config.translation_target_lang,
                max_retries=self.config.translation_max_retries
            )

            # 翻譯新聞文本（失敗時自動降級回原文）
            translated_text = translator.translate(text, fallback_to_original=True)

            logger.debug(
                f"新聞翻譯成功：{commodity} (ID: {news_id}), "
                f"{len(text)} 字元 -> {len(translated_text)} 字元"
            )

        except Exception as e:
            # 翻譯失敗，降級回原文
            logger.error(f"翻譯失敗（{commodity}, ID: {news_id}），使用原文：{e}")
            translated_text = text
    else:
        # 未啟用翻譯，直接使用原文
        translated_text = text
        logger.debug(f"翻譯已停用，使用原文：{commodity} (ID: {news_id})")
    # ================================================

    # 限制文本長度（Telegram 單則訊息最多 4096 字元）
    max_length = 3000
    if len(translated_text) > max_length:
        translated_text = translated_text[:max_length] + "..."

    # 根據商品類型選擇表情符號
    emoji_map = {
        'Gold': '🟡',
        'Silver': '🔘',
        'Bitcoin': '₿',
        'Ethereum': '⟠',
        'Brent': '🛢️',
        'Wti': '🛢️',
        'Copper': '🔶',
        'Corn': '🌽',
        'Coffee': '☕',
        'Wheat': '🌾',
    }
    emoji = emoji_map.get(commodity, '📊')

    message = (
        f"{emoji} **{commodity} 商品新聞** (ID: {news_id})\n"
        f"{'─' * 40}\n\n"
        f"{translated_text}\n\n"  # 使用翻譯後的文本
        f"{'─' * 40}\n"
        f"⏰ {time}"
    )

    return message
```

### 實作步驟

**步驟 1：新增導入**

在 `scheduler.py` 頂部新增 `from .translator import get_translator`

**步驟 2：修改 _format_news_message() 方法**

1. 在 `text = news['text']` 後新增翻譯邏輯區塊
2. 根據 `self.config.enable_translation` 決定是否翻譯
3. 使用 `translated_text` 替代原本的 `text` 變數
4. 新增適當的日誌記錄（debug 和 error 級別）

**步驟 3：驗證邏輯**

確保以下情況都能正確處理：
- 啟用翻譯 + 翻譯成功 → 使用繁體中文
- 啟用翻譯 + 翻譯失敗 → 降級回英文
- 停用翻譯 → 使用英文原文

### 測試方式

**整合測試腳本**：

建立 `tests/test_crawler/test_scheduler_translation.py`：

```python
"""
scheduler.py 翻譯整合測試

測試 _format_news_message() 方法的翻譯功能。
"""

import pytest
from unittest.mock import Mock, patch
from src.crawler.scheduler import CrawlerScheduler
from src.crawler.config import CrawlerConfig


class TestSchedulerTranslation:
    """scheduler.py 翻譯功能整合測試"""

    def create_config(self, enable_translation: bool = True) -> CrawlerConfig:
        """建立測試配置"""
        return CrawlerConfig(
            target_url='https://example.com',
            crawl_interval_minutes=5,
            interval_jitter_seconds=15,
            markets_dir='markets',
            enabled=True,
            telegram_notify_groups=[],
            enable_translation=enable_translation,
            translation_target_lang='zh-TW',
            translation_max_retries=3
        )

    def test_format_message_with_translation_enabled(self):
        """測試啟用翻譯時的訊息格式化"""
        config = self.create_config(enable_translation=True)
        scheduler = CrawlerScheduler(config)

        news = {
            'commodity': 'Gold',
            'news_id': 1,
            'text': 'Gold prices surge amid market volatility',
            'time': '2026-01-02T10:00:00Z'
        }

        message = scheduler._format_news_message(news)

        # 訊息應包含基本元素
        assert 'Gold' in message
        assert 'ID: 1' in message
        assert '2026-01-02T10:00:00Z' in message

        # 應包含翻譯後的文本或原文（降級）
        assert len(message) > 0

    def test_format_message_with_translation_disabled(self):
        """測試停用翻譯時的訊息格式化"""
        config = self.create_config(enable_translation=False)
        scheduler = CrawlerScheduler(config)

        news = {
            'commodity': 'Gold',
            'news_id': 1,
            'text': 'Gold prices surge amid market volatility',
            'time': '2026-01-02T10:00:00Z'
        }

        message = scheduler._format_news_message(news)

        # 訊息應包含英文原文
        assert 'Gold prices surge' in message
        assert 'Gold' in message
        assert 'ID: 1' in message

    def test_format_message_with_long_text(self):
        """測試長文本截斷"""
        config = self.create_config(enable_translation=True)
        scheduler = CrawlerScheduler(config)

        # 建立超過 3000 字元的長文本
        long_text = "Gold prices surge. " * 200  # 約 3800 字元

        news = {
            'commodity': 'Gold',
            'news_id': 1,
            'text': long_text,
            'time': '2026-01-02T10:00:00Z'
        }

        message = scheduler._format_news_message(news)

        # 訊息長度應小於 Telegram 限制
        assert len(message) < 4096

        # 應包含截斷標記
        assert '...' in message

    def test_format_message_with_empty_text(self):
        """測試空文本處理"""
        config = self.create_config(enable_translation=True)
        scheduler = CrawlerScheduler(config)

        news = {
            'commodity': 'Gold',
            'news_id': 1,
            'text': '',
            'time': '2026-01-02T10:00:00Z'
        }

        message = scheduler._format_news_message(news)

        # 訊息應能正常生成
        assert 'Gold' in message
        assert 'ID: 1' in message

    def test_format_message_different_commodities(self):
        """測試不同商品的表情符號"""
        config = self.create_config(enable_translation=False)
        scheduler = CrawlerScheduler(config)

        commodities = {
            'Gold': '🟡',
            'Silver': '🔘',
            'Bitcoin': '₿',
            'Copper': '🔶',
        }

        for commodity, emoji in commodities.items():
            news = {
                'commodity': commodity,
                'news_id': 1,
                'text': f'{commodity} prices surge',
                'time': '2026-01-02T10:00:00Z'
            }

            message = scheduler._format_news_message(news)

            # 應包含對應的表情符號
            assert emoji in message
            assert commodity in message
```

執行測試：

```bash
python -m pytest tests/test_crawler/test_scheduler_translation.py -v
```

**手動端到端測試**：

建立 `scripts/test_end_to_end.py`：

```python
#!/usr/bin/env python3
"""
端到端翻譯測試腳本

模擬完整的新聞格式化流程。
"""

from src.crawler.scheduler import CrawlerScheduler
from src.crawler.config import CrawlerConfig

# 載入配置（從 .env）
config = CrawlerConfig.from_env()

# 建立 scheduler（不需要 telegram_app）
scheduler = CrawlerScheduler(config, telegram_app=None)

# 模擬新聞資料
test_news_list = [
    {
        'commodity': 'Gold',
        'news_id': 1,
        'text': 'Gold prices surge amid market volatility and geopolitical tensions in the Middle East.',
        'time': '2026-01-02T10:00:00Z'
    },
    {
        'commodity': 'Bitcoin',
        'news_id': 2,
        'text': 'Bitcoin breaks resistance level at $100,000 as institutional investors show renewed interest.',
        'time': '2026-01-02T10:05:00Z'
    },
    {
        'commodity': 'Copper',
        'news_id': 3,
        'text': 'Copper demand rises in China as manufacturing activity rebounds in December.',
        'time': '2026-01-02T10:10:00Z'
    }
]

print("=" * 80)
print("端到端翻譯測試")
print("=" * 80)
print(f"翻譯啟用: {config.enable_translation}")
print(f"目標語言: {config.translation_target_lang}")
print(f"重試次數: {config.translation_max_retries}")
print("=" * 80)

# 格式化並顯示每則新聞
for news in test_news_list:
    message = scheduler._format_news_message(news)

    print(f"\n新聞 ID: {news['news_id']}")
    print("-" * 80)
    print(message)
    print("-" * 80)

print("\n" + "=" * 80)
print("測試完成")
print("=" * 80)
```

執行測試：

```bash
# 啟用翻譯
python scripts/test_end_to_end.py

# 停用翻譯測試
# 先修改 .env：CRAWLER_ENABLE_TRANSLATION=false
python scripts/test_end_to_end.py
```

### 成功標準

#### 自動化驗證

- [ ] `python -m pytest tests/test_crawler/test_scheduler_translation.py` 所有測試通過
- [ ] 啟用翻譯時訊息包含翻譯後的文本
- [ ] 停用翻譯時訊息包含英文原文
- [ ] 長文本正確截斷至 3000 字元
- [ ] 空文本不導致錯誤
- [ ] 不同商品顯示正確的表情符號

#### 手動驗證

- [ ] `python scripts/test_end_to_end.py` 顯示繁體中文訊息
- [ ] 設定 `CRAWLER_ENABLE_TRANSLATION=false` 後顯示英文訊息
- [ ] 翻譯後的訊息格式正確（包含商品名、ID、時間）
- [ ] 翻譯失敗時降級回英文（可透過斷網模擬）
- [ ] 日誌中顯示翻譯成功/失敗的 debug/error 訊息

**完成此階段後，請暫停並確認測試通過後再繼續。**

---

## 階段四：測試和驗證

### 概述

執行完整的測試流程，包括單元測試、整合測試和真實環境測試，確保翻譯功能正常運作且不影響現有功能。

### 測試計畫

#### 1. 單元測試

**測試範圍**：
- `translator.py` 的核心翻譯功能
- 重試機制和錯誤處理
- 降級策略

**執行命令**：

```bash
# 測試翻譯模組
python -m pytest tests/test_crawler/test_translator.py -v

# 測試 scheduler 整合
python -m pytest tests/test_crawler/test_scheduler_translation.py -v

# 測試配置載入
python scripts/test_config.py
```

**預期結果**：
- 所有測試通過（綠色 PASSED）
- 無警告或錯誤訊息
- 測試覆蓋率 > 80%（可選）

#### 2. 整合測試

**測試範圍**：
- 完整的訊息格式化流程
- 翻譯功能與 scheduler 的整合
- 配置選項的實際效果

**測試腳本**：

建立 `scripts/integration_test.py`：

```python
#!/usr/bin/env python3
"""
整合測試腳本

測試翻譯功能的完整整合。
"""

import asyncio
from src.crawler.scheduler import CrawlerScheduler
from src.crawler.config import CrawlerConfig
from loguru import logger

async def test_integration():
    """執行整合測試"""

    # 載入配置
    config = CrawlerConfig.from_env()

    print("=" * 80)
    print("整合測試開始")
    print("=" * 80)
    print(f"翻譯啟用: {config.enable_translation}")
    print(f"目標語言: {config.translation_target_lang}")
    print("=" * 80)

    # 建立 scheduler
    scheduler = CrawlerScheduler(config, telegram_app=None)

    # 測試案例
    test_cases = [
        {
            'name': '正常新聞',
            'news': {
                'commodity': 'Gold',
                'news_id': 1,
                'text': 'Gold prices surge amid market volatility.',
                'time': '2026-01-02T10:00:00Z'
            }
        },
        {
            'name': '長文本',
            'news': {
                'commodity': 'Bitcoin',
                'news_id': 2,
                'text': 'Bitcoin prices. ' * 300,  # 超過 3000 字元
                'time': '2026-01-02T10:00:00Z'
            }
        },
        {
            'name': '空文本',
            'news': {
                'commodity': 'Copper',
                'news_id': 3,
                'text': '',
                'time': '2026-01-02T10:00:00Z'
            }
        },
        {
            'name': '特殊字元',
            'news': {
                'commodity': 'Silver',
                'news_id': 4,
                'text': 'Silver @ $30/oz, up 5% today! 🚀',
                'time': '2026-01-02T10:00:00Z'
            }
        }
    ]

    # 執行測試
    results = []
    for case in test_cases:
        print(f"\n測試案例: {case['name']}")
        print("-" * 80)

        try:
            message = scheduler._format_news_message(case['news'])

            # 驗證訊息
            assert len(message) > 0, "訊息不應為空"
            assert len(message) < 4096, "訊息長度應小於 Telegram 限制"
            assert case['news']['commodity'] in message, "應包含商品名稱"

            print(f"✅ 通過")
            print(f"訊息長度: {len(message)} 字元")
            print(f"訊息預覽:\n{message[:200]}...")

            results.append({'case': case['name'], 'status': 'PASSED'})

        except Exception as e:
            print(f"❌ 失敗: {e}")
            results.append({'case': case['name'], 'status': 'FAILED', 'error': str(e)})

    # 顯示測試結果摘要
    print("\n" + "=" * 80)
    print("測試結果摘要")
    print("=" * 80)

    passed = sum(1 for r in results if r['status'] == 'PASSED')
    failed = sum(1 for r in results if r['status'] == 'FAILED')

    for result in results:
        status_icon = "✅" if result['status'] == 'PASSED' else "❌"
        print(f"{status_icon} {result['case']}: {result['status']}")
        if 'error' in result:
            print(f"   錯誤: {result['error']}")

    print(f"\n通過: {passed}/{len(results)}")
    print(f"失敗: {failed}/{len(results)}")
    print("=" * 80)

    return failed == 0

if __name__ == '__main__':
    success = asyncio.run(test_integration())
    exit(0 if success else 1)
```

執行測試：

```bash
python scripts/integration_test.py
```

#### 3. 真實環境測試

**測試範圍**：
- 實際觸發爬蟲並發送 Telegram 訊息
- 驗證翻譯功能在真實場景中的表現

**測試步驟**：

1. **準備環境**：
   ```bash
   # 確保 .env 配置正確
   CRAWLER_ENABLE_TRANSLATION=true
   CRAWLER_TRANSLATION_TARGET_LANG=zh-TW
   CRAWLER_NOTIFY_GROUPS=你的群組ID
   ```

2. **啟動 Bot**：
   ```bash
   python scripts/run_bot.py
   ```

3. **手動觸發爬蟲**：
   在 Telegram 群組中發送：
   ```
   /crawl_now
   ```

4. **檢查 Telegram 訊息**：
   - 訊息應為繁體中文
   - 格式正確（包含商品名、ID、時間）
   - 表情符號顯示正確

5. **檢查保存的檔案**：
   ```bash
   # 檢視 markets/ 目錄下的最新檔案
   cat markets/Gold/news_YYYYMMDD_HHMMSS.txt
   ```
   - 檔案內容應為英文原文
   - 檔案格式不變

6. **測試停用翻譯**：
   ```bash
   # 修改 .env
   CRAWLER_ENABLE_TRANSLATION=false

   # 重啟 Bot
   python scripts/run_bot.py

   # 在 Telegram 觸發
   /crawl_now
   ```
   - 訊息應為英文原文

7. **測試錯誤處理**：
   - 斷網狀態下觸發 `/crawl_now`
   - 應收到英文訊息（降級）
   - Bot 不應崩潰

#### 4. 效能測試

**測試範圍**：
- 翻譯速度
- 對爬蟲整體效能的影響

**測試腳本**：

建立 `scripts/performance_test.py`：

```python
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
```

執行測試：

```bash
python scripts/performance_test.py
```

**預期結果**：
- 短文本（< 100 字元）：< 1 秒
- 中等文本（< 1000 字元）：< 2 秒
- 長文本（< 3000 字元）：< 3 秒

### 驗收標準

#### 自動化驗證（必須全部通過）

- [ ] `python -m pytest tests/test_crawler/ -v` 所有測試通過
- [ ] `python scripts/test_config.py` 配置載入成功
- [ ] `python scripts/integration_test.py` 整合測試通過
- [ ] `python scripts/performance_test.py` 效能符合預期
- [ ] 無 Python 語法錯誤或導入錯誤
- [ ] 日誌中無未處理的例外

#### 手動驗證（必須全部通過）

- [ ] Telegram 訊息顯示繁體中文（啟用翻譯時）
- [ ] Telegram 訊息顯示英文原文（停用翻譯時）
- [ ] `markets/` 目錄下的檔案為英文原文
- [ ] 訊息格式正確（商品名、ID、時間、表情符號）
- [ ] 長文本正確截斷（不超過 3000 字元）
- [ ] 空文本不導致錯誤
- [ ] 斷網時降級回英文，Bot 不崩潰
- [ ] 翻譯速度可接受（< 3 秒/則）

#### 回歸測試（確保現有功能不受影響）

- [ ] 爬蟲定時任務正常運行
- [ ] 檔案保存功能正常（格式、路徑、內容不變）
- [ ] Bot 其他指令正常運作（`/help`, `/status` 等）
- [ ] 日誌記錄正常
- [ ] 無新增的記憶體洩漏或效能問題

### 錯誤處理測試清單

**測試各種錯誤情況**：

- [ ] **網路錯誤**：斷網時翻譯失敗降級回原文
- [ ] **速率限制**：模擬 429 錯誤，驗證重試機制
- [ ] **超長文本**：超過 5000 字元的文本不導致崩潰
- [ ] **無效語言代碼**：設定錯誤的語言代碼時有適當錯誤訊息
- [ ] **空配置**：未設定環境變數時使用預設值
- [ ] **Telegram 發送失敗**：Telegram API 錯誤不影響檔案保存

### 測試完成後的清理工作

**完成所有測試後**：

1. **確認測試檔案**：
   - 所有測試腳本已建立
   - 測試資料已清理（如有）

2. **更新文檔**：
   - README 中新增翻譯功能說明
   - 配置指南包含翻譯相關環境變數

3. **檢查日誌**：
   - 移除測試期間的 debug 日誌（若有）
   - 確保生產環境日誌級別正確

4. **提交變更**（可選）：
   ```bash
   git add .
   git status
   # 檢查變更內容
   ```

---

## 測試策略總結

### 測試層級

| 測試類型 | 工具 | 目標 | 預估時間 |
|---------|------|------|---------|
| 單元測試 | pytest | 翻譯模組核心功能 | 10 分鐘 |
| 整合測試 | 自定義腳本 | scheduler 整合 | 15 分鐘 |
| 真實環境測試 | Telegram Bot | 端到端流程 | 20 分鐘 |
| 效能測試 | 自定義腳本 | 翻譯速度 | 10 分鐘 |
| 回歸測試 | 手動測試 | 現有功能 | 15 分鐘 |

**總測試時間**：約 70 分鐘（1 小時 10 分鐘）

### 測試優先級

**P0（必須）**：
- 翻譯功能基本運作
- 檔案保存不受影響
- Bot 不崩潰

**P1（重要）**：
- 錯誤降級策略生效
- 配置選項正常運作
- 效能符合預期

**P2（可選）**：
- 重試機制在真實場景中的表現
- 長文本處理優化
- 日誌訊息完整性

---

## 潛在風險和解決方案

### 技術風險

| 風險 | 影響 | 機率 | 解決方案 |
|------|------|------|---------|
| **速率限制** | 翻譯失敗 | 低 | 重試機制 + 降級策略 |
| **網路不穩定** | 翻譯失敗 | 中 | 重試機制 + 降級策略 |
| **翻譯質量不佳** | 使用者體驗差 | 中 | 未來可建立術語字典 |
| **長文本處理** | 翻譯失敗或截斷 | 低 | 簡單截斷（目前）+ 未來優化 |
| **依賴套件問題** | 安裝失敗 | 低 | 明確版本號 + 測試 |

### 營運風險

| 風險 | 影響 | 機率 | 解決方案 |
|------|------|------|---------|
| **配置錯誤** | 功能異常 | 中 | 預設值 + 詳細註解 |
| **效能影響** | 爬蟲變慢 | 低 | 效能測試 + 監控 |
| **向後相容性** | 現有功能損壞 | 低 | 回歸測試 + 可選功能 |

### 風險緩解措施

**主動措施**：
1. **降級策略**：翻譯失敗時自動返回英文原文
2. **可選功能**：可透過配置停用翻譯
3. **完整測試**：多層級測試確保穩定性
4. **日誌記錄**：記錄所有翻譯失敗情況

**被動措施**：
1. **監控**：定期檢查日誌中的翻譯失敗率
2. **快速回退**：設定 `CRAWLER_ENABLE_TRANSLATION=false` 即可停用
3. **文檔**：詳細的配置指南和故障排除步驟

---

## 效能考量

### 翻譯延遲

**單則新聞翻譯時間**：
- 短文本（< 100 字元）：約 0.5-1 秒
- 中等文本（100-500 字元）：約 1-2 秒
- 長文本（500-3000 字元）：約 2-3 秒

**對爬蟲的影響**：
- 每次爬取約 1-10 則新聞
- 總翻譯時間：約 5-30 秒
- 爬蟲間隔：5 分鐘
- **結論**：翻譯延遲可接受，不影響整體流程

### 優化建議（未來）

**階段一（當前實作）**：
- ✅ 基本翻譯功能
- ✅ 重試機制
- ✅ 降級策略

**階段二（未來優化）**：
- ⏳ 翻譯緩存（減少重複翻譯）
- ⏳ 批次翻譯（提高效率）
- ⏳ 非同步翻譯（不阻塞主流程）

**階段三（進階優化）**：
- ⏳ 專業術語字典（提高翻譯品質）
- ⏳ 長文本分段翻譯（保持句子完整性）
- ⏳ 整合 DeepL API（更高翻譯品質）

---

## 參考資料

### 研究文檔

- [deep-translator 整合商品新聞爬蟲翻譯功能研究](thoughts/shared/research/2026-01-02-deep-translator-integration-research.md)

### 外部資源

- [deep-translator PyPI](https://pypi.org/project/deep-translator/)
- [deep-translator 官方文檔](https://deep-translator.readthedocs.io/en/latest/README.html)
- [deep-translator GitHub](https://github.com/nidhaloff/deep-translator)
- [Google Cloud Translation API 語言支援](https://cloud.google.com/translate/docs/languages)

### 相關檔案

- `src/crawler/scheduler.py`：訊息發送邏輯
- `src/crawler/news_crawler.py`：新聞爬取邏輯
- `src/crawler/config.py`：配置管理
- `requirements.txt`：依賴套件清單
- `.env.example`：環境變數範例

---

## 實作時間估計

### 各階段時間分配

| 階段 | 主要任務 | 預估時間 |
|------|---------|---------|
| **階段一** | 建立翻譯模組 + 基本測試 | 45 分鐘 |
| **階段二** | 配置管理 + 配置測試 | 20 分鐘 |
| **階段三** | scheduler 整合 + 整合測試 | 30 分鐘 |
| **階段四** | 完整測試 + 驗證 | 70 分鐘 |
| **額外時間** | 文檔、除錯、優化 | 30 分鐘 |

**總計**：約 3 小時 15 分鐘

### 時間緩衝

- **最佳情況**：2 小時（所有步驟順利）
- **預期情況**：3 小時（包含測試和小問題處理）
- **最壞情況**：4 小時（需要除錯或優化）

---

## 實作檢查清單

### 前置準備

- [ ] 閱讀完整研究報告
- [ ] 理解現有代碼結構
- [ ] 準備測試環境（Telegram Bot、測試群組）

### 階段一：基礎翻譯模組

- [ ] 更新 `requirements.txt` 新增 deep-translator
- [ ] 執行 `pip install deep-translator>=1.11.0`
- [ ] 建立 `src/crawler/translator.py` 檔案
- [ ] 實作 `NewsTranslator` 類別
- [ ] 實作重試機制（`_translate_with_retry`）
- [ ] 實作指數退避計算（`_calculate_backoff_delay`）
- [ ] 實作單例模式（`get_translator`）
- [ ] 建立單元測試 `tests/test_crawler/test_translator.py`
- [ ] 建立手動測試腳本 `scripts/test_translator.py`
- [ ] 執行測試並確認通過

### 階段二：配置管理

- [ ] 修改 `src/crawler/config.py` 新增翻譯配置欄位
- [ ] 在 `from_env()` 方法中新增環境變數讀取
- [ ] 更新 `.env.example` 新增翻譯配置區塊
- [ ] （可選）更新本地 `.env` 檔案
- [ ] 建立配置測試腳本 `scripts/test_config.py`
- [ ] 執行測試並確認配置載入正確

### 階段三：整合到 scheduler

- [ ] 修改 `src/crawler/scheduler.py` 新增導入
- [ ] 修改 `_format_news_message()` 方法整合翻譯
- [ ] 新增適當的日誌記錄
- [ ] 建立 scheduler 整合測試
- [ ] 建立端到端測試腳本 `scripts/test_end_to_end.py`
- [ ] 執行測試並確認整合成功

### 階段四：測試和驗證

- [ ] 執行所有單元測試
- [ ] 執行所有整合測試
- [ ] 建立真實環境測試計畫
- [ ] 執行真實環境測試（Telegram Bot）
- [ ] 執行效能測試
- [ ] 執行回歸測試
- [ ] 執行錯誤處理測試
- [ ] 記錄測試結果
- [ ] 修復發現的問題（如有）

### 文檔和清理

- [ ] 更新 README（可選）
- [ ] 檢查並清理測試資料
- [ ] 確認日誌級別正確
- [ ] 檢查程式碼風格（可選）
- [ ] 準備 commit message（如需提交）

### 最終驗證

- [ ] 所有自動化測試通過
- [ ] 所有手動驗證完成
- [ ] 回歸測試確認現有功能正常
- [ ] 效能符合預期
- [ ] 文檔完整且準確

---

## 成功標準

### 功能完整性

✅ **必須達成**：
1. Telegram 訊息自動翻譯為繁體中文
2. 檔案保存維持英文原文
3. 翻譯失敗時自動降級回英文
4. 可透過配置啟用/停用翻譯
5. Bot 不崩潰，現有功能不受影響

✅ **建議達成**：
1. 重試機制在速率限制時生效
2. 長文本正確截斷
3. 效能影響可接受（< 3 秒/則）
4. 日誌記錄完整（debug、info、error 級別）

### 品質標準

✅ **程式碼品質**：
- 遵循現有專案的程式碼風格
- 函式和類別有完整的 docstring
- 變數命名清晰易懂
- 無未處理的例外

✅ **測試覆蓋率**：
- 核心功能有單元測試
- 整合點有整合測試
- 錯誤處理有測試覆蓋

✅ **文檔完整性**：
- 配置選項有清晰說明
- 使用範例完整
- 故障排除指南（可選）

---

## 後續優化方向

### 短期優化（1-2 週內）

1. **監控翻譯品質**
   - 收集使用者回饋
   - 記錄翻譯失敗案例
   - 分析常見的翻譯錯誤

2. **效能監控**
   - 記錄翻譯速度統計
   - 監控速率限制觸發次數
   - 觀察對整體爬蟲效能的影響

### 中期優化（1-2 個月內）

1. **翻譯緩存**
   - 實作 SQLite 翻譯緩存
   - 減少重複翻譯
   - 提高翻譯速度

2. **專業術語字典**
   - 建立商品領域術語對照表
   - 後處理修正常見誤譯
   - 提高翻譯專業度

3. **長文本處理優化**
   - 實作分段翻譯（保持句子完整性）
   - 處理特殊格式（列表、引用等）

### 長期優化（3 個月以上）

1. **整合其他翻譯 API**
   - 整合 DeepL API（更高品質）
   - 支援多翻譯引擎切換
   - 實作翻譯品質比較

2. **多語言支援**
   - 支援日文、韓文等其他語言
   - 可配置多個目標語言
   - 同時發送多語言訊息

3. **AI 輔助翻譯優化**
   - 使用 Claude API 進行專業術語翻譯
   - 上下文感知翻譯
   - 翻譯品質自動評估

---

## 結論

本實作計畫提供了完整、可執行的步驟，將 deep-translator 整合到現有的商品新聞爬蟲系統中。計畫採用分階段實作方式，每個階段都有明確的目標、步驟、測試方式和成功標準。

### 核心特點

✅ **漸進式實作**：分為四個階段，每階段完成後暫停驗證
✅ **完整測試**：涵蓋單元測試、整合測試、真實環境測試
✅ **穩健設計**：重試機制、降級策略、錯誤處理
✅ **可配置性**：所有功能可透過環境變數控制
✅ **向後相容**：不影響現有功能，可選擇性啟用

### 預期成果

實作完成後，系統將具備以下能力：

1. **自動翻譯**：英文新聞自動翻譯為繁體中文發送到 Telegram
2. **檔案保存不變**：保存的檔案仍為英文原文
3. **穩健運行**：翻譯失敗時自動降級，不阻塞通知流程
4. **靈活配置**：可輕鬆啟用/停用翻譯功能

### 下一步行動

1. 確認理解整個計畫
2. 準備開發環境（安裝依賴、配置 .env）
3. 從階段一開始，逐步實作
4. 每個階段完成後執行測試並確認通過
5. 記錄問題和解決方案（若有）

---

**計畫制定日期**：2026-01-02
**預估總時間**：2-3 小時
**建議優先級**：中（功能增強，非核心必要）
**狀態**：待實作

---
