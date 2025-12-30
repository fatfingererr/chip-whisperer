"""
MT5Config 類別的單元測試
"""

import pytest
from pathlib import Path
import tempfile
import os

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.mt5_config import MT5Config


class TestMT5Config:
    """MT5Config 測試類別"""

    def test_init_with_dict(self):
        """測試使用字典初始化"""
        config_dict = {
            'login': 12345678,
            'password': 'test_password',
            'server': 'TestServer-Demo'
        }

        config = MT5Config(config_dict=config_dict)

        assert config.get('login') == 12345678
        assert config.get('password') == 'test_password'
        assert config.get('server') == 'TestServer-Demo'

    def test_validate_success(self):
        """測試設定驗證成功"""
        config_dict = {
            'login': 12345678,
            'password': 'test_password',
            'server': 'TestServer-Demo'
        }

        config = MT5Config(config_dict=config_dict)

        # 不應該拋出例外
        assert config.validate() is True

    def test_validate_missing_fields(self):
        """測試缺少必要欄位時的驗證"""
        config_dict = {
            'login': 12345678,
            # 缺少 password
            'server': 'TestServer-Demo'
        }

        config = MT5Config(config_dict=config_dict)

        # 應該拋出 ValueError
        with pytest.raises(ValueError) as exc_info:
            config.validate()

        assert 'password' in str(exc_info.value)

    def test_validate_invalid_login(self):
        """測試無效的 login 欄位"""
        config_dict = {
            'login': 'invalid_login',  # 應該是整數
            'password': 'test_password',
            'server': 'TestServer-Demo'
        }

        config = MT5Config(config_dict=config_dict)

        # 應該拋出 ValueError
        with pytest.raises(ValueError) as exc_info:
            config.validate()

        assert 'login' in str(exc_info.value).lower()

    def test_get_connection_config(self):
        """測試取得連線設定"""
        config_dict = {
            'login': '12345678',  # 字串形式
            'password': 'test_password',
            'server': 'TestServer-Demo',
            'timeout': 60000
        }

        config = MT5Config(config_dict=config_dict)
        conn_config = config.get_connection_config()

        # login 應該被轉換為整數
        assert isinstance(conn_config['login'], int)
        assert conn_config['login'] == 12345678

    def test_repr_hides_password(self):
        """測試字串表示隱藏密碼"""
        config_dict = {
            'login': 12345678,
            'password': 'secret_password',
            'server': 'TestServer-Demo'
        }

        config = MT5Config(config_dict=config_dict)
        repr_str = repr(config)

        # 密碼應該被隱藏
        assert 'secret_password' not in repr_str
        assert '***' in repr_str

    def test_dict_access(self):
        """測試字典式存取"""
        config_dict = {
            'login': 12345678,
            'password': 'test_password',
            'server': 'TestServer-Demo'
        }

        config = MT5Config(config_dict=config_dict)

        # 測試 __getitem__
        assert config['login'] == 12345678

        # 測試 __contains__
        assert 'login' in config
        assert 'nonexistent' not in config

    def test_env_config_priority(self):
        """測試環境變數優先權"""
        # 設定環境變數
        os.environ['MT5_LOGIN'] = '99999999'
        os.environ['MT5_PASSWORD'] = 'env_password'
        os.environ['MT5_SERVER'] = 'EnvServer'

        try:
            config = MT5Config()

            # 環境變數應該被載入
            assert config.get('login') == '99999999'
            assert config.get('password') == 'env_password'
            assert config.get('server') == 'EnvServer'

        finally:
            # 清理環境變數
            del os.environ['MT5_LOGIN']
            del os.environ['MT5_PASSWORD']
            del os.environ['MT5_SERVER']

    def test_default_values(self):
        """測試預設值"""
        config_dict = {
            'login': 12345678,
            'password': 'test_password',
            'server': 'TestServer-Demo'
        }

        config = MT5Config(config_dict=config_dict)

        # 測試未設定的欄位有預設值
        assert config.get('timeout', 60000) == 60000
        assert config.get('portable', False) is False
        assert config.get('max_retries', 3) == 3
