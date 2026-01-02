#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MT5 商品列表導出腳本

此腳本會連接到 MT5，導出所有啟用的商品列表，並為每個商品創建文件夾。

使用方式：
    python scripts/export_symbols.py

輸出：
    - markets/enabled_symbols.txt: 所有啟用商品的列表
    - markets/{Symbol}/: 每個商品的文件夾（首字大寫其餘小寫）
"""

import sys
import re
from pathlib import Path
from typing import List, Tuple

# 確保可以匯入 src 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

import MetaTrader5 as mt5
from loguru import logger
from src.core.mt5_client import ChipWhispererMT5Client
from src.core.mt5_config import MT5Config


# Futures 月份代碼對應表
FUTURES_MONTH_CODES = {
    'F': 'January', 'G': 'February', 'H': 'March', 'J': 'April',
    'K': 'May', 'M': 'June', 'N': 'July', 'Q': 'August',
    'U': 'September', 'V': 'October', 'X': 'November', 'Z': 'December'
}


def normalize_symbol_name(symbol: str) -> str:
    """
    正規化商品名稱為文件夾名稱

    規則：
    - 如果是以 # 開頭的 Future（如 #Cocoa_H26），去掉 # 和 _ 後面的內容
    - 如果是傳統 Future 格式（ESZ24, NQH25），移除月份和年份
    - 轉換為首字大寫其餘小寫

    範例：
        #Cocoa_H26 -> Cocoa
        #Coffee_H26 -> Coffee
        ESZ24 -> Es (E-mini S&P 500 December 2024)
        NQH25 -> Nq (E-mini Nasdaq March 2025)
        EURUSD -> Eurusd
        AAPL -> Aapl

    參數：
        symbol: 原始商品符號

    回傳：
        正規化後的名稱
    """
    # 處理以 # 開頭的 Future（例如：#Cocoa_H26, #Coffee_H26）
    if symbol.startswith('#'):
        # 去掉 # 符號
        symbol_without_hash = symbol[1:]

        # 如果包含 _，移除 _ 後面的內容
        if '_' in symbol_without_hash:
            base_symbol = symbol_without_hash.split('_')[0]
            logger.debug(f"檢測到 # Future: {symbol} -> {base_symbol}")
            return base_symbol.capitalize()
        else:
            # 沒有 _，直接去掉 # 並首字大寫
            return symbol_without_hash.capitalize()

    # 檢測傳統 futures 格式（例如：ESZ24, NQH25）
    # 格式通常是：商品代碼 + 月份代碼(單字母) + 年份(2位數)
    futures_pattern = r'^([A-Z]+)([FGHJKMNQUVXZ])(\d{2})$'
    match = re.match(futures_pattern, symbol)

    if match:
        # 是 futures，提取商品代碼部分
        base_symbol = match.group(1)
        month_code = match.group(2)
        year = match.group(3)

        month_name = FUTURES_MONTH_CODES.get(month_code, 'Unknown')
        logger.debug(
            f"檢測到 Futures: {symbol} -> {base_symbol} "
            f"({month_name} 20{year})"
        )

        return base_symbol.capitalize()

    # 不是 futures 或無法識別，直接轉換
    return symbol.capitalize()


def get_enabled_symbols(client: ChipWhispererMT5Client) -> List[Tuple[str, str]]:
    """
    獲取所有啟用的商品列表

    參數：
        client: MT5 客戶端

    回傳：
        (原始符號, 正規化名稱) 的列表
    """
    client.ensure_connected()

    # 獲取所有商品
    symbols = mt5.symbols_get()

    if symbols is None:
        logger.error("無法獲取商品列表")
        return []

    # 過濾啟用的商品
    enabled_symbols = []
    for symbol in symbols:
        # visible=True 表示在 Market Watch 中可見（啟用）
        if symbol.visible:
            original_name = symbol.name
            normalized_name = normalize_symbol_name(original_name)
            enabled_symbols.append((original_name, normalized_name))

    logger.info(f"找到 {len(enabled_symbols)} 個啟用的商品")
    return enabled_symbols


def export_symbols_list(symbols: List[Tuple[str, str]], output_dir: Path) -> None:
    """
    導出商品列表到文本文件

    參數：
        symbols: 商品列表
        output_dir: 輸出目錄
    """
    # 確保目錄存在
    output_dir.mkdir(parents=True, exist_ok=True)

    # 寫入文本文件
    output_file = output_dir / 'symbols.txt'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# MT5 啟用的商品列表\n")
        f.write(f"# 總計：{len(symbols)} 個商品\n")
        f.write("# 格式：原始符號 -> 文件夾名稱\n\n")

        for original, normalized in sorted(symbols):
            f.write(f"{original} -> {normalized}\n")

    logger.info(f"商品列表已導出到：{output_file}")


def create_symbol_folders(symbols: List[Tuple[str, str]], output_dir: Path) -> None:
    """
    為每個商品創建文件夾

    參數：
        symbols: 商品列表
        output_dir: 輸出目錄
    """
    # 使用 set 去重（因為多個 futures 可能對應同一個基礎商品）
    unique_folders = set(normalized for _, normalized in symbols)

    created_count = 0
    for folder_name in sorted(unique_folders):
        folder_path = output_dir / folder_name

        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            created_count += 1
            logger.debug(f"創建文件夾：{folder_path}")
        else:
            logger.debug(f"文件夾已存在：{folder_path}")

    logger.info(f"創建了 {created_count} 個新文件夾（共 {len(unique_folders)} 個唯一商品）")


def main():
    """主函式"""
    try:
        logger.info("=" * 60)
        logger.info("MT5 商品列表導出工具")
        logger.info("=" * 60)

        # 載入設定
        config = MT5Config()

        # 創建客戶端並連接
        with ChipWhispererMT5Client(config) as client:
            # 獲取啟用的商品
            symbols = get_enabled_symbols(client)

            if not symbols:
                logger.warning("沒有找到啟用的商品")
                return

            # 設定輸出目錄
            project_root = Path(__file__).parent.parent
            output_dir = project_root / 'markets'

            # 導出商品列表
            export_symbols_list(symbols, output_dir)

            # 創建商品文件夾
            create_symbol_folders(symbols, output_dir)

        logger.info("=" * 60)
        logger.info("導出完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"執行過程中發生錯誤：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
