# VPPA (Volume Profile Pivot Anchored) 實作計劃

## 概述

為 Chip Whisperer 專案實作完整的 Volume Profile Pivot Anchored 指標功能。此指標結合 Pivot Point 技術分析與 Volume Profile，提供動態的市場結構視角，將成交量分析錨定在關鍵的價格轉折點上。

## 當前狀態分析

### 現有功能

**檔案位置**：`src/agent/indicators.py` 第 13-148 行

現有的 `calculate_volume_profile()` 函數特點：
- 計算整個資料集的 Volume Profile（無 Pivot Point 錨點）
- 價格分層數量預設 100 層
- Value Area 固定 70%
- 成交量分配演算法：按比例均勻分配到涵蓋的價格區間
- 已實作 POC、VAH、VAL 計算

### 缺少的功能

根據 `thoughts/shared/research/2024-12-30-vppa-pinescript-analysis.md` 研究報告：

1. **Pivot Point 偵測機制**：需要實作類似 PineScript `ta.pivothigh()` 和 `ta.pivotlow()` 的功能
2. **多區間 Volume Profile**：每個 Pivot Point 區間計算獨立的 Volume Profile
3. **即時發展中區間**：從最後一個確認的 Pivot Point 到當前時間的即時 Profile
4. **動態成交量分配演算法**：更精確的成交量分配到價格層級的邏輯

### 關鍵發現

**檔案位置**：`vendor/vppa.txt` 第 154-186 行

- **Pivot Point 確認延遲**：需要右側 `pvtLength` 根 K 線才能確認（預設 20）
- **成交量分配公式**：`分配到該層級的成交量 = K線成交量 × (priceStep / K線價格範圍)`
- **Value Area 擴展邏輯**：從 POC 開始向兩側擴展，每次選擇成交量較大的一側
- **區間定義**：相鄰兩個 Pivot Point 之間的時間範圍 `[x1, x2]`

## 期望的最終狀態

實作完成後，系統能夠：

1. 自動偵測價格資料中的所有 Pivot High 和 Pivot Low 點
2. 為每個相鄰 Pivot Point 區間計算獨立的 Volume Profile
3. 輸出包含以下資訊的結構化資料：
   - 所有已確認的 Pivot Point 區間及其 VP 數據
   - 即時發展中的區間（從最後一個 Pivot Point 到現在）
   - 每個區間的 POC、VAH、VAL、總成交量等統計資訊
4. 支援不同的參數配置（pivot_length、price_levels、value_area_pct）
5. 提供完整的單元測試覆蓋

### 驗證標準

執行以下測試通過即為成功：
```python
df = fetch_historical_data('BTCUSDT', '1h', '2024-01-01', '2024-01-31')
vppa_result = calculate_vppa(df, pivot_length=20, price_levels=25, value_area_pct=0.68)

# 應該包含多個區間
assert len(vppa_result['pivot_ranges']) > 0
# 每個區間都有完整的 VP 數據
for range_data in vppa_result['pivot_ranges']:
    assert 'poc' in range_data
    assert 'vah' in range_data
    assert 'val' in range_data
    assert len(range_data['volume_profile']) == 25
```

## 不在範圍內的功能

為了避免範圍膨脹，以下功能明確列為不實作：

1. ❌ POC 延伸選項（'Until Bar Cross'、'Until Bar Touch'）
2. ❌ 視覺化繪圖功能（box、line、label 的座標生成）
3. ❌ Volume Weighted Colored Bars（成交量加權彩色 K 線）
4. ❌ 價格穿越警報機制
5. ❌ 多時間週期 VPPA 分析
6. ❌ 與 TradingView 相容的輸出格式

這些功能可以在基礎功能完成後，作為後續迭代的增強項目。

## 實作策略

採用**分階段增量實作**策略：

1. **Phase 1**：實作 Pivot Point 偵測和區間提取
2. **Phase 2**：實作改進的 Volume Profile 計算（替代現有算法）
3. **Phase 3**：實作 Value Area 計算
4. **Phase 4**：整合所有功能並實作主函數
5. **Phase 5**：撰寫單元測試和整合測試

每個階段完成後都要通過自動化測試，才能進入下一階段。

---

## Phase 1：Pivot Point 偵測功能

### 概述

實作 Pivot Point 偵測機制，能夠識別價格資料中的轉折點（高點和低點）。

### 需要的變更

#### 1. 新增 `find_pivot_points()` 函數

**檔案**：`src/agent/indicators.py`

**位置**：在現有 `calculate_volume_profile()` 函數之後新增

**程式碼**：

```python
def find_pivot_points(
    df: pd.DataFrame,
    length: int = 20
) -> pd.DataFrame:
    """
    偵測 Pivot High 和 Pivot Low

    Pivot High：中心點的 high 價格高於左右各 length 根 K 線
    Pivot Low：中心點的 low 價格低於左右各 length 根 K 線

    參數：
        df: K 線資料 DataFrame（必須包含 'high' 和 'low' 欄位）
        length: 左右觀察窗口大小（預設 20）

    回傳：
        添加 'pivot_high' 和 'pivot_low' 欄位的 DataFrame 副本
        - pivot_high: Pivot High 的價格，非 Pivot High 位置為 NaN
        - pivot_low: Pivot Low 的價格，非 Pivot Low 位置為 NaN

    例外：
        ValueError: 輸入資料格式錯誤或資料量不足時

    注意：
        - Pivot Point 的確認需要右側 length 根 K 線，因此最後 length 根 K 線無法確認
        - 這是符合交易實務的延遲特性
    """
    logger.info(f"開始偵測 Pivot Points（左右窗口：{length}）")

    # 驗證輸入
    required_columns = ['high', 'low']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    if len(df) < length * 2 + 1:
        raise ValueError(
            f"資料筆數（{len(df)}）不足以偵測 Pivot Points"
            f"（需要至少 {length * 2 + 1} 筆）"
        )

    # 建立副本以避免修改原始資料
    df_result = df.copy()
    df_result['pivot_high'] = np.nan
    df_result['pivot_low'] = np.nan

    # 遍歷可能的 Pivot Point 位置（排除前後各 length 根）
    for i in range(length, len(df) - length):
        # 檢查 Pivot High
        center_high = df['high'].iloc[i]
        left_window = df['high'].iloc[i-length:i]
        right_window = df['high'].iloc[i+1:i+length+1]

        # 中心點必須嚴格大於左右兩側的所有點
        if (center_high > left_window.max() and
            center_high > right_window.max()):
            df_result.loc[df_result.index[i], 'pivot_high'] = center_high
            logger.debug(
                f"偵測到 Pivot High：索引 {i}，價格 {center_high:.2f}"
            )

        # 檢查 Pivot Low
        center_low = df['low'].iloc[i]
        left_window_low = df['low'].iloc[i-length:i]
        right_window_low = df['low'].iloc[i+1:i+length+1]

        # 中心點必須嚴格小於左右兩側的所有點
        if (center_low < left_window_low.min() and
            center_low < right_window_low.min()):
            df_result.loc[df_result.index[i], 'pivot_low'] = center_low
            logger.debug(
                f"偵測到 Pivot Low：索引 {i}，價格 {center_low:.2f}"
            )

    # 統計結果
    pivot_high_count = df_result['pivot_high'].notna().sum()
    pivot_low_count = df_result['pivot_low'].notna().sum()
    logger.info(
        f"偵測完成：找到 {pivot_high_count} 個 Pivot High，"
        f"{pivot_low_count} 個 Pivot Low"
    )

    return df_result
```

#### 2. 新增 `extract_pivot_ranges()` 函數

**檔案**：`src/agent/indicators.py`

**位置**：緊接在 `find_pivot_points()` 之後

**程式碼**：

```python
def extract_pivot_ranges(df: pd.DataFrame) -> list:
    """
    從 DataFrame 中提取 Pivot Point 區間配對

    相鄰的兩個 Pivot Point（無論是 High 還是 Low）形成一個區間，
    用於計算該區間的 Volume Profile。

    參數：
        df: 包含 'pivot_high' 和 'pivot_low' 欄位的 DataFrame
            （通常是 find_pivot_points() 的輸出）

    回傳：
        區間列表，每個元素是一個字典：
        {
            'start_idx': int,        # 起始位置（整數索引）
            'end_idx': int,          # 結束位置（整數索引）
            'start_time': Timestamp, # 起始時間
            'end_time': Timestamp,   # 結束時間
            'pivot_type': str,       # 結束位置的 Pivot 類型（'H' 或 'L'）
            'pivot_price': float     # 結束位置的 Pivot 價格
        }

    例外：
        ValueError: 輸入資料格式錯誤時
    """
    logger.info("開始提取 Pivot Point 區間")

    # 驗證輸入
    required_columns = ['pivot_high', 'pivot_low']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    # 找出所有 Pivot Point 的位置
    pivot_points = []

    for i in range(len(df)):
        if not pd.isna(df['pivot_high'].iloc[i]):
            pivot_points.append({
                'idx': i,
                'type': 'H',
                'price': df['pivot_high'].iloc[i],
                'time': df.index[i]
            })
        elif not pd.isna(df['pivot_low'].iloc[i]):
            pivot_points.append({
                'idx': i,
                'type': 'L',
                'price': df['pivot_low'].iloc[i],
                'time': df.index[i]
            })

    if len(pivot_points) < 2:
        logger.warning(f"Pivot Point 數量不足（僅 {len(pivot_points)} 個），無法形成區間")
        return []

    # 配對相鄰的 Pivot Points 形成區間
    ranges = []
    for i in range(len(pivot_points) - 1):
        start_pivot = pivot_points[i]
        end_pivot = pivot_points[i + 1]

        range_info = {
            'start_idx': start_pivot['idx'],
            'end_idx': end_pivot['idx'],
            'start_time': start_pivot['time'],
            'end_time': end_pivot['time'],
            'pivot_type': end_pivot['type'],
            'pivot_price': end_pivot['price'],
            'bar_count': end_pivot['idx'] - start_pivot['idx']
        }

        ranges.append(range_info)

        logger.debug(
            f"區間 {i+1}：索引 {range_info['start_idx']} -> {range_info['end_idx']}，"
            f"類型 {range_info['pivot_type']}，K 線數 {range_info['bar_count']}"
        )

    logger.info(f"提取完成：共 {len(ranges)} 個區間")

    return ranges
```

### 成功標準

#### 自動化驗證
- [ ] 單元測試通過：`pytest tests/test_indicators.py::test_find_pivot_points -v`
- [ ] 單元測試通過：`pytest tests/test_indicators.py::test_extract_pivot_ranges -v`
- [ ] 型別檢查通過：`mypy src/agent/indicators.py`
- [ ] 程式碼風格通過：`flake8 src/agent/indicators.py`

#### 手動驗證
- [ ] 使用真實的 BTCUSDT 1小時資料（至少 1000 根 K 線）測試
- [ ] 偵測到的 Pivot High 確實是局部高點（手動檢查前後 20 根）
- [ ] 偵測到的 Pivot Low 確實是局部低點（手動檢查前後 20 根）
- [ ] 區間數量 = Pivot Point 總數 - 1
- [ ] 每個區間的 `bar_count > 0`

**實作注意**：完成此階段後，暫停並等待手動驗證通過，再進入 Phase 2。

---

## Phase 2：Volume Profile 計算（取代現有算法）

### 概述

實作改進的 Volume Profile 計算函數，支援指定區間計算，並採用與 PineScript VPPA 相同的成交量分配演算法。

### 需要的變更

#### 1. 新增 `calculate_volume_profile_for_range()` 函數

**檔案**：`src/agent/indicators.py`

**位置**：在 `extract_pivot_ranges()` 之後新增

**程式碼**：

```python
def calculate_volume_profile_for_range(
    df: pd.DataFrame,
    start_idx: int,
    end_idx: int,
    price_levels: int = 25
) -> dict:
    """
    計算指定區間的 Volume Profile

    此函數實作與 PineScript VPPA 相同的成交量分配演算法：
    - 價格範圍平均分為 price_levels 層
    - 每根 K 線的成交量按其覆蓋的價格層級比例分配

    參數：
        df: K 線資料 DataFrame（必須包含 'high', 'low', 'real_volume'）
        start_idx: 起始索引（包含，整數位置）
        end_idx: 結束索引（包含，整數位置）
        price_levels: 價格分層數量（預設 25）

    回傳：
        字典，包含：
        {
            'volume_profile': np.ndarray,   # 每層的成交量（長度 = price_levels）
            'price_lowest': float,          # 區間最低價
            'price_highest': float,         # 區間最高價
            'price_step': float,            # 每層的價格高度
            'price_centers': np.ndarray,    # 每層的中心價格
            'total_volume': float,          # 區間總成交量
            'bar_count': int                # K 線數量
        }

    例外：
        ValueError: 輸入資料格式錯誤或索引超出範圍時
    """
    logger.debug(
        f"計算 Volume Profile：索引 {start_idx} -> {end_idx}，"
        f"價格層級 {price_levels}"
    )

    # 驗證輸入
    required_columns = ['high', 'low', 'real_volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    if start_idx < 0 or end_idx >= len(df) or start_idx >= end_idx:
        raise ValueError(
            f"無效的索引範圍：start_idx={start_idx}, end_idx={end_idx}, "
            f"資料長度={len(df)}"
        )

    # 取得區間資料（包含 end_idx）
    range_df = df.iloc[start_idx:end_idx+1]
    bar_count = len(range_df)

    # 計算價格範圍
    price_highest = range_df['high'].max()
    price_lowest = range_df['low'].min()
    price_range = price_highest - price_lowest

    if price_range == 0:
        logger.warning(
            f"區間價格無變化（{price_lowest:.2f}），"
            "無法計算 Volume Profile"
        )
        # 回傳空的 Profile
        return {
            'volume_profile': np.zeros(price_levels),
            'price_lowest': price_lowest,
            'price_highest': price_highest,
            'price_step': 0,
            'price_centers': np.full(price_levels, price_lowest),
            'total_volume': range_df['real_volume'].sum(),
            'bar_count': bar_count
        }

    price_step = price_range / price_levels

    # 初始化成交量儲存陣列
    volume_storage = np.zeros(price_levels)

    # 遍歷每根 K 線，分配成交量到價格層級
    for idx in range(len(range_df)):
        row = range_df.iloc[idx]
        bar_high = row['high']
        bar_low = row['low']
        bar_volume = row['real_volume']
        bar_range = bar_high - bar_low

        # 遍歷每個價格層級
        for level in range(price_levels):
            level_low = price_lowest + level * price_step
            level_high = price_lowest + (level + 1) * price_step

            # 檢查 K 線是否覆蓋此價格層級
            # 條件：K 線的 high >= 層級下界 AND K 線的 low < 層級上界
            if bar_high >= level_low and bar_low < level_high:
                # 按比例分配成交量
                if bar_range == 0:
                    # K 線是一條線（開盤價 = 收盤價），全部分配給此層級
                    volume_storage[level] += bar_volume
                else:
                    # 按 price_step / bar_range 比例分配
                    # 這是 PineScript VPPA 的核心公式
                    ratio = price_step / bar_range
                    volume_storage[level] += bar_volume * ratio

    # 計算每層的中心價格
    price_centers = np.array([
        price_lowest + (level + 0.5) * price_step
        for level in range(price_levels)
    ])

    total_volume = volume_storage.sum()

    logger.debug(
        f"Volume Profile 計算完成：總成交量 {total_volume:.0f}，"
        f"價格範圍 {price_lowest:.2f} - {price_highest:.2f}"
    )

    return {
        'volume_profile': volume_storage,
        'price_lowest': price_lowest,
        'price_highest': price_highest,
        'price_step': price_step,
        'price_centers': price_centers,
        'total_volume': total_volume,
        'bar_count': bar_count
    }
```

#### 2. 更新現有 `calculate_volume_profile()` 函數

**檔案**：`src/agent/indicators.py`

**位置**：第 13-148 行

**變更**：添加 docstring 說明此函數用於計算整個資料集的 VP，並建議使用新的函數計算區間 VP

在 docstring 中添加：

```python
"""
計算整個資料集的 Volume Profile

注意：此函數計算整個 DataFrame 的 Volume Profile。
如果需要計算特定區間的 Volume Profile（例如 Pivot Point 之間的區間），
請使用 calculate_volume_profile_for_range() 函數。

參數：
    ...（保持原有參數說明）
"""
```

### 成功標準

#### 自動化驗證
- [ ] 單元測試通過：`pytest tests/test_indicators.py::test_calculate_volume_profile_for_range -v`
- [ ] 回歸測試通過：`pytest tests/test_indicators.py::test_calculate_volume_profile -v`（確保沒有破壞現有功能）
- [ ] 型別檢查通過：`mypy src/agent/indicators.py`
- [ ] Linting 通過：`flake8 src/agent/indicators.py`

#### 手動驗證
- [ ] 使用小範圍測試資料（例如 50 根 K 線），手動計算成交量分配並驗證結果正確
- [ ] 驗證邊界情況：
  - 價格無變化的區間（price_range = 0）
  - 單根 K 線的區間
  - K 線是水平線（high = low）的情況
- [ ] 與 PineScript VPPA 的輸出比對（使用相同的輸入資料）

**實作注意**：完成此階段並通過所有測試後，進入 Phase 3。

---

## Phase 3：Value Area 計算

### 概述

實作 Value Area 計算邏輯，包括 POC（Point of Control）、VAH（Value Area High）、VAL（Value Area Low）的計算。

### 需要的變更

#### 1. 新增 `calculate_value_area()` 函數

**檔案**：`src/agent/indicators.py`

**位置**：在 `calculate_volume_profile_for_range()` 之後新增

**程式碼**：

```python
def calculate_value_area(
    volume_storage: np.ndarray,
    price_lowest: float,
    price_step: float,
    value_area_pct: float = 0.68
) -> dict:
    """
    計算 Value Area（價值區域）

    Value Area 是包含指定百分比總成交量的價格區間，
    從 POC（成交量最大的價格層級）開始向兩側擴展。

    演算法：
    1. 找出 POC（Point of Control）- 成交量最大的層級
    2. 從 POC 開始，累積成交量
    3. 向兩側擴展，每次選擇成交量較大的一側
    4. 直到累積成交量達到目標百分比（預設 68%）

    參數：
        volume_storage: 每個價格層級的成交量陣列
        price_lowest: 區間最低價
        price_step: 每層的價格高度
        value_area_pct: Value Area 包含的成交量百分比（預設 0.68 即 68%）

    回傳：
        字典，包含：
        {
            'poc_level': int,           # POC 所在層級索引
            'poc_price': float,         # POC 價格（層級中心）
            'poc_volume': float,        # POC 的成交量
            'poc_volume_pct': float,    # POC 佔總成交量的百分比
            'vah': float,               # Value Area High
            'val': float,               # Value Area Low
            'value_area_volume': float, # Value Area 內的成交量
            'total_volume': float,      # 總成交量
            'value_area_pct': float,    # Value Area 實際達到的百分比
            'value_area_width': float,  # Value Area 價格寬度（vah - val）
            'level_above_poc': int,     # VAH 所在層級
            'level_below_poc': int      # VAL 所在層級
        }

    例外：
        ValueError: 輸入參數無效時
    """
    logger.debug(
        f"計算 Value Area：目標百分比 {value_area_pct*100:.1f}%"
    )

    # 驗證輸入
    if len(volume_storage) == 0:
        raise ValueError("volume_storage 不能為空")

    if value_area_pct <= 0 or value_area_pct > 1:
        raise ValueError(
            f"value_area_pct 必須在 0 到 1 之間，得到：{value_area_pct}"
        )

    if price_step < 0:
        raise ValueError(f"price_step 必須為正數，得到：{price_step}")

    # 計算 POC (Point of Control)
    poc_level = int(np.argmax(volume_storage))
    poc_volume = volume_storage[poc_level]
    poc_price = price_lowest + (poc_level + 0.5) * price_step

    total_volume = volume_storage.sum()

    if total_volume == 0:
        logger.warning("總成交量為 0，無法計算 Value Area")
        return {
            'poc_level': poc_level,
            'poc_price': poc_price,
            'poc_volume': 0,
            'poc_volume_pct': 0,
            'vah': price_lowest + (poc_level + 1.0) * price_step,
            'val': price_lowest + (poc_level + 0.0) * price_step,
            'value_area_volume': 0,
            'total_volume': 0,
            'value_area_pct': 0,
            'value_area_width': 0,
            'level_above_poc': poc_level,
            'level_below_poc': poc_level
        }

    poc_volume_pct = (poc_volume / total_volume * 100) if total_volume > 0 else 0

    logger.debug(
        f"POC：層級 {poc_level}，價格 {poc_price:.2f}，"
        f"成交量 {poc_volume:.0f} ({poc_volume_pct:.1f}%)"
    )

    # 計算目標成交量
    target_volume = total_volume * value_area_pct

    # 從 POC 開始向兩側擴展
    value_area_volume = poc_volume
    level_above_poc = poc_level
    level_below_poc = poc_level

    while value_area_volume < target_volume:
        # 檢查是否已經到達邊界
        if level_below_poc == 0 and level_above_poc == len(volume_storage) - 1:
            logger.debug("已擴展到價格範圍邊界，停止擴展")
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

        # 如果兩側都沒有成交量，停止擴展
        if volume_above == 0 and volume_below == 0:
            logger.debug("兩側都無成交量，停止擴展")
            break

        # 選擇成交量較大的一側擴展
        # 如果成交量相等，優先向上擴展（與 PineScript 行為一致）
        if volume_above >= volume_below:
            value_area_volume += volume_above
            level_above_poc += 1
            logger.debug(
                f"向上擴展到層級 {level_above_poc}，"
                f"增加成交量 {volume_above:.0f}"
            )
        else:
            value_area_volume += volume_below
            level_below_poc -= 1
            logger.debug(
                f"向下擴展到層級 {level_below_poc}，"
                f"增加成交量 {volume_below:.0f}"
            )

    # 計算 VAH 和 VAL
    # VAH = 上邊界層級的上界
    vah = price_lowest + (level_above_poc + 1.0) * price_step
    # VAL = 下邊界層級的下界
    val = price_lowest + (level_below_poc + 0.0) * price_step

    value_area_width = vah - val
    actual_value_area_pct = (
        (value_area_volume / total_volume * 100) if total_volume > 0 else 0
    )

    logger.debug(
        f"Value Area 計算完成：VAH {vah:.2f}，VAL {val:.2f}，"
        f"寬度 {value_area_width:.2f}，"
        f"成交量 {value_area_volume:.0f} ({actual_value_area_pct:.1f}%)"
    )

    return {
        'poc_level': int(poc_level),
        'poc_price': float(poc_price),
        'poc_volume': float(poc_volume),
        'poc_volume_pct': float(poc_volume_pct),
        'vah': float(vah),
        'val': float(val),
        'value_area_volume': float(value_area_volume),
        'total_volume': float(total_volume),
        'value_area_pct': float(actual_value_area_pct),
        'value_area_width': float(value_area_width),
        'level_above_poc': int(level_above_poc),
        'level_below_poc': int(level_below_poc)
    }
```

### 成功標準

#### 自動化驗證
- [ ] 單元測試通過：`pytest tests/test_indicators.py::test_calculate_value_area -v`
- [ ] 測試各種邊界情況：
  - POC 在最上層的情況
  - POC 在最下層的情況
  - 目標百分比 100% 的情況
  - 所有成交量集中在單一層級的情況
- [ ] 型別檢查通過：`mypy src/agent/indicators.py`
- [ ] Linting 通過：`flake8 src/agent/indicators.py`

#### 手動驗證
- [ ] 使用人工構造的簡單成交量分佈（例如 10 層），手動計算 Value Area 並驗證
- [ ] 驗證 `value_area_volume >= target_volume` 或已到達邊界
- [ ] 驗證 `val <= poc_price <= vah`
- [ ] 與 PineScript VPPA 的 Value Area 計算結果比對

**實作注意**：完成此階段並通過所有測試後，進入 Phase 4。

---

## Phase 4：主整合函數

### 概述

實作 `calculate_vppa()` 主函數，整合所有前面實作的功能，協調 Pivot Point 偵測、區間提取、Volume Profile 計算和 Value Area 計算。

### 需要的變更

#### 1. 新增 `calculate_vppa()` 主函數

**檔案**：`src/agent/indicators.py`

**位置**：在所有輔助函數之後新增（接近檔案末尾）

**程式碼**：

```python
def calculate_vppa(
    df: pd.DataFrame,
    pivot_length: int = 20,
    price_levels: int = 25,
    value_area_pct: float = 0.68,
    include_developing: bool = True
) -> dict:
    """
    計算 Volume Profile Pivot Anchored (VPPA)

    此函數是 VPPA 指標的主要入口，整合以下功能：
    1. 偵測所有 Pivot Points（高點和低點）
    2. 提取相鄰 Pivot Points 之間的區間
    3. 為每個區間計算 Volume Profile
    4. 計算每個區間的 Value Area（POC、VAH、VAL）
    5. 計算即時發展中的區間（從最後一個 Pivot Point 到現在）

    參數：
        df: K 線資料 DataFrame（必須包含 'high', 'low', 'real_volume' 欄位）
        pivot_length: Pivot Point 左右觀察窗口大小（預設 20）
        price_levels: Volume Profile 價格分層數量（預設 25）
        value_area_pct: Value Area 包含的成交量百分比（預設 0.68 即 68%）
        include_developing: 是否包含即時發展中的區間（預設 True）

    回傳：
        字典，包含：
        {
            # 元數據
            'metadata': {
                'total_bars': int,              # 總 K 線數
                'pivot_length': int,
                'price_levels': int,
                'value_area_pct': float,
                'total_pivot_points': int,      # Pivot Points 總數
                'total_ranges': int,            # 區間總數
                'pivot_high_count': int,        # Pivot High 數量
                'pivot_low_count': int          # Pivot Low 數量
            },

            # Pivot Points 摘要
            'pivot_summary': [
                {
                    'idx': int,                 # K 線索引
                    'type': str,                # 'H' 或 'L'
                    'price': float,             # Pivot 價格
                    'time': Timestamp           # 時間戳
                },
                ...
            ],

            # 已確認的 Pivot Point 區間（歷史區間）
            'pivot_ranges': [
                {
                    # 區間資訊
                    'range_id': int,            # 區間編號（從 0 開始）
                    'start_idx': int,
                    'end_idx': int,
                    'start_time': Timestamp,
                    'end_time': Timestamp,
                    'bar_count': int,

                    # Pivot Point 資訊
                    'pivot_type': str,          # 'H' 或 'L'
                    'pivot_price': float,

                    # 價格範圍
                    'price_highest': float,
                    'price_lowest': float,
                    'price_range': float,
                    'price_step': float,

                    # Volume Profile 資料
                    'volume_profile': list,     # 每層成交量（轉為 list 方便序列化）
                    'price_centers': list,      # 每層中心價格

                    # POC 資訊
                    'poc': {
                        'level': int,
                        'price': float,
                        'volume': float,
                        'volume_pct': float
                    },

                    # Value Area 資訊
                    'vah': float,
                    'val': float,
                    'value_area_width': float,
                    'value_area_volume': float,
                    'value_area_pct': float,

                    # 統計資訊
                    'total_volume': float,
                    'avg_volume_per_bar': float
                },
                ...
            ],

            # 即時發展中的區間（可選）
            'developing_range': {
                # 結構同 pivot_ranges，但標記為 is_developing = True
                'is_developing': True,
                ...
            } 或 None（如果 include_developing=False 或無法計算）
        }

    例外：
        ValueError: 輸入資料格式錯誤或資料量不足時
    """
    logger.info("=" * 60)
    logger.info("開始計算 VPPA (Volume Profile Pivot Anchored)")
    logger.info("=" * 60)
    logger.info(
        f"參數：pivot_length={pivot_length}, price_levels={price_levels}, "
        f"value_area_pct={value_area_pct*100:.1f}%"
    )
    logger.info(f"資料筆數：{len(df)} 根 K 線")

    # 驗證輸入
    required_columns = ['high', 'low', 'real_volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要欄位：{missing_columns}")

    if len(df) < pivot_length * 2 + 1:
        raise ValueError(
            f"資料筆數（{len(df)}）不足以計算 VPPA"
            f"（需要至少 {pivot_length * 2 + 1} 筆）"
        )

    # Step 1: 偵測 Pivot Points
    logger.info("Step 1/5: 偵測 Pivot Points")
    df_with_pivots = find_pivot_points(df, length=pivot_length)

    pivot_high_count = df_with_pivots['pivot_high'].notna().sum()
    pivot_low_count = df_with_pivots['pivot_low'].notna().sum()
    total_pivot_points = pivot_high_count + pivot_low_count

    # Step 2: 提取區間
    logger.info("Step 2/5: 提取 Pivot Point 區間")
    ranges = extract_pivot_ranges(df_with_pivots)

    if len(ranges) == 0:
        logger.warning("未找到任何 Pivot Point 區間，回傳空結果")
        return {
            'metadata': {
                'total_bars': len(df),
                'pivot_length': pivot_length,
                'price_levels': price_levels,
                'value_area_pct': value_area_pct,
                'total_pivot_points': total_pivot_points,
                'total_ranges': 0,
                'pivot_high_count': pivot_high_count,
                'pivot_low_count': pivot_low_count
            },
            'pivot_summary': [],
            'pivot_ranges': [],
            'developing_range': None
        }

    # Step 3: 計算每個區間的 Volume Profile
    logger.info(f"Step 3/5: 計算 {len(ranges)} 個區間的 Volume Profile")

    pivot_ranges_data = []

    for i, range_info in enumerate(ranges):
        logger.info(f"處理區間 {i+1}/{len(ranges)}：索引 {range_info['start_idx']} -> {range_info['end_idx']}")

        # 計算 Volume Profile
        vp_result = calculate_volume_profile_for_range(
            df,
            start_idx=range_info['start_idx'],
            end_idx=range_info['end_idx'],
            price_levels=price_levels
        )

        # 計算 Value Area
        va_result = calculate_value_area(
            volume_storage=vp_result['volume_profile'],
            price_lowest=vp_result['price_lowest'],
            price_step=vp_result['price_step'],
            value_area_pct=value_area_pct
        )

        # 整合所有資料
        range_data = {
            # 區間資訊
            'range_id': i,
            'start_idx': range_info['start_idx'],
            'end_idx': range_info['end_idx'],
            'start_time': range_info['start_time'],
            'end_time': range_info['end_time'],
            'bar_count': range_info['bar_count'],

            # Pivot Point 資訊
            'pivot_type': range_info['pivot_type'],
            'pivot_price': range_info['pivot_price'],

            # 價格範圍
            'price_highest': vp_result['price_highest'],
            'price_lowest': vp_result['price_lowest'],
            'price_range': vp_result['price_highest'] - vp_result['price_lowest'],
            'price_step': vp_result['price_step'],

            # Volume Profile（轉為 list 以便序列化）
            'volume_profile': vp_result['volume_profile'].tolist(),
            'price_centers': vp_result['price_centers'].tolist(),

            # POC
            'poc': {
                'level': va_result['poc_level'],
                'price': va_result['poc_price'],
                'volume': va_result['poc_volume'],
                'volume_pct': va_result['poc_volume_pct']
            },

            # Value Area
            'vah': va_result['vah'],
            'val': va_result['val'],
            'value_area_width': va_result['value_area_width'],
            'value_area_volume': va_result['value_area_volume'],
            'value_area_pct': va_result['value_area_pct'],

            # 統計
            'total_volume': vp_result['total_volume'],
            'avg_volume_per_bar': (
                vp_result['total_volume'] / vp_result['bar_count']
                if vp_result['bar_count'] > 0 else 0
            )
        }

        pivot_ranges_data.append(range_data)

        logger.debug(
            f"區間 {i+1} 完成：POC={va_result['poc_price']:.2f}, "
            f"VAH={va_result['vah']:.2f}, VAL={va_result['val']:.2f}"
        )

    # Step 4: 建立 Pivot Points 摘要
    logger.info("Step 4/5: 建立 Pivot Points 摘要")

    pivot_summary = []
    for i in range(len(df_with_pivots)):
        if not pd.isna(df_with_pivots['pivot_high'].iloc[i]):
            pivot_summary.append({
                'idx': i,
                'type': 'H',
                'price': df_with_pivots['pivot_high'].iloc[i],
                'time': df_with_pivots.index[i]
            })
        elif not pd.isna(df_with_pivots['pivot_low'].iloc[i]):
            pivot_summary.append({
                'idx': i,
                'type': 'L',
                'price': df_with_pivots['pivot_low'].iloc[i],
                'time': df_with_pivots.index[i]
            })

    # Step 5: 計算即時發展中的區間（可選）
    logger.info("Step 5/5: 計算即時發展中的區間")

    developing_range = None

    if include_developing and len(pivot_summary) > 0:
        # 最後一個 Pivot Point
        last_pivot = pivot_summary[-1]
        last_pivot_idx = last_pivot['idx']
        current_idx = len(df) - 1

        # 確保有足夠的 K 線形成區間
        if current_idx > last_pivot_idx:
            logger.info(
                f"計算發展中區間：索引 {last_pivot_idx} -> {current_idx} "
                f"({current_idx - last_pivot_idx} 根 K 線)"
            )

            try:
                # 計算 Volume Profile
                vp_dev = calculate_volume_profile_for_range(
                    df,
                    start_idx=last_pivot_idx,
                    end_idx=current_idx,
                    price_levels=price_levels
                )

                # 計算 Value Area
                va_dev = calculate_value_area(
                    volume_storage=vp_dev['volume_profile'],
                    price_lowest=vp_dev['price_lowest'],
                    price_step=vp_dev['price_step'],
                    value_area_pct=value_area_pct
                )

                developing_range = {
                    'is_developing': True,
                    'range_id': len(ranges),  # 接續最後一個歷史區間的 ID
                    'start_idx': last_pivot_idx,
                    'end_idx': current_idx,
                    'start_time': df.index[last_pivot_idx],
                    'end_time': df.index[current_idx],
                    'bar_count': current_idx - last_pivot_idx + 1,

                    # Pivot Point 資訊（發展中，使用最後一個 Pivot）
                    'pivot_type': last_pivot['type'],
                    'pivot_price': last_pivot['price'],

                    # 價格範圍
                    'price_highest': vp_dev['price_highest'],
                    'price_lowest': vp_dev['price_lowest'],
                    'price_range': vp_dev['price_highest'] - vp_dev['price_lowest'],
                    'price_step': vp_dev['price_step'],

                    # Volume Profile
                    'volume_profile': vp_dev['volume_profile'].tolist(),
                    'price_centers': vp_dev['price_centers'].tolist(),

                    # POC
                    'poc': {
                        'level': va_dev['poc_level'],
                        'price': va_dev['poc_price'],
                        'volume': va_dev['poc_volume'],
                        'volume_pct': va_dev['poc_volume_pct']
                    },

                    # Value Area
                    'vah': va_dev['vah'],
                    'val': va_dev['val'],
                    'value_area_width': va_dev['value_area_width'],
                    'value_area_volume': va_dev['value_area_volume'],
                    'value_area_pct': va_dev['value_area_pct'],

                    # 統計
                    'total_volume': vp_dev['total_volume'],
                    'avg_volume_per_bar': (
                        vp_dev['total_volume'] / vp_dev['bar_count']
                        if vp_dev['bar_count'] > 0 else 0
                    )
                }

                logger.info(
                    f"發展中區間完成：POC={va_dev['poc_price']:.2f}, "
                    f"VAH={va_dev['vah']:.2f}, VAL={va_dev['val']:.2f}"
                )

            except Exception as e:
                logger.warning(f"計算發展中區間時發生錯誤：{e}")
                developing_range = None
        else:
            logger.info("最後一個 Pivot Point 後沒有足夠的 K 線，跳過發展中區間")

    # 組裝最終結果
    result = {
        'metadata': {
            'total_bars': len(df),
            'pivot_length': pivot_length,
            'price_levels': price_levels,
            'value_area_pct': value_area_pct,
            'total_pivot_points': total_pivot_points,
            'total_ranges': len(ranges),
            'pivot_high_count': pivot_high_count,
            'pivot_low_count': pivot_low_count
        },
        'pivot_summary': pivot_summary,
        'pivot_ranges': pivot_ranges_data,
        'developing_range': developing_range
    }

    logger.info("=" * 60)
    logger.info("VPPA 計算完成")
    logger.info(f"找到 {total_pivot_points} 個 Pivot Points（{pivot_high_count} High, {pivot_low_count} Low）")
    logger.info(f"產生 {len(ranges)} 個歷史區間")
    logger.info(f"發展中區間：{'是' if developing_range else '否'}")
    logger.info("=" * 60)

    return result
```

### 成功標準

#### 自動化驗證
- [ ] 單元測試通過：`pytest tests/test_indicators.py::test_calculate_vppa -v`
- [ ] 整合測試通過：`pytest tests/test_indicators.py::test_vppa_integration -v`
- [ ] 型別檢查通過：`mypy src/agent/indicators.py`
- [ ] Linting 通過：`flake8 src/agent/indicators.py`
- [ ] 所有測試通過：`pytest tests/test_indicators.py -v`

#### 手動驗證
- [ ] 使用真實的市場資料（BTCUSDT 1小時，2024年1月資料）測試
- [ ] 驗證輸出資料結構完整且正確
- [ ] 驗證 `len(pivot_ranges) == total_pivot_points - 1`
- [ ] 驗證每個區間的 `value_area_pct` 接近目標值 68%（或已擴展到邊界）
- [ ] 將結果匯出為 JSON，檢查是否可正常序列化
- [ ] 驗證發展中區間的計算正確（bar_count、時間範圍等）

**實作注意**：完成此階段並通過所有測試後，進入 Phase 5。

---

## Phase 5：單元測試和整合測試

### 概述

撰寫全面的單元測試和整合測試，確保所有功能正確且穩定。

### 需要的變更

#### 1. 建立測試檔案

**檔案**：`tests/test_indicators.py`

**位置**：新建檔案（如果不存在）或在現有檔案中添加測試

**程式碼**：

```python
"""
indicators.py 模組的單元測試與整合測試
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from agent.indicators import (
    find_pivot_points,
    extract_pivot_ranges,
    calculate_volume_profile_for_range,
    calculate_value_area,
    calculate_vppa
)


class TestFindPivotPoints:
    """測試 find_pivot_points() 函數"""

    def test_basic_pivot_detection(self):
        """測試基本的 Pivot Point 偵測"""
        # 建立測試資料：明顯的高低點
        highs = [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1]
        lows = [0.5, 1.5, 2.5, 3.5, 4.5, 3.5, 2.5, 1.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 4.5, 3.5, 2.5, 1.5, 0.5]

        df = pd.DataFrame({
            'high': highs,
            'low': lows
        })

        # 使用小窗口（length=3）以便測試
        result = find_pivot_points(df, length=3)

        # 應該偵測到 Pivot High 和 Pivot Low
        assert result['pivot_high'].notna().sum() > 0
        assert result['pivot_low'].notna().sum() > 0

    def test_pivot_high_position(self):
        """測試 Pivot High 的位置正確性"""
        # 建立清晰的高點：索引 10 應該是 Pivot High
        highs = [1] * 8 + [2, 3, 10, 3, 2] + [1] * 8
        lows = [h - 0.5 for h in highs]

        df = pd.DataFrame({
            'high': highs,
            'low': lows
        })

        result = find_pivot_points(df, length=3)

        # 索引 10 應該被偵測為 Pivot High
        assert not pd.isna(result['pivot_high'].iloc[10])
        assert result['pivot_high'].iloc[10] == 10

    def test_pivot_low_position(self):
        """測試 Pivot Low 的位置正確性"""
        # 建立清晰的低點：索引 10 應該是 Pivot Low
        lows = [10] * 8 + [9, 8, 1, 8, 9] + [10] * 8
        highs = [l + 0.5 for l in lows]

        df = pd.DataFrame({
            'high': highs,
            'low': lows
        })

        result = find_pivot_points(df, length=3)

        # 索引 10 應該被偵測為 Pivot Low
        assert not pd.isna(result['pivot_low'].iloc[10])
        assert result['pivot_low'].iloc[10] == 1

    def test_insufficient_data(self):
        """測試資料量不足的情況"""
        df = pd.DataFrame({
            'high': [1, 2, 3],
            'low': [0.5, 1.5, 2.5]
        })

        with pytest.raises(ValueError) as exc_info:
            find_pivot_points(df, length=20)

        assert "資料筆數" in str(exc_info.value)

    def test_missing_columns(self):
        """測試缺少必要欄位"""
        df = pd.DataFrame({
            'high': [1, 2, 3]
        })

        with pytest.raises(ValueError) as exc_info:
            find_pivot_points(df, length=1)

        assert "缺少必要欄位" in str(exc_info.value)


class TestExtractPivotRanges:
    """測試 extract_pivot_ranges() 函數"""

    def test_basic_range_extraction(self):
        """測試基本的區間提取"""
        # 建立有兩個 Pivot Points 的資料
        df = pd.DataFrame({
            'pivot_high': [np.nan] * 10 + [100.0] + [np.nan] * 10 + [110.0] + [np.nan] * 10,
            'pivot_low': [np.nan] * 30
        })

        ranges = extract_pivot_ranges(df)

        # 應該有一個區間（從第一個 Pivot 到第二個）
        assert len(ranges) == 1
        assert ranges[0]['start_idx'] == 10
        assert ranges[0]['end_idx'] == 21
        assert ranges[0]['pivot_type'] == 'H'

    def test_alternating_pivots(self):
        """測試交替的高低點"""
        pivot_highs = [np.nan] * 5 + [100.0] + [np.nan] * 10 + [110.0] + [np.nan] * 10
        pivot_lows = [np.nan] * 15 + [90.0] + [np.nan] * 10

        df = pd.DataFrame({
            'pivot_high': pivot_highs,
            'pivot_low': pivot_lows
        })

        ranges = extract_pivot_ranges(df)

        # 應該有兩個區間
        assert len(ranges) == 2
        # 第一個區間：從 Pivot High (5) 到 Pivot Low (15)
        assert ranges[0]['start_idx'] == 5
        assert ranges[0]['end_idx'] == 15
        assert ranges[0]['pivot_type'] == 'L'
        # 第二個區間：從 Pivot Low (15) 到 Pivot High (21)
        assert ranges[1]['start_idx'] == 15
        assert ranges[1]['end_idx'] == 21
        assert ranges[1]['pivot_type'] == 'H'

    def test_insufficient_pivots(self):
        """測試 Pivot Points 不足的情況"""
        df = pd.DataFrame({
            'pivot_high': [100.0] + [np.nan] * 10,
            'pivot_low': [np.nan] * 11
        })

        ranges = extract_pivot_ranges(df)

        # 只有一個 Pivot，無法形成區間
        assert len(ranges) == 0


class TestCalculateVolumeProfileForRange:
    """測試 calculate_volume_profile_for_range() 函數"""

    def test_basic_volume_distribution(self):
        """測試基本的成交量分配"""
        # 建立簡單的測試資料：5 根 K 線，價格從 100 到 110
        df = pd.DataFrame({
            'high': [102, 104, 106, 108, 110],
            'low': [100, 102, 104, 106, 108],
            'real_volume': [100, 100, 100, 100, 100]
        })

        result = calculate_volume_profile_for_range(
            df,
            start_idx=0,
            end_idx=4,
            price_levels=5
        )

        # 驗證基本屬性
        assert result['price_lowest'] == 100
        assert result['price_highest'] == 110
        assert result['price_step'] == 2.0  # (110 - 100) / 5
        assert result['total_volume'] == 500
        assert len(result['volume_profile']) == 5

    def test_single_bar_range(self):
        """測試單根 K 線的區間"""
        df = pd.DataFrame({
            'high': [105],
            'low': [100],
            'real_volume': [100]
        })

        result = calculate_volume_profile_for_range(
            df,
            start_idx=0,
            end_idx=0,
            price_levels=5
        )

        assert result['bar_count'] == 1
        assert result['total_volume'] == 100

    def test_flat_price_range(self):
        """測試價格無變化的情況"""
        df = pd.DataFrame({
            'high': [100, 100, 100],
            'low': [100, 100, 100],
            'real_volume': [50, 50, 50]
        })

        result = calculate_volume_profile_for_range(
            df,
            start_idx=0,
            end_idx=2,
            price_levels=5
        )

        # 價格無變化，price_step 應該為 0
        assert result['price_step'] == 0
        assert result['total_volume'] == 150

    def test_invalid_index_range(self):
        """測試無效的索引範圍"""
        df = pd.DataFrame({
            'high': [100, 105, 110],
            'low': [95, 100, 105],
            'real_volume': [100, 100, 100]
        })

        with pytest.raises(ValueError):
            calculate_volume_profile_for_range(df, start_idx=2, end_idx=1, price_levels=5)


class TestCalculateValueArea:
    """測試 calculate_value_area() 函數"""

    def test_simple_value_area(self):
        """測試簡單的 Value Area 計算"""
        # 建立簡單的成交量分佈：中間層級成交量最大
        volume_storage = np.array([10, 20, 50, 20, 10])  # POC 在索引 2

        result = calculate_value_area(
            volume_storage=volume_storage,
            price_lowest=100.0,
            price_step=2.0,
            value_area_pct=0.7
        )

        # POC 應該在索引 2
        assert result['poc_level'] == 2
        assert result['poc_price'] == 100.0 + (2 + 0.5) * 2.0  # 105.0

        # Value Area 應該包含 70% 的成交量
        target_volume = 110 * 0.7  # 總成交量 110
        assert result['value_area_volume'] >= target_volume

    def test_poc_at_edge(self):
        """測試 POC 在邊界的情況"""
        # POC 在最上層
        volume_storage = np.array([10, 20, 30, 40, 100])

        result = calculate_value_area(
            volume_storage=volume_storage,
            price_lowest=100.0,
            price_step=2.0,
            value_area_pct=0.68
        )

        assert result['poc_level'] == 4
        # VAH 不能超出範圍
        assert result['vah'] <= 100.0 + 5 * 2.0

    def test_zero_total_volume(self):
        """測試總成交量為 0 的情況"""
        volume_storage = np.zeros(5)

        result = calculate_value_area(
            volume_storage=volume_storage,
            price_lowest=100.0,
            price_step=2.0,
            value_area_pct=0.68
        )

        # 應該回傳有效的結果（雖然成交量為 0）
        assert result['total_volume'] == 0
        assert result['value_area_volume'] == 0


class TestCalculateVPPA:
    """測試 calculate_vppa() 主函數（整合測試）"""

    def test_basic_vppa_calculation(self):
        """測試基本的 VPPA 計算"""
        # 建立足夠的測試資料
        np.random.seed(42)

        # 建立一個有趨勢的價格序列
        prices = 100 + np.cumsum(np.random.randn(100)) * 2

        df = pd.DataFrame({
            'high': prices + 1,
            'low': prices - 1,
            'real_volume': np.random.randint(50, 150, size=100)
        })
        df.index = pd.date_range('2024-01-01', periods=100, freq='h')

        result = calculate_vppa(
            df,
            pivot_length=10,
            price_levels=10,
            value_area_pct=0.68,
            include_developing=True
        )

        # 驗證結果結構
        assert 'metadata' in result
        assert 'pivot_summary' in result
        assert 'pivot_ranges' in result
        assert 'developing_range' in result

        # 驗證元數據
        assert result['metadata']['total_bars'] == 100
        assert result['metadata']['pivot_length'] == 10
        assert result['metadata']['price_levels'] == 10

    def test_vppa_range_count(self):
        """測試區間數量正確性"""
        # 建立測試資料
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(200)) * 2

        df = pd.DataFrame({
            'high': prices + 1,
            'low': prices - 1,
            'real_volume': np.random.randint(50, 150, size=200)
        })
        df.index = pd.date_range('2024-01-01', periods=200, freq='h')

        result = calculate_vppa(df, pivot_length=15, price_levels=20)

        # 區間數量應該 = Pivot Points 總數 - 1
        total_pivots = result['metadata']['total_pivot_points']
        total_ranges = result['metadata']['total_ranges']

        if total_pivots > 0:
            assert total_ranges == total_pivots - 1

    def test_vppa_each_range_complete(self):
        """測試每個區間的資料完整性"""
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(150)) * 2

        df = pd.DataFrame({
            'high': prices + 1,
            'low': prices - 1,
            'real_volume': np.random.randint(50, 150, size=150)
        })
        df.index = pd.date_range('2024-01-01', periods=150, freq='h')

        result = calculate_vppa(df, pivot_length=10, price_levels=15)

        # 檢查每個區間
        for range_data in result['pivot_ranges']:
            # 必要欄位存在
            assert 'range_id' in range_data
            assert 'start_idx' in range_data
            assert 'end_idx' in range_data
            assert 'poc' in range_data
            assert 'vah' in range_data
            assert 'val' in range_data
            assert 'volume_profile' in range_data

            # volume_profile 長度正確
            assert len(range_data['volume_profile']) == 15

            # VAL <= POC <= VAH
            assert range_data['val'] <= range_data['poc']['price']
            assert range_data['poc']['price'] <= range_data['vah']

    def test_vppa_with_insufficient_data(self):
        """測試資料不足的情況"""
        df = pd.DataFrame({
            'high': [100, 101, 102],
            'low': [99, 100, 101],
            'real_volume': [50, 50, 50]
        })

        with pytest.raises(ValueError) as exc_info:
            calculate_vppa(df, pivot_length=20)

        assert "資料筆數" in str(exc_info.value)


# Fixtures

@pytest.fixture
def sample_ohlcv_data():
    """建立範例 OHLCV 資料"""
    np.random.seed(42)

    prices = 100 + np.cumsum(np.random.randn(200)) * 2

    df = pd.DataFrame({
        'high': prices + 1,
        'low': prices - 1,
        'close': prices,
        'real_volume': np.random.randint(50, 150, size=200)
    })
    df.index = pd.date_range('2024-01-01', periods=200, freq='h')

    return df
```

#### 2. 建立整合測試資料

**檔案**：`tests/fixtures/vppa_test_data.csv`（可選）

建立真實的測試資料檔案，用於更真實的整合測試。

### 成功標準

#### 自動化驗證
- [ ] 所有單元測試通過：`pytest tests/test_indicators.py -v`
- [ ] 測試覆蓋率 >= 80%：`pytest tests/test_indicators.py --cov=src/agent/indicators --cov-report=html`
- [ ] 無 linting 錯誤：`flake8 tests/test_indicators.py`
- [ ] 型別檢查通過：`mypy tests/test_indicators.py`

#### 手動驗證
- [ ] 檢查測試報告，確認所有邊界情況都已覆蓋
- [ ] 執行效能測試，確保計算時間可接受（1000 根 K 線 < 5 秒）
- [ ] 在真實環境中測試完整流程：
  ```python
  from core.data_fetcher import HistoricalDataFetcher
  from agent.indicators import calculate_vppa

  # 獲取真實資料
  fetcher = HistoricalDataFetcher(mt5_client)
  df = fetcher.fetch_historical_data('BTCUSDT', 'H1', '2024-01-01', '2024-01-31')

  # 計算 VPPA
  vppa_result = calculate_vppa(df)

  # 驗證結果
  print(f"找到 {vppa_result['metadata']['total_ranges']} 個區間")
  ```

**實作注意**：所有測試通過後，此階段完成，VPPA 功能開發完成。

---

## 測試策略

### 單元測試（Unit Tests）

針對每個函數獨立測試：

1. **`find_pivot_points()`**
   - 測試正常情況：明確的高低點
   - 測試邊界：資料不足、無 Pivot Point
   - 測試異常：缺少欄位、無效參數

2. **`extract_pivot_ranges()`**
   - 測試正常配對
   - 測試單一 Pivot（無法形成區間）
   - 測試交替的高低點

3. **`calculate_volume_profile_for_range()`**
   - 測試成交量分配正確性
   - 測試價格無變化的情況
   - 測試單根 K 線

4. **`calculate_value_area()`**
   - 測試 POC 計算
   - 測試 Value Area 擴展邏輯
   - 測試邊界情況（POC 在最上/下層）

5. **`calculate_vppa()`**
   - 測試完整流程
   - 測試輸出資料結構
   - 測試即時區間計算

### 整合測試（Integration Tests）

測試完整的使用場景：

1. **真實資料測試**
   - 使用 BTCUSDT 1小時資料（2024年1月，約 720 根 K 線）
   - 驗證所有區間都有合理的 VP 數據
   - 驗證輸出可正常序列化為 JSON

2. **不同參數組合測試**
   - `pivot_length = [10, 20, 30]`
   - `price_levels = [10, 25, 50]`
   - `value_area_pct = [0.5, 0.68, 0.8]`

3. **效能測試**
   - 1000 根 K 線的計算時間應 < 5 秒
   - 10000 根 K 線的計算時間應 < 60 秒

### 測試資料準備

1. **人工構造的簡單資料**：用於單元測試，確保結果可預測
2. **真實市場資料**：用於整合測試，確保實際可用性
3. **邊界情況資料**：極端價格、極端成交量、異常模式

---

## 效能考量

### 預期效能

- **1000 根 K 線**：< 5 秒
- **5000 根 K 線**：< 20 秒
- **10000 根 K 線**：< 60 秒

### 優化策略（如果需要）

1. **向量化運算**：使用 NumPy 的向量化操作替代迴圈
2. **快取機制**：快取中間計算結果
3. **並行處理**：使用多進程計算多個區間的 VP（可選）

目前實作優先考慮正確性和可讀性，效能優化可在後續迭代中進行。

---

## 遷移說明

### 對現有代碼的影響

1. **`calculate_volume_profile()` 函數保持不變**
   - 現有使用此函數的代碼不受影響
   - 只是添加 docstring 說明用途

2. **新增的函數**
   - 所有新函數都是獨立的，不影響現有功能
   - 可以逐步引入到現有工作流程中

3. **測試**
   - 現有的 `test_indicators.py` 測試仍然有效
   - 新增的測試不會影響現有測試

### 向後相容性

此實作完全向後相容，不會破壞任何現有功能。

---

## 參考資料

### 研究文檔
- **研究報告**：`thoughts/shared/research/2024-12-30-vppa-pinescript-analysis.md`
- **原始 PineScript**：`vendor/vppa.txt`

### 現有實作
- **現有 VP 函數**：`src/agent/indicators.py` 第 13-148 行

### 外部資源
- [TradingView PineScript 文檔](https://www.tradingview.com/pine-script-docs/)
- [CME Group: Understanding Volume Profile](https://www.cmegroup.com/education/courses/market-profile/understanding-volume-profile.html)

---

## 結論

此實作計劃採用分階段增量策略，每個階段都有明確的成功標準和驗證方法。通過將複雜的 VPPA 指標分解為五個可管理的階段，我們可以：

1. **降低風險**：每個階段獨立測試，問題可以早期發現
2. **提高品質**：充分的測試覆蓋和手動驗證
3. **保持靈活**：如有需要可在階段間調整策略
4. **確保相容**：不破壞現有功能，向後相容

預計完整實作時間：**5-7 個工作日**（包含測試和文檔）

每個階段完成後，建議進行 code review 和手動測試，確保品質後再進入下一階段。

---

**計劃制定時間**：2024-12-30
**預計開始時間**：待確認
**預計完成時間**：開始後 5-7 個工作日
