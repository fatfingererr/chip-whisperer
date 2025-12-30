"""
MT5 客戶端封裝模組

此模組提供 Chip Whisperer 專用的 MT5 客戶端封裝，簡化 MT5 連線和操作。
支援 context manager 模式，自動管理連線生命週期。
"""

from typing import Optional
import MetaTrader5 as mt5
from loguru import logger

from .mt5_config import MT5Config


class ChipWhispererMT5Client:
    """
    Chip Whisperer 專用的 MT5 客戶端封裝

    提供簡化的介面和增強的錯誤處理，並支援 context manager (with 語句)。
    """

    def __init__(self, config: Optional[MT5Config] = None):
        """
        初始化客戶端

        參數：
            config: MT5 設定物件（若為 None 則使用預設設定）
        """
        self.config = config or MT5Config()
        self._connected = False

        # 驗證設定
        try:
            self.config.validate()
        except ValueError as e:
            logger.error(f"MT5 設定驗證失敗：{e}")
            raise

        logger.debug("ChipWhispererMT5Client 初始化完成")

    def connect(self) -> bool:
        """
        連線到 MT5

        回傳：
            True 如果連線成功，False 如果失敗

        例外：
            RuntimeError: 連線過程發生錯誤時
        """
        if self._connected:
            logger.warning("已經連線到 MT5，無需重複連線")
            return True

        try:
            logger.info("正在連線到 MT5...")

            # 取得連線設定
            conn_config = self.config.get_connection_config()

            # 初始化 MT5
            path = conn_config.get('path')
            if path:
                if not mt5.initialize(path=path):
                    error_code = mt5.last_error()
                    error_msg = f"MT5 初始化失敗：{error_code}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            else:
                if not mt5.initialize():
                    error_code = mt5.last_error()
                    error_msg = f"MT5 初始化失敗：{error_code}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

            logger.debug("MT5 終端機初始化成功")

            # 登入帳戶
            login = conn_config.get('login')
            password = conn_config.get('password')
            server = conn_config.get('server')
            timeout = conn_config.get('timeout', 60000)

            if not mt5.login(login=login, password=password, server=server, timeout=timeout):
                error_code = mt5.last_error()
                error_msg = f"MT5 登入失敗：{error_code}"
                logger.error(error_msg)
                mt5.shutdown()
                raise RuntimeError(error_msg)

            self._connected = True
            logger.info("MT5 連線成功")

            # 顯示帳戶資訊
            account_info = mt5.account_info()
            if account_info:
                logger.info(
                    f"帳戶資訊：帳號={account_info.login}, "
                    f"餘額={account_info.balance} {account_info.currency}, "
                    f"槓桿=1:{account_info.leverage}"
                )
            else:
                logger.warning("無法取得帳戶資訊")

            return True

        except Exception as e:
            logger.error(f"MT5 連線錯誤：{e}")
            self._connected = False
            raise RuntimeError(f"無法連線到 MT5：{e}") from e

    def disconnect(self) -> bool:
        """
        斷開 MT5 連線

        回傳：
            True 如果斷線成功
        """
        if not self._connected:
            logger.debug("尚未連線，無需斷線")
            return True

        try:
            mt5.shutdown()
            self._connected = False
            logger.info("已斷開 MT5 連線")
            return True

        except Exception as e:
            logger.error(f"斷線時發生錯誤：{e}")
            return False

    def is_connected(self) -> bool:
        """
        檢查連線狀態

        回傳：
            True 如果已連線
        """
        # 雙重檢查：內部狀態和 MT5 終端機狀態
        if not self._connected:
            return False

        # 嘗試取得終端機資訊來確認連線狀態
        try:
            terminal_info = mt5.terminal_info()
            return terminal_info is not None
        except Exception:
            return False

    def ensure_connected(self) -> None:
        """
        確保已連線，若未連線則自動連線

        例外：
            RuntimeError: 連線失敗時
        """
        if not self.is_connected():
            logger.debug("偵測到未連線，嘗試自動連線...")
            self.connect()

    def get_account_info(self) -> Optional[dict]:
        """
        取得帳戶資訊

        回傳：
            包含帳戶資訊的字典，失敗時回傳 None
        """
        self.ensure_connected()

        try:
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("無法取得帳戶資訊")
                return None

            return account_info._asdict()

        except Exception as e:
            logger.error(f"取得帳戶資訊時發生錯誤：{e}")
            return None

    def get_terminal_info(self) -> Optional[dict]:
        """
        取得終端機資訊

        回傳：
            包含終端機資訊的字典，失敗時回傳 None
        """
        self.ensure_connected()

        try:
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                logger.error("無法取得終端機資訊")
                return None

            return terminal_info._asdict()

        except Exception as e:
            logger.error(f"取得終端機資訊時發生錯誤：{e}")
            return None

    def __enter__(self):
        """
        支援 context manager（with 語句）進入

        回傳：
            self
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        支援 context manager（with 語句）退出

        自動斷線
        """
        self.disconnect()

    def __repr__(self) -> str:
        """
        字串表示

        回傳：
            物件的字串描述
        """
        status = "已連線" if self._connected else "未連線"
        login = self.config.get('login', 'N/A')
        server = self.config.get('server', 'N/A')
        return f"ChipWhispererMT5Client(login={login}, server={server}, status={status})"
