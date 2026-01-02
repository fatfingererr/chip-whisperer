"""
Agent 核心邏輯模組

此模組整合 Anthropic Claude API 和自訂工具，
提供自然語言查詢和智能分析功能。
"""

from typing import List, Dict, Any, Optional
import os
from loguru import logger
import anthropic
from dotenv import load_dotenv

from .tools import TOOLS, execute_tool


class MT5Agent:
    """
    MT5 交易助手 Agent

    整合 Claude API 和 MT5 工具，提供自然語言查詢功能。
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        初始化 Agent

        參數：
            api_key: Anthropic API Key（若未提供則從環境變數讀取）
            model: Claude 模型別名（預設為 sonnet，即 Sonnet 4.5）
        """
        # 載入環境變數
        load_dotenv()

        # 設定 API Key
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("未設定 ANTHROPIC_API_KEY 環境變數")

        # 設定模型（支援別名：default, sonnet, opus, haiku, sonnet[1m], opusplan）
        self.model = model or os.getenv('CLAUDE_MODEL', 'sonnet')

        # 初始化 Anthropic 客戶端
        self.client = anthropic.Anthropic(api_key=self.api_key)

        # 對話歷史（用於多輪對話）
        self.conversation_history: List[Dict[str, Any]] = []

        # 儲存最後的工具結果（用於傳遞圖片等資源）
        self.last_tool_result: Optional[Dict[str, Any]] = None

        logger.info(f"MT5 Agent 初始化完成（模型：{self.model}）")

    def process_message(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        max_turns: int = 10
    ) -> str:
        """
        處理用戶訊息並回傳 Agent 回應

        參數：
            user_message: 用戶訊息
            system_prompt: 系統提示（可選）
            max_turns: 最大工具調用輪數（預設 10）

        回傳：
            Agent 的回應文字
        """
        logger.info(f"處理用戶訊息：{user_message}")

        # 預設系統提示
        if system_prompt is None:
            system_prompt = """你是一個專業的 MT5 交易助手，可以協助用戶查詢市場數據、計算技術指標並提供分析。

你可以使用以下工具：
1. get_candles - 取得歷史 K 線資料
2. calculate_volume_profile - 計算 Volume Profile（POC, VAH, VAL）
3. calculate_sma - 計算簡單移動平均線
4. calculate_rsi - 計算相對強弱指標
5. get_account_info - 取得帳戶資訊

請根據用戶的需求，自動選擇並調用適當的工具。在使用計算工具前，需要先使用 get_candles 取得資料。

回答時請：
- 使用繁體中文
- 清晰解釋分析結果
- 提供實用的交易見解
- 保持專業和友善的語氣
"""

        # 建立用戶訊息
        messages = [{"role": "user", "content": user_message}]

        # 開始對話循環（支援多輪工具調用）
        turn_count = 0
        while turn_count < max_turns:
            turn_count += 1
            logger.debug(f"對話輪次：{turn_count}/{max_turns}")

            try:
                # 調用 Claude API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=16384,  # 增加 token 限制以避免截斷
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages
                )

                logger.debug(f"API 回應狀態：{response.stop_reason}")

                # 處理回應
                if response.stop_reason == "end_turn" or response.stop_reason == "max_tokens":
                    # 正常結束或達到 token 限制，提取文字回應
                    if response.stop_reason == "max_tokens":
                        logger.info("回應達到 token 限制，但仍提取可用內容")
                    text_response = self._extract_text_response(response)
                    logger.info("對話完成")

                    # 如果有圖片資源，合併到回應中
                    if self.last_tool_result:
                        result = self.last_tool_result.copy()
                        result["message"] = text_response
                        # 清空以便下次使用
                        self.last_tool_result = None
                        return result

                    return text_response

                elif response.stop_reason == "tool_use":
                    # 需要調用工具
                    logger.info("檢測到工具調用請求")

                    # 將 Assistant 的回應加入訊息歷史
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    # 執行所有工具調用
                    tool_results = []
                    for content_block in response.content:
                        if content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input
                            tool_use_id = content_block.id

                            logger.info(f"執行工具：{tool_name}")
                            logger.debug(f"工具輸入：{tool_input}")

                            # 執行工具
                            tool_result = execute_tool(tool_name, tool_input)

                            # 儲存工具結果（用於圖片等資源傳遞）
                            if isinstance(tool_result, dict) and tool_result.get("data", {}).get("image_path"):
                                self.last_tool_result = tool_result
                                logger.info(f"偵測到圖片資源：{tool_result['data']['image_path']}")

                            # 格式化工具結果
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": str(tool_result)
                            })

                            logger.debug(f"工具結果：{tool_result}")

                    # 將工具結果加入訊息歷史
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # 繼續下一輪對話
                    continue

                else:
                    # 其他停止原因
                    logger.warning(f"未預期的停止原因：{response.stop_reason}")
                    return self._extract_text_response(response)

            except anthropic.APIError as e:
                logger.exception("Anthropic API 錯誤")
                return f"抱歉，發生錯誤：{str(e)}"

            except Exception as e:
                logger.exception("處理訊息時發生錯誤")
                return f"抱歉，處理您的請求時發生錯誤：{str(e)}"

        # 達到最大輪數
        logger.warning(f"達到最大工具調用輪數：{max_turns}")
        return "抱歉，處理您的請求時超過了最大步驟數。請簡化您的問題或分多次詢問。"

    def _extract_text_response(self, response: anthropic.types.Message) -> str:
        """
        從 API 回應中提取文字內容

        參數：
            response: Anthropic API 回應

        回傳：
            提取的文字內容
        """
        text_parts = []
        for content_block in response.content:
            if hasattr(content_block, 'text'):
                text_parts.append(content_block.text)

        return '\n'.join(text_parts) if text_parts else "抱歉，我無法生成回應。"

    def reset_conversation(self):
        """重設對話歷史"""
        self.conversation_history = []
        logger.info("對話歷史已重設")
