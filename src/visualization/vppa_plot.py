"""
VPPA 視覺化主模組

提供 VPPA 分析結果的 Plotly 圖表繪製功能。
"""

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from loguru import logger
from typing import Optional
from datetime import timedelta

from .chart_config import COLORS, DEFAULT_LAYOUT, LINE_STYLES
from .plotly_utils import (
    validate_vppa_json,
    validate_candles_df,
    map_idx_to_time,
    normalize_volume_width,
    get_volume_colors
)


def _add_candlestick(fig: go.Figure, df: pd.DataFrame) -> None:
    """
    添加 K 線圖層

    參數：
        fig: Plotly Figure 物件
        df: K 線 DataFrame
    """
    logger.debug("添加 K 線圖層")

    candlestick = go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='K線',
        increasing_line_color=COLORS['candle_up'],
        decreasing_line_color=COLORS['candle_down'],
        increasing_fillcolor=COLORS['candle_up'],
        decreasing_fillcolor=COLORS['candle_down']
    )

    fig.add_trace(candlestick)
    logger.debug(f"K 線圖層添加完成：{len(df)} 根 K 線")


def _add_range_boxes(
    ranges: list,
    show_developing: bool = True
) -> list:
    """
    建立 Pivot Range 方塊的 shapes

    參數：
        ranges: pivot_ranges 列表
        show_developing: 是否顯示發展中區間

    回傳：
        方塊 shapes 列表
    """
    logger.debug(f"建立 {len(ranges)} 個 Pivot Range 方塊")

    shapes = []

    for range_data in ranges:
        # 直接使用 JSON 中的時間欄位（已經是正確順序）
        x0 = pd.Timestamp(range_data['start_time'])
        x1 = pd.Timestamp(range_data['end_time'])

        # 價格範圍
        lowest_price = range_data['price_info']['lowest']
        highest_price = range_data['price_info']['highest']

        # 建立矩形
        shapes.append(dict(
            type='rect',
            x0=x0,
            x1=x1,
            y0=lowest_price,
            y1=highest_price,
            fillcolor=COLORS['range_fill'],
            line=dict(
                color=COLORS['range_border'],
                width=2
            ),
            layer='below'  # 放在 K 線圖下層
        ))

    logger.debug(f"方塊建立完成：{len(shapes)} 個")
    return shapes


def _add_volume_profiles(
    ranges: list,
    timeframe: str = 'M1'
) -> list:
    """
    建立 Volume Profile shapes（使用矩形繪製）

    Volume Profile 的最大寬度為該 Range 寬度的 2/3

    參數：
        ranges: pivot_ranges 列表
        timeframe: 時間週期

    回傳：
        Volume Profile shapes 列表
    """
    logger.debug(f"添加 {len(ranges)} 個 Volume Profile")

    vp_shapes = []

    for range_data in ranges:
        # 取得資料
        price_centers = np.array(range_data['volume_profile']['price_centers'])
        volumes = np.array(range_data['volume_profile']['volumes'])

        # 直接使用 JSON 中的時間欄位
        range_start = pd.Timestamp(range_data['start_time'])
        range_end = pd.Timestamp(range_data['end_time'])

        # 計算 Range 寬度（分鐘）
        range_width_minutes = (range_end - range_start).total_seconds() / 60

        # Volume Profile 最大寬度 = Range 寬度的 2/3
        max_width_minutes = range_width_minutes * (2 / 3)

        # 正規化成交量寬度
        max_volume = volumes.max()
        if max_volume == 0:
            continue

        # 取得 Value Area 範圍
        vah = range_data['value_area']['vah']
        val = range_data['value_area']['val']

        # 計算長條高度（價格方向）
        price_step = range_data['price_info']['step']
        half_step = price_step / 2

        # 為每個價格層級繪製矩形
        for j, (price, volume) in enumerate(zip(price_centers, volumes)):
            if volume == 0:
                continue

            # 計算寬度（分鐘），最大成交量對應 2/3 range 寬度
            width_minutes = (volume / max_volume) * max_width_minutes

            # 計算 X 座標（從 range 左邊開始往右畫）
            x0 = range_start
            x1 = range_start + timedelta(minutes=width_minutes)

            # 計算 Y 座標
            y0 = price - half_step
            y1 = price + half_step

            # 選擇顏色（Value Area 內外不同）
            if val <= price <= vah:
                fill_color = COLORS['volume_in_va']
            else:
                fill_color = COLORS['volume_out_va']

            # 建立矩形 shape
            vp_shapes.append(dict(
                type='rect',
                x0=x0,
                x1=x1,
                y0=y0,
                y1=y1,
                fillcolor=fill_color,
                line=dict(width=0),
                layer='below'
            ))

    logger.debug(f"Volume Profile 繪製完成：{len(vp_shapes)} 個矩形")
    return vp_shapes


def _add_poc_lines(fig: go.Figure, ranges: list) -> None:
    """
    添加 POC（Point of Control）線

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
    """
    logger.debug(f"添加 {len(ranges)} 條 POC 線")

    # 合併所有 POC 線為單一 Trace（效能優化）
    all_x = []
    all_y = []

    for range_data in ranges:
        # 直接使用 JSON 中的時間欄位
        x0 = pd.Timestamp(range_data['start_time'])
        x1 = pd.Timestamp(range_data['end_time'])
        poc_price = range_data['poc']['price']

        # 添加線段（使用 None 分隔不同線段）
        all_x.extend([x0, x1, None])
        all_y.extend([poc_price, poc_price, None])

    # 繪製所有 POC 線
    fig.add_trace(go.Scatter(
        x=all_x,
        y=all_y,
        mode='lines',
        line=dict(
            color=COLORS['poc_line'],
            width=2,
            dash=LINE_STYLES['poc']
        ),
        name='POC',
        showlegend=True,
        hovertemplate='POC: %{y:.2f}<extra></extra>'
    ))

    logger.debug(f"POC 線繪製完成：{len(ranges)} 條")


def _add_value_area_lines(fig: go.Figure, ranges: list) -> None:
    """
    添加 VAH（Value Area High）和 VAL（Value Area Low）線

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
    """
    logger.debug(f"添加 {len(ranges)} 組 Value Area 線")

    # VAH 線（合併）
    vah_x = []
    vah_y = []

    # VAL 線（合併）
    val_x = []
    val_y = []

    for range_data in ranges:
        # 直接使用 JSON 中的時間欄位
        x0 = pd.Timestamp(range_data['start_time'])
        x1 = pd.Timestamp(range_data['end_time'])
        vah = range_data['value_area']['vah']
        val = range_data['value_area']['val']

        # VAH 線段
        vah_x.extend([x0, x1, None])
        vah_y.extend([vah, vah, None])

        # VAL 線段
        val_x.extend([x0, x1, None])
        val_y.extend([val, val, None])

    # 繪製 VAH 線
    fig.add_trace(go.Scatter(
        x=vah_x,
        y=vah_y,
        mode='lines',
        line=dict(
            color=COLORS['va_line'],
            width=1.5,
            dash=LINE_STYLES['va']
        ),
        name='VAH',
        showlegend=True,
        hovertemplate='VAH: %{y:.2f}<extra></extra>'
    ))

    # 繪製 VAL 線
    fig.add_trace(go.Scatter(
        x=val_x,
        y=val_y,
        mode='lines',
        line=dict(
            color=COLORS['va_line'],
            width=1.5,
            dash=LINE_STYLES['va']
        ),
        name='VAL',
        showlegend=True,
        hovertemplate='VAL: %{y:.2f}<extra></extra>'
    ))

    logger.debug(f"Value Area 線繪製完成：{len(ranges)} 組")


def _add_pivot_markers(fig: go.Figure, pivot_points: list, df: pd.DataFrame) -> None:
    """
    添加 Pivot Points 標記（可選）

    參數：
        fig: Plotly Figure 物件
        pivot_points: pivot_points 列表
        df: K 線 DataFrame
    """
    if not pivot_points:
        logger.debug("無 Pivot Points 需要標記")
        return

    logger.debug(f"添加 {len(pivot_points)} 個 Pivot Points 標記")

    # 分離 Pivot High 和 Pivot Low
    high_points = [p for p in pivot_points if p['type'] == 'H']
    low_points = [p for p in pivot_points if p['type'] == 'L']

    # Pivot High 標記
    if high_points:
        high_times = [map_idx_to_time(p['idx'], df) for p in high_points]
        high_prices = [p['price'] for p in high_points]

        fig.add_trace(go.Scatter(
            x=high_times,
            y=high_prices,
            mode='markers',
            marker=dict(
                symbol='triangle-down',
                size=10,
                color=COLORS['pivot_high']
            ),
            name='Pivot High',
            showlegend=True,
            hovertemplate='Pivot High: %{y:.2f}<extra></extra>'
        ))

    # Pivot Low 標記
    if low_points:
        low_times = [map_idx_to_time(p['idx'], df) for p in low_points]
        low_prices = [p['price'] for p in low_points]

        fig.add_trace(go.Scatter(
            x=low_times,
            y=low_prices,
            mode='markers',
            marker=dict(
                symbol='triangle-up',
                size=10,
                color=COLORS['pivot_low']
            ),
            name='Pivot Low',
            showlegend=True,
            hovertemplate='Pivot Low: %{y:.2f}<extra></extra>'
        ))

    logger.debug(f"Pivot Points 標記完成：{len(high_points)} High, {len(low_points)} Low")


def plot_vppa_chart(
    vppa_json: dict,
    candles_df: pd.DataFrame,
    output_path: Optional[str] = None,
    show_pivot_points: bool = True,
    show_developing: bool = True,
    width: int = 1600,
    height: int = 900
) -> go.Figure:
    """
    繪製 VPPA 圖表（K 線圖 + Volume Profile）

    參數：
        vppa_json: analyze_vppa.py 的 JSON 輸出
        candles_df: K 線 DataFrame（需包含 'time', 'open', 'high', 'low', 'close'）
        output_path: PNG 輸出路徑（若為 None 則不儲存）
        show_pivot_points: 是否顯示 Pivot Points 標記
        show_developing: 是否顯示發展中區間
        width: 圖表寬度（像素）
        height: 圖表高度（像素）

    回傳：
        Plotly Figure 物件

    例外：
        ValueError: 資料格式錯誤或不一致時
    """
    logger.info("=" * 60)
    logger.info("開始繪製 VPPA 圖表")
    logger.info("=" * 60)

    # 驗證輸入
    validate_vppa_json(vppa_json)
    validate_candles_df(candles_df)

    # 取得時間週期
    timeframe = vppa_json.get('timeframe', 'M1')

    # 建立 Figure
    fig = go.Figure()

    # 1. 先收集所有 shapes（方塊 + Volume Profile）
    all_shapes = []

    # 建立 Pivot Range 方塊
    range_shapes = _add_range_boxes(
        vppa_json['pivot_ranges'], show_developing
    )
    all_shapes.extend(range_shapes)

    # 建立 Volume Profile shapes（最大寬度 = Range 寬度的 2/3）
    vp_shapes = _add_volume_profiles(
        vppa_json['pivot_ranges'], timeframe=timeframe
    )
    all_shapes.extend(vp_shapes)

    # 2. 批量添加所有 shapes（放在 K 線下層）
    fig.update_layout(shapes=all_shapes)

    # 3. 添加 K 線圖（最上層）
    _add_candlestick(fig, candles_df)

    # 4. 添加輔助線
    _add_poc_lines(fig, vppa_json['pivot_ranges'])
    _add_value_area_lines(fig, vppa_json['pivot_ranges'])

    # 5. 可選：Pivot Points 標記
    if show_pivot_points:
        _add_pivot_markers(fig, vppa_json['pivot_points'], candles_df)

    # 設定布局
    symbol = vppa_json['symbol']
    timeframe = vppa_json['timeframe']

    fig.update_layout(
        title={
            'text': f'{symbol} {timeframe} - Volume Profile Pivot Anchored',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis={
            'title': '時間',
            'type': 'date',
            'rangeslider': {'visible': False}
        },
        yaxis={
            'title': '價格',
            'fixedrange': False
        },
        width=width,
        height=height,
        **DEFAULT_LAYOUT
    )

    # 輸出 PNG
    if output_path:
        logger.info(f"輸出 PNG 到：{output_path}")
        fig.write_image(output_path, width=width, height=height, scale=2)
        logger.info("PNG 輸出完成")

    logger.info("=" * 60)
    logger.info("VPPA 圖表繪製完成")
    logger.info("=" * 60)

    return fig
