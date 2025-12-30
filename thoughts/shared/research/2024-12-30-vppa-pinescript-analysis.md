---
title: "VPPA PineScript 原始碼分析：Volume Profile 與 Pivot Point 整合"
date: 2024-12-30
author: Claude Code
tags: [pinescript, volume-profile, pivot-point, technical-analysis, python-conversion]
status: completed
related_files:
  - vendor/vppa.txt
  - src/agent/indicators.py
last_updated: 2024-12-30
last_updated_by: Claude Code
---

# VPPA PineScript 原始碼分析

## 研究問題

分析 `vendor/vppa.txt` 中的 Volume Profile Pivot Anchored (VP-PA) 指標，理解其 Pivot Point 與 Volume Profile 計算邏輯，並規劃如何轉換為 Python 實作。

## 摘要

`vendor/vppa.txt` 包含一個完整的 PineScript v5 指標，名為「Volume Profile, Pivot Anchored by DGT」。此指標的核心概念是：

1. **使用 Pivot Points 作為錨點**：透過 `ta.pivothigh()` 和 `ta.pivotlow()` 偵測價格的高低轉折點
2. **在相鄰 Pivot Points 之間計算 Volume Profile**：每當偵測到新的 Pivot Point，就為前一個區間計算完整的 Volume Profile
3. **即時更新當前區間的 Volume Profile**：從最後一個 Pivot Point 到現在的即時 Profile

此指標提供了一個動態的視角，將時間序列的成交量分析錨定在關鍵的技術轉折點上，而非固定的時間週期。

## 詳細發現

### 1. Pivot Point 計算邏輯

#### 1.1 Pivot Point 偵測機制

**檔案位置**：`vendor/vppa.txt` 第 154-169 行

```pinescript
pvtHigh  = ta.pivothigh(pvtLength, pvtLength)
pvtLow   = ta.pivotlow (pvtLength, pvtLength)
proceed  = not na(pvtHigh) or not na(pvtLow)

if proceed
    x1 := x2
    x2 := bar_index

if not na(pvtHigh)
    pvtHigh1 := pvtHigh
    pvtLast  := 'H'

if not na(pvtLow)
    pvtLow1  := pvtLow
    pvtLast  := 'L'
```

**關鍵概念**：

- **`pvtLength` 參數**：預設為 20，定義 Pivot Point 的左右觀察窗口
- **`ta.pivothigh(left, right)`**：當中心 bar 的 high 價格高於左右各 `pvtLength` 根 K 線時，確認為 Pivot High
- **`ta.pivotlow(left, right)`**：當中心 bar 的 low 價格低於左右各 `pvtLength` 根 K 線時，確認為 Pivot Low
- **`x1` 和 `x2`**：記錄相鄰兩個 Pivot Point 的 bar_index（時間位置）
- **`pvtLast`**：記錄最後一個 Pivot Point 類型（'H' 或 'L'）

**重要特性**：
- Pivot Point 的確認有延遲性：需要等待右側 `pvtLength` 根 K 線才能確認
- 每次確認新的 Pivot Point 時，`x1` 被設為上一個 Pivot Point 位置（`x2`），`x2` 被設為當前位置
- 這形成了一個**時間區間** `[x1, x2]`，即兩個相鄰 Pivot Points 之間的範圍

#### 1.2 Python 轉換建議

PineScript 的 `ta.pivothigh()` 和 `ta.pivotlow()` 可用以下邏輯實作：

```python
def find_pivot_points(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """
    找出 Pivot High 和 Pivot Low

    參數：
        df: 包含 'high' 和 'low' 的 DataFrame
        length: 左右觀察窗口大小

    回傳：
        添加 'pivot_high' 和 'pivot_low' 欄位的 DataFrame
    """
    df = df.copy()
    df['pivot_high'] = np.nan
    df['pivot_low'] = np.nan

    for i in range(length, len(df) - length):
        # Pivot High: 中心點的 high 是區間內最高
        if df['high'].iloc[i] == df['high'].iloc[i-length:i+length+1].max():
            # 確保是真正的峰值（不只是平坦）
            left_max = df['high'].iloc[i-length:i].max()
            right_max = df['high'].iloc[i+1:i+length+1].max()
            if df['high'].iloc[i] > left_max and df['high'].iloc[i] > right_max:
                df.loc[df.index[i], 'pivot_high'] = df['high'].iloc[i]

        # Pivot Low: 中心點的 low 是區間內最低
        if df['low'].iloc[i] == df['low'].iloc[i-length:i+length+1].min():
            left_min = df['low'].iloc[i-length:i].min()
            right_min = df['low'].iloc[i+1:i+length+1].min()
            if df['low'].iloc[i] < left_min and df['low'].iloc[i] < right_min:
                df.loc[df.index[i], 'pivot_low'] = df['low'].iloc[i]

    return df
```

### 2. Volume Profile 計算邏輯

#### 2.1 價格範圍與分層

**檔案位置**：`vendor/vppa.txt` 第 40-54 行（輔助函數）、第 171-174 行（主邏輯）

```pinescript
// 輔助函數：計算區間內的最高價、最低價和總成交量
f_getHighLow(_len, _calc, _offset) =>
    if _calc
        htf_l = low [_offset]
        htf_h = high[_offset]
        vol   = 0.

        for x = 0 to _len - 1
            htf_l := math.min(low [_offset + x], htf_l)
            htf_h := math.max(high[_offset + x], htf_h)
            vol += volume[_offset + x]

        htf_l := math.min(low [_offset + _len], htf_l)
        htf_h := math.max(high[_offset + _len], htf_h)

        [htf_h, htf_l, vol]

// 主邏輯：計算價格步長
profileLength = x2 - x1
[priceHighest, priceLowest, tradedVolume] = f_getHighLow(profileLength, proceed, pvtLength)
priceStep = (priceHighest - priceLowest) / profileLevels
```

**關鍵概念**：

- **`profileLength`**：兩個 Pivot Points 之間的 K 線數量
- **`priceHighest` 和 `priceLowest`**：區間內的最高價和最低價
- **`profileLevels`**：價格分層數量（預設 25，可調整至 10-100）
- **`priceStep`**：每層的價格範圍 = (最高價 - 最低價) / 層數

#### 2.2 成交量分配演算法

**檔案位置**：`vendor/vppa.txt` 第 176-186 行

這是整個指標最核心的部分：

```pinescript
if proceed and nzVolume and priceStep > 0 and bar_index > profileLength and profileLength > 0

    for barIndexx = 1 to profileLength
        level = 0
        barIndex = barIndexx + pvtLength

        for priceLevel = priceLowest to priceHighest by priceStep
            if barPriceHigh[barIndex] >= priceLevel and barPriceLow[barIndex] < priceLevel + priceStep
                array.set(volumeStorageT, level, array.get(volumeStorageT, level) + nzVolume[barIndex] * ((barPriceHigh[barIndex] - barPriceLow[barIndex]) == 0 ? 1 : priceStep / (barPriceHigh[barIndex] - barPriceLow[barIndex])) )
            level += 1
```

**演算法步驟**：

1. **初始化**：建立 `volumeStorageT` 陣列，大小為 `profileLevels + 1`，初始值全為 0
2. **遍歷每根 K 線**：從區間起點到終點（`x1` 到 `x2`）
3. **遍歷每個價格層級**：從 `priceLowest` 到 `priceHighest`，步進 `priceStep`
4. **檢查重疊**：如果 K 線的 `[low, high]` 範圍與當前價格層級 `[priceLevel, priceLevel + priceStep]` 有重疊
5. **按比例分配成交量**：
   - 如果 K 線是一條線（high == low），成交量全部分配給該層級
   - 否則，成交量按 `priceStep / (high - low)` 比例分配

**關鍵公式**：

```
分配到該層級的成交量 = K線成交量 × (priceStep / K線價格範圍)
```

這個公式假設成交量在 K 線的價格範圍內均勻分布。

#### 2.3 Python 轉換建議

```python
def calculate_volume_profile_for_range(
    df: pd.DataFrame,
    start_idx: int,
    end_idx: int,
    price_levels: int = 25
) -> Tuple[np.ndarray, float, float]:
    """
    計算指定區間的 Volume Profile

    參數：
        df: K 線資料
        start_idx: 起始索引
        end_idx: 結束索引
        price_levels: 價格分層數量

    回傳：
        (volume_storage, price_lowest, price_step)
        - volume_storage: 每個價格層級的成交量陣列
        - price_lowest: 區間最低價
        - price_step: 價格步長
    """
    # 取得區間資料
    range_df = df.iloc[start_idx:end_idx+1]

    # 計算價格範圍
    price_highest = range_df['high'].max()
    price_lowest = range_df['low'].min()
    price_step = (price_highest - price_lowest) / price_levels

    # 初始化成交量儲存陣列
    volume_storage = np.zeros(price_levels + 1)

    # 遍歷每根 K 線
    for idx in range(len(range_df)):
        row = range_df.iloc[idx]
        bar_high = row['high']
        bar_low = row['low']
        bar_volume = row['real_volume']

        # 計算 K 線價格範圍
        bar_range = bar_high - bar_low

        # 遍歷每個價格層級
        for level in range(price_levels):
            level_low = price_lowest + level * price_step
            level_high = price_lowest + (level + 1) * price_step

            # 檢查 K 線是否覆蓋此價格層級
            if bar_high >= level_low and bar_low < level_high:
                # 按比例分配成交量
                if bar_range == 0:
                    # K 線是一條線，全部分配
                    volume_storage[level] += bar_volume
                else:
                    # 按比例分配
                    ratio = price_step / bar_range
                    volume_storage[level] += bar_volume * ratio

    return volume_storage, price_lowest, price_step
```

### 3. POC (Point of Control) 計算

#### 3.1 POC 定義

**檔案位置**：`vendor/vppa.txt` 第 187 行

```pinescript
pocLevel = array.indexof(volumeStorageT, array.max(volumeStorageT))
```

**定義**：成交量最大的價格層級。

在 Python 中：

```python
poc_level = np.argmax(volume_storage)
poc_price = price_lowest + (poc_level + 0.5) * price_step  # 取層級中點
```

#### 3.2 POC 延伸功能

**檔案位置**：`vendor/vppa.txt` 第 224-225 行、第 258-259 行

PineScript 提供了 POC 線的延伸選項：
- `'Until Last Bar'`：延伸到最後一根 K 線
- `'Until Bar Cross'`：延伸到價格穿越 POC 為止
- `'Until Bar Touch'`：延伸到價格觸碰 POC 為止
- `'None'`：不延伸

Python 實作時，這部分是視覺化相關，可以在繪圖階段處理。

### 4. Value Area 計算邏輯

#### 4.1 Value Area 定義

**檔案位置**：`vendor/vppa.txt` 第 97 行、第 188-213 行

```pinescript
isValueArea = input.float(68, "Value Area Volume %", minval = 0, maxval = 100, ...) / 100

pocLevel          = array.indexof(volumeStorageT, array.max(volumeStorageT))
totalVolumeTraded = array.sum(volumeStorageT) * isValueArea
valueArea         = array.get(volumeStorageT, pocLevel)
levelAbovePoc    := pocLevel
levelBelowPoc    := pocLevel

while valueArea < totalVolumeTraded
    if levelBelowPoc == 0 and levelAbovePoc == profileLevels - 1
        break

    volumeAbovePoc = 0.
    if levelAbovePoc < profileLevels - 1
        volumeAbovePoc := array.get(volumeStorageT, levelAbovePoc + 1)

    volumeBelowPoc = 0.
    if levelBelowPoc > 0
        volumeBelowPoc := array.get(volumeStorageT, levelBelowPoc - 1)

    if volumeBelowPoc == 0 and volumeAbovePoc == 0
        break

    if volumeAbovePoc >= volumeBelowPoc
        valueArea     += volumeAbovePoc
        levelAbovePoc += 1
    else
        valueArea     += volumeBelowPoc
        levelBelowPoc -= 1
```

**演算法**：

1. **目標成交量**：總成交量的 68%（預設值，可調整為 0-100%）
2. **初始狀態**：從 POC 層級開始（`levelAbovePoc` 和 `levelBelowPoc` 都等於 `pocLevel`）
3. **向兩側擴展**：
   - 比較 POC 上方和下方相鄰層級的成交量
   - 選擇成交量較大的一側擴展
   - 累加成交量到 `valueArea`
4. **終止條件**：
   - 累積成交量達到目標（68% 總成交量）
   - 或已擴展到價格範圍的邊界

**Value Area High (VAH) 和 Low (VAL)**：

```pinescript
vah = priceLowest + (levelAbovePoc + 1.00) * priceStep
val = priceLowest + (levelBelowPoc + 0.00) * priceStep
```

#### 4.2 Python 轉換建議

```python
def calculate_value_area(
    volume_storage: np.ndarray,
    price_lowest: float,
    price_step: float,
    value_area_pct: float = 0.68
) -> Dict:
    """
    計算 Value Area

    參數：
        volume_storage: 每個價格層級的成交量陣列
        price_lowest: 區間最低價
        price_step: 價格步長
        value_area_pct: Value Area 百分比（預設 0.68）

    回傳：
        包含 POC、VAH、VAL 的字典
    """
    # POC
    poc_level = np.argmax(volume_storage)
    poc_price = price_lowest + (poc_level + 0.5) * price_step

    # 目標成交量
    total_volume = volume_storage.sum()
    target_volume = total_volume * value_area_pct

    # 從 POC 開始擴展
    value_area_volume = volume_storage[poc_level]
    level_above_poc = poc_level
    level_below_poc = poc_level

    while value_area_volume < target_volume:
        # 檢查是否到達邊界
        if level_below_poc == 0 and level_above_poc == len(volume_storage) - 1:
            break

        # 取得上下相鄰層級的成交量
        volume_above = (
            volume_storage[level_above_poc + 1]
            if level_above_poc < len(volume_storage) - 1
            else 0
        )
        volume_below = (
            volume_storage[level_below_poc - 1]
            if level_below_poc > 0
            else 0
        )

        # 如果兩側都沒有成交量，停止
        if volume_above == 0 and volume_below == 0:
            break

        # 選擇成交量較大的一側擴展
        if volume_above >= volume_below:
            value_area_volume += volume_above
            level_above_poc += 1
        else:
            value_area_volume += volume_below
            level_below_poc -= 1

    # 計算 VAH 和 VAL
    vah = price_lowest + (level_above_poc + 1.0) * price_step
    val = price_lowest + (level_below_poc + 0.0) * price_step

    return {
        'poc_level': int(poc_level),
        'poc_price': float(poc_price),
        'vah': float(vah),
        'val': float(val),
        'value_area_volume': float(value_area_volume),
        'total_volume': float(total_volume),
        'value_area_pct': float(value_area_volume / total_volume * 100)
    }
```

### 5. 兩個 Volume Profile 模式

#### 5.1 歷史 Profile（已確認的 Pivot Point 區間）

**檔案位置**：`vendor/vppa.txt` 第 176-256 行

當偵測到新的 Pivot Point 時（`proceed == true`），計算前一個區間 `[x1, x2]` 的 Volume Profile：

- 這是**已完成的區間**，不會再變動
- 繪製固定的 box 和 line
- 包含完整的 Profile 視覺化（橫向柱狀圖）

**時間偏移**：注意所有繪圖都使用 `bar_index[pvtLength]`，這是因為 Pivot Point 的確認有延遲。

#### 5.2 即時 Profile（發展中的區間）

**檔案位置**：`vendor/vppa.txt` 第 261-350 行

從最後一個 Pivot Point 到目前為止的 Volume Profile：

```pinescript
profileLength := barstate.islast ? last_bar_index - x2 + pvtLength : 1
```

- 只在 `barstate.islast`（圖表最後一根 K 線）時計算
- 區間是 `[x2, last_bar_index]`
- 這個 Profile 會隨著新 K 線不斷更新
- 使用 `var id = ...` 和動態更新（`f_drawLineX`）來優化繪圖效能

### 6. 與現有 Python 實作的差異

#### 6.1 現有 `src/agent/indicators.py` 的實作

**檔案位置**：`src/agent/indicators.py` 第 13-148 行

現有的 `calculate_volume_profile()` 函數：

**特點**：
- 計算**整個資料集**的 Volume Profile（無 Pivot Point 錨點）
- 價格分層數量預設 100（vs PineScript 的 25）
- Value Area 固定 70%（vs PineScript 的 68%）
- 成交量分配演算法相同（按比例分配）

**缺少的功能**：
1. **Pivot Point 偵測**
2. **多區間 Volume Profile**（每個 Pivot Point 區間一個 Profile）
3. **即時 Profile 更新**
4. **POC 延伸選項**

#### 6.2 需要新增的功能

為了實作完整的 VP-PA 指標，需要新增：

1. **`find_pivot_points()` 函數**：偵測 Pivot High 和 Pivot Low
2. **`calculate_vppa()` 函數**：主函數，協調所有計算
3. **修改 `calculate_volume_profile()`**：支援指定區間計算

### 7. 如何結合 Pivot Point 與 Volume Profile

#### 7.1 整體流程

```
1. 載入 K 線資料
   ↓
2. 偵測所有 Pivot Points（使用 find_pivot_points）
   ↓
3. 提取相鄰 Pivot Points 的配對（形成區間）
   ↓
4. 對每個區間：
   - 計算 Volume Profile
   - 計算 POC、VAH、VAL
   - 儲存結果
   ↓
5. 計算即時區間（最後一個 Pivot Point 到現在）
   ↓
6. 整合所有結果
```

#### 7.2 Pivot Point 配對邏輯

**關鍵概念**：PineScript 中，`x1` 和 `x2` 記錄相鄰兩個 Pivot Point 的位置，無論是 High 還是 Low。

Python 實作：

```python
def extract_pivot_ranges(df: pd.DataFrame) -> List[Tuple[int, int, str]]:
    """
    從 DataFrame 中提取 Pivot Point 區間

    回傳：
        [(start_idx, end_idx, pivot_type), ...]
        pivot_type: 'H' 或 'L'
    """
    ranges = []

    # 找出所有有 Pivot Point 的索引
    pivot_indices = []
    for i in df.index:
        if not pd.isna(df.loc[i, 'pivot_high']):
            pivot_indices.append((i, 'H', df.loc[i, 'pivot_high']))
        elif not pd.isna(df.loc[i, 'pivot_low']):
            pivot_indices.append((i, 'L', df.loc[i, 'pivot_low']))

    # 配對相鄰的 Pivot Points
    for i in range(len(pivot_indices) - 1):
        start_idx = pivot_indices[i][0]
        end_idx = pivot_indices[i + 1][0]
        pivot_type = pivot_indices[i + 1][1]
        ranges.append((start_idx, end_idx, pivot_type))

    return ranges
```

## Python 實作建議

### 整體架構

```python
def calculate_vppa(
    df: pd.DataFrame,
    pivot_length: int = 20,
    price_levels: int = 25,
    value_area_pct: float = 0.68
) -> Dict:
    """
    計算 Volume Profile Pivot Anchored

    參數：
        df: K 線資料（必須包含 'high', 'low', 'real_volume'）
        pivot_length: Pivot Point 左右觀察窗口
        price_levels: 價格分層數量
        value_area_pct: Value Area 百分比

    回傳：
        {
            'pivot_ranges': [
                {
                    'start_idx': int,
                    'end_idx': int,
                    'pivot_type': str,  # 'H' 或 'L'
                    'pivot_price': float,
                    'volume_profile': np.ndarray,
                    'price_lowest': float,
                    'price_highest': float,
                    'price_step': float,
                    'poc': {...},
                    'vah': float,
                    'val': float,
                    'total_volume': float
                },
                ...
            ],
            'developing_range': {
                # 即時區間的 Profile（從最後一個 Pivot Point 到現在）
                ...
            }
        }
    """
```

### 核心函數清單

1. **`find_pivot_points(df, length)`**
   - 偵測 Pivot High 和 Pivot Low
   - 回傳添加 'pivot_high' 和 'pivot_low' 欄位的 DataFrame

2. **`extract_pivot_ranges(df)`**
   - 提取相鄰 Pivot Points 形成的區間
   - 回傳區間列表

3. **`calculate_volume_profile_for_range(df, start_idx, end_idx, price_levels)`**
   - 計算指定區間的 Volume Profile
   - 回傳 volume_storage、price_lowest、price_step

4. **`calculate_value_area(volume_storage, price_lowest, price_step, value_area_pct)`**
   - 計算 POC、VAH、VAL
   - 回傳包含所有關鍵數據的字典

5. **`calculate_vppa(df, pivot_length, price_levels, value_area_pct)`**
   - 主函數，協調所有計算
   - 回傳完整的 VPPA 數據結構

### 與現有代碼的整合

**修改 `src/agent/indicators.py`**：

1. 保留現有的 `calculate_volume_profile()` 函數（用於單一區間）
2. 新增上述 5 個函數
3. 確保函數簽名和文檔符合現有風格
4. 使用 `loguru.logger` 記錄關鍵步驟

## 輸出資料結構設計

### 1. 單一區間的 Volume Profile 資料

```python
{
    # 區間資訊
    'start_idx': 100,           # 起始 K 線索引
    'end_idx': 150,             # 結束 K 線索引（Pivot Point 位置）
    'start_time': '2024-01-01 09:00:00',  # 起始時間
    'end_time': '2024-01-05 15:00:00',    # 結束時間
    'bar_count': 50,            # K 線數量

    # Pivot Point 資訊
    'pivot_type': 'H',          # 'H' (High) 或 'L' (Low)
    'pivot_price': 45000.0,     # Pivot Point 價格
    'price_change_pct': 5.2,    # 相對前一個 Pivot Point 的價格變化百分比

    # 價格範圍資訊
    'price_highest': 45200.0,   # 區間最高價
    'price_lowest': 44000.0,    # 區間最低價
    'price_range': 1200.0,      # 價格範圍
    'price_step': 48.0,         # 每層價格步長（price_range / price_levels）

    # Volume Profile 資料
    'volume_profile': np.array([...]),  # 每層的成交量（長度 = price_levels）
    'price_levels': 25,         # 價格分層數量
    'price_centers': np.array([...]),   # 每層的中心價格

    # POC (Point of Control)
    'poc': {
        'level': 12,            # POC 所在層級
        'price': 44576.0,       # POC 價格（層級中心）
        'volume': 125000.0,     # POC 的成交量
        'volume_pct': 15.2      # POC 佔總成交量的百分比
    },

    # Value Area
    'vah': 44880.0,             # Value Area High
    'val': 44280.0,             # Value Area Low
    'value_area_width': 600.0,  # Value Area 寬度（vah - val）
    'value_area_width_pct': 50.0,  # VA 寬度佔價格範圍的百分比
    'value_area_volume': 560000.0,  # Value Area 內的成交量
    'value_area_pct': 68.0,     # Value Area 成交量佔比

    # 成交量統計
    'total_volume': 823500.0,   # 區間總成交量
    'avg_volume_per_bar': 16470.0,  # 平均每根 K 線的成交量

    # 其他統計
    'profile_balance': 0.85,    # Profile 平衡度（POC 相對於價格範圍的位置）
}
```

### 2. 完整 VPPA 資料結構

```python
{
    # 元數據
    'symbol': 'BTCUSDT',
    'timeframe': '1h',
    'calculation_time': '2024-12-30 10:00:00',
    'pivot_length': 20,
    'price_levels': 25,
    'value_area_pct': 68.0,

    # 所有已確認的 Pivot Point 區間
    'pivot_ranges': [
        {
            # 第一個區間（如上述單一區間資料結構）
            ...
        },
        {
            # 第二個區間
            ...
        },
        # ... 更多區間
    ],

    # 即時發展中的區間（從最後一個 Pivot Point 到現在）
    'developing_range': {
        'start_idx': 500,
        'end_idx': 550,         # 當前最後一根 K 線
        'is_developing': True,  # 標記為發展中
        # ... 其他欄位同上
    },

    # 全域統計
    'total_pivot_points': 10,
    'total_ranges': 9,
    'avg_range_bars': 45.2,
    'avg_range_volume': 750000.0,

    # Pivot Points 摘要
    'pivot_summary': [
        {
            'idx': 100,
            'type': 'H',
            'price': 45000.0,
            'time': '2024-01-05 15:00:00'
        },
        {
            'idx': 150,
            'type': 'L',
            'price': 44000.0,
            'time': '2024-01-10 09:00:00'
        },
        # ... 更多 Pivot Points
    ]
}
```

### 3. 資料儲存格式

#### 3.1 JSON 格式（適合序列化和傳輸）

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "pivot_ranges": [
    {
      "start_idx": 100,
      "end_idx": 150,
      "pivot_type": "H",
      "poc": {
        "price": 44576.0,
        "volume": 125000.0
      },
      "vah": 44880.0,
      "val": 44280.0,
      "total_volume": 823500.0
    }
  ]
}
```

**注意**：NumPy 陣列需要轉換：
- `volume_profile` 和 `price_centers` 轉為列表
- 使用 `array.tolist()` 方法

#### 3.2 Pandas DataFrame 格式（適合分析）

**方案 A：寬格式（每個區間一行）**

```python
pd.DataFrame([
    {
        'range_id': 0,
        'start_idx': 100,
        'end_idx': 150,
        'pivot_type': 'H',
        'poc_price': 44576.0,
        'vah': 44880.0,
        'val': 44280.0,
        'total_volume': 823500.0,
        # ...
    },
    # ... 更多區間
])
```

**方案 B：長格式（每個價格層級一行）**

```python
pd.DataFrame([
    {
        'range_id': 0,
        'level': 0,
        'price': 44024.0,
        'volume': 5200.0
    },
    {
        'range_id': 0,
        'level': 1,
        'price': 44072.0,
        'volume': 7800.0
    },
    # ... 每個區間的所有層級
])
```

### 4. 視覺化資料需求

如果需要繪製圖表，額外提供：

```python
{
    'visualization_data': {
        # 每個區間的繪圖座標
        'profile_boxes': [
            {
                'range_id': 0,
                'boxes': [
                    {
                        'x1': 100,      # 起始 K 線索引
                        'x2': 120,      # 結束 K 線索引（依成交量長度）
                        'y1': 44000.0,  # 價格層級下界
                        'y2': 44048.0,  # 價格層級上界
                        'color': 'rgba(251, 192, 45, 0.35)',  # 顏色
                        'is_value_area': True  # 是否在 Value Area 內
                    },
                    # ... 更多 box
                ]
            }
        ],

        # POC 線座標
        'poc_lines': [
            {
                'range_id': 0,
                'x1': 100,
                'x2': 150,
                'y': 44576.0,
                'color': 'red'
            }
        ],

        # VAH/VAL 線座標
        'va_lines': [
            {
                'range_id': 0,
                'type': 'vah',
                'x1': 100,
                'x2': 150,
                'y': 44880.0,
                'color': 'blue'
            },
            {
                'range_id': 0,
                'type': 'val',
                'x1': 100,
                'x2': 150,
                'y': 44280.0,
                'color': 'blue'
            }
        ]
    }
}
```

## 實作優先順序建議

### Phase 1：基礎功能（必須）

1. ✅ `find_pivot_points()`：Pivot Point 偵測
2. ✅ `extract_pivot_ranges()`：區間提取
3. ✅ `calculate_volume_profile_for_range()`：單一區間 VP 計算
4. ✅ `calculate_value_area()`：Value Area 計算

### Phase 2：整合功能（必須）

5. ✅ `calculate_vppa()`：主函數
6. ✅ 資料結構設計和序列化
7. ✅ 單元測試

### Phase 3：進階功能（可選）

8. ⭕ POC 延伸邏輯（'Until Bar Cross' 等）
9. ⭕ 即時 Profile 更新機制
10. ⭕ 視覺化資料生成
11. ⭕ 效能優化（NumPy 向量化）

### Phase 4：額外功能（可選）

12. ⭕ Volume Weighted Colored Bars（成交量加權彩色 K 線）
13. ⭕ 價格穿越 POC/VAH/VAL 的警報機制
14. ⭕ Profile 平衡度分析
15. ⭕ 多時間週期 VPPA

## 關鍵技術挑戰

### 1. Pivot Point 偵測的延遲性

**問題**：PineScript 的 `ta.pivothigh(20, 20)` 需要等待右側 20 根 K 線才能確認，這意味著：
- Pivot Point 總是**延遲 20 根 K 線**才被偵測到
- 即時交易時，最近的 20 根 K 線不可能有已確認的 Pivot Point

**解決方案**：
- 歷史分析：正常運作，所有 Pivot Points 都能被偵測
- 即時交易：需要維護「發展中的區間」（developing_range），從最後一個確認的 Pivot Point 到現在

### 2. 成交量分配的精確度

**問題**：PineScript 假設成交量在 K 線的價格範圍內**均勻分布**，這是一個簡化假設。

**改進方向**（可選）：
- 使用 Tick 資料或訂單簿資料（如果可用）
- 根據 K 線的開盤/收盤位置加權分配
- 使用機器學習預測成交量分布

### 3. 效能考量

**問題**：雙層迴圈（K 線 × 價格層級）可能在大數據集上較慢。

**優化方案**：
```python
# 使用 NumPy 向量化
def calculate_volume_profile_vectorized(df, start_idx, end_idx, price_levels):
    range_df = df.iloc[start_idx:end_idx+1]

    price_highest = range_df['high'].max()
    price_lowest = range_df['low'].min()
    price_edges = np.linspace(price_lowest, price_highest, price_levels + 1)

    volume_storage = np.zeros(price_levels)

    for idx in range(len(range_df)):
        row = range_df.iloc[idx]

        # 找出 K 線覆蓋的層級（向量化）
        in_range = (price_edges[:-1] <= row['high']) & (price_edges[1:] > row['low'])

        # 計算分配比例
        bar_range = row['high'] - row['low']
        ratio = (price_edges[1] - price_edges[0]) / bar_range if bar_range > 0 else 1

        # 分配成交量
        volume_storage[in_range] += row['real_volume'] * ratio

    return volume_storage
```

## 參考文獻

### PineScript 官方文檔

- [ta.pivothigh()](https://www.tradingview.com/pine-script-reference/v5/#fun_ta.pivothigh)
- [ta.pivotlow()](https://www.tradingview.com/pine-script-reference/v5/#fun_ta.pivotlow)
- [Array 操作](https://www.tradingview.com/pine-script-docs/en/v5/language/Arrays.html)

### Volume Profile 相關資源

- CME Group: [Understanding Volume Profile](https://www.cmegroup.com/education/courses/market-profile/understanding-volume-profile.html)
- [Market Profile 理論](https://en.wikipedia.org/wiki/Market_profile)

### 相關檔案

- **原始碼**：`vendor/vppa.txt`（第 1-387 行）
- **現有實作**：`src/agent/indicators.py`（第 13-148 行）

## 附錄：PineScript vs Python 語法對照表

| PineScript | Python (NumPy/Pandas) | 說明 |
|------------|----------------------|------|
| `ta.pivothigh(left, right)` | 自定義函數（見上文） | 偵測 Pivot High |
| `ta.pivotlow(left, right)` | 自定義函數（見上文） | 偵測 Pivot Low |
| `array.new_float(size, value)` | `np.full(size, value)` | 建立陣列 |
| `array.get(arr, idx)` | `arr[idx]` | 取得元素 |
| `array.set(arr, idx, val)` | `arr[idx] = val` | 設定元素 |
| `array.max(arr)` | `arr.max()` 或 `np.max(arr)` | 最大值 |
| `array.sum(arr)` | `arr.sum()` 或 `np.sum(arr)` | 總和 |
| `array.indexof(arr, val)` | `np.argmax(arr == val)` | 找索引 |
| `math.min(a, b)` | `min(a, b)` 或 `np.min([a, b])` | 最小值 |
| `math.max(a, b)` | `max(a, b)` 或 `np.max([a, b])` | 最大值 |
| `bar_index` | DataFrame 索引 | K 線索引 |
| `high[offset]` | `df['high'].iloc[-offset-1]` | 歷史 high（注意方向） |
| `low[offset]` | `df['low'].iloc[-offset-1]` | 歷史 low |
| `volume[offset]` | `df['volume'].iloc[-offset-1]` | 歷史成交量 |
| `barstate.islast` | `idx == len(df) - 1` | 是否為最後一根 K 線 |

**重要差異**：
- PineScript 的 `[offset]` 是**向過去**索引（`[1]` 是前一根）
- Pandas 的 `.iloc[-1]` 也是向過去，但索引方向相反
- 建議使用正向索引以避免混淆

## 結論

「Volume Profile, Pivot Anchored」是一個將 Volume Profile 與 Pivot Point 技術分析結合的強大工具。通過將成交量分析錨定在關鍵的價格轉折點上，它提供了比傳統固定時間週期 Volume Profile 更具動態性和適應性的市場結構視圖。

Python 實作的核心挑戰在於：
1. 正確偵測 Pivot Points（需處理邊界條件）
2. 精確的成交量分配演算法
3. Value Area 的雙向擴展邏輯
4. 維護「發展中的區間」以支援即時分析

建議採用分階段實作策略，先完成基礎功能並通過測試，再逐步添加進階特性。

---

**研究完成時間**：2024-12-30
**下一步行動**：實作 Phase 1 的四個基礎函數，並撰寫單元測試驗證計算正確性。
