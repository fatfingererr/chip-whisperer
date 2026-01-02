"""
圖表配置常數
"""

# 顏色配置
COLORS = {
    # K 線顏色
    'candle_up': '#26a69a',      # 上漲（綠色）
    'candle_down': '#ef5350',    # 下跌（紅色）

    # Pivot Range 方塊
    'range_fill': 'rgba(255, 255, 153, 0.5)',    # 淺黃色填充，透明度 50%
    'range_border': 'rgba(204, 153, 0, 1.0)',    # 深黃色邊框

    # Volume Profile（提高不透明度使其更明顯）
    'volume_in_va': 'rgba(213, 166, 52, 0.85)',   # Value Area 內（金黃色 #D5A634）
    'volume_out_va': 'rgba(128, 128, 128, 0.65)', # Value Area 外（灰色）

    # 輔助線
    'poc_line': 'rgb(255, 0, 0)',        # POC（紅色）
    'va_line': 'rgb(0, 128, 0)',         # VAH/VAL（綠色）

    # Pivot Points 標記
    'pivot_high': 'red',
    'pivot_low': 'green'
}

# 線條樣式
LINE_STYLES = {
    'poc': 'solid',    # 實線
    'va': 'dot'        # 點線
}

# 圖表布局
DEFAULT_LAYOUT = {
    'plot_bgcolor': 'white',
    'paper_bgcolor': 'white',
    'font': {'family': 'Arial, sans-serif', 'size': 12},
    'hovermode': 'x unified'
    # showlegend 和 legend 由主函數控制
}
