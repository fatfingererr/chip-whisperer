# 商品新聞爬蟲功能實作計畫

## 概述

根據研究報告 `thoughts/shared/research/2026-01-02-commodity-news-crawler-research.md`，本計畫旨在實作一個自動化的商品新聞爬蟲系統，每 5 分鐘（±5% 隨機性）從 tradingeconomics.com 抓取商品相關新聞，並將新聞儲存到對應的商品目錄中，同時發送通知到 Telegram 群組。

## 目前狀態分析

### 已存在的元件

1. **Telegram Bot 架構** (`src/bot/telegram_bot.py`)
   - 支援 async/await 模式
   - 提供 `_post_init()` 和 `_post_shutdown()` 生命週期鉤子
   - 已有群組訊息發送機制
   - Application 實例可共享給其他模組

2. **配置管理系統** (`src/bot/config.py`)
   - BotConfig 資料類別
   - 環境變數載入機制
   - 可擴充新增爬蟲配置

3. **日誌系統** (`scripts/run_bot.py`)
   - Loguru 日誌庫
   - 控制台 + 檔案輸出
   - 每日輪換，保留 30 天

4. **Markets 目錄結構** (`markets/`)
   - 現有 20 個商品目錄（Gold, Silver, Brent, Wti, Bitcoin, Ethereum, Solana 等）
   - 目前目錄為空，待填充新聞資料

### 缺少的元件

1. **爬蟲模組** (`src/crawler/`)
   - 新聞爬蟲核心
   - 商品名稱映射器
   - 新聞儲存管理
   - 定時任務調度器
   - 爬蟲配置

2. **依賴套件**
   - httpx（HTTP 客戶端）
   - beautifulsoup4（HTML 解析）
   - lxml（HTML parser）
   - APScheduler（定時任務）

3. **環境變數配置**
   - 爬蟲啟用開關
   - 目標 URL
   - 爬取間隔設定
   - 通知群組 ID

## 期望的最終狀態

### 功能性驗證

1. **定時爬取運作中**
   - Bot 啟動後自動啟動爬蟲定時任務
   - 每 5 分鐘執行一次（±15 秒隨機性）
   - 日誌顯示爬取開始和結束訊息

2. **新聞正確儲存**
   - 新聞保存到 `markets/<商品>/yyyymmdd.txt`
   - 每則新聞有遞增 ID（格式：`[1] 新聞內容`）
   - 同一天的新聞追加到同一檔案
   - 重複新聞被過濾不保存

3. **Telegram 通知正常**
   - 新抓取的新聞立即發送到配置的群組
   - 訊息格式清晰（商品名稱、ID、內容、時間）
   - 發送失敗有錯誤日誌記錄

4. **防爬蟲機制生效**
   - 請求前有 0.5-2 秒隨機延遲
   - User-Agent 隨機輪換
   - Headers 偽裝完整

### 非功能性驗證

1. **效能穩定**
   - 不影響 Telegram Bot 主功能
   - 記憶體占用穩定（無記憶體洩漏）
   - 爬取失敗不影響 Bot 運行

2. **可維護性**
   - 程式碼結構清晰，職責分離
   - 有完整的錯誤處理和日誌
   - 配置可透過環境變數靈活調整

3. **可擴展性**
   - 商品映射表易於新增
   - 可輕鬆調整爬取間隔
   - 可停用爬蟲功能（CRAWLER_ENABLED=false）

## 我們不做的事情

為避免範圍膨脹，以下功能明確排除在本次實作之外：

1. ❌ **多語言翻譯**：不將英文新聞翻譯為中文
2. ❌ **情感分析**：不分析新聞情感（正面/負面）
3. ❌ **Web Dashboard**：不提供網頁介面查看新聞
4. ❌ **資料庫儲存**：本階段使用純文字檔案，不使用 SQLite
5. ❌ **多來源整合**：只爬取 tradingeconomics.com，不整合其他網站
6. ❌ **代理 IP 池**：初期不整合代理 IP，依賴基本防爬策略
7. ❌ **新聞分類**：不對新聞進行自動分類或標籤
8. ❌ **歷史資料回填**：不回填過去的新聞資料

## 實作方法

採用分階段、增量式的開發方式，每個階段都有明確的可驗證目標。各階段之間有清晰的依賴關係，確保穩固的基礎上逐步增加功能。

### 關鍵技術決策

1. **HTTP 客戶端**：httpx（支援 async/await，與現有架構契合）
2. **HTML 解析**：BeautifulSoup4 + lxml（易用且容錯能力強）
3. **定時任務**：APScheduler（支援 jitter，與 asyncio 整合良好）
4. **檔案鎖**：Windows 使用 try-except 包裝（避免 fcntl 不相容問題）
5. **去重策略**：簡單的字串包含檢查（初期方案，可升級為 hash）

---

## 階段一：前置準備與環境設定

### 概述

建立爬蟲模組的基礎架構，安裝必要依賴，配置環境變數，確保專案可正常啟動。

### 需要創建/修改的檔案

#### 1. 安裝依賴套件

**檔案**：`requirements.txt`

**修改內容**：在檔案末尾新增

```txt
# 新聞爬蟲相關
httpx>=0.25.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
APScheduler>=3.10.0
```

**執行指令**：
```bash
pip install httpx beautifulsoup4 lxml APScheduler
```

#### 2. 更新環境變數範本

**檔案**：`.env.example`

**修改內容**：在檔案末尾新增

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
# 建議使用與 TELEGRAM_GROUP_IDS 相同的值
CRAWLER_NOTIFY_GROUPS=
```

#### 3. 更新實際環境設定

**檔案**：`.env`（請手動創建或修改）

**修改內容**：複製 `.env.example` 的新增內容，並填入實際值

```bash
CRAWLER_ENABLED=true
CRAWLER_TARGET_URL=https://tradingeconomics.com/stream?c=commodity
CRAWLER_INTERVAL_MINUTES=5
CRAWLER_JITTER_SECONDS=15
MARKETS_DIR=markets
CRAWLER_NOTIFY_GROUPS=-1001234567890  # 替換為實際的群組 ID
```

#### 4. 建立爬蟲模組目錄結構

**執行指令**：
```bash
# 建立 src/crawler 目錄
mkdir -p src/crawler

# 建立 __init__.py（模組標記檔案）
touch src/crawler/__init__.py
```

### 成功標準

#### 自動化驗證
- [ ] `pip list` 顯示 httpx, beautifulsoup4, lxml, APScheduler 已安裝
- [ ] `.env.example` 包含爬蟲相關環境變數說明
- [ ] `src/crawler/` 目錄存在且包含 `__init__.py`

#### 手動驗證
- [ ] `.env` 檔案已更新並填入實際設定值
- [ ] 執行 `python scripts/run_bot.py` 可正常啟動（不報錯）

**實作提示**：此階段不涉及爬蟲邏輯，只是準備環境，應該快速完成（15-30 分鐘）。

---

## 階段二：基礎架構模組

### 概述

實作爬蟲的基礎元件：配置管理、商品名稱映射、新聞儲存管理。這些是爬蟲核心的支撐模組。

### 需要創建的檔案

#### 1. 爬蟲配置模組

**檔案**：`src/crawler/config.py`

**功能**：
- 定義 `CrawlerConfig` 資料類別
- 從環境變數載入爬蟲配置
- 驗證配置的有效性

**完整程式碼**：

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
            interval_jitter_seconds=int(os.getenv('CRAWLER_JITTER_SECONDS', '15')),
            markets_dir=os.getenv('MARKETS_DIR', 'markets'),
            enabled=os.getenv('CRAWLER_ENABLED', 'true').lower() in ('true', '1', 'yes'),
            telegram_notify_groups=[
                int(gid.strip())
                for gid in os.getenv('CRAWLER_NOTIFY_GROUPS', '').split(',')
                if gid.strip()
            ]
        )
```

**測試方式**：

```python
# 在 Python REPL 中測試
from src.crawler.config import CrawlerConfig

config = CrawlerConfig.from_env()
print(f"啟用狀態: {config.enabled}")
print(f"目標 URL: {config.target_url}")
print(f"爬取間隔: {config.crawl_interval_minutes} 分鐘")
print(f"通知群組: {config.telegram_notify_groups}")
```

#### 2. 商品名稱映射模組

**檔案**：`src/crawler/commodity_mapper.py`

**功能**：
- 提供新聞關鍵字與 markets 目錄的映射關係
- 從新聞文本中提取商品名稱
- 驗證商品目錄是否存在

**完整程式碼**：

```python
"""
商品名稱映射模組

提供新聞中的商品名稱與 markets/ 目錄的映射關係。
"""

from typing import Optional
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

        # 農產品
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

**測試方式**：

```python
# 在 Python REPL 中測試
from src.crawler.commodity_mapper import CommodityMapper

mapper = CommodityMapper('markets')

# 測試提取商品
print(mapper.extract_commodity("Gold prices surge to new high"))  # 應輸出: Gold
print(mapper.extract_commodity("Bitcoin breaks $100,000"))  # 應輸出: Bitcoin
print(mapper.extract_commodity("Random news about stocks"))  # 應輸出: None
```

#### 3. 新聞儲存管理模組

**檔案**：`src/crawler/news_storage.py`

**功能**：
- 將新聞保存到 `markets/<商品>/yyyymmdd.txt`
- 自動管理遞增 ID
- 檢查新聞重複
- 處理檔案鎖（跨平台相容）

**完整程式碼**：

```python
"""
新聞儲存模組

負責將新聞保存到 markets/<商品>/yyyymmdd.txt，並管理 ID。
"""

from typing import Optional, Tuple
from pathlib import Path
from datetime import datetime
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
                # Windows 不支援 fcntl，使用 try-except 包裝
                try:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except (ImportError, OSError):
                    # Windows 或不支援檔案鎖的系統，直接寫入
                    pass

                # 寫入格式：[ID] 新聞內容
                f.write(f"[{next_id}] {news_text}\n")
                f.write("-" * 80 + "\n")

                # 解鎖（若有鎖）
                try:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except (ImportError, OSError):
                    pass

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

            # 簡單的字串包含檢查
            # 移除 news_text 前後空白，並檢查是否已在檔案中
            return news_text.strip() in content

        except Exception as e:
            logger.warning(f"檢查重複時發生錯誤：{e}")
            return False
```

**測試方式**：

```python
# 在 Python REPL 中測試
from src.crawler.news_storage import NewsStorage

storage = NewsStorage('markets')

# 測試保存新聞
success, news_id = storage.save_news('Gold', 'Gold prices surge to new high')
print(f"保存成功: {success}, ID: {news_id}")

# 測試重複檢查
is_dup = storage.check_duplicate('Gold', 'Gold prices surge to new high')
print(f"是否重複: {is_dup}")
```

### 成功標準

#### 自動化驗證
- [ ] `src/crawler/config.py` 存在且可正常導入
- [ ] `src/crawler/commodity_mapper.py` 存在且可正常導入
- [ ] `src/crawler/news_storage.py` 存在且可正常導入
- [ ] 在 Python REPL 中可成功執行上述測試程式碼

#### 手動驗證
- [ ] `CrawlerConfig.from_env()` 能正確載入環境變數
- [ ] `CommodityMapper` 能正確匹配商品（測試 Gold, Bitcoin, 無匹配案例）
- [ ] `NewsStorage` 能正確保存新聞到檔案，ID 遞增正常
- [ ] 重複新聞被正確識別

**實作提示**：
- 此階段著重於基礎模組，不涉及網路請求
- 可在本地測試，無需啟動 Bot
- 預估時間：1-1.5 小時

---

## 階段三：爬蟲核心模組

### 概述

實作新聞爬蟲的核心功能：HTML 抓取、解析、商品提取、新聞儲存。這是整個系統的心臟。

### 關鍵前置步驟：HTML 結構分析

**⚠️ 重要**：在實作之前，必須手動分析 tradingeconomics.com 的實際 HTML 結構。

**分析步驟**：

1. 使用瀏覽器訪問 `https://tradingeconomics.com/stream?c=commodity`
2. 按 F12 打開開發者工具
3. 使用「元素選擇器」（游標圖示）點選新聞項目
4. 記錄以下資訊：
   - 新聞容器的 CSS 類別或 ID
   - 標題元素的選擇器
   - 內容元素的選擇器
   - 時間元素的選擇器（如有）

**範例記錄表**（需根據實際填寫）：

```
新聞容器: div.stream-item
標題元素: h3.stream-title
內容元素: p.stream-content
時間元素: time (datetime 屬性)
```

### 需要創建的檔案

#### 1. 新聞爬蟲核心模組

**檔案**：`src/crawler/news_crawler.py`

**功能**：
- 從目標網站抓取 HTML
- 解析新聞列表
- 提取商品名稱並儲存
- 防爬蟲策略（延遲、User-Agent 輪換）

**完整程式碼**：

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
        delay = random.uniform(0.5, 2.0)
        logger.debug(f"請求前延遲 {delay:.2f} 秒")
        await asyncio.sleep(delay)

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

        ⚠️ 重要：此函式的 CSS 選擇器需要根據實際網站結構調整！

        參數：
            html: 網頁 HTML 內容

        回傳：
            新聞列表 [{'title': ..., 'content': ..., 'full_text': ..., 'time': ...}, ...]
        """
        soup = BeautifulSoup(html, 'lxml')
        news_list = []

        # TODO: 根據實際網站結構調整選擇器
        # 以下為示意程式碼，需根據 tradingeconomics.com 的實際 HTML 結構修改
        try:
            # 範例：假設新聞在 <div class="stream-item"> 中
            # ⚠️ 請根據實際 HTML 結構修改此選擇器
            items = soup.select('div.stream-item')

            if not items:
                # 嘗試備用選擇器
                logger.warning("主要選擇器 'div.stream-item' 無匹配，嘗試備用選擇器")
                items = soup.select('article.news-item')

            if not items:
                logger.warning("所有選擇器都無法匹配，請檢查網站結構")

            for item in items:
                try:
                    # 提取標題
                    # ⚠️ 請根據實際 HTML 結構修改此選擇器
                    title_elem = item.select_one('h3, h2, .title')
                    title = title_elem.get_text(strip=True) if title_elem else ''

                    # 提取內容
                    # ⚠️ 請根據實際 HTML 結構修改此選擇器
                    content_elem = item.select_one('p, .content, .description')
                    content = content_elem.get_text(strip=True) if content_elem else ''

                    # 提取時間
                    # ⚠️ 請根據實際 HTML 結構修改此選擇器
                    time_elem = item.select_one('time, .timestamp, .date')
                    time_str = ''
                    if time_elem:
                        time_str = time_elem.get('datetime', '') or time_elem.get_text(strip=True)

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

### HTML 結構調整指引

**在 `parse_news()` 函式中需要調整的地方**（標記為 `⚠️`）：

1. **新聞容器選擇器**（第 158 行）
   ```python
   items = soup.select('div.stream-item')  # ← 根據實際修改
   ```

2. **標題選擇器**（第 168 行）
   ```python
   title_elem = item.select_one('h3, h2, .title')  # ← 根據實際修改
   ```

3. **內容選擇器**（第 173 行）
   ```python
   content_elem = item.select_one('p, .content, .description')  # ← 根據實際修改
   ```

4. **時間選擇器**（第 178 行）
   ```python
   time_elem = item.select_one('time, .timestamp, .date')  # ← 根據實際修改
   ```

### 測試方式

#### 獨立測試爬蟲

建立測試腳本 `test_crawler_standalone.py`（專案根目錄）：

```python
"""
獨立測試爬蟲功能
"""
import asyncio
from src.crawler.config import CrawlerConfig
from src.crawler.news_crawler import NewsCrawler
from loguru import logger

async def test_crawl():
    """測試爬取功能"""
    # 載入配置
    config = CrawlerConfig.from_env()

    # 創建爬蟲
    crawler = NewsCrawler(config)

    # 執行爬取
    saved_news = await crawler.crawl()

    # 顯示結果
    logger.info(f"測試完成，共保存 {len(saved_news)} 則新聞")
    for news in saved_news:
        logger.info(f"  - {news['commodity']} (ID: {news['news_id']}): {news['text'][:50]}...")

if __name__ == '__main__':
    asyncio.run(test_crawl())
```

**執行測試**：
```bash
python test_crawler_standalone.py
```

### 成功標準

#### 自動化驗證
- [ ] `src/crawler/news_crawler.py` 存在且可正常導入
- [ ] 執行 `test_crawler_standalone.py` 不報錯
- [ ] 網頁抓取成功（HTTP 200）

#### 手動驗證
- [ ] `parse_news()` 能正確解析出新聞列表（至少 1 則）
- [ ] 新聞被正確保存到 `markets/<商品>/yyyymmdd.txt`
- [ ] 檔案中的 ID 正確遞增（[1], [2], [3]...）
- [ ] 重複新聞不會被重複保存
- [ ] 日誌顯示商品匹配資訊（如 "匹配商品：gold -> Gold"）

**實作提示**：
- 此階段是核心功能，需要耐心調整 CSS 選擇器
- 建議先在瀏覽器中驗證選擇器的正確性
- 若解析失敗，檢查日誌中的錯誤訊息
- 預估時間：1.5-2 小時（包含 HTML 結構分析）

**⚠️ 階段三完成檢查點**：在進入階段四之前，請確保爬蟲能獨立運行並正確儲存新聞到檔案。

---

## 階段四：定時任務整合

### 概述

實作定時任務調度器，將爬蟲整合到 Telegram Bot 的生命週期中，實現自動化定時爬取。

### 需要創建/修改的檔案

#### 1. 爬蟲調度器模組

**檔案**：`src/crawler/scheduler.py`

**功能**：
- 使用 APScheduler 管理定時任務
- 整合 Telegram 通知功能
- 與 Bot 生命週期同步

**完整程式碼**：

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
                    logger.info(f"已發送通知到群組 {group_id}")

                except Exception as e:
                    logger.error(f"發送通知到群組 {group_id} 失敗：{e}")

    def _format_news_message(self, news: dict) -> str:
        """
        格式化新聞訊息

        參數：
            news: 新聞資料

        回傳：
            格式化後的 Markdown 訊息
        """
        commodity = news['commodity']
        news_id = news['news_id']
        text = news['text']
        time = news.get('time', 'N/A')

        # 限制文本長度（Telegram 單則訊息最多 4096 字元）
        max_length = 3000
        if len(text) > max_length:
            text = text[:max_length] + "..."

        message = (
            f"📰 **{commodity} 商品新聞** (ID: {news_id})\n\n"
            f"{text}\n\n"
            f"⏰ {time}"
        )

        return message

    def start(self):
        """
        啟動定時任務
        """
        if not self.config.enabled:
            logger.info("爬蟲已停用（CRAWLER_ENABLED=false），不啟動定時任務")
            return

        # 計算 jitter（隨機化範圍）
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

#### 2. 整合到 Telegram Bot

**檔案**：`src/bot/telegram_bot.py`

**修改內容**：在檔案開頭導入爬蟲模組，並在 `__init__()` 和生命週期鉤子中整合爬蟲。

**修改步驟**：

**步驟 1**：在檔案開頭新增導入（約第 19 行之後）

```python
from .config import BotConfig
from .handlers import (
    start_command,
    help_command,
    status_command,
    handle_message,
    handle_error
)

# 新增：導入爬蟲模組
from src.crawler.config import CrawlerConfig
from src.crawler.scheduler import CrawlerScheduler
```

**步驟 2**：在 `__init__()` 方法中初始化爬蟲調度器（約第 58 行之後）

```python
    def __init__(self, config: BotConfig):
        """
        初始化 Bot

        參數：
            config: Bot 設定
        """
        self.config = config

        # 建立 Application
        self.application = (
            Application.builder()
            .token(config.telegram_bot_token)
            .build()
        )

        # 儲存設定到 bot_data
        self.application.bot_data['config'] = config

        # 註冊處理器
        self._register_handlers()

        # 新增：初始化爬蟲調度器
        crawler_config = CrawlerConfig.from_env()
        self.crawler_scheduler = CrawlerScheduler(
            config=crawler_config,
            telegram_app=self.application
        )

        logger.info("Telegram Bot 初始化完成")
```

**步驟 3**：在 `_post_init()` 方法中啟動爬蟲（約第 95 行之後）

```python
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
```

**步驟 4**：在 `_post_shutdown()` 方法中停止爬蟲（約第 128 行之後）

```python
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

### 測試方式

#### 啟動 Bot 並驗證爬蟲整合

```bash
python scripts/run_bot.py
```

**預期日誌輸出**：

```
2026-01-02 14:30:00 | INFO | 爬蟲調度器初始化完成
2026-01-02 14:30:00 | INFO | Telegram Bot 初始化完成
2026-01-02 14:30:01 | INFO | Bot 用戶名：@YourBotName
2026-01-02 14:30:01 | INFO | Bot ID：1234567890
2026-01-02 14:30:01 | INFO | 已發送開張訊息到群組 -1001234567890
2026-01-02 14:30:01 | INFO | 爬蟲定時任務已啟動：每 5 分鐘 (±15 秒) 執行一次
2026-01-02 14:30:01 | INFO | 爬蟲定時任務已整合到 Bot 生命週期
```

#### 驗證定時任務觸發

等待約 5 分鐘，應看到爬蟲自動執行：

```
2026-01-02 14:35:12 | INFO | =============================================================
2026-01-02 14:35:12 | INFO | 開始爬取商品新聞
2026-01-02 14:35:12 | INFO | =============================================================
2026-01-02 14:35:13 | INFO | 正在抓取：https://tradingeconomics.com/stream?c=commodity
2026-01-02 14:35:14 | INFO | 網頁抓取成功
2026-01-02 14:35:14 | INFO | 成功解析 10 則新聞
2026-01-02 14:35:14 | INFO | 新聞已保存：Gold ID=1
2026-01-02 14:35:14 | INFO | 已發送通知到群組 -1001234567890
...
```

### 成功標準

#### 自動化驗證
- [ ] `src/crawler/scheduler.py` 存在且可正常導入
- [ ] `src/bot/telegram_bot.py` 修改後無語法錯誤
- [ ] 執行 `python scripts/run_bot.py` 可正常啟動
- [ ] 日誌顯示「爬蟲定時任務已啟動」

#### 手動驗證
- [ ] Bot 啟動後自動啟動爬蟲定時任務
- [ ] 等待 5 分鐘後，爬蟲自動執行一次
- [ ] 日誌顯示爬取過程和結果
- [ ] 若有新新聞，Telegram 群組收到通知
- [ ] 使用 Ctrl+C 停止 Bot 時，日誌顯示「爬蟲定時任務已停止」

**實作提示**：
- 此階段整合了 Bot 和爬蟲，需要確保不影響 Bot 原有功能
- 可先設定 `CRAWLER_ENABLED=false` 測試 Bot 啟動，確認無影響
- 預估時間：30-45 分鐘

---

## 階段五：Telegram 通知優化與測試

### 概述

優化 Telegram 通知訊息格式，新增手動測試指令，進行完整的端到端測試。

### 需要創建/修改的檔案

#### 1. 新增手動測試指令（選用）

**檔案**：`src/bot/handlers.py`

**功能**：新增 `/crawl_now` 指令，讓管理員可以手動觸發一次爬取

**修改內容**：在檔案末尾新增

```python
async def crawl_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /crawl_now 指令處理器

    手動觸發一次新聞爬取（僅限管理員）
    """
    config = context.application.bot_data.get('config')

    # 檢查是否在允許的群組中
    if not config or not config.is_allowed_group(update.effective_chat.id):
        return

    # 檢查是否為管理員
    chat_member = await update.effective_chat.get_member(update.effective_user.id)
    if chat_member.status not in ['creator', 'administrator']:
        await update.message.reply_text("⚠️ 此指令僅限群組管理員使用")
        return

    await update.message.reply_text("🔄 正在手動觸發新聞爬取...")

    try:
        # 取得爬蟲調度器（從 Bot 實例）
        # 注意：需要在 telegram_bot.py 中將 crawler_scheduler 儲存到 bot_data
        crawler_scheduler = context.application.bot_data.get('crawler_scheduler')

        if crawler_scheduler:
            await crawler_scheduler._crawl_and_notify()
            await update.message.reply_text("✅ 爬取完成，請查看上方通知")
        else:
            await update.message.reply_text("❌ 爬蟲未啟動")

    except Exception as e:
        logger.error(f"手動爬取失敗：{e}")
        await update.message.reply_text(f"❌ 爬取失敗：{e}")
```

**整合到 Bot**：

**檔案**：`src/bot/telegram_bot.py`

**修改 `_register_handlers()` 方法**（約第 66 行）：

```python
    def _register_handlers(self):
        """註冊所有訊息處理器"""

        # 指令處理器（群組中的指令）
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("status", status_command))

        # 新增：手動爬取指令（選用）
        from .handlers import crawl_now_command
        self.application.add_handler(CommandHandler("crawl_now", crawl_now_command))

        # 訊息處理器：只接收群組中的非指令文字訊息
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
                handle_message
            )
        )

        # 錯誤處理器
        self.application.add_error_handler(handle_error)

        logger.info("所有處理器註冊完成（純群組模式）")
```

**修改 `__init__()` 方法**，將 `crawler_scheduler` 儲存到 `bot_data`（約第 76 行）：

```python
        # 新增：初始化爬蟲調度器
        crawler_config = CrawlerConfig.from_env()
        self.crawler_scheduler = CrawlerScheduler(
            config=crawler_config,
            telegram_app=self.application
        )

        # 新增：儲存到 bot_data，供指令處理器使用
        self.application.bot_data['crawler_scheduler'] = self.crawler_scheduler
```

#### 2. 優化通知訊息格式

**檔案**：`src/crawler/scheduler.py`

**修改 `_format_news_message()` 方法**（約第 76 行）：

```python
    def _format_news_message(self, news: dict) -> str:
        """
        格式化新聞訊息

        參數：
            news: 新聞資料

        回傳：
            格式化後的 Markdown 訊息
        """
        commodity = news['commodity']
        news_id = news['news_id']
        text = news['text']
        time = news.get('time', 'N/A')

        # 限制文本長度（Telegram 單則訊息最多 4096 字元）
        max_length = 3000
        if len(text) > max_length:
            text = text[:max_length] + "..."

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
            f"{text}\n\n"
            f"{'─' * 40}\n"
            f"⏰ {time}"
        )

        return message
```

### 測試計畫

#### 1. 單元測試（選用）

**檔案**：`tests/test_crawler/test_scheduler.py`

```python
"""
測試爬蟲調度器
"""
import pytest
from src.crawler.config import CrawlerConfig
from src.crawler.scheduler import CrawlerScheduler


def test_format_news_message():
    """測試訊息格式化"""
    config = CrawlerConfig.from_env()
    scheduler = CrawlerScheduler(config)

    news = {
        'commodity': 'Gold',
        'news_id': 1,
        'text': 'Gold prices surge to new high',
        'time': '2026-01-02T14:30:00Z'
    }

    message = scheduler._format_news_message(news)

    assert 'Gold' in message
    assert 'ID: 1' in message
    assert 'Gold prices surge' in message
```

#### 2. 整合測試

**測試步驟**：

1. **啟動 Bot**
   ```bash
   python scripts/run_bot.py
   ```

2. **驗證啟動訊息**
   - Telegram 群組收到「Chip House 傳出工作聲...」訊息

3. **手動觸發爬取**（若實作了 `/crawl_now` 指令）
   - 在群組中發送 `/crawl_now`
   - 驗證收到「正在手動觸發...」訊息
   - 驗證收到新聞通知（若有新新聞）

4. **等待自動爬取**
   - 等待 5 分鐘
   - 驗證爬蟲自動執行
   - 驗證 Telegram 通知

5. **檢查檔案儲存**
   ```bash
   # 查看今天的新聞檔案
   ls markets/Gold/
   cat markets/Gold/20260102.txt
   ```
   - 驗證 ID 格式正確（[1], [2], ...）
   - 驗證新聞內容完整

6. **停止 Bot**
   - Ctrl+C 停止
   - 驗證日誌顯示「爬蟲定時任務已停止」

#### 3. 壓力測試（選用）

**測試場景**：
- 設定 `CRAWLER_INTERVAL_MINUTES=1`，觀察 1 小時
- 驗證無記憶體洩漏
- 驗證日誌檔案大小合理

### 成功標準

#### 自動化驗證
- [ ] Bot 可正常啟動和停止
- [ ] 爬蟲定時任務正常運作
- [ ] 無 Python 異常或錯誤日誌

#### 手動驗證
- [ ] Telegram 通知訊息格式美觀、可讀性強
- [ ] `/crawl_now` 指令可正常觸發爬取（若實作）
- [ ] 新聞儲存到檔案，格式正確
- [ ] 重複新聞不會被重複通知
- [ ] 爬蟲失敗不影響 Bot 其他功能（如 Claude 對話）
- [ ] 日誌記錄詳細且易於除錯

**實作提示**：
- 此階段著重於使用者體驗和穩定性
- 建議在測試群組中進行完整測試
- 預估時間：1-1.5 小時

---

## 階段六：文檔與收尾

### 概述

撰寫使用說明、更新專案文檔、處理邊界情況、優化錯誤處理。

### 需要創建/修改的檔案

#### 1. 更新專案 README（選用）

**檔案**：`README.md`

**新增內容**（在適當位置）：

```markdown
## 商品新聞爬蟲功能

Bot 內建商品新聞爬蟲，可自動從 tradingeconomics.com 抓取商品相關新聞。

### 功能特色

- ⏰ 每 5 分鐘自動爬取一次（可配置）
- 📁 新聞保存到 `markets/<商品>/yyyymmdd.txt`
- 📱 即時發送到 Telegram 群組
- 🔒 防爬蟲策略（延遲、User-Agent 輪換）
- 🔄 自動去重

### 配置

在 `.env` 檔案中配置：

```bash
# 啟用爬蟲
CRAWLER_ENABLED=true

# 爬取間隔（分鐘）
CRAWLER_INTERVAL_MINUTES=5

# 通知群組 ID
CRAWLER_NOTIFY_GROUPS=-1001234567890
```

### 手動觸發

群組管理員可使用 `/crawl_now` 指令手動觸發一次爬取。

### 停用爬蟲

若要停用爬蟲功能：

```bash
CRAWLER_ENABLED=false
```
```

#### 2. 建立爬蟲模組 README

**檔案**：`src/crawler/README.md`

```markdown
# 商品新聞爬蟲模組

## 架構概述

```
src/crawler/
├── __init__.py             # 模組初始化
├── config.py               # 配置管理
├── commodity_mapper.py     # 商品名稱映射
├── news_storage.py         # 新聞儲存管理
├── news_crawler.py         # 爬蟲核心
└── scheduler.py            # 定時任務調度
```

## 模組職責

### config.py - 配置管理
- 從環境變數載入爬蟲配置
- 提供配置驗證

### commodity_mapper.py - 商品名稱映射
- 維護新聞關鍵字與 markets 目錄的映射表
- 從新聞文本中提取商品名稱

### news_storage.py - 新聞儲存管理
- 將新聞保存到 `markets/<商品>/yyyymmdd.txt`
- 自動管理遞增 ID
- 檢查新聞重複

### news_crawler.py - 爬蟲核心
- 從 tradingeconomics.com 抓取 HTML
- 解析新聞列表
- 提取商品並儲存

### scheduler.py - 定時任務調度
- 使用 APScheduler 管理定時任務
- 整合 Telegram 通知
- 與 Bot 生命週期同步

## 使用範例

### 獨立使用爬蟲

```python
import asyncio
from src.crawler.config import CrawlerConfig
from src.crawler.news_crawler import NewsCrawler

async def crawl():
    config = CrawlerConfig.from_env()
    crawler = NewsCrawler(config)
    saved_news = await crawler.crawl()
    print(f"共保存 {len(saved_news)} 則新聞")

asyncio.run(crawl())
```

### 整合到 Bot

爬蟲已自動整合到 `TelegramBot` 的生命週期中：

- Bot 啟動時自動啟動爬蟲定時任務
- Bot 關閉時自動停止爬蟲

## 維護指南

### 更新商品映射表

編輯 `commodity_mapper.py` 的 `COMMODITY_MAP`：

```python
COMMODITY_MAP = {
    'new_commodity': 'NewCommodity',  # 新增
    # ...
}
```

### 調整 HTML 選擇器

若網站結構改變，編輯 `news_crawler.py` 的 `parse_news()` 方法。

### 調整爬取間隔

修改 `.env` 檔案：

```bash
CRAWLER_INTERVAL_MINUTES=10  # 改為 10 分鐘
```

## 故障排除

### 問題：爬蟲無法解析新聞

**原因**：網站 HTML 結構改變

**解決**：
1. 訪問目標網站，檢查 HTML 結構
2. 使用瀏覽器開發者工具找到新的選擇器
3. 更新 `news_crawler.py` 的 CSS 選擇器

### 問題：Telegram 通知失敗

**原因**：群組 ID 錯誤或 Bot 無權限

**解決**：
1. 確認 `CRAWLER_NOTIFY_GROUPS` 設定正確
2. 確認 Bot 已加入群組
3. 確認 Bot 有發送訊息權限

### 問題：新聞重複保存

**原因**：去重邏輯失效

**解決**：
1. 檢查 `news_storage.py` 的 `check_duplicate()` 方法
2. 考慮使用 hash 去重（更可靠）
```

#### 3. 建立故障排除文檔

**檔案**：`docs/crawler-troubleshooting.md`

```markdown
# 爬蟲故障排除指南

## 常見問題

### 1. 爬蟲無法啟動

**症狀**：日誌顯示「爬蟲已停用」

**解決**：
```bash
# 檢查 .env 檔案
CRAWLER_ENABLED=true
```

### 2. 網頁抓取失敗（HTTP 403/429）

**症狀**：日誌顯示「HTTP 403」或「HTTP 429」

**原因**：IP 被封鎖或請求過於頻繁

**解決**：
- 增加爬取間隔：`CRAWLER_INTERVAL_MINUTES=10`
- 檢查 User-Agent 是否正常輪換
- 考慮使用代理 IP（進階）

### 3. 無法解析新聞

**症狀**：日誌顯示「成功解析 0 則新聞」

**原因**：HTML 結構改變

**解決**：
1. 訪問 https://tradingeconomics.com/stream?c=commodity
2. 按 F12 打開開發者工具
3. 找到新聞容器的 CSS 選擇器
4. 更新 `src/crawler/news_crawler.py` 的 `parse_news()` 方法

### 4. Telegram 通知失敗

**症狀**：日誌顯示「發送通知失敗」

**可能原因**：
- 群組 ID 錯誤
- Bot 未加入群組
- Bot 無發送訊息權限
- 訊息過長（超過 4096 字元）

**解決**：
- 檢查 `CRAWLER_NOTIFY_GROUPS` 設定
- 確認 Bot 在群組中
- 檢查訊息長度限制邏輯

### 5. 檔案寫入失敗

**症狀**：日誌顯示「保存新聞失敗」

**可能原因**：
- `markets/` 目錄權限不足
- 磁碟空間不足
- 路徑錯誤

**解決**：
```bash
# 檢查目錄權限
ls -la markets/

# 確保目錄存在
mkdir -p markets/Gold markets/Silver
```

## 除錯技巧

### 啟用詳細日誌

```bash
# .env
DEBUG=true
```

### 檢視爬蟲日誌

```bash
# 查看今天的日誌
cat logs/bot_2026-01-02.log | grep crawler

# 即時查看
tail -f logs/bot_2026-01-02.log
```

### 手動測試爬蟲

```python
# test_manual_crawl.py
import asyncio
from src.crawler.config import CrawlerConfig
from src.crawler.news_crawler import NewsCrawler

async def test():
    config = CrawlerConfig.from_env()
    crawler = NewsCrawler(config)

    # 測試抓取
    html = await crawler.fetch_page()
    print(f"HTML 長度: {len(html)}")

    # 測試解析
    news_list = crawler.parse_news(html)
    print(f"解析到 {len(news_list)} 則新聞")
    for news in news_list[:3]:
        print(f"  - {news['title']}")

asyncio.run(test())
```

## 效能監控

### 記憶體使用

```bash
# 監控 Python 程序記憶體
ps aux | grep python
```

### 爬取成功率

定期檢查日誌，統計成功/失敗次數：

```bash
grep "爬取完成" logs/bot_*.log | wc -l  # 成功次數
grep "爬取失敗" logs/bot_*.log | wc -l  # 失敗次數
```
```

### 成功標準

#### 自動化驗證
- [ ] 文檔檔案存在且格式正確
- [ ] README 包含爬蟲功能說明

#### 手動驗證
- [ ] 文檔清晰易懂，有範例程式碼
- [ ] 故障排除指南涵蓋常見問題
- [ ] 維護指南提供必要的操作步驟

**實作提示**：
- 文檔應面向未來的維護者
- 範例程式碼應可直接執行
- 預估時間：30-45 分鐘

---

## 整體測試與驗收

### 完整端到端測試

1. **環境準備**
   ```bash
   # 確認環境變數
   cat .env | grep CRAWLER

   # 確認依賴已安裝
   pip list | grep -E "httpx|beautifulsoup4|lxml|APScheduler"
   ```

2. **啟動 Bot**
   ```bash
   python scripts/run_bot.py
   ```

3. **驗證爬蟲啟動**
   - [ ] 日誌顯示「爬蟲定時任務已啟動」
   - [ ] 日誌顯示爬取間隔（如「每 5 分鐘 (±15 秒) 執行一次」）

4. **等待第一次爬取**
   - [ ] 約 5 分鐘後，日誌顯示「開始爬取商品新聞」
   - [ ] 日誌顯示「網頁抓取成功」
   - [ ] 日誌顯示「成功解析 X 則新聞」
   - [ ] 日誌顯示「新聞已保存：Gold ID=1」（或其他商品）
   - [ ] 日誌顯示「已發送通知到群組」

5. **檢查 Telegram 群組**
   - [ ] 收到新聞通知訊息
   - [ ] 訊息格式正確（商品名、ID、內容、時間）
   - [ ] 表情符號顯示正確

6. **檢查檔案儲存**
   ```bash
   # 查看今天的新聞
   ls markets/Gold/
   cat markets/Gold/20260102.txt
   ```
   - [ ] 檔案存在
   - [ ] ID 格式正確：`[1] 新聞內容`
   - [ ] 分隔線正確：`--------...`

7. **測試手動觸發**（若實作）
   - [ ] 在群組中發送 `/crawl_now`
   - [ ] 收到「正在手動觸發...」回覆
   - [ ] 爬蟲立即執行
   - [ ] 收到新新聞通知（若有）

8. **測試去重**
   - [ ] 等待下一次爬取（5 分鐘後）
   - [ ] 重複新聞不再發送通知
   - [ ] 日誌顯示「新聞重複，忽略」

9. **測試停用功能**
   ```bash
   # 修改 .env
   CRAWLER_ENABLED=false

   # 重啟 Bot
   python scripts/run_bot.py
   ```
   - [ ] 日誌顯示「爬蟲已停用，不啟動定時任務」
   - [ ] 無爬取活動

10. **壓力測試**（選用）
    ```bash
    # 設定為 1 分鐘間隔
    CRAWLER_INTERVAL_MINUTES=1
    ```
    - [ ] 運行 1 小時，無異常
    - [ ] 記憶體穩定
    - [ ] 日誌檔案大小合理

### 邊界情況測試

1. **網路故障**
   - [ ] 拔除網路線，爬蟲失敗但不影響 Bot
   - [ ] 日誌顯示「網頁抓取異常」
   - [ ] 重新連接後，下次爬取恢復正常

2. **目標網站無回應**
   - [ ] 修改 `CRAWLER_TARGET_URL` 為無效 URL
   - [ ] 爬蟲失敗，日誌記錄錯誤
   - [ ] Bot 其他功能正常

3. **磁碟空間不足**（模擬）
   - [ ] 爬蟲報錯但不崩潰
   - [ ] 日誌記錄「保存新聞失敗」

4. **Telegram API 限流**
   - [ ] 短時間內發送大量訊息
   - [ ] 失敗訊息有日誌記錄
   - [ ] 不影響後續爬取

## 潛在風險與解決方案

### 風險 1：網站 HTML 結構改變

**影響**：爬蟲無法解析新聞

**解決方案**：
- 使用多個備用 CSS 選擇器
- 定期監控爬取成功率
- 建立告警機制（如爬取失敗超過 3 次發送通知）

**程式碼範例**（已在 `news_crawler.py` 實作）：

```python
# 主要選擇器
items = soup.select('div.stream-item')

if not items:
    # 備用選擇器
    items = soup.select('article.news-item')

if not items:
    logger.warning("所有選擇器都無法匹配")
```

### 風險 2：IP 被封鎖

**影響**：無法抓取網頁（HTTP 403/429）

**解決方案**：
- 已實作：隨機延遲、User-Agent 輪換、Headers 偽裝
- 進階：整合代理 IP 池（本次實作不包含）
- 應急：增加爬取間隔（如 10 分鐘）

### 風險 3：商品名稱匹配不準

**影響**：新聞保存到錯誤商品或未保存

**解決方案**：
- 擴充 `COMMODITY_MAP` 映射表
- 記錄未匹配的新聞（日誌級別 DEBUG）
- 定期人工檢視，優化映射規則

**改進範例**（未來可實作）：

```python
# 使用正則表達式提高準確性
import re

COMMODITY_PATTERNS = {
    'Gold': [r'\bgold\b', r'\bxau\b', r'\bgc\b'],
    'Silver': [r'\bsilver\b', r'\bxag\b', r'\bsi\b'],
}
```

### 風險 4：新聞重複檢測失效

**影響**：同一新聞被多次保存

**解決方案**：
- 目前使用簡單字串包含檢查（可應對大部分情況）
- 進階：使用 MD5 hash 去重（更可靠）

**改進範例**（未來可實作）：

```python
import hashlib

def get_news_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()

# 儲存 hash 到檔案或資料庫，檢查時比對 hash
```

### 風險 5：檔案併發寫入衝突

**影響**：多個爬蟲實例同時寫入，資料損壞

**解決方案**：
- 已實作：檔案鎖（Linux/Unix 使用 fcntl）
- Windows：目前使用 try-except 忽略（單實例運行無問題）
- 確保只運行一個 Bot 實例

**Windows 檔案鎖改進**（未來可實作）：

```python
import msvcrt

def save_with_windows_lock(file_path, content):
    with open(file_path, 'a', encoding='utf-8') as f:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1024)
        f.write(content)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1024)
```

## 後續優化建議

完成基本實作後，可考慮以下優化（不在本次實作範圍）：

### 1. 資料庫儲存

**目標**：使用 SQLite 替代純文字檔案

**優點**：
- 更可靠的去重機制
- 支援複雜查詢
- 更好的併發控制

**實作概要**：
```python
# 資料表結構
CREATE TABLE news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commodity TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### 2. 多語言支援

**目標**：翻譯英文新聞為繁體中文

**實作方式**：
- 使用翻譯 API（Google Translate, DeepL）
- 或整合 Claude API 進行翻譯

### 3. 情感分析

**目標**：分析新聞情感（看漲/看跌）

**實作方式**：
- 使用 NLP 庫（如 TextBlob, VADER）
- 或使用 Claude API 進行分析

### 4. Web Dashboard

**目標**：提供網頁介面查看歷史新聞

**技術棧**：
- 後端：Flask/FastAPI
- 前端：Vue.js/React
- 資料庫：SQLite/PostgreSQL

### 5. 多來源整合

**目標**：整合多個新聞來源

**來源建議**：
- Reuters
- Bloomberg
- Investing.com
- MarketWatch

### 6. 告警機制

**目標**：爬取失敗時發送告警

**實作方式**：
```python
# 連續失敗 3 次時發送告警
if consecutive_failures >= 3:
    await send_alert("⚠️ 爬蟲連續失敗 3 次，請檢查")
```

## 時間預估總結

| 階段 | 預估時間 | 累計時間 |
|------|---------|---------|
| 階段一：前置準備與環境設定 | 15-30 分鐘 | 0.5 小時 |
| 階段二：基礎架構模組 | 1-1.5 小時 | 2 小時 |
| 階段三：爬蟲核心模組 | 1.5-2 小時 | 4 小時 |
| 階段四：定時任務整合 | 30-45 分鐘 | 4.75 小時 |
| 階段五：Telegram 通知優化與測試 | 1-1.5 小時 | 6 小時 |
| 階段六：文檔與收尾 | 30-45 分鐘 | 6.5-7 小時 |
| **總計** | **5.5-7 小時** | - |

**注意**：實際時間可能因以下因素變化：
- HTML 結構分析的複雜度
- 除錯和調整的時間
- 測試的完整程度
- 對專案架構的熟悉度

## 最終驗收清單

### 功能性

- [ ] 爬蟲可正常啟動和停止
- [ ] 定時任務按配置間隔執行
- [ ] 網頁抓取成功（HTTP 200）
- [ ] HTML 解析正確，能提取新聞
- [ ] 商品名稱匹配準確
- [ ] 新聞正確儲存到 `markets/<商品>/yyyymmdd.txt`
- [ ] ID 遞增正常（[1], [2], [3]...）
- [ ] 重複新聞被過濾
- [ ] Telegram 通知正常發送
- [ ] 訊息格式清晰美觀
- [ ] 手動觸發指令可用（若實作）
- [ ] 停用功能正常（CRAWLER_ENABLED=false）

### 非功能性

- [ ] 防爬蟲策略生效（延遲、UA 輪換）
- [ ] 錯誤處理完善，不崩潰
- [ ] 日誌記錄詳細且有用
- [ ] 記憶體使用穩定（無洩漏）
- [ ] 不影響 Bot 其他功能
- [ ] 程式碼結構清晰，易於維護
- [ ] 環境變數配置靈活

### 文檔

- [ ] README 包含爬蟲功能說明
- [ ] 爬蟲模組有獨立 README
- [ ] 故障排除文檔完整
- [ ] 程式碼註解清晰
- [ ] 有使用範例

## 參考資源

### 技術文檔

- **httpx**: https://www.python-httpx.org/
- **BeautifulSoup4**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- **APScheduler**: https://apscheduler.readthedocs.io/
- **python-telegram-bot**: https://docs.python-telegram-bot.org/

### 相關研究

- 研究報告：`thoughts/shared/research/2026-01-02-commodity-news-crawler-research.md`

### CSS 選擇器參考

- **MDN CSS Selectors**: https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Selectors
- **BeautifulSoup CSS Selectors**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/#css-selectors

---

**計畫制定日期**：2026-01-02
**預估總時間**：5.5-7 小時
**優先級**：🔴 高（核心功能）
**負責人**：開發團隊

---

## 附錄：快速啟動指令

```bash
# 1. 安裝依賴
pip install httpx beautifulsoup4 lxml APScheduler

# 2. 配置環境變數（編輯 .env）
nano .env
# 新增：
# CRAWLER_ENABLED=true
# CRAWLER_NOTIFY_GROUPS=-1001234567890

# 3. 啟動 Bot
python scripts/run_bot.py

# 4. 檢視日誌
tail -f logs/bot_$(date +%Y-%m-%d).log

# 5. 檢查新聞檔案
ls markets/Gold/
cat markets/Gold/$(date +%Y%m%d).txt
```

祝實作順利！🚀
