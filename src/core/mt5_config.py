"""
MT5 設定管理模組

此模組負責載入和管理 MT5 連線所需的所有設定參數。
僅支援 .env 檔案作為設定來源。
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from loguru import logger


class MT5Config:
    """
    MT5 設定管理類別

    負責從 .env 檔案載入設定，並提供驗證和存取介面。
    優先順序：環境變數 > .env 檔案 > 預設值
    """

    def __init__(
        self,
        env_file: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None
    ):
        """
        初始化設定管理器

        參數：
            env_file: .env 檔案路徑（若為 None 則使用專案根目錄的 .env）
            config_dict: 直接提供的設定字典（優先權最高）
        """
        self._config: Dict[str, Any] = {}

        # 載入 .env 設定
        self._load_env_config(env_file)

        # 如果直接提供設定字典，覆蓋現有設定
        if config_dict:
            self._config.update(config_dict)

        logger.debug(f"MT5Config 初始化完成，設定來源：env_file={env_file}")

    def _load_env_config(self, env_file: Optional[str] = None) -> None:
        """
        從環境變數和 .env 檔案載入設定

        參數：
            env_file: .env 檔案路徑
        """
        # 載入 .env 檔案
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
            logger.debug(f"已載入 .env 檔案：{env_file}")
        else:
            # 嘗試載入專案根目錄的 .env
            default_env = Path.cwd() / '.env'
            if default_env.exists():
                load_dotenv(default_env)
                logger.debug(f"已載入預設 .env 檔案：{default_env}")

        # 從環境變數讀取設定
        env_config = {
            'login': os.getenv('MT5_LOGIN'),
            'password': os.getenv('MT5_PASSWORD'),
            'server': os.getenv('MT5_SERVER'),
            'path': os.getenv('MT5_PATH'),
            'timeout': int(os.getenv('MT5_TIMEOUT', '60000')),
            'portable': os.getenv('MT5_PORTABLE', 'false').lower() == 'true',
            'debug': os.getenv('DEBUG', 'false').lower() == 'true',
            'max_retries': int(os.getenv('MT5_MAX_RETRIES', '3')),
            'backoff_factor': float(os.getenv('MT5_BACKOFF_FACTOR', '1.5')),
            'cooldown_time': float(os.getenv('MT5_COOLDOWN_TIME', '2.0')),
        }

        # 只保留有值的設定項目
        env_config = {k: v for k, v in env_config.items() if v is not None}

        # 更新設定
        self._config.update(env_config)

    def get(self, key: str, default: Any = None) -> Any:
        """
        取得設定值

        參數：
            key: 設定鍵名
            default: 預設值

        回傳：
            設定值或預設值
        """
        return self._config.get(key, default)

    def get_connection_config(self) -> Dict[str, Any]:
        """
        取得 MT5 連線所需的完整設定字典

        回傳：
            包含所有連線參數的字典
        """
        # 確保必要欄位的型別正確
        config = self._config.copy()

        # 轉換 login 為整數（如果是字串）
        if 'login' in config and isinstance(config['login'], str):
            try:
                config['login'] = int(config['login'])
            except ValueError:
                logger.error(f"無法將 login 轉換為整數：{config['login']}")

        return config

    def validate(self) -> bool:
        """
        驗證設定是否完整有效

        回傳：
            True 如果設定有效

        例外：
            ValueError: 必要設定缺失時拋出
        """
        required_fields = ['login', 'password', 'server']
        missing_fields = []

        for field in required_fields:
            value = self._config.get(field)
            if not value:
                missing_fields.append(field)

        if missing_fields:
            error_msg = f"缺少必要的 MT5 設定欄位：{', '.join(missing_fields)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 驗證 login 是否為有效的數字
        try:
            login = self._config['login']
            if isinstance(login, str):
                int(login)
            elif not isinstance(login, int):
                raise ValueError(f"login 必須是整數，目前型別：{type(login)}")
        except ValueError as e:
            error_msg = f"login 欄位無效：{e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug("MT5 設定驗證通過")
        return True

    def __repr__(self) -> str:
        """
        字串表示（隱藏敏感資訊）

        回傳：
            安全的字串表示
        """
        safe_config = self._config.copy()

        # 隱藏密碼
        if 'password' in safe_config:
            safe_config['password'] = '***'

        return f"MT5Config({safe_config})"

    def __getitem__(self, key: str) -> Any:
        """
        支援字典式存取

        參數：
            key: 設定鍵名

        回傳：
            設定值
        """
        return self._config[key]

    def __contains__(self, key: str) -> bool:
        """
        檢查設定是否存在

        參數：
            key: 設定鍵名

        回傳：
            True 如果設定存在
        """
        return key in self._config
