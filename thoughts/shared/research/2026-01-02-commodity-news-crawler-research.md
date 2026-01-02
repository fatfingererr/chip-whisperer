---
title: 商品新聞爬蟲功能實現研究
date: 2026-01-02
ticket: N/A
author: Claude Code
tags:
  - web-crawler
  - news-scraping
  - telegram-integration
  - commodity-news
  - automation
  - anti-bot-detection
status: completed
related_files:
  - src/bot/telegram_bot.py
  - src/bot/handlers.py
  - src/bot/config.py
  - src/core/data_fetcher.py
  - markets/symbols.txt
  - scripts/run_bot.py
last_updated: 2026-01-02
last_updated_by: Claude Code
---

# 商品新聞爬蟲功能實現研究

## 研究問題

如何在現有的 Chip Whisperer 專案中實現一個商品新聞爬蟲功能，需求如下：

### 核心需求

1. **定時抓取**：每 5 分鐘（+/- 5% 隨機性）拉取 `https://tradingeconomics.com/stream?c=commodity` 網站
2. **防檢測機制**：添加頓點操作（延遲、隨機化等）避免被檢測為 AI 爬蟲
3. **智慧儲存**：
   - 根據新聞內容將資料保存到 `markets/<對應商品>/yyyymmdd.txt`
   - 若沒有對應商品則不保存
   - 若沒有日期檔案則自動創建
4. **ID 管理**：每則新聞在當天有遞增 ID，保存英文原文
5. **Telegram 通知**：將英文原文發送到 Telegram 群組

---

## 摘要

本研究深入分析了現有專案的架構和可復用元件，提出了一個完整的商品新聞爬蟲實現方案。主要發現包括：

- **現有可復用元件**：Telegram Bot 訊息發送機制、BotConfig 配置管理、Loguru 日誌系統、asyncio 支援
- **建議架構**：在 `src/` 下新增 `crawler/` 模組，包含新聞爬蟲、商品映射、檔案管理等功能
- **技術選型**：httpx + BeautifulSoup4 + APScheduler，支援 async/await 和防爬蟲策略
- **整合方式**：與現有 Telegram Bot 共享 Application 實例，使用 `post_init` 鉤子啟動爬蟲

**預估實作時間**：4-6 小時（包含測試和除錯）

---

## 詳細研究結果

### 1. 現有程式碼架構分析

#### 1.1 專案目錄結構

```
chip-whisperer/
├── src/
│   ├── agent/          # Claude Agent（MT5 工具整合）
│   ├── bot/            # Telegram Bot 核心
│   │   ├── config.py   # 配置管理
│   │   ├── handlers.py # 訊息處理器
│   │   └── telegram_bot.py  # Bot 主程式
│   ├── core/           # MT5 客戶端與資料抓取
│   │   ├── mt5_client.py
│   │   ├── mt5_config.py
│   │   ├── data_fetcher.py  # 歷史資料抓取
│   │   └── sqlite_cache.py  # SQLite 快取管理
│   └── visualization/  # 視覺化模組
├── markets/            # 商品資料目錄
│   ├── Gold/
│   ├── Silver/
│   ├── Brent/
│   ├── Wti/
│   └── symbols.txt     # 商品符號對照表
├── scripts/
│   ├── run_bot.py      # Bot 啟動腳本
│   └── backfill_data.py  # 資料回填腳本
└── requirements.txt
```

#### 1.2 Telegram Bot 架構

**檔案**: `src/bot/telegram_bot.py`（第 29-195 行）

- **核心類別**: `TelegramBot`
- **運行模式**: Polling 模式（`run()` 方法，第 130-152 行）
- **生命週期鉤子**:
  - `_post_init()`: Bot 啟動後回調（第 81-95 行）
  - `_post_shutdown()`: Bot 關閉前回調（第 122-128 行）
- **Application**: 使用 `python-telegram-bot` 的 `Application.builder()`（第 46-50 行）

**關鍵發現**：
- Bot 已支援 `async/await` 模式
- 可在 `_post_init()` 中啟動背景任務（如爬蟲定時器）
- Application 實例儲存在 `self.application`，可共享給其他模組

#### 1.3 配置管理機制

**檔案**: `src/bot/config.py`（第 14-107 行）

- **配置類別**: `BotConfig` (dataclass)
- **環境變數載入**: `from_env()` 類方法（第 38-94 行）
- **現有配置項**:
  - `telegram_bot_token`
  - `telegram_group_ids`
  - `anthropic_api_key`
  - `claude_model`
  - `debug`

**擴充點**：可在 `BotConfig` 中新增爬蟲相關配置（爬取間隔、目標群組等）

#### 1.4 訊息發送機制

**檔案**: `src/bot/handlers.py`（第 194-280 行）

**訊息發送方式**：
```python
await update.message.reply_text(response)
# 或直接發送到指定群組
await application.bot.send_message(
    chat_id=group_id,
    text=message
)
```

**關鍵發現**：
- `telegram_bot.py` 第 111-120 行已展示如何批次發送訊息到多個群組
- 可直接使用 `application.bot.send_message()` 發送新聞通知

#### 1.5 markets/ 目錄結構

**檔案**: `markets/symbols.txt`（第 1-25 行）

**現有商品清單**（共 20 個）：
```
ALUMINIUM -> Aluminium
BITCOIN -> Bitcoin
BRENT -> Brent
COPPER -> Copper
ETHEREUM -> Ethereum
GOLD -> Gold
LEAD -> Lead
PALLADIUM -> Palladium
PLATINUM -> Platinum
SILVER -> Silver
SOLANA -> Solana
WTI -> Wti
ZINC -> Zinc
# 農產品（已註解）：
# Cocoa_H26 -> Cocoa
# Coffee_H26 -> Coffee
# Corn_H26 -> Corn
# Cotton_H26 -> Cotton
# SBean_H26 -> Sbean
# Sugar_H26 -> Sugar
# Wheat_H26 -> Wheat
```

**目錄結構範例**：
```
markets/Gold/
markets/Silver/
markets/Brent/
markets/Wti/
...（目前都是空目錄）
```

**關鍵發現**：
- 需要建立商品名稱映射表（新聞中的名稱 → markets/ 目錄名）
- 檔案命名格式需統一（建議 `yyyymmdd.txt`）

#### 1.6 日誌系統

**檔案**: `scripts/run_bot.py`（第 30-64 行）

- **日誌庫**: Loguru
- **輸出方式**:
  - 控制台輸出（彩色格式）
  - 檔案輸出（`logs/bot_{time:YYYY-MM-DD}.log`，每日輪換，保留 30 天）
- **日誌級別**: 可透過 `DEBUG` 環境變數控制

**關鍵發現**：爬蟲可直接使用現有的 Loguru 配置，無需額外設定

---

### 2. 技術選型建議

#### 2.1 Web 爬蟲庫

| 套件 | 優點 | 缺點 | 建議 |
|------|------|------|------|
| **httpx** | 支援 async/await、效能優秀、API 類似 requests | 需手動處理 cookies | ✅ **推薦** |
| requests | 成熟穩定、文檔豐富 | 不支援 async | ❌ 不適合 |
| aiohttp | 已在 `requirements.txt`（第 30 行） | API 較複雜 | ⚠️ 可用 |
| selenium | 可執行 JavaScript | 資源消耗大、慢 | ❌ 過度設計 |

**最終選擇**：`httpx` + `httpx_socks`（若需代理）

**理由**：
- 與現有 `aiohttp` 共存（不衝突）
- 支援 async/await，與 Telegram Bot 整合容易
- 輕量級，適合簡單的 HTML 抓取

#### 2.2 HTML 解析庫

| 套件 | 優點 | 缺點 | 建議 |
|------|------|------|------|
| **BeautifulSoup4** | 易用、容錯能力強 | 效能稍慢 | ✅ **推薦** |
| lxml | 效能最佳 | 語法較複雜 | ⚠️ 可用 |
| html.parser | 內建 | 功能較弱 | ❌ 不推薦 |

**最終選擇**：`beautifulsoup4` + `lxml` (作為 parser)

**理由**：
- 易於解析 HTML 結構
- 容錯能力強（即使網站結構改變也能部分解析）
- 社群支援良好

#### 2.3 定時任務實現

| 方案 | 優點 | 缺點 | 建議 |
|------|------|------|------|
| **APScheduler** | 功能完整、支援多種觸發器、與 asyncio 整合 | 需額外依賴 | ✅ **推薦** |
| asyncio.create_task + sleep | 輕量級、無額外依賴 | 需手動管理重啟邏輯 | ⚠️ 可用 |
| Celery | 功能強大 | 過度複雜（需 Redis/RabbitMQ） | ❌ 過度設計 |

**最終選擇**：`APScheduler` (AsyncIOScheduler)

**理由**：
- 支援隨機化間隔（jitter）
- 與 `python-telegram-bot` 的 asyncio 整合良好
- 可在 Bot 的生命週期內優雅啟動/關閉

**範例程式碼**：
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler()
scheduler.add_job(
    crawl_news,
    trigger=IntervalTrigger(minutes=5, jitter=15),  # 5 ± 0.25 分鐘（5% 隨機性）
    id='news_crawler'
)
scheduler.start()
```

#### 2.4 防爬蟲策略

| 策略 | 實現方式 | 優先級 |
|------|----------|--------|
| **User-Agent 輪換** | 隨機選擇常見瀏覽器 UA | 🔴 必要 |
| **請求間隔隨機化** | APScheduler jitter + 每次請求延遲 | 🔴 必要 |
| **Headers 偽裝** | 添加 Referer, Accept-Language 等 | 🟡 推薦 |
| **代理 IP** | 透過 httpx-socks | 🟢 選用 |
| **Cookie 管理** | httpx.Client() 自動處理 | 🟡 推薦 |

**建議實現**：

```python
import random
import asyncio

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
]

async def fetch_with_delay(url: str) -> str:
    """帶延遲的請求"""
    # 隨機延遲 0.5-2 秒
    await asyncio.sleep(random.uniform(0.5, 2.0))

    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://tradingeconomics.com/',
        'Connection': 'keep-alive'
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=30.0)
        return response.text
```

---

### 3. 建議架構設計

#### 3.1 新模組目錄結構

```
src/
├── crawler/                    # 新增爬蟲模組
│   ├── __init__.py
│   ├── config.py              # 爬蟲配置
│   ├── news_crawler.py        # 新聞爬蟲核心
│   ├── commodity_mapper.py    # 商品名稱映射
│   ├── news_storage.py        # 新聞儲存管理
│   └── scheduler.py           # 定時任務管理
└── bot/
    └── telegram_bot.py        # 修改：整合爬蟲啟動
```

#### 3.2 模組職責劃分

##### 3.2.1 `crawler/config.py` - 爬蟲配置

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

    屬性：
        target_url: 目標網站 URL
        crawl_interval_minutes: 爬取間隔（分鐘）
        interval_jitter_seconds: 間隔隨機化範圍（秒）
        markets_dir: markets 目錄路徑
        enabled: 是否啟用爬蟲
        telegram_notify_groups: 要通知的 Telegram 群組 ID 列表
    """

    target_url: str
    crawl_interval_minutes: int
    interval_jitter_seconds: int
    markets_dir: str
    enabled: bool
    telegram_notify_groups: List[int]

    @classmethod
    def from_env(cls) -> 'CrawlerConfig':
        """
        從環境變數載入配置

        回傳：
            CrawlerConfig 實例
        """
        load_dotenv()

        return cls(
            target_url=os.getenv(
                'CRAWLER_TARGET_URL',
                'https://tradingeconomics.com/stream?c=commodity'
            ),
            crawl_interval_minutes=int(os.getenv('CRAWLER_INTERVAL_MINUTES', '5')),
            interval_jitter_seconds=int(os.getenv('CRAWLER_JITTER_SECONDS', '15')),  # 5%
            markets_dir=os.getenv('MARKETS_DIR', 'markets'),
            enabled=os.getenv('CRAWLER_ENABLED', 'true').lower() in ('true', '1', 'yes'),
            telegram_notify_groups=[
                int(gid.strip())
                for gid in os.getenv('CRAWLER_NOTIFY_GROUPS', '').split(',')
                if gid.strip()
            ]
        )
```

##### 3.2.2 `crawler/commodity_mapper.py` - 商品名稱映射

```python
"""
商品名稱映射模組

提供新聞中的商品名稱與 markets/ 目錄的映射關係。
"""

from typing import Optional, Dict
from pathlib import Path
from loguru import logger


class CommodityMapper:
    """
    商品名稱映射器

    負責將新聞中的商品名稱映射到 markets/ 目錄名稱。
    """

    # 商品名稱映射表（新聞關鍵字 -> markets 目錄名）
    COMMODITY_MAP = {
        # 貴金屬
        'gold': 'Gold',
        'silver': 'Silver',
        'platinum': 'Platinum',
        'palladium': 'Palladium',

        # 能源
        'crude oil': 'Wti',
        'wti': 'Wti',
        'brent': 'Brent',
        'oil': 'Wti',  # 預設為 WTI

        # 基本金屬
        'copper': 'Copper',
        'aluminium': 'Aluminium',
        'aluminum': 'Aluminium',  # 美式拼法
        'zinc': 'Zinc',
        'lead': 'Lead',

        # 加密貨幣
        'bitcoin': 'Bitcoin',
        'btc': 'Bitcoin',
        'ethereum': 'Ethereum',
        'eth': 'Ethereum',
        'solana': 'Solana',
        'sol': 'Solana',

        # 農產品（如果啟用）
        'cocoa': 'Cocoa',
        'coffee': 'Coffee',
        'corn': 'Corn',
        'cotton': 'Cotton',
        'soybean': 'Sbean',
        'sugar': 'Sugar',
        'wheat': 'Wheat',
    }

    def __init__(self, markets_dir: str = 'markets'):
        """
        初始化映射器

        參數：
            markets_dir: markets 目錄路徑
        """
        self.markets_dir = Path(markets_dir)
        self._load_available_commodities()

    def _load_available_commodities(self):
        """載入 markets/ 目錄下實際存在的商品"""
        if not self.markets_dir.exists():
            logger.warning(f"markets 目錄不存在：{self.markets_dir}")
            self.available_commodities = set()
            return

        # 取得所有子目錄名稱
        self.available_commodities = {
            d.name for d in self.markets_dir.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        }

        logger.info(f"已載入 {len(self.available_commodities)} 個可用商品目錄")
        logger.debug(f"可用商品：{sorted(self.available_commodities)}")

    def extract_commodity(self, news_text: str) -> Optional[str]:
        """
        從新聞文本中提取商品名稱

        參數：
            news_text: 新聞文本（英文）

        回傳：
            商品目錄名稱（如 'Gold'），若無匹配則回傳 None
        """
        news_lower = news_text.lower()

        # 按映射表逐一檢查
        for keyword, commodity_dir in self.COMMODITY_MAP.items():
            if keyword in news_lower:
                # 檢查該商品目錄是否存在
                if commodity_dir in self.available_commodities:
                    logger.debug(f"匹配商品：{keyword} -> {commodity_dir}")
                    return commodity_dir
                else:
                    logger.debug(f"商品 {commodity_dir} 目錄不存在，忽略")

        return None

    def is_valid_commodity(self, commodity_dir: str) -> bool:
        """
        檢查商品目錄是否有效

        參數：
            commodity_dir: 商品目錄名稱

        回傳：
            是否有效
        """
        return commodity_dir in self.available_commodities
```

##### 3.2.3 `crawler/news_storage.py` - 新聞儲存管理

```python
"""
新聞儲存模組

負責將新聞保存到 markets/<商品>/yyyymmdd.txt，並管理 ID。
"""

from typing import Optional, Tuple
from pathlib import Path
from datetime import datetime
import fcntl  # Unix/Linux 檔案鎖（Windows 需使用 msvcrt）
from loguru import logger


class NewsStorage:
    """
    新聞儲存管理器

    負責將新聞保存到對應商品目錄，並管理遞增 ID。
    """

    def __init__(self, markets_dir: str = 'markets'):
        """
        初始化儲存管理器

        參數：
            markets_dir: markets 目錄路徑
        """
        self.markets_dir = Path(markets_dir)
        self.markets_dir.mkdir(parents=True, exist_ok=True)

    def save_news(
        self,
        commodity_dir: str,
        news_text: str,
        date: Optional[datetime] = None
    ) -> Tuple[bool, int]:
        """
        保存新聞到指定商品目錄

        參數：
            commodity_dir: 商品目錄名稱（如 'Gold'）
            news_text: 新聞文本（英文原文）
            date: 日期（預設為當天）

        回傳：
            (是否成功, 新聞 ID)
        """
        if date is None:
            date = datetime.now()

        # 確保商品目錄存在
        commodity_path = self.markets_dir / commodity_dir
        commodity_path.mkdir(parents=True, exist_ok=True)

        # 檔案路徑
        date_str = date.strftime('%Y%m%d')
        file_path = commodity_path / f"{date_str}.txt"

        # 取得下一個 ID
        next_id = self._get_next_id(file_path)

        # 寫入新聞（附加模式）
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                # 檔案鎖（避免並發寫入）
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except:
                    pass  # Windows 不支援 fcntl，忽略

                # 寫入格式：[ID] 新聞內容
                f.write(f"[{next_id}] {news_text}\n")
                f.write("-" * 80 + "\n")

            logger.info(f"新聞已保存：{file_path} (ID: {next_id})")
            return True, next_id

        except Exception as e:
            logger.error(f"保存新聞失敗：{e}")
            return False, -1

    def _get_next_id(self, file_path: Path) -> int:
        """
        取得檔案中的下一個 ID

        參數：
            file_path: 檔案路徑

        回傳：
            下一個 ID（從 1 開始）
        """
        if not file_path.exists():
            return 1

        # 讀取檔案，計算現有 ID 數量
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 統計 [ID] 出現次數
            id_count = sum(1 for line in lines if line.strip().startswith('['))
            return id_count + 1

        except Exception as e:
            logger.warning(f"讀取檔案失敗，ID 從 1 開始：{e}")
            return 1

    def check_duplicate(
        self,
        commodity_dir: str,
        news_text: str,
        date: Optional[datetime] = None
    ) -> bool:
        """
        檢查新聞是否已存在（去重）

        參數：
            commodity_dir: 商品目錄名稱
            news_text: 新聞文本
            date: 日期

        回傳：
            是否重複
        """
        if date is None:
            date = datetime.now()

        date_str = date.strftime('%Y%m%d')
        file_path = self.markets_dir / commodity_dir / f"{date_str}.txt"

        if not file_path.exists():
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 簡單的字串包含檢查（可改為更精確的去重邏輯）
            return news_text.strip() in content

        except Exception as e:
            logger.warning(f"檢查重複時發生錯誤：{e}")
            return False
```

##### 3.2.4 `crawler/news_crawler.py` - 新聞爬蟲核心

```python
"""
新聞爬蟲核心模組

負責從目標網站抓取商品新聞。
"""

from typing import List, Dict, Optional
import random
import asyncio
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from datetime import datetime

from .config import CrawlerConfig
from .commodity_mapper import CommodityMapper
from .news_storage import NewsStorage


# User-Agent 列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]


class NewsCrawler:
    """
    商品新聞爬蟲

    負責從 tradingeconomics.com 抓取商品新聞。
    """

    def __init__(self, config: CrawlerConfig):
        """
        初始化爬蟲

        參數：
            config: 爬蟲配置
        """
        self.config = config
        self.mapper = CommodityMapper(config.markets_dir)
        self.storage = NewsStorage(config.markets_dir)

        logger.info("新聞爬蟲初始化完成")

    async def fetch_page(self) -> Optional[str]:
        """
        抓取目標網頁 HTML

        回傳：
            HTML 內容，失敗時回傳 None
        """
        # 隨機延遲（0.5-2 秒）
        await asyncio.sleep(random.uniform(0.5, 2.0))

        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://tradingeconomics.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                logger.info(f"正在抓取：{self.config.target_url}")
                response = await client.get(self.config.target_url, headers=headers)

                if response.status_code == 200:
                    logger.info("網頁抓取成功")
                    return response.text
                else:
                    logger.error(f"網頁抓取失敗：HTTP {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"網頁抓取異常：{e}")
            return None

    def parse_news(self, html: str) -> List[Dict[str, str]]:
        """
        解析 HTML，提取新聞列表

        參數：
            html: 網頁 HTML 內容

        回傳：
            新聞列表 [{'title': ..., 'content': ..., 'time': ...}, ...]
        """
        soup = BeautifulSoup(html, 'lxml')
        news_list = []

        # TODO: 根據實際網站結構調整選擇器
        # 以下為示意程式碼，需根據 tradingeconomics.com 的實際 HTML 結構修改
        try:
            # 範例：假設新聞在 <div class="stream-item"> 中
            items = soup.select('div.stream-item')  # 需根據實際調整

            for item in items:
                try:
                    # 提取標題
                    title_elem = item.select_one('h3')  # 需根據實際調整
                    title = title_elem.get_text(strip=True) if title_elem else ''

                    # 提取內容
                    content_elem = item.select_one('p')  # 需根據實際調整
                    content = content_elem.get_text(strip=True) if content_elem else ''

                    # 提取時間
                    time_elem = item.select_one('time')  # 需根據實際調整
                    time_str = time_elem.get('datetime', '') if time_elem else ''

                    # 組合完整文本
                    full_text = f"{title}\n{content}" if content else title

                    if full_text:
                        news_list.append({
                            'title': title,
                            'content': content,
                            'full_text': full_text,
                            'time': time_str
                        })

                except Exception as e:
                    logger.warning(f"解析單則新聞時發生錯誤：{e}")
                    continue

            logger.info(f"成功解析 {len(news_list)} 則新聞")

        except Exception as e:
            logger.error(f"解析 HTML 時發生錯誤：{e}")

        return news_list

    async def process_and_save(
        self,
        news_list: List[Dict[str, str]]
    ) -> List[Dict[str, any]]:
        """
        處理新聞列表並保存

        參數：
            news_list: 解析後的新聞列表

        回傳：
            已保存的新聞列表（包含商品和 ID 資訊）
        """
        saved_news = []

        for news in news_list:
            full_text = news['full_text']

            # 提取商品
            commodity = self.mapper.extract_commodity(full_text)
            if not commodity:
                logger.debug(f"新聞未匹配任何商品，忽略：{full_text[:50]}...")
                continue

            # 檢查重複
            if self.storage.check_duplicate(commodity, full_text):
                logger.debug(f"新聞重複，忽略：{full_text[:50]}...")
                continue

            # 保存新聞
            success, news_id = self.storage.save_news(commodity, full_text)

            if success:
                saved_news.append({
                    'commodity': commodity,
                    'news_id': news_id,
                    'text': full_text,
                    'time': news.get('time', '')
                })
                logger.info(f"新聞已保存：{commodity} ID={news_id}")

        return saved_news

    async def crawl(self) -> List[Dict[str, any]]:
        """
        執行完整的爬取流程

        回傳：
            已保存的新聞列表
        """
        logger.info("=" * 60)
        logger.info("開始爬取商品新聞")
        logger.info("=" * 60)

        # 1. 抓取網頁
        html = await self.fetch_page()
        if not html:
            logger.error("網頁抓取失敗，本次爬取結束")
            return []

        # 2. 解析新聞
        news_list = self.parse_news(html)
        if not news_list:
            logger.warning("未解析到任何新聞")
            return []

        # 3. 處理並保存
        saved_news = await self.process_and_save(news_list)

        logger.info("=" * 60)
        logger.info(f"爬取完成：共保存 {len(saved_news)} 則新聞")
        logger.info("=" * 60)

        return saved_news
```

##### 3.2.5 `crawler/scheduler.py` - 定時任務管理

```python
"""
爬蟲定時任務管理模組

負責啟動和管理新聞爬蟲的定時任務。
"""

from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from telegram.ext import Application

from .config import CrawlerConfig
from .news_crawler import NewsCrawler


class CrawlerScheduler:
    """
    爬蟲定時任務管理器

    使用 APScheduler 管理爬蟲的定時執行。
    """

    def __init__(
        self,
        config: CrawlerConfig,
        telegram_app: Optional[Application] = None
    ):
        """
        初始化調度器

        參數：
            config: 爬蟲配置
            telegram_app: Telegram Application 實例（用於發送通知）
        """
        self.config = config
        self.telegram_app = telegram_app
        self.crawler = NewsCrawler(config)
        self.scheduler = AsyncIOScheduler()

        logger.info("爬蟲調度器初始化完成")

    async def _crawl_and_notify(self):
        """
        爬取新聞並發送 Telegram 通知
        """
        try:
            # 執行爬取
            saved_news = await self.crawler.crawl()

            # 發送 Telegram 通知
            if saved_news and self.telegram_app and self.config.telegram_notify_groups:
                await self._send_telegram_notifications(saved_news)

        except Exception as e:
            logger.exception(f"爬蟲執行失敗：{e}")

    async def _send_telegram_notifications(self, saved_news: list):
        """
        發送 Telegram 通知

        參數：
            saved_news: 已保存的新聞列表
        """
        for news in saved_news:
            message = (
                f"📰 **{news['commodity']} 商品新聞** (ID: {news['news_id']})\n\n"
                f"{news['text']}\n\n"
                f"⏰ {news.get('time', 'N/A')}"
            )

            # 發送到所有配置的群組
            for group_id in self.config.telegram_notify_groups:
                try:
                    await self.telegram_app.bot.send_message(
                        chat_id=group_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    logger.info(f"已發送通知到群組 {group_id}")

                except Exception as e:
                    logger.error(f"發送通知到群組 {group_id} 失敗：{e}")

    def start(self):
        """
        啟動定時任務
        """
        if not self.config.enabled:
            logger.info("爬蟲已停用，不啟動定時任務")
            return

        # 計算 jitter（5% 隨機性）
        jitter = self.config.interval_jitter_seconds

        # 新增任務
        self.scheduler.add_job(
            self._crawl_and_notify,
            trigger=IntervalTrigger(
                minutes=self.config.crawl_interval_minutes,
                jitter=jitter
            ),
            id='news_crawler',
            name='商品新聞爬蟲',
            replace_existing=True
        )

        # 啟動調度器
        self.scheduler.start()

        logger.info(
            f"爬蟲定時任務已啟動：每 {self.config.crawl_interval_minutes} 分鐘 "
            f"(±{jitter} 秒) 執行一次"
        )

    def stop(self):
        """
        停止定時任務
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("爬蟲定時任務已停止")
```

#### 3.3 整合到 Telegram Bot

**修改檔案**: `src/bot/telegram_bot.py`

**修改位置**: `_post_init()` 方法（第 81-95 行）

```python
from src.crawler.config import CrawlerConfig
from src.crawler.scheduler import CrawlerScheduler


class TelegramBot:
    def __init__(self, config: BotConfig):
        # ... 原有程式碼 ...

        # 新增：初始化爬蟲調度器
        crawler_config = CrawlerConfig.from_env()
        self.crawler_scheduler = CrawlerScheduler(
            config=crawler_config,
            telegram_app=self.application
        )

    async def _post_init(self, application: Application):
        """
        初始化後回調

        在 Bot 啟動後執行的初始化任務。
        """
        logger.info("Bot 啟動後初始化...")

        # 取得 Bot 資訊
        bot = await application.bot.get_me()
        logger.info(f"Bot 用戶名：@{bot.username}")
        logger.info(f"Bot ID：{bot.id}")

        # 發送開張訊息到所有配置的群組
        await self._send_startup_message(application)

        # 新增：啟動爬蟲定時任務
        self.crawler_scheduler.start()
        logger.info("爬蟲定時任務已整合到 Bot 生命週期")

    async def _post_shutdown(self, application: Application):
        """
        關閉後回調

        在 Bot 關閉前執行的清理任務。
        """
        logger.info("Bot 正在關閉...")

        # 新增：停止爬蟲定時任務
        self.crawler_scheduler.stop()
        logger.info("爬蟲定時任務已停止")
```

---

### 4. 環境變數配置

**修改檔案**: `.env.example`

**新增內容**：

```bash
# ============================================================================
# 商品新聞爬蟲設定
# ============================================================================

# 是否啟用爬蟲（可選，預設為 true）
CRAWLER_ENABLED=true

# 目標網站 URL（可選，預設為 tradingeconomics.com）
CRAWLER_TARGET_URL=https://tradingeconomics.com/stream?c=commodity

# 爬取間隔（分鐘，可選，預設為 5）
CRAWLER_INTERVAL_MINUTES=5

# 間隔隨機化範圍（秒，可選，預設為 15 秒，即 5% 隨機性）
CRAWLER_JITTER_SECONDS=15

# markets 目錄路徑（可選，預設為 'markets'）
MARKETS_DIR=markets

# 要通知的 Telegram 群組 ID（可選，用逗號分隔）
# 若不設定則只保存到檔案，不發送通知
# 可使用 TELEGRAM_GROUP_IDS 的值
CRAWLER_NOTIFY_GROUPS=-1001234567890
```

---

### 5. 需要新增的依賴套件

**修改檔案**: `requirements.txt`

**新增內容**：

```txt
# 新聞爬蟲相關
httpx>=0.25.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
APScheduler>=3.10.0
```

**安裝指令**：

```bash
pip install httpx beautifulsoup4 lxml APScheduler
```

---

### 6. 實現流程圖

```
┌─────────────────────────────────────────────────────────────┐
│                  Telegram Bot 啟動                          │
│                  (run_bot.py)                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  TelegramBot._post_init()                                   │
│  - 初始化 Bot                                               │
│  - 發送開張訊息                                             │
│  - 啟動爬蟲調度器 (CrawlerScheduler.start())                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  APScheduler 定時觸發 (每 5 分鐘 ± 15 秒)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  CrawlerScheduler._crawl_and_notify()                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  NewsCrawler.crawl()                                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. fetch_page()                                       │  │
│  │    - 隨機延遲 0.5-2 秒                                │  │
│  │    - 隨機 User-Agent                                  │  │
│  │    - 偽裝 Headers                                     │  │
│  │    - httpx.AsyncClient.get()                          │  │
│  └──────────────────────────┬───────────────────────────┘  │
│                             ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2. parse_news()                                       │  │
│  │    - BeautifulSoup 解析 HTML                          │  │
│  │    - 提取新聞標題、內容、時間                         │  │
│  │    - 返回新聞列表                                     │  │
│  └──────────────────────────┬───────────────────────────┘  │
│                             ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 3. process_and_save()                                 │  │
│  │    For each news:                                     │  │
│  │    ├─ CommodityMapper.extract_commodity()             │  │
│  │    │  (提取商品名稱)                                  │  │
│  │    ├─ NewsStorage.check_duplicate()                   │  │
│  │    │  (檢查重複)                                      │  │
│  │    └─ NewsStorage.save_news()                         │  │
│  │       (保存到 markets/<商品>/yyyymmdd.txt)            │  │
│  └──────────────────────────┬───────────────────────────┘  │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  CrawlerScheduler._send_telegram_notifications()            │
│  - 遍歷已保存的新聞                                         │
│  - 格式化訊息                                               │
│  - application.bot.send_message() 發送到群組                │
└─────────────────────────────────────────────────────────────┘
```

---

### 7. 潛在的技術挑戰和解決方案

#### 7.1 網站結構變化

**挑戰**：tradingeconomics.com 的 HTML 結構可能改變，導致解析失敗。

**解決方案**：
1. 使用多個 CSS 選擇器備選方案
2. 增加錯誤處理和日誌記錄
3. 定期監控爬取成功率
4. 考慮使用 API（若網站提供）

**範例程式碼**：
```python
def parse_news_safe(self, html: str) -> List[Dict]:
    """容錯的新聞解析"""
    soup = BeautifulSoup(html, 'lxml')

    # 嘗試多種選擇器
    selectors = [
        'div.stream-item',
        'article.news-item',
        'div.commodity-news'
    ]

    for selector in selectors:
        items = soup.select(selector)
        if items:
            logger.debug(f"使用選擇器：{selector}")
            return self._parse_items(items)

    logger.warning("所有選擇器都無法匹配")
    return []
```

#### 7.2 IP 封鎖風險

**挑戰**：頻繁請求可能導致 IP 被封鎖。

**解決方案**：
1. 控制請求頻率（5 分鐘已足夠安全）
2. 使用隨機延遲和 jitter
3. 輪換 User-Agent
4. 若需要，整合代理 IP 池

**範例程式碼**：
```python
# 配置代理（選用）
async def fetch_with_proxy(self, url: str, proxy: str = None):
    async with httpx.AsyncClient(proxies=proxy) as client:
        return await client.get(url, ...)
```

#### 7.3 新聞重複過濾

**挑戰**：同一則新聞可能在不同時間被抓到。

**解決方案**：
1. 基於內容的去重（目前實現）
2. 儲存新聞 hash（MD5/SHA256）
3. 使用資料庫（SQLite）儲存已抓取的新聞 ID

**優化範例**：
```python
import hashlib

def get_news_hash(self, text: str) -> str:
    """計算新聞 hash"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def check_duplicate_by_hash(self, news_hash: str) -> bool:
    """使用 hash 檢查重複"""
    # 查詢資料庫或檔案
    pass
```

#### 7.4 併發寫入衝突

**挑戰**：若多個爬蟲實例同時運行，可能導致檔案寫入衝突。

**解決方案**：
1. 使用檔案鎖（fcntl 或 msvcrt）
2. 確保只有一個 Bot 實例運行
3. 使用資料庫替代檔案儲存

**Windows 檔案鎖範例**：
```python
import msvcrt

def save_with_lock(self, file_path: Path, content: str):
    """Windows 檔案鎖"""
    with open(file_path, 'a', encoding='utf-8') as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1024)
        f.write(content)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1024)
```

#### 7.5 商品名稱匹配準確性

**挑戰**：新聞中的商品名稱可能有多種表達方式。

**解決方案**：
1. 擴充商品映射表（包含別名、簡稱）
2. 使用正則表達式或 NLP（如有需要）
3. 記錄未匹配的新聞，手動分析

**優化範例**：
```python
import re

COMMODITY_PATTERNS = {
    'Gold': [r'\bgold\b', r'\bxau\b', r'\bgc\b'],
    'Silver': [r'\bsilver\b', r'\bxag\b', r'\bsi\b'],
}

def extract_commodity_regex(self, text: str) -> Optional[str]:
    """使用正則表達式匹配"""
    for commodity, patterns in COMMODITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return commodity
    return None
```

---

### 8. 測試計畫

#### 8.1 單元測試

**測試檔案**: `tests/test_crawler/`

```python
# tests/test_crawler/test_commodity_mapper.py
import pytest
from src.crawler.commodity_mapper import CommodityMapper

def test_extract_gold():
    mapper = CommodityMapper()
    assert mapper.extract_commodity("Gold prices surge") == "Gold"

def test_extract_no_match():
    mapper = CommodityMapper()
    assert mapper.extract_commodity("Some random news") is None

# tests/test_crawler/test_news_storage.py
from src.crawler.news_storage import NewsStorage

def test_save_news(tmp_path):
    storage = NewsStorage(markets_dir=str(tmp_path))
    success, news_id = storage.save_news('Gold', 'Test news')
    assert success
    assert news_id == 1
```

#### 8.2 整合測試

```python
# tests/test_crawler/test_integration.py
import pytest
from src.crawler.news_crawler import NewsCrawler
from src.crawler.config import CrawlerConfig

@pytest.mark.asyncio
async def test_full_crawl():
    config = CrawlerConfig(
        target_url='https://tradingeconomics.com/stream?c=commodity',
        crawl_interval_minutes=5,
        interval_jitter_seconds=15,
        markets_dir='markets',
        enabled=True,
        telegram_notify_groups=[]
    )

    crawler = NewsCrawler(config)
    saved_news = await crawler.crawl()

    # 檢查是否有新聞被保存
    assert isinstance(saved_news, list)
```

#### 8.3 手動測試

1. **啟動 Bot 並驗證爬蟲啟動**：
   ```bash
   python scripts/run_bot.py
   # 檢查日誌：「爬蟲定時任務已啟動」
   ```

2. **檢查 markets/ 目錄**：
   ```bash
   ls -la markets/Gold/
   # 應該看到 yyyymmdd.txt 檔案
   ```

3. **檢查 Telegram 通知**：
   - 在群組中確認是否收到新聞通知

---

### 9. 實作步驟建議

1. **階段一：基礎架構**（1-2 小時）
   - 建立 `src/crawler/` 目錄
   - 實現 `config.py`
   - 實現 `commodity_mapper.py`
   - 實現 `news_storage.py`
   - 撰寫單元測試

2. **階段二：爬蟲核心**（1-2 小時）
   - 實現 `news_crawler.py`
   - 分析 tradingeconomics.com HTML 結構
   - 調整 CSS 選擇器
   - 測試網頁抓取和解析

3. **階段三：定時任務**（30 分鐘）
   - 實現 `scheduler.py`
   - 整合到 `telegram_bot.py`
   - 測試定時觸發

4. **階段四：Telegram 通知**（30 分鐘）
   - 實現通知發送邏輯
   - 測試訊息格式
   - 調整訊息內容

5. **階段五：測試與優化**（1 小時）
   - 整合測試
   - 處理邊界情況
   - 優化效能和錯誤處理
   - 撰寫文檔

---

### 10. 未來擴充建議

1. **資料庫儲存**：
   - 使用 SQLite 儲存新聞，替代純文字檔案
   - 支援更複雜的查詢和去重邏輯

2. **多語言支援**：
   - 使用翻譯 API 將英文新聞翻譯為繁體中文
   - 提供雙語通知

3. **情感分析**：
   - 使用 NLP 分析新聞情感（正面/負面）
   - 標記重要新聞（如價格大幅波動）

4. **Web Dashboard**：
   - 提供 Web 介面查看歷史新聞
   - 可視化新聞趨勢

5. **多來源整合**：
   - 整合多個新聞來源（Reuters, Bloomberg 等）
   - 聚合並去重

---

## 程式碼範例總結

### 最小可行實現（MVP）

**檔案**: `examples/simple_crawler.py`

```python
#!/usr/bin/env python3
"""
簡化版商品新聞爬蟲範例

此範例展示最小可行實現（無 Telegram 整合）。
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime


async def simple_crawl():
    """簡單的新聞爬蟲範例"""

    # 1. 抓取網頁
    url = 'https://tradingeconomics.com/stream?c=commodity'
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        html = response.text

    # 2. 解析新聞
    soup = BeautifulSoup(html, 'lxml')
    items = soup.select('div.stream-item')  # 需根據實際調整

    # 3. 儲存新聞
    markets_dir = Path('markets')
    date_str = datetime.now().strftime('%Y%m%d')

    for item in items:
        title = item.select_one('h3').get_text(strip=True)

        # 簡單的商品匹配
        if 'gold' in title.lower():
            commodity = 'Gold'
        elif 'silver' in title.lower():
            commodity = 'Silver'
        else:
            continue

        # 保存到檔案
        file_path = markets_dir / commodity / f"{date_str}.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"{title}\n")
            f.write("-" * 80 + "\n")

        print(f"已保存：{commodity} - {title}")


if __name__ == '__main__':
    asyncio.run(simple_crawl())
```

---

## 附錄

### A. tradingeconomics.com HTML 結構分析

**注意**：實際實現時需要手動訪問網站並檢查 HTML 結構。

**建議步驟**：
1. 使用瀏覽器開發者工具（F12）
2. 找到新聞列表的容器元素
3. 記錄 CSS 選擇器或 XPath
4. 確認新聞標題、內容、時間的元素位置

**範例分析**（需根據實際調整）：
```html
<!-- 假設的 HTML 結構 -->
<div class="stream-container">
    <div class="stream-item" data-id="12345">
        <h3 class="stream-title">Gold prices rise on inflation fears</h3>
        <p class="stream-content">Gold futures climbed...</p>
        <time datetime="2026-01-02T10:30:00Z">2 hours ago</time>
    </div>
    <!-- 更多新聞... -->
</div>
```

**對應的 CSS 選擇器**：
```python
items = soup.select('div.stream-item')
title = item.select_one('h3.stream-title')
content = item.select_one('p.stream-content')
time = item.select_one('time')
```

### B. 參考資源

- **httpx 文檔**: https://www.python-httpx.org/
- **BeautifulSoup 文檔**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- **APScheduler 文檔**: https://apscheduler.readthedocs.io/
- **python-telegram-bot 文檔**: https://docs.python-telegram-bot.org/

---

**研究完成時間**: 2026-01-02
**預估實作時間**: 4-6 小時（包含測試和除錯）
**建議優先級**: 🔴 高（核心功能）
