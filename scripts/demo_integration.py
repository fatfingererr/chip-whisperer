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
                'text': 'Silver @ $30/oz, up 5% today!',
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

            print(f"通過")
            print(f"訊息長度: {len(message)} 字元")
            print(f"訊息預覽:\n{message[:200]}...")

            results.append({'case': case['name'], 'status': 'PASSED'})

        except Exception as e:
            print(f"失敗: {e}")
            results.append({'case': case['name'], 'status': 'FAILED', 'error': str(e)})

    # 顯示測試結果摘要
    print("\n" + "=" * 80)
    print("測試結果摘要")
    print("=" * 80)

    passed = sum(1 for r in results if r['status'] == 'PASSED')
    failed = sum(1 for r in results if r['status'] == 'FAILED')

    for result in results:
        status_icon = "PASS" if result['status'] == 'PASSED' else "FAIL"
        print(f"[{status_icon}] {result['case']}: {result['status']}")
        if 'error' in result:
            print(f"   錯誤: {result['error']}")

    print(f"\n通過: {passed}/{len(results)}")
    print(f"失敗: {failed}/{len(results)}")
    print("=" * 80)

    return failed == 0

if __name__ == '__main__':
    success = asyncio.run(test_integration())
    exit(0 if success else 1)
