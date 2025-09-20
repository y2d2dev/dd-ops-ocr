"""
LLM方向判定評価器
Gemini APIを使用して画像の方向を判定
"""

import os
import json
import logging
from typing import Dict, Optional
import base64

logger = logging.getLogger(__name__)


class LLMOrientationEvaluator:
    """LLM方向判定専用クラス"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config (Dict): LLM設定
        """
        self.config = config.get('llm_evaluation', {}).get('orientation_judgment', {})
        self.provider = self.config.get('provider', 'gemini')
        self.model = self.config.get('model', 'gemini-2.0-flash-lite')
        self.max_retries = self.config.get('max_retries', 3)
        self.timeout = self.config.get('timeout', 30)
        self.temperature = self.config.get('temperature', 0.1)
        self.max_output_tokens = self.config.get('max_output_tokens', 8192)
        
        # Vertex AI初期化用の環境変数チェック
        self.project_id = os.getenv('GCP_PROJECT_ID')
        self.location = os.getenv('GCP_LOCATION', 'us-central1')
        if not self.project_id:
            logger.warning("GCP_PROJECT_ID環境変数が設定されていません")
        
        logger.debug(f"LLMOrientationEvaluator初期化: {self.provider}/{self.model}")
    
    def _encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """
        画像ファイルをBase64エンコード
        
        Args:
            image_path (str): 画像ファイルパス
            
        Returns:
            Optional[str]: Base64エンコードされた画像データ、失敗時はNone
        """
        try:
            with open(image_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"画像エンコードエラー: {e}")
            return None
    
    async def _call_vertex_ai_api(self, image_path: str, prompts: Dict) -> Dict:
        """
        Vertex AIを呼び出して方向判定を実行

        Args:
            image_path (str): 画像ファイルパス
            prompts (Dict): プロンプト設定

        Returns:
            Dict: API応答結果
        """
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel, GenerationConfig, Image

            # Vertex AI初期化
            vertexai.init(project=self.project_id, location=self.location)
            model = GenerativeModel(self.model)

            # プロンプト作成
            system_prompt = prompts.get('system_prompt', '')
            user_prompt = prompts.get('user_prompt', '')

            # 画像読み込み
            image = Image.load_from_file(image_path)

            # 生成設定
            generation_config = GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens
            )

            # API呼び出し（非同期対応）
            import asyncio

            # Vertex AIの呼び出しを非同期で実行
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.generate_content([
                    system_prompt + "\n\n" + user_prompt,
                    image
                ], generation_config=generation_config)
            )

            return {
                "success": True,
                "response_text": response.text,
                "model": self.model
            }

        except Exception as e:
            logger.error(f"Vertex AI API呼び出しエラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_llm_response(self, response_text: str) -> Dict:
        """
        LLMの応答からJSON部分を抽出・パース
        
        Args:
            response_text (str): LLMの応答テキスト
            
        Returns:
            Dict: パースされた判定結果
        """
        try:
            # JSONブロックを検索（```json ... ```）
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            
            if json_match:
                json_text = json_match.group(1)
            else:
                # JSONブロック記号なしの場合、全文をJSONとして試行
                json_text = response_text.strip()
            
            # JSONパース
            parsed_result = json.loads(json_text)
            
            # 必要なキーの存在確認
            required_keys = ['rotation_needed', 'recommended_angle']
            for key in required_keys:
                if key not in parsed_result:
                    logger.warning(f"必須キー '{key}' が応答に含まれていません")
            
            return {
                "success": True,
                "judgment": parsed_result,
                "raw_response": response_text
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            return {
                "success": False,
                "error": f"JSON解析失敗: {str(e)}",
                "raw_response": response_text
            }
        except Exception as e:
            logger.error(f"応答解析エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_response": response_text
            }
    
    async def evaluate_orientation(self, image_path: str, prompts: Dict) -> Dict:
        """
        画像の方向を判定
        
        Args:
            image_path (str): 判定対象画像パス
            prompts (Dict): プロンプト設定
            
        Returns:
            Dict: 判定結果
        """
        logger.debug(f"LLM方向判定開始: {os.path.basename(image_path)}")
        
        try:
            # 画像ファイル存在確認
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "error": f"画像ファイルが見つかりません: {image_path}"
                }
            
            # Project ID確認
            if not self.project_id:
                return {
                    "success": False,
                    "error": "GCP_PROJECT_ID環境変数が設定されていません"
                }

            # リトライ処理
            last_error = None
            for attempt in range(self.max_retries):
                logger.debug(f"LLM API呼び出し試行 {attempt + 1}/{self.max_retries}")

                # API呼び出し（非同期）
                api_result = await self._call_vertex_ai_api(image_path, prompts)
                
                if api_result.get("success"):
                    # 応答解析
                    parse_result = self._parse_llm_response(api_result["response_text"])
                    
                    if parse_result.get("success"):
                        logger.debug("LLM方向判定完了")
                        return {
                            "success": True,
                            "judgment": parse_result["judgment"],
                            "model_info": {
                                "provider": self.provider,
                                "model": self.model,
                                "attempt": attempt + 1
                            },
                            "raw_response": parse_result["raw_response"]
                        }
                    else:
                        last_error = parse_result["error"]
                        logger.warning(f"応答解析失敗 (試行{attempt + 1}): {last_error}")
                else:
                    last_error = api_result["error"]
                    logger.warning(f"API呼び出し失敗 (試行{attempt + 1}): {last_error}")
            
            # 全試行失敗
            return {
                "success": False,
                "error": f"LLM方向判定失敗: {last_error} (最大{self.max_retries}回試行)"
            }
            
        except Exception as e:
            logger.error(f"LLM方向判定エラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def save_result(self, result: Dict, output_file: str) -> bool:
        """
        判定結果をJSONファイルに保存
        
        Args:
            result (Dict): 判定結果
            output_file (str): 出力ファイルパス
            
        Returns:
            bool: 保存成功時True
        """
        try:
            # 出力ディレクトリを作成
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # JSON保存
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"方向判定結果保存: {os.path.basename(output_file)}")
            return True
            
        except Exception as e:
            logger.error(f"結果保存エラー: {e}")
            return False
    
    def get_judgment_summary(self, result: Dict) -> Dict:
        """
        判定結果の要約を生成
        
        Args:
            result (Dict): 判定結果
            
        Returns:
            Dict: 要約情報
        """
        if not result.get("success"):
            return {"error": "方向判定失敗"}
        
        judgment = result.get("judgment", {})
        
        return {
            "rotation_needed": judgment.get("rotation_needed", False),
            "recommended_angle": judgment.get("recommended_angle", 0),
            "confidence": judgment.get("confidence_score", 0.0),
            "reasoning": judgment.get("reasoning", ""),
            "text_quality": judgment.get("text_readability", "unknown")
        }