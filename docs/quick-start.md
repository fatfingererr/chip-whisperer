# Chip Whisperer - 快速設定指南

## 📋 安裝步驟

### 1. 建立虛擬環境

```bash
python -m venv venv
venv\Scripts\activate
```

### 2. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 3. 設定 MT5 帳號

```bash
# 複製設定範本
copy .env.example .env

# 用文字編輯器開啟 .env 並填入您的資訊
notepad .env
```

**需要填入的資訊**：
```env
MT5_LOGIN=12345678              # 您的 MT5 帳號
MT5_PASSWORD=your_password      # 您的 MT5 密碼
MT5_SERVER=YourBroker-Server    # 券商伺服器名稱
```

### 4. 驗證安裝

```bash
python verify_installation.py
```

如果看到 ✓ 表示安裝成功！

---

## 🚀 執行範例

### 基本 K 線資料取得

```bash
python examples/fetch_historical_data.py
```

### Volume Profile 分析

```bash
python examples/demo_volume_profile_data.py
```

---

## ❓ 常見問題

### Q: 如何找到我的伺服器名稱？

在 MT5 終端機中：
1. 點擊「工具」→「選項」
2. 切換到「伺服器」分頁
3. 伺服器名稱會顯示在那裡（例如：`XMGlobal-MT5`）

### Q: 連線失敗怎麼辦？

1. 確認 MT5 終端機已開啟
2. 確認帳號、密碼、伺服器名稱正確
3. 嘗試在 MT5 中手動登入測試

### Q: .env 檔案會被提交到 Git 嗎？

不會！`.env` 已在 `.gitignore` 中，您的帳號資訊是安全的。

---

完整文檔請參考：[MT5 整合說明](mt5-integration.md)
