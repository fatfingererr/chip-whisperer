"""
VPPA 視覺化主模組

提供 VPPA 分析結果的 Plotly 圖表繪製功能。
"""

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from loguru import logger
from typing import Optional
from datetime import datetime, timedelta

from .chart_config import COLORS, DEFAULT_LAYOUT, LINE_STYLES
from .plotly_utils import (
    validate_vppa_json,
    validate_candles_df,
    map_idx_to_time,
    normalize_volume_width,
    get_volume_colors
)


def _convert_vppa_times_to_local(vppa_json: dict, local_tz) -> dict:
    """
    將 vppa_json 中的時間字串轉換為本地時區

    參數：
        vppa_json: VPPA JSON 資料
        local_tz: 本地時區

    回傳：
        轉換後的 vppa_json（深複製）
    """
    import copy
    result = copy.deepcopy(vppa_json)

    def convert_time(time_str: str) -> str:
        """轉換時間字串到本地時區"""
        ts = pd.Timestamp(time_str)
        if ts.tz is None:
            ts = ts.tz_localize('UTC')
        ts = ts.tz_convert(local_tz)
        return ts.isoformat()

    # 轉換 pivot_ranges
    for range_data in result.get('pivot_ranges', []):
        range_data['start_time'] = convert_time(range_data['start_time'])
        range_data['end_time'] = convert_time(range_data['end_time'])

    # 轉換 developing_range
    if result.get('developing_range'):
        result['developing_range']['start_time'] = convert_time(result['developing_range']['start_time'])
        result['developing_range']['end_time'] = convert_time(result['developing_range']['end_time'])

    return result


def _find_time_gaps(candles_df: pd.DataFrame, min_gap_hours: float = 1.0) -> list[dict]:
    """
    找出資料中的時間間隙（間隔超過指定小時數的地方）

    參數：
        candles_df: K 線 DataFrame
        min_gap_hours: 最小間隙時數（預設 1 小時）

    回傳：
        rangebreaks 列表，每個元素為 dict(values=[start, end])
    """
    if candles_df.empty or len(candles_df) < 2:
        return []

    # 確保按時間排序
    df_sorted = candles_df.sort_values('time').reset_index(drop=True)

    # 計算相鄰 K 線的時間差
    time_diffs = df_sorted['time'].diff()

    # 找出間隙超過閾值的位置
    min_gap = timedelta(hours=min_gap_hours)
    gaps = []

    for i in range(1, len(df_sorted)):
        if time_diffs.iloc[i] > min_gap:
            # 間隙的起始時間（前一根 K 線的時間 + 1 分鐘）
            gap_start = df_sorted['time'].iloc[i - 1]
            # 間隙的結束時間（當前 K 線的時間）
            gap_end = df_sorted['time'].iloc[i]

            # 轉換為 ISO 格式字串
            gaps.append(dict(
                values=[gap_start.isoformat(), gap_end.isoformat()]
            ))

    logger.debug(f"找到 {len(gaps)} 個時間間隙（閾值：{min_gap_hours} 小時）")
    return gaps


def _generate_date_aware_ticks(
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    dtick_ms: int
) -> tuple[list, list]:
    """
    產生時間軸刻度，跨日時顯示日期

    參數：
        start_time: 開始時間
        end_time: 結束時間
        dtick_ms: 刻度間隔（毫秒）

    回傳：
        (tickvals, ticktext) 元組
    """
    dtick_delta = timedelta(milliseconds=dtick_ms)

    # 對齊到整點（根據 dtick）
    if dtick_ms >= 86400000:  # >= 1 天
        current = start_time.normalize()  # 對齊到當天 00:00
    elif dtick_ms >= 3600000:  # >= 1 小時
        current = start_time.replace(minute=0, second=0, microsecond=0)
    else:
        current = start_time.replace(second=0, microsecond=0)

    tickvals = []
    ticktext = []
    prev_date = None

    # 間隔 >= 1 天時，只顯示日期（不顯示時間）
    is_daily_interval = dtick_ms >= 86400000

    while current <= end_time:
        if current >= start_time:
            current_date = current.date()

            if is_daily_interval:
                # 日線級別：只顯示日期
                ticktext.append(current.strftime('%m/%d'))
            else:
                # 分鐘/小時級別：跨日顯示日期，否則只顯示時間
                if prev_date is None or current_date != prev_date:
                    ticktext.append(current.strftime('%m/%d\n%H:%M'))
                    prev_date = current_date
                else:
                    ticktext.append(current.strftime('%H:%M'))

            tickvals.append(current)

        current = current + dtick_delta

    return tickvals, ticktext


def calculate_y_grid_interval(latest_price: float) -> float:
    """
    根據價格位數計算 Y 軸網格間隔

    規則：最小值的 1/20
    例如 4000 (4位數) → 最小值 1000 → 間隔 50
    例如 25000 (5位數) → 最小值 10000 → 間隔 500

    參數：
        latest_price: 最新價格

    回傳：
        Y 軸網格間隔
    """
    price_int = int(latest_price)
    price_digits = len(str(price_int))
    min_unit = 10 ** (price_digits - 1)
    interval = min_unit / 20
    return interval


def get_x_grid_interval(timeframe: str) -> int:
    """
    根據時間週期取得 X 軸網格間隔（毫秒）

    規則：
    - M1/M5/M15: 1 小時
    - M30/H1/H4: 1 日
    - D1 以上: 1 日

    參數：
        timeframe: 時間週期

    回傳：
        X 軸網格間隔（毫秒）
    """
    intervals = {
        'M1': 3600000,       # 1 小時
        'M5': 3600000,
        'M15': 3600000,
        'M30': 86400000,     # 1 日
        'H1': 86400000,      # 1 日
        'H4': 86400000,      # 1 日
        'D1': 86400000,      # 1 日
        'W1': 604800000,     # 1 週
        'MN1': 2592000000    # 1 月
    }
    return intervals.get(timeframe, 3600000)


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
        showlegend=False,  # 移除 legend
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


def _find_poc_end_point(
    poc_price: float,
    current_range_idx: int,
    ranges: list,
    latest_time: pd.Timestamp
) -> tuple[pd.Timestamp, bool]:
    """
    找出 POC 線的終點（被後續 VA 覆蓋時停止，否則延伸到最右邊）

    參數：
        poc_price: POC 價格
        current_range_idx: 當前 Range 的索引
        ranges: 所有 ranges 列表
        latest_time: 最新 K 線的時間

    回傳：
        (終點時間, 是否為 Naked POC)
    """
    # 檢查後續的 Ranges
    for i in range(current_range_idx + 1, len(ranges)):
        next_range = ranges[i]
        next_vah = next_range['value_area']['vah']
        next_val = next_range['value_area']['val']
        next_start = pd.Timestamp(next_range['start_time'])

        # 如果 POC 價格在後續 Range 的 Value Area 內，停止延伸
        if next_val <= poc_price <= next_vah:
            return next_start, False  # 不是 Naked POC

    # 沒有被任何後續 VA 覆蓋，延伸到最右邊
    return latest_time, True  # 是 Naked POC


def _add_poc_lines(fig: go.Figure, ranges: list, latest_time: pd.Timestamp, latest_price: float) -> None:
    """
    添加 POC 線（Naked POC 延伸到最右邊並標註，被 VA 覆蓋的停止在該 Range 起始處）

    參數：
        fig: Plotly Figure 物件
        ranges: pivot_ranges 列表
        latest_time: 最新 K 線的時間
        latest_price: 最新收盤價
    """
    logger.debug(f"添加 {len(ranges)} 條 POC 線")

    # 合併所有 POC 線為單一 Trace（效能優化）
    all_x = []
    all_y = []

    # Naked POC 標註資料（延伸到最右邊的）
    naked_annotation_x = []
    naked_annotation_y = []
    naked_annotation_text = []

    for idx, range_data in enumerate(ranges):
        # 直接使用 JSON 中的時間欄位
        x0 = pd.Timestamp(range_data['start_time'])
        poc_price = range_data['poc']['price']

        # 找出 POC 線的終點
        x1, is_naked = _find_poc_end_point(poc_price, idx, ranges, latest_time)

        # 添加線段（使用 None 分隔不同線段）
        all_x.extend([x0, x1, None])
        all_y.extend([poc_price, poc_price, None])

        # 只有 Naked POC 才標註價格和差距
        if is_naked:
            price_diff = latest_price - poc_price  # 正數表示上漲(+)，負數表示下跌(-)
            naked_annotation_x.append(x1)
            naked_annotation_y.append(poc_price)
            naked_annotation_text.append(f"{poc_price:.2f} ({price_diff:+.2f})")

    # 繪製所有 POC 線（移除 legend）
    fig.add_trace(go.Scatter(
        x=all_x,
        y=all_y,
        mode='lines',
        line=dict(
            color=COLORS['poc_line'],
            width=2,
            dash=LINE_STYLES['poc']  # 'solid' 實線
        ),
        name='POC',
        showlegend=False,  # 移除 legend
        hovertemplate='POC: %{y:.2f}<extra></extra>'
    ))

    # 添加 Naked POC 價格和漲跌幅標註（字體放大 2 倍）
    if naked_annotation_x:
        fig.add_trace(go.Scatter(
            x=naked_annotation_x,
            y=naked_annotation_y,
            mode='text',
            text=naked_annotation_text,
            textposition='middle right',
            textfont=dict(size=18, color='red'),  # 字體放大 2 倍（9 -> 18）
            showlegend=False,
            hoverinfo='skip',
            cliponaxis=False  # 防止文字被裁剪
        ))

    # 添加最新價格標註（黑色，字體與 Naked POC 一樣大）
    fig.add_trace(go.Scatter(
        x=[latest_time],
        y=[latest_price],
        mode='text',
        text=[f"{latest_price:.2f}"],
        textposition='middle right',
        textfont=dict(size=18, color='black'),  # 黑色，字體一樣大
        showlegend=False,
        hoverinfo='skip',
        cliponaxis=False  # 防止文字被裁剪
    ))

    logger.debug(f"POC 線繪製完成：{len(ranges)} 條，Naked POC：{len(naked_annotation_x)} 條")


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

    # 複製 DataFrame 避免修改原始資料
    candles_df = candles_df.copy()

    # 取得本地時區
    local_tz = datetime.now().astimezone().tzinfo

    # 轉換 candles_df 時間到本地時區
    if candles_df['time'].dt.tz is not None:
        candles_df['time'] = candles_df['time'].dt.tz_convert(local_tz)
    else:
        candles_df['time'] = candles_df['time'].dt.tz_localize('UTC').dt.tz_convert(local_tz)

    # 轉換 vppa_json 時間到本地時區
    vppa_json = _convert_vppa_times_to_local(vppa_json, local_tz)

    # 取得時間週期和最新價格（用於網格計算和 POC 延伸）
    timeframe = vppa_json.get('timeframe', 'M1')
    latest_price = candles_df['close'].iloc[-1]
    latest_time = candles_df['time'].iloc[-1]

    # 建立 Figure
    fig = go.Figure()

    # 1. 先收集所有 shapes（方塊 + Volume Profile）
    all_shapes = []

    # 收集所有區間（包含 developing_range）
    all_ranges = vppa_json['pivot_ranges'].copy()

    # 如果存在 developing_range，也加入繪製
    if show_developing and vppa_json.get('developing_range'):
        all_ranges.append(vppa_json['developing_range'])

    # 建立 Pivot Range 方塊
    range_shapes = _add_range_boxes(all_ranges, show_developing)
    all_shapes.extend(range_shapes)

    # 建立 Volume Profile shapes（最大寬度 = Range 寬度的 2/3）
    vp_shapes = _add_volume_profiles(all_ranges, timeframe=timeframe)
    all_shapes.extend(vp_shapes)

    # 2. 批量添加所有 shapes（放在 K 線下層）
    fig.update_layout(shapes=all_shapes)

    # 3. 添加 K 線圖（最上層）
    _add_candlestick(fig, candles_df)

    # 4. 添加輔助線（POC 延伸到最右邊並標註）
    # 使用 all_ranges 以包含 developing_range 的 POC
    _add_poc_lines(fig, all_ranges, latest_time, latest_price)
    # 移除 VAH/VAL 線（需求 1(b)）
    # _add_value_area_lines(fig, vppa_json['pivot_ranges'])

    # 5. 移除 Pivot Points 標記（需求 1(a)）
    # if show_pivot_points:
    #     _add_pivot_markers(fig, vppa_json['pivot_points'], candles_df)

    # 計算網格間隔
    y_grid_interval = calculate_y_grid_interval(latest_price)
    x_grid_interval = get_x_grid_interval(timeframe)

    # 產生自訂時間軸刻度（跨日時顯示日期）
    start_time = candles_df['time'].iloc[0]
    tickvals, ticktext = _generate_date_aware_ticks(start_time, latest_time, x_grid_interval)

    # 注意：rangebreaks 與 datetime 座標的 shapes 不相容
    # shapes（Volume Profile、Range 方塊）使用 datetime 座標繪製，
    # 但 rangebreaks 會壓縮時間軸，導致 shapes 位置錯亂
    # 因此暫時停用 rangebreaks 功能

    # 設定布局
    symbol = vppa_json['symbol']
    timeframe = vppa_json['timeframe']

    # 產生更新時間字串
    update_time_str = datetime.now().strftime('%Y/%m/%d %H:%M:%S')

    fig.update_layout(
        title={
            'text': f'{symbol}, {timeframe} - Volume Profile, Pivot Anchored (Updated: {update_time_str})',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18}
        },
        xaxis={
            'title': '',  # 移除軸標題
            'type': 'date',
            # 使用自訂刻度（跨日時顯示日期）
            'tickmode': 'array',
            'tickvals': tickvals,
            'ticktext': ticktext,
            'rangeslider': {'visible': False},
            'showgrid': True,            # 顯示網格
            'gridcolor': 'lightgray',
            'gridwidth': 0.5
            # rangebreaks 已停用（與 shapes 不相容）
        },
        yaxis={
            'title': '',  # 移除軸標題
            'fixedrange': False,
            'showgrid': True,            # 顯示網格
            'dtick': y_grid_interval,    # Y 軸間隔
            'gridcolor': 'lightgray',
            'gridwidth': 0.5,
            'tickfont': {'size': 24}     # Y 軸價格 label 放大 2 倍（12 -> 24）
        },
        width=width,
        height=height,
        showlegend=False,  # 移除所有 legend
        margin={'r': 180},  # 右側邊距給標註空間
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
