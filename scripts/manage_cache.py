#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 快取管理命令列工具

使用方式：
    python scripts/manage_cache.py status
    python scripts/manage_cache.py check-gaps --symbol GOLD --timeframe H1
    python scripts/manage_cache.py fill-gaps --symbol GOLD --timeframe H1
    python scripts/manage_cache.py clear --symbol GOLD --timeframe H1
    python scripts/manage_cache.py optimize
"""

import sys
from pathlib import Path

# 新增專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from loguru import logger
from tabulate import tabulate

from src.core.sqlite_cache import SQLiteCacheManager
from src.core.mt5_client import ChipWhispererMT5Client
from src.core.mt5_config import MT5Config
from src.core.data_fetcher import HistoricalDataFetcher


@click.group()
@click.option(
    '--db-path',
    default='data/cache/mt5_cache.db',
    help='SQLite 資料庫路徑'
)
@click.pass_context
def cli(ctx, db_path):
    """SQLite 快取管理工具"""
    ctx.ensure_object(dict)
    ctx.obj['db_path'] = db_path
    ctx.obj['cache_manager'] = SQLiteCacheManager(db_path)


@cli.command()
@click.pass_context
def status(ctx):
    """顯示快取狀態"""
    manager = ctx.obj['cache_manager']

    # 查詢所有快取元數據
    conn = manager._get_connection()

    try:
        import pandas as pd

        query = "SELECT * FROM cache_metadata ORDER BY symbol, timeframe"
        df = pd.read_sql_query(query, conn)

        if df.empty:
            click.echo("快取為空")
            return

        # 格式化顯示
        df['first_time'] = pd.to_datetime(df['first_time']).dt.strftime('%Y-%m-%d')
        df['last_time'] = pd.to_datetime(df['last_time']).dt.strftime('%Y-%m-%d')
        df['last_update_time'] = pd.to_datetime(
            df['last_update_time']
        ).dt.strftime('%Y-%m-%d %H:%M')

        # 選擇要顯示的欄位
        display_df = df[[
            'symbol', 'timeframe', 'total_records',
            'first_time', 'last_time', 'has_gaps', 'gap_count'
        ]]

        click.echo("\n快取狀態摘要：\n")
        click.echo(tabulate(
            display_df.values,
            headers=display_df.columns,
            tablefmt='grid'
        ))

        # 統計資訊
        click.echo(f"\n總商品-週期組合數：{len(df)}")
        click.echo(f"總記錄數：{df['total_records'].sum()}")
        click.echo(f"有缺口的組合數：{df['has_gaps'].sum()}")

    finally:
        conn.close()


@cli.command()
@click.option('--symbol', required=True, help='商品代碼')
@click.option('--timeframe', required=True, help='時間週期')
@click.pass_context
def check_gaps(ctx, symbol, timeframe):
    """檢查數據缺口"""
    manager = ctx.obj['cache_manager']

    click.echo(f"\n檢查 {symbol} {timeframe} 的數據缺口...\n")

    # 執行缺口檢測
    gaps = manager.detect_data_gaps(symbol, timeframe)

    if not gaps:
        click.echo("未發現數據缺口")
        return

    click.echo(f"發現 {len(gaps)} 個數據缺口：\n")

    # 格式化顯示
    for i, gap in enumerate(gaps, 1):
        click.echo(f"{i}. {gap['gap_start']} ~ {gap['gap_end']}")
        click.echo(f"   時長：{gap['gap_duration_minutes']} 分鐘")
        click.echo(f"   預期記錄數：{gap['expected_records']}")
        click.echo()


@cli.command()
@click.option('--symbol', required=True, help='商品代碼')
@click.option('--timeframe', required=True, help='時間週期')
@click.option('--auto', is_flag=True, help='自動填補（不詢問）')
@click.pass_context
def fill_gaps(ctx, symbol, timeframe, auto):
    """填補數據缺口"""
    manager = ctx.obj['cache_manager']

    # 查詢未填補的缺口
    gaps_df = manager.get_gaps(symbol, timeframe, status='detected')

    if gaps_df.empty:
        click.echo("沒有需要填補的缺口")
        return

    click.echo(f"\n發現 {len(gaps_df)} 個未填補的缺口")

    # 顯示缺口清單
    for _, gap in gaps_df.iterrows():
        click.echo(
            f"  - {gap['gap_start']} ~ {gap['gap_end']} "
            f"(預期 {gap['expected_records']} 筆)"
        )

    # 確認是否填補
    if not auto:
        if not click.confirm('\n是否開始填補？'):
            click.echo("已取消")
            return

    # 建立 MT5 連線和 Fetcher
    client = None
    try:
        config = MT5Config()
        client = ChipWhispererMT5Client(config)
        client.connect()

        fetcher = HistoricalDataFetcher(client, use_sqlite=False)

        # 定義回調函數
        def fetch_callback(sym, tf, start, end):
            return fetcher._fetch_from_mt5_by_date(sym, tf, start, end)

        # 執行填補
        click.echo("\n開始填補缺口...\n")
        filled_count = manager.fill_data_gaps(
            symbol, timeframe, fetch_callback
        )

        click.echo(f"\n填補完成：成功填補 {filled_count} 個缺口")

    except Exception as e:
        click.echo(f"\n錯誤：{e}", err=True)
    finally:
        if client and client.is_connected():
            client.disconnect()


@cli.command()
@click.option('--symbol', help='商品代碼（可選）')
@click.option('--timeframe', help='時間週期（可選）')
@click.option('--force', is_flag=True, help='強制清除（不詢問）')
@click.pass_context
def clear(ctx, symbol, timeframe, force):
    """清除快取數據"""
    manager = ctx.obj['cache_manager']

    # 確認訊息
    if symbol and timeframe:
        msg = f"清除 {symbol} {timeframe} 的所有快取數據"
    elif symbol:
        msg = f"清除 {symbol} 的所有快取數據"
    else:
        msg = "清除所有快取數據"

    click.echo(f"\n{msg}")

    if not force:
        if not click.confirm('確定要繼續嗎？'):
            click.echo("已取消")
            return

    # 執行清除
    deleted_count = manager.clear_cache(symbol, timeframe)
    click.echo(f"\n已刪除 {deleted_count} 筆記錄")


@cli.command()
@click.pass_context
def optimize(ctx):
    """優化資料庫"""
    db_path = ctx.obj['db_path']

    click.echo("\n開始資料庫優化...\n")

    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # ANALYZE
        click.echo("1/3 分析查詢計劃...")
        cursor.execute("ANALYZE")

        # REINDEX
        click.echo("2/3 重建索引...")
        cursor.execute("REINDEX")

        # VACUUM
        click.echo("3/3 清理碎片...")
        cursor.execute("VACUUM")

        conn.commit()
        click.echo("\n資料庫優化完成")

    except Exception as e:
        click.echo(f"\n優化失敗：{e}", err=True)
    finally:
        conn.close()


if __name__ == '__main__':
    cli()
