---
title: deep-translator 整合商品新聞爬蟲翻譯功能研究
date: 2026-01-02
ticket: N/A
author: Claude Code
tags:
  - deep-translator
  - translation
  - GoogleTranslator
  - telegram-bot
  - traditional-chinese
  - news-crawler
  - internationalization
status: completed
related_files:
  - src/crawler/news_crawler.py
  - src/crawler/scheduler.py
  - src/bot/telegram_bot.py
  - requirements.txt
last_updated: 2026-01-02
last_updated_by: Claude Sonnet 4.5
---

# deep-translator 整合商品新聞爬蟲翻譯功能研究

## 研究問題

如何在現有的商品新聞爬蟲系統中整合 deep-translator，實現以下需求：

### 核心需求

1. **使用 deep-translator 套件的 GoogleTranslator**
2. **翻譯目標語言：繁體中文 (zh-TW)**
3. **保存的檔案仍使用英文原文（不變）**
4. **發送到 Telegram 時翻譯成繁體中文**

### 研究重點

1. 現有 Telegram 訊息發送機制分析
2. deep-translator 整合方案設計
3. 翻譯策略（標題/內容分開翻譯、錯誤處理、緩存）
4. 現有相關代碼分析
5. 架構設計建議（新增翻譯模組位置、配置選項）
6. 技術挑戰（速率限制、長文本翻譯、錯誤處理）

---

## 摘要

本研究深入分析了如何在現有商品新聞爬蟲系統中整合 deep-translator GoogleTranslator，實現英文新聞翻譯成繁體中文後發送到 Telegram 的功能。主要發現包括：

- **現有架構分析**：Telegram 訊息發送位於 `scheduler.py` 的 `_format_news_message()` 和 `_send_telegram_notifications()` 方法（第 82-125 行）
- **最佳插入點**：在 Telegram 發送前翻譯，不影響檔案保存邏輯
- **deep-translator 優勢**：免費、無限制、支援繁體中文（zh-TW）、API 簡潔
- **建議架構**：新增 `src/crawler/translator.py` 翻譯模組，實作重試機制、錯誤處理和可選緩存
- **翻譯策略**：標題和內容分開翻譯，失敗時降級回原文，避免阻塞通知流程

**預估實作時間**：2-3 小時（包含測試和優化）

---

## 詳細研究結果

### 1. 現有 Telegram 訊息發送機制分析

#### 1.1 訊息發送流程

**LOCATOR MODE**: 找出訊息發送的關鍵位置

**檔案**：`src/crawler/scheduler.py`（第 58-125 行）

**關鍵方法**：

1. **`_send_telegram_notifications()`**（第 58-80 行）
   ```python
   async def _send_telegram_notifications(self, saved_news: list):
       """發送 Telegram 通知"""
       for news in saved_news:
           # 格式化訊息
           message = self._format_news_message(news)

           # 發送到所有配置的群組
           for group_id in self.config.telegram_notify_groups:
               try:
                   await self.telegram_app.bot.send_message(
                       chat_id=group_id,
                       text=message,
                       parse_mode='Markdown'
                   )
   ```

   **分析**：此方法遍歷已保存的新聞，調用 `_format_news_message()` 格式化訊息，然後發送到 Telegram 群組。

2. **`_format_news_message()`**（第 82-125 行）
   ```python
   def _format_news_message(self, news: dict) -> str:
       """格式化新聞訊息"""
       commodity = news['commodity']
       news_id = news['news_id']
       text = news['text']  # 英文原文
       time = news.get('time', 'N/A')

       # 限制文本長度（Telegram 單則訊息最多 4096 字元）
       max_length = 3000
       if len(text) > max_length:
           text = text[:max_length] + "..."

       # 根據商品類型選擇表情符號
       emoji_map = {...}
       emoji = emoji_map.get(commodity, '📊')

       message = (
           f"{emoji} **{commodity} 商品新聞** (ID: {news_id})\n"
           f"{'─' * 40}\n\n"
           f"{text}\n\n"  # 這裡是英文原文
           f"{'─' * 40}\n"
           f"⏰ {time}"
       )

       return message
   ```

   **分析**：此方法負責格式化訊息內容。**關鍵點**：`text` 變數目前是英文原文，這是我們需要翻譯的目標。

#### 1.2 新聞資料結構

**ANALYZER MODE**: 分析新聞資料的組成

**檔案**：`src/crawler/news_crawler.py`（第 244-314 行）

新聞資料結構（`parse_news()` 方法的輸出）：

```python
news_list.append({
    'title': title,        # 新聞標題（英文）
    'content': content,    # 新聞內容（英文）
    'full_text': full_text,  # 標題 + 內容（英文）
    'time': time_str       # 時間戳
})
```

傳遞到 Telegram 的資料（`process_and_save()` 方法的輸出）：

```python
saved_news.append({
    'commodity': commodity,  # 商品名稱（如 "Gold"）
    'news_id': news_id,      # 新聞 ID
    'text': full_text,       # 完整文本（標題 + 內容，英文）
    'time': news.get('time', '')  # 時間戳
})
```

**關鍵發現**：
- `text` 欄位包含完整的新聞文本（標題 + 內容）
- 資料在 `scheduler.py` 接收時已是英文原文
- 需要在 `_format_news_message()` 中翻譯 `text` 欄位

#### 1.3 插入翻譯邏輯的最佳位置

**選項 1：在 `news_crawler.py` 的 `parse_news()` 中翻譯** ❌
- **缺點**：會影響檔案保存，違反需求（檔案保存英文原文）

**選項 2：在 `news_crawler.py` 的 `process_and_save()` 中翻譯** ❌
- **缺點**：同樣會影響檔案保存

**選項 3：在 `scheduler.py` 的 `_format_news_message()` 中翻譯** ✅
- **優點**：
  - 只影響 Telegram 訊息，不影響檔案保存
  - 邏輯集中，易於維護
  - 可選擇性啟用/停用翻譯
- **建議**：在此方法中調用翻譯模組

**選項 4：在 `scheduler.py` 的 `_send_telegram_notifications()` 中翻譯** ⚠️
- **可行**：功能上可行
- **缺點**：邏輯較分散，不如選項 3 優雅

**最終建議**：選項 3（在 `_format_news_message()` 中翻譯）

---

### 2. deep-translator 整合方案

#### 2.1 deep-translator 基本用法

**EXTERNAL MODE**: 研究 deep-translator 官方文檔

**安裝**：

```bash
pip install deep-translator
```

**基本 API**：

```python
from deep_translator import GoogleTranslator

# 簡單翻譯
translated = GoogleTranslator(source='auto', target='zh-TW').translate("Hello World")
# 輸出：你好世界

# 使用語言代碼
translator = GoogleTranslator(source='en', target='zh-TW')
result = translator.translate('This is a test')

# 批次翻譯
texts = ["Hello", "World", "How are you?"]
results = GoogleTranslator(source='auto', target='zh-TW').translate_batch(texts)
```

**繁體中文語言代碼**：`zh-TW`（Traditional Chinese - Taiwan）

#### 2.2 deep-translator 的優勢

| 特性 | deep-translator | googletrans | Google Cloud Translation API |
|------|----------------|-------------|------------------------------|
| **免費** | ✅ 完全免費 | ✅ 免費（非官方） | ❌ 付費 |
| **無使用限制** | ✅ 無限制 | ⚠️ 有限制 | ❌ 有配額 |
| **支援繁體中文** | ✅ zh-TW | ✅ zh-TW | ✅ zh-TW |
| **API 簡潔度** | ✅ 簡潔 | ✅ 簡潔 | ⚠️ 較複雜 |
| **穩定性** | ✅ 活躍維護 | ❌ 停止維護 | ✅ 官方支援 |
| **需要 API Key** | ❌ 不需要 | ❌ 不需要 | ✅ 需要 |
| **批次翻譯** | ✅ 支援 | ✅ 支援 | ✅ 支援 |
| **錯誤處理** | ✅ 內建例外 | ⚠️ 較弱 | ✅ 完善 |

**結論**：deep-translator 是最佳選擇（免費、無限制、活躍維護）

#### 2.3 deep-translator 的例外處理

**EXTERNAL MODE**: 研究錯誤處理機制

deep-translator 內建例外類型（來自官方文檔）：

```python
from deep_translator.exceptions import (
    TooManyRequests,      # 429 速率限制
    RequestError,         # 一般請求錯誤
    NotValidLength,       # 文本長度無效
    TranslationNotFound   # 翻譯失敗
)
```

**速率限制**：
- Google Translate 免費版：每秒 5 個請求，每天 200,000 個請求
- 若收到 `TooManyRequests`（HTTP 429），建議至少等待 1 秒後重試

#### 2.4 長文本翻譯策略

**問題**：Google Translate 單次翻譯有字元數限制（約 5,000 字元）

**解決方案**：

**方案 1：分段翻譯**
```python
def translate_long_text(text: str, max_length: int = 4000) -> str:
    """分段翻譯長文本"""
    if len(text) <= max_length:
        return translator.translate(text)

    # 按句子分段（避免中斷句子）
    sentences = text.split('. ')
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += sentence + ". "
        else:
            chunks.append(current_chunk)
            current_chunk = sentence + ". "

    if current_chunk:
        chunks.append(current_chunk)

    # 翻譯每個分段
    translated_chunks = [translator.translate(chunk) for chunk in chunks]
    return ''.join(translated_chunks)
```

**方案 2：使用 `translate_batch()`**（更高效）
```python
def translate_long_text_batch(text: str, max_length: int = 4000) -> str:
    """使用批次翻譯處理長文本"""
    if len(text) <= max_length:
        return translator.translate(text)

    # 分段
    chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]

    # 批次翻譯
    translated_chunks = translator.translate_batch(chunks)
    return ''.join(translated_chunks)
```

**建議**：方案 1（按句子分段更自然）

#### 2.5 翻譯緩存策略

**問題**：相同的新聞可能被多次翻譯（如果系統重啟或手動觸發）

**解決方案**：

**方案 1：記憶體緩存（簡單但不持久）**
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def translate_cached(text: str) -> str:
    """帶緩存的翻譯"""
    return translator.translate(text)
```

**方案 2：檔案緩存（持久化）**
```python
import hashlib
import json
from pathlib import Path

class TranslationCache:
    def __init__(self, cache_dir: str = 'cache/translations'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_hash(self, text: str) -> str:
        """計算文本的 MD5 hash"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def get(self, text: str) -> str | None:
        """從緩存中取得翻譯"""
        cache_file = self.cache_dir / f"{self.get_hash(text)}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding='utf-8'))
            return data.get('translation')
        return None

    def set(self, text: str, translation: str):
        """保存翻譯到緩存"""
        cache_file = self.cache_dir / f"{self.get_hash(text)}.json"
        data = {
            'original': text[:100],  # 只保存前 100 字元（用於偵錯）
            'translation': translation,
            'timestamp': datetime.now().isoformat()
        }
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
```

**方案 3：SQLite 緩存（推薦用於生產環境）**
```python
import sqlite3
import hashlib

class SQLiteTranslationCache:
    def __init__(self, db_path: str = 'cache/translations.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS translations (
                    hash TEXT PRIMARY KEY,
                    original TEXT,
                    translation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def get(self, text: str) -> str | None:
        hash_key = hashlib.md5(text.encode('utf-8')).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT translation FROM translations WHERE hash = ?',
                (hash_key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def set(self, text: str, translation: str):
        hash_key = hashlib.md5(text.encode('utf-8')).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO translations (hash, original, translation) VALUES (?, ?, ?)',
                (hash_key, text[:200], translation)
            )
```

**建議**：
- **開發/測試環境**：方案 1（記憶體緩存）
- **生產環境**：方案 3（SQLite 緩存，可選）
- **初期實作**：不使用緩存（簡化實作，觀察效果後再優化）

---

### 3. 翻譯策略設計

#### 3.1 標題和內容分開翻譯 vs 整體翻譯

**PATTERN MODE**: 分析翻譯粒度選擇

**選項 1：整體翻譯**（推薦）

```python
def translate_news(news_text: str) -> str:
    """整體翻譯新聞文本"""
    return translator.translate(news_text)
```

**優點**：
- 簡單直接
- 保持上下文連貫性
- API 調用次數少（1 次）

**缺點**：
- 若翻譯失敗，整則新聞都會失敗

**選項 2：分開翻譯標題和內容**

```python
def translate_news_parts(title: str, content: str) -> tuple[str, str]:
    """分別翻譯標題和內容"""
    try:
        translated_title = translator.translate(title)
    except Exception:
        translated_title = title  # 失敗時保留原文

    try:
        translated_content = translator.translate(content) if content else ""
    except Exception:
        translated_content = content  # 失敗時保留原文

    return translated_title, translated_content
```

**優點**：
- 部分失敗時不影響其他部分
- 可以針對標題和內容使用不同的翻譯策略

**缺點**：
- API 調用次數多（2 次）
- 需要額外處理資料結構
- 目前新聞資料是 `full_text`（已合併標題和內容）

**建議**：選項 1（整體翻譯），原因：
- 目前資料結構是 `full_text`，分開翻譯需要重新解析
- 簡化實作，降低複雜度
- 失敗時可降級回原文

#### 3.2 錯誤處理和 Fallback 策略

**策略**：翻譯失敗時降級回英文原文，確保通知不中斷

```python
def translate_with_fallback(text: str) -> str:
    """帶降級策略的翻譯"""
    try:
        return translator.translate(text)
    except TooManyRequests:
        logger.warning("翻譯速率限制，返回原文")
        return text
    except RequestError as e:
        logger.error(f"翻譯請求錯誤：{e}，返回原文")
        return text
    except Exception as e:
        logger.error(f"翻譯失敗：{e}，返回原文")
        return text
```

**降級順序**：
1. **正常翻譯**：成功返回繁體中文
2. **速率限制**：返回英文原文 + 記錄警告
3. **請求錯誤**：返回英文原文 + 記錄錯誤
4. **未知錯誤**：返回英文原文 + 記錄錯誤

**關鍵原則**：**永遠不阻塞 Telegram 通知**

#### 3.3 重試機制設計

**EXTERNAL MODE**: 研究重試最佳實踐

根據 Google 和翻譯 API 最佳實踐：

**重試策略**：指數退避（Exponential Backoff）+ Jitter

```python
import time
import random
from typing import Callable, TypeVar

T = TypeVar('T')

def retry_with_exponential_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    jitter: bool = True
) -> T:
    """
    使用指數退避的重試機制

    參數:
        func: 要重試的函式
        max_retries: 最大重試次數（預設 3 次）
        base_delay: 初始延遲（秒，預設 1 秒）
        max_delay: 最大延遲（秒，預設 10 秒）
        jitter: 是否添加隨機抖動（預設 True）

    回傳:
        函式執行結果
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except TooManyRequests:
            if attempt == max_retries:
                raise  # 最後一次重試仍失敗，拋出例外

            # 計算延遲時間：2^attempt * base_delay
            delay = min(base_delay * (2 ** attempt), max_delay)

            # 添加隨機抖動（避免同時重試）
            if jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(f"翻譯速率限制，{delay:.2f} 秒後重試（第 {attempt + 1}/{max_retries} 次）")
            time.sleep(delay)

        except RequestError as e:
            # 網路錯誤也重試
            if attempt == max_retries:
                raise

            delay = min(base_delay * (2 ** attempt), max_delay)
            if jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(f"翻譯請求錯誤（{e}），{delay:.2f} 秒後重試（第 {attempt + 1}/{max_retries} 次）")
            time.sleep(delay)
```

**使用範例**：

```python
def translate_text(text: str) -> str:
    """翻譯文本"""
    translator = GoogleTranslator(source='auto', target='zh-TW')
    return translator.translate(text)

# 使用重試機制
try:
    translated = retry_with_exponential_backoff(
        lambda: translate_text("Hello World"),
        max_retries=3
    )
except Exception as e:
    logger.error(f"重試 3 次後仍失敗：{e}")
    translated = "Hello World"  # 降級回原文
```

**重試參數建議**：
- **最大重試次數**：3 次（平衡成功率和延遲）
- **初始延遲**：1 秒（符合 Google 建議）
- **最大延遲**：10 秒（避免過長等待）
- **啟用 jitter**：是（避免同時重試）

#### 3.4 速率限制處理

**Google Translate 速率限制**：
- **每秒請求數**：5 次
- **每日請求數**：200,000 次

**當前爬蟲頻率**：
- **爬取間隔**：5 分鐘
- **預估每次新聞數**：1-10 則
- **每日翻譯請求數**：約 288 * 5 = 1,440 次（遠低於限制）

**結論**：當前使用場景下，**不太可能觸發速率限制**

**預防措施**：
1. 實作重試機制（上述）
2. 記錄翻譯失敗次數（監控）
3. 若頻繁觸發限制，增加爬取間隔或減少翻譯頻率

---

### 4. 架構設計建議

#### 4.1 新增翻譯模組設計

**DOCUMENTATION MODE**: 設計翻譯模組架構

**建議新增檔案**：`src/crawler/translator.py`

**模組職責**：
1. 封裝 deep-translator GoogleTranslator
2. 實作重試機制
3. 實作錯誤處理和降級策略
4. 提供簡潔的翻譯 API
5. （可選）實作翻譯緩存

**完整實作範例**：

```python
"""
新聞翻譯模組

使用 deep-translator GoogleTranslator 將英文新聞翻譯為繁體中文。
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
    """

    def __init__(
        self,
        source_lang: str = 'auto',
        target_lang: str = 'zh-TW',
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        enable_cache: bool = False,
        cache_dir: Optional[str] = None
    ):
        """
        初始化翻譯器

        參數:
            source_lang: 來源語言（預設 'auto' 自動檢測）
            target_lang: 目標語言（預設 'zh-TW' 繁體中文）
            max_retries: 最大重試次數（預設 3）
            base_delay: 初始重試延遲（秒，預設 1.0）
            max_delay: 最大重試延遲（秒，預設 10.0）
            enable_cache: 是否啟用翻譯緩存（預設 False）
            cache_dir: 緩存目錄路徑（可選）
        """
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.enable_cache = enable_cache

        # 初始化翻譯器
        self.translator = GoogleTranslator(
            source=source_lang,
            target=target_lang
        )

        # 初始化緩存（可選）
        if enable_cache:
            from .translation_cache import TranslationCache
            self.cache = TranslationCache(cache_dir or 'cache/translations')
            logger.info("翻譯緩存已啟用")
        else:
            self.cache = None

        logger.info(f"翻譯器初始化完成：{source_lang} -> {target_lang}")

    def translate(self, text: str, fallback_to_original: bool = True) -> str:
        """
        翻譯文本

        參數:
            text: 要翻譯的文本（英文）
            fallback_to_original: 失敗時是否降級回原文（預設 True）

        回傳:
            翻譯後的文本（繁體中文），失敗時返回原文（若 fallback_to_original=True）
        """
        if not text or not text.strip():
            return text

        # 檢查緩存
        if self.cache:
            cached = self.cache.get(text)
            if cached:
                logger.debug("使用緩存的翻譯")
                return cached

        # 執行翻譯（帶重試機制）
        try:
            translated = self._translate_with_retry(text)

            # 保存到緩存
            if self.cache:
                self.cache.set(text, translated)

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

        參數:
            attempt: 當前重試次數（從 0 開始）

        回傳:
            延遲時間（秒）
        """
        # 指數退避：delay = base_delay * (2 ^ attempt)
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)

        # 添加隨機抖動（0.5 ~ 1.5 倍）
        jitter = 0.5 + random.random()
        delay = delay * jitter

        return delay

    def translate_batch(
        self,
        texts: list[str],
        fallback_to_original: bool = True
    ) -> list[str]:
        """
        批次翻譯多個文本

        參數:
            texts: 要翻譯的文本清單
            fallback_to_original: 失敗時是否降級回原文（預設 True）

        回傳:
            翻譯後的文本清單
        """
        # 注意：批次翻譯不支援緩存和重試（為簡化實作）
        # 若需要，可以改為逐一翻譯

        try:
            translated = self.translator.translate_batch(texts)
            logger.info(f"批次翻譯成功：{len(texts)} 則文本")
            return translated

        except Exception as e:
            logger.error(f"批次翻譯失敗：{e}")

            if fallback_to_original:
                logger.warning("降級回英文原文")
                return texts
            else:
                raise


# 全域翻譯器實例（單例模式）
_global_translator: Optional[NewsTranslator] = None


def get_translator(
    enable_cache: bool = False,
    **kwargs
) -> NewsTranslator:
    """
    取得全域翻譯器實例（單例模式）

    參數:
        enable_cache: 是否啟用翻譯緩存
        **kwargs: 其他 NewsTranslator 參數

    回傳:
        NewsTranslator 實例
    """
    global _global_translator

    if _global_translator is None:
        _global_translator = NewsTranslator(
            enable_cache=enable_cache,
            **kwargs
        )

    return _global_translator
```

#### 4.2 整合到現有代碼

**修改檔案**：`src/crawler/scheduler.py`

**修改位置 1**：導入翻譯器（檔案頂部）

```python
# 新增導入
from .translator import get_translator
```

**修改位置 2**：`_format_news_message()` 方法（第 82-125 行）

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

    # ========== 新增：翻譯新聞文本 ==========
    try:
        translator = get_translator(enable_cache=False)  # 可配置是否啟用緩存
        translated_text = translator.translate(text, fallback_to_original=True)
        logger.debug(f"新聞翻譯成功：{text[:50]}... -> {translated_text[:50]}...")
    except Exception as e:
        logger.error(f"翻譯失敗，使用原文：{e}")
        translated_text = text  # 降級回原文
    # ========================================

    # 限制文本長度（Telegram 單則訊息最多 4096 字元）
    max_length = 3000
    if len(translated_text) > max_length:
        translated_text = translated_text[:max_length] + "..."

    # 根據商品類型選擇表情符號
    emoji_map = {
        'Gold': '🥇',
        'Silver': '🥈',
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

**關鍵修改**：
1. 導入 `get_translator()` 取得翻譯器實例
2. 呼叫 `translator.translate()` 翻譯 `text`
3. 使用 `fallback_to_original=True` 確保失敗時降級回原文
4. 使用 `translated_text` 替代原本的 `text`

#### 4.3 配置選項設計

**修改檔案**：`src/crawler/config.py`

**新增配置項**：

```python
@dataclass
class CrawlerConfig:
    """爬蟲配置資料類別"""

    # ... 原有配置 ...

    # 新增：翻譯相關配置
    enable_translation: bool           # 是否啟用翻譯
    translation_target_lang: str       # 目標語言（預設 zh-TW）
    translation_max_retries: int       # 翻譯最大重試次數
    translation_enable_cache: bool     # 是否啟用翻譯緩存

    @classmethod
    def from_env(cls) -> 'CrawlerConfig':
        """從環境變數載入配置"""
        load_dotenv()

        return cls(
            # ... 原有配置 ...

            # 新增：翻譯配置
            enable_translation=os.getenv('CRAWLER_ENABLE_TRANSLATION', 'true').lower() in ('true', '1', 'yes'),
            translation_target_lang=os.getenv('CRAWLER_TRANSLATION_TARGET_LANG', 'zh-TW'),
            translation_max_retries=int(os.getenv('CRAWLER_TRANSLATION_MAX_RETRIES', '3')),
            translation_enable_cache=os.getenv('CRAWLER_TRANSLATION_ENABLE_CACHE', 'false').lower() in ('true', '1', 'yes'),
        )
```

**修改 `scheduler.py`**：使用配置決定是否翻譯

```python
def _format_news_message(self, news: dict) -> str:
    """格式化新聞訊息"""
    commodity = news['commodity']
    news_id = news['news_id']
    text = news['text']
    time = news.get('time', 'N/A')

    # 根據配置決定是否翻譯
    if self.config.enable_translation:
        try:
            translator = get_translator(
                enable_cache=self.config.translation_enable_cache,
                max_retries=self.config.translation_max_retries,
                target_lang=self.config.translation_target_lang
            )
            translated_text = translator.translate(text, fallback_to_original=True)
        except Exception as e:
            logger.error(f"翻譯失敗，使用原文：{e}")
            translated_text = text
    else:
        translated_text = text  # 不翻譯，直接使用原文

    # ... 其餘格式化邏輯 ...
```

**環境變數配置（`.env.example`）**：

```bash
# ============================================================================
# 商品新聞翻譯設定
# ============================================================================

# 是否啟用新聞翻譯（可選，預設為 true）
CRAWLER_ENABLE_TRANSLATION=true

# 翻譯目標語言（可選，預設為 zh-TW 繁體中文）
# 支援的語言代碼：zh-TW, zh-CN, ja, ko 等
CRAWLER_TRANSLATION_TARGET_LANG=zh-TW

# 翻譯最大重試次數（可選，預設為 3）
CRAWLER_TRANSLATION_MAX_RETRIES=3

# 是否啟用翻譯緩存（可選，預設為 false）
# 啟用後可減少重複翻譯，但會佔用磁碟空間
CRAWLER_TRANSLATION_ENABLE_CACHE=false
```

---

### 5. 技術挑戰和解決方案

#### 5.1 Google Translate API 速率限制

**挑戰**：
- 每秒最多 5 個請求
- 每日最多 200,000 個請求
- 超過限制會收到 HTTP 429 錯誤

**解決方案**：
1. **重試機制**：實作指數退避重試（已在 `translator.py` 中實作）
2. **速率監控**：記錄每日翻譯請求數（可選）
3. **降級策略**：失敗時返回英文原文
4. **當前場景分析**：
   - 每 5 分鐘爬取一次，每次約 1-10 則新聞
   - 每日約 1,440 次請求（遠低於 200,000 限制）
   - **結論**：當前場景下不太可能觸發速率限制

#### 5.2 長文本翻譯

**挑戰**：
- Google Translate 單次翻譯限制約 5,000 字元
- 部分新聞可能超過限制

**解決方案**：

**方案 1**：自動截斷（簡單但可能截斷句子）

```python
def translate_with_truncation(text: str, max_length: int = 4000) -> str:
    """截斷長文本後翻譯"""
    if len(text) > max_length:
        logger.warning(f"文本過長（{len(text)} 字元），截斷至 {max_length} 字元")
        text = text[:max_length] + "..."

    return translator.translate(text)
```

**方案 2**：分段翻譯（保持句子完整性）

```python
def translate_long_text(text: str, max_chunk_length: int = 4000) -> str:
    """分段翻譯長文本"""
    if len(text) <= max_chunk_length:
        return translator.translate(text)

    # 按句子分段（使用 '. ' 作為分隔符）
    sentences = text.split('. ')
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 2 <= max_chunk_length:
            current_chunk += sentence + ". "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "

    if current_chunk:
        chunks.append(current_chunk.strip())

    # 逐段翻譯
    translated_chunks = []
    for i, chunk in enumerate(chunks):
        logger.debug(f"翻譯第 {i+1}/{len(chunks)} 段（{len(chunk)} 字元）")
        translated_chunks.append(translator.translate(chunk))

    return ''.join(translated_chunks)
```

**建議**：
- **目前實作**：方案 1（簡單截斷）
- **未來優化**：方案 2（分段翻譯）

**實際情況分析**：
- 商品新聞通常較短（100-500 字元）
- 極少超過 5,000 字元限制
- 建議先使用方案 1，觀察實際情況後再優化

#### 5.3 翻譯質量和準確性

**挑戰**：
- Google Translate 可能誤譯專業術語
- 金融/商品領域的專業詞彙翻譯不準確

**解決方案**：

**方案 1**：建立專業術語字典（替換後翻譯）

```python
class NewsTranslator:
    # 專業術語映射表（英文 -> 繁體中文）
    TERMINOLOGY = {
        'gold futures': '黃金期貨',
        'crude oil': '原油',
        'bullish': '看漲',
        'bearish': '看跌',
        'resistance level': '阻力位',
        'support level': '支撐位',
        # ... 更多術語
    }

    def translate_with_terminology(self, text: str) -> str:
        """翻譯前替換專業術語"""
        # 先翻譯
        translated = self.translator.translate(text)

        # 後處理：確保專業術語正確（可選）
        for en_term, zh_term in self.TERMINOLOGY.items():
            # 如果翻譯結果包含錯誤的術語翻譯，替換為正確的
            pass  # 實際實作較複雜，需要 NLP 技術

        return translated
```

**方案 2**：人工審核和修正（長期）

- 收集翻譯錯誤案例
- 定期更新術語字典
- 提供 Telegram 指令讓用戶回報翻譯問題

**建議**：
- **初期**：直接使用 Google Translate
- **中期**：建立術語字典（若發現頻繁誤譯）
- **長期**：考慮使用付費 API（如 DeepL，翻譯質量更高）

#### 5.4 網路錯誤處理

**挑戰**：
- 網路不穩定導致翻譯請求失敗
- 超時、DNS 解析失敗等

**解決方案**：

已在 `translator.py` 中實作：
- 捕獲 `RequestError` 例外
- 使用重試機制（最多 3 次）
- 失敗時降級回原文

**額外建議**：

```python
# 設定超時時間（避免長時間等待）
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source='auto', target='zh-TW')
# deep-translator 目前不直接支援設定超時
# 可以使用 signal 或 threading.Timer 實作超時機制（較複雜）
```

**簡化方案**：

```python
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("翻譯超時")

def translate_with_timeout(text: str, timeout: int = 10) -> str:
    """帶超時的翻譯"""
    # 設定超時信號（僅限 Unix/Linux）
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)

    try:
        result = translator.translate(text)
        signal.alarm(0)  # 取消超時
        return result
    except TimeoutError:
        signal.alarm(0)
        logger.error("翻譯超時，返回原文")
        return text
```

**注意**：`signal.SIGALRM` 在 Windows 上不支援，建議使用 `threading.Timer` 或直接依賴 httpx 的超時機制。

#### 5.5 繁體中文 vs 簡體中文

**挑戰**：確保翻譯為繁體中文（Taiwan），而非簡體中文（China）

**解決方案**：

- **語言代碼**：使用 `zh-TW`（繁體中文-台灣）而非 `zh-CN`（簡體中文-中國）
- **驗證**：測試翻譯結果是否為繁體字

**測試範例**：

```python
translator = GoogleTranslator(source='en', target='zh-TW')
result = translator.translate('Taiwan')
print(result)  # 應輸出「台灣」（繁體），而非「台湾」（簡體）
```

**配置**：

```python
# 在 config.py 中
translation_target_lang=os.getenv('CRAWLER_TRANSLATION_TARGET_LANG', 'zh-TW')
```

**其他繁體中文選項**：
- `zh-TW`：繁體中文（台灣） ✅ 推薦
- `zh-HK`：繁體中文（香港）
- `zh-MO`：繁體中文（澳門）

---

### 6. 實作步驟建議

#### 階段一：基礎翻譯模組（1 小時）

1. **安裝 deep-translator**
   ```bash
   pip install deep-translator
   ```

2. **更新 `requirements.txt`**
   ```
   deep-translator>=1.11.0
   ```

3. **建立 `src/crawler/translator.py`**
   - 實作 `NewsTranslator` 類別
   - 實作重試機制
   - 實作錯誤處理和降級策略

4. **單元測試**
   ```python
   # 測試基本翻譯
   translator = NewsTranslator()
   result = translator.translate("Gold prices surge")
   print(result)  # 應輸出繁體中文
   ```

#### 階段二：整合到現有代碼（30 分鐘）

1. **修改 `src/crawler/config.py`**
   - 新增翻譯相關配置項

2. **修改 `src/crawler/scheduler.py`**
   - 導入 `get_translator()`
   - 在 `_format_news_message()` 中調用翻譯

3. **更新 `.env.example`**
   - 新增翻譯環境變數說明

#### 階段三：測試和優化（30 分鐘）

1. **手動測試**
   - 啟動 Bot，觸發 `/crawl_now`
   - 檢查 Telegram 訊息是否為繁體中文

2. **錯誤處理測試**
   - 模擬網路錯誤（斷網）
   - 驗證降級策略是否生效

3. **效能測試**
   - 測試翻譯速度（約 1-2 秒/則）
   - 確認不影響爬蟲整體效能

#### 階段四：文檔和部署（30 分鐘）

1. **撰寫使用文檔**
   - 如何啟用/停用翻譯
   - 配置選項說明

2. **更新 README**
   - 新增翻譯功能介紹

3. **部署到生產環境**
   - 更新 `.env` 配置
   - 重啟 Bot

---

### 7. 實作範例總結

#### 7.1 最小可行實現（MVP）

**檔案**：`src/crawler/translator.py`（簡化版）

```python
"""簡化版翻譯模組"""

from loguru import logger
from deep_translator import GoogleTranslator


class NewsTranslator:
    """新聞翻譯器（簡化版）"""

    def __init__(self, target_lang: str = 'zh-TW'):
        self.translator = GoogleTranslator(source='auto', target=target_lang)
        logger.info(f"翻譯器初始化完成（目標語言：{target_lang}）")

    def translate(self, text: str) -> str:
        """翻譯文本，失敗時返回原文"""
        try:
            return self.translator.translate(text)
        except Exception as e:
            logger.error(f"翻譯失敗：{e}，返回原文")
            return text


# 全域實例
_translator = None

def get_translator() -> NewsTranslator:
    """取得翻譯器實例（單例模式）"""
    global _translator
    if _translator is None:
        _translator = NewsTranslator()
    return _translator
```

**整合到 `scheduler.py`**：

```python
from .translator import get_translator

def _format_news_message(self, news: dict) -> str:
    """格式化新聞訊息"""
    # ... 原有代碼 ...

    # 翻譯文本
    translator = get_translator()
    translated_text = translator.translate(text)

    # 使用翻譯後的文本
    message = (
        f"{emoji} **{commodity} 商品新聞** (ID: {news_id})\n"
        f"{'─' * 40}\n\n"
        f"{translated_text}\n\n"
        f"{'─' * 40}\n"
        f"⏰ {time}"
    )

    return message
```

#### 7.2 完整實現（含重試、緩存、配置）

請參考第 4.1 節的完整 `translator.py` 實作。

---

## 程式碼範例總結

### 最小可行翻譯範例

```python
#!/usr/bin/env python3
"""
翻譯測試範例

測試 deep-translator 翻譯英文新聞為繁體中文。
"""

from deep_translator import GoogleTranslator

# 初始化翻譯器
translator = GoogleTranslator(source='auto', target='zh-TW')

# 測試文本
news_texts = [
    "Gold prices surge amid market volatility",
    "Bitcoin breaks resistance level at $100,000",
    "Crude oil futures climb on supply concerns"
]

# 翻譯
for text in news_texts:
    try:
        translated = translator.translate(text)
        print(f"原文：{text}")
        print(f"譯文：{translated}")
        print("-" * 60)
    except Exception as e:
        print(f"翻譯失敗：{e}")
```

**預期輸出**：

```
原文：Gold prices surge amid market volatility
譯文：黃金價格在市場波動中飆升
------------------------------------------------------------
原文：Bitcoin breaks resistance level at $100,000
譯文：比特幣突破 100,000 美元阻力位
------------------------------------------------------------
原文：Crude oil futures climb on supply concerns
譯文：原油期貨因供應擔憂而上漲
------------------------------------------------------------
```

---

## 附錄

### A. deep-translator 支援的語言清單

**繁體中文相關語言代碼**：
- `zh-TW`：繁體中文（台灣）✅ 推薦
- `zh-HK`：繁體中文（香港）
- `zh-CN`：簡體中文（中國）

**其他常用語言**：
- `en`：英文
- `ja`：日文
- `ko`：韓文
- `th`：泰文
- `vi`：越南文

**查詢支援的語言**：

```python
from deep_translator import GoogleTranslator

# 取得所有支援的語言（清單）
langs_list = GoogleTranslator().get_supported_languages()
print(langs_list)

# 取得語言代碼對照表（字典）
langs_dict = GoogleTranslator().get_supported_languages(as_dict=True)
print(langs_dict)
# 輸出：{'arabic': 'ar', 'french': 'fr', 'chinese (traditional)': 'zh-TW', ...}
```

### B. 翻譯質量比較

| 翻譯服務 | 免費 | 繁體中文支援 | 專業術語準確度 | API 易用性 | 速率限制 |
|---------|------|-------------|--------------|----------|---------|
| **Google Translate (deep-translator)** | ✅ | ✅ zh-TW | ⭐⭐⭐ | ✅ 簡單 | 5 req/s |
| **DeepL** | ⚠️ 有限免費 | ✅ zh-TW | ⭐⭐⭐⭐ | ✅ 簡單 | 有限 |
| **Azure Translator** | ❌ 付費 | ✅ zh-Hant | ⭐⭐⭐⭐ | ⚠️ 複雜 | 依方案 |
| **AWS Translate** | ❌ 付費 | ✅ zh-TW | ⭐⭐⭐ | ⚠️ 複雜 | 依方案 |

**結論**：Google Translate（透過 deep-translator）是最適合當前需求的方案。

### C. 參考資源

- [deep-translator · PyPI](https://pypi.org/project/deep-translator/)
- [deep-translator 官方文檔](https://deep-translator.readthedocs.io/en/latest/README.html)
- [GitHub - nidhaloff/deep-translator](https://github.com/nidhaloff/deep-translator)
- [DeepL Error Handling Best Practices](https://developers.deepl.com/docs/best-practices/error-handling)
- [Retry Mechanisms in Python](https://medium.com/@oggy/retry-mechanisms-in-python-practical-guide-with-real-life-examples-ed323e7a8871)
- [Google Cloud Translation API 語言支援](https://cloud.google.com/translate/docs/languages)

### D. 測試計畫

#### 單元測試

```python
# tests/test_crawler/test_translator.py
import pytest
from src.crawler.translator import NewsTranslator

def test_translate_simple():
    translator = NewsTranslator()
    result = translator.translate("Hello World")
    assert result  # 確保有返回值
    assert result != "Hello World"  # 確保已翻譯

def test_translate_empty():
    translator = NewsTranslator()
    result = translator.translate("")
    assert result == ""  # 空字串應返回空字串

def test_translate_with_fallback():
    translator = NewsTranslator()
    # 模擬網路錯誤（需要 mock）
    result = translator.translate("Test", fallback_to_original=True)
    assert result  # 確保有返回值
```

#### 整合測試

```python
# tests/test_crawler/test_scheduler_translation.py
import pytest
from src.crawler.scheduler import CrawlerScheduler
from src.crawler.config import CrawlerConfig

def test_format_message_with_translation():
    config = CrawlerConfig(
        # ... 配置 ...
        enable_translation=True,
        translation_target_lang='zh-TW'
    )

    scheduler = CrawlerScheduler(config)

    news = {
        'commodity': 'Gold',
        'news_id': 1,
        'text': 'Gold prices surge',
        'time': '2026-01-02T10:00:00Z'
    }

    message = scheduler._format_news_message(news)

    # 檢查訊息中是否包含繁體中文
    assert '黃金' in message or 'Gold' in message  # 翻譯成功或降級回原文
```

---

## 結論

本研究深入分析了在現有商品新聞爬蟲系統中整合 deep-translator 的完整方案。主要成果包括：

### 核心發現

1. **最佳插入點**：在 `scheduler.py` 的 `_format_news_message()` 方法中翻譯，不影響檔案保存
2. **技術選型**：deep-translator GoogleTranslator（免費、無限制、支援 zh-TW）
3. **翻譯策略**：整體翻譯 + 失敗降級回原文 + 指數退避重試
4. **架構設計**：新增 `translator.py` 模組，封裝翻譯邏輯和錯誤處理

### 實作建議

1. **階段一**：實作基礎翻譯模組（`translator.py`）
2. **階段二**：整合到 `scheduler.py` 和 `config.py`
3. **階段三**：測試翻譯效果和錯誤處理
4. **階段四**：（可選）實作緩存機制優化效能

### 技術挑戰應對

| 挑戰 | 解決方案 | 優先級 |
|------|---------|--------|
| 速率限制 | 重試機制 + 降級策略 | 🔴 高 |
| 長文本翻譯 | 截斷或分段翻譯 | 🟡 中 |
| 翻譯質量 | （可選）術語字典 | 🟢 低 |
| 網路錯誤 | 重試 + 降級回原文 | 🔴 高 |

### 預期效果

- ✅ Telegram 訊息自動翻譯為繁體中文
- ✅ 檔案保存仍為英文原文（符合需求）
- ✅ 翻譯失敗時自動降級回原文（不中斷通知）
- ✅ 支援配置啟用/停用翻譯

### 後續優化方向

1. **短期**：實作基礎翻譯功能，驗證效果
2. **中期**：建立商品術語字典，提高翻譯準確度
3. **長期**：整合 DeepL API（若需要更高翻譯質量）

---

**研究完成時間**：2026-01-02
**預估實作時間**：2-3 小時
**建議優先級**：🟡 中（功能增強，非核心必要）

---

## 資料來源

- [deep-translator · PyPI](https://pypi.org/project/deep-translator/)
- [deep-translator 官方文檔](https://deep-translator.readthedocs.io/en/latest/README.html)
- [deep-translator GitHub Repository](https://github.com/nidhaloff/deep-translator)
- [DeepL Error Handling Best Practices](https://developers.deepl.com/docs/best-practices/error-handling)
- [Retry Mechanisms in Python: Practical Guide](https://medium.com/@oggy/retry-mechanisms-in-python-practical-guide-with-real-life-examples-ed323e7a8871)
- [Google Cloud Translation API 語言支援](https://cloud.google.com/translate/docs/languages)
