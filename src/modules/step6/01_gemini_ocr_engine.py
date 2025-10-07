"""
Step6-01: Gemini OCRエンジン
Gemini 2.5 Proを使用してOCR処理を実行
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Union
import base64
from pathlib import Path

logger = logging.getLogger(__name__)


class GeminiOCREngine:
    """Gemini OCRエンジン"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: OCR設定
                - model: Geminiモデル名（デフォルト: gemini-2.0-flash-exp）
                - temperature: 生成温度（デフォルト: 0.1）
                - max_output_tokens: 最大出力トークン（デフォルト: 8192）
                - max_retries: リトライ回数（デフォルト: 3）
                - timeout: タイムアウト秒（デフォルト: 60）
        """
        self.config = config.get('gemini_ocr', {})
        self.model = self.config.get('model', 'gemini-2.0-flash-exp')  # TODO: Gemini 2.5 Proがリリースされたら変更
        self.temperature = self.config.get('temperature', 0.1)
        self.max_output_tokens = self.config.get('max_output_tokens', 32768)
        self.max_retries = self.config.get('max_retries', 3)
        self.timeout = self.config.get('timeout', 60)
        
        # Vertex AI初期化用の環境変数チェック
        self.project_id = os.getenv('GCP_PROJECT_ID')
        self.location = os.getenv('GCP_LOCATION', 'us-central1')
        if not self.project_id:
            logger.warning("GCP_PROJECT_ID環境変数が設定されていません")
        
        logger.debug(f"GeminiOCREngine初期化: {self.model}")
    
    def _encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """
        画像ファイルをBase64エンコード
        
        Args:
            image_path: 画像ファイルパス
            
        Returns:
            Optional[str]: Base64エンコードされた画像データ、失敗時はNone
        """
        try:
            with open(image_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"画像エンコードエラー ({image_path}): {e}")
            return None
    
    def _prepare_images_for_api(self, image_paths: List[str]) -> List:
        """
        複数画像をVertex AI用に準備

        Args:
            image_paths: 画像パスのリスト

        Returns:
            List: Vertex AI用画像オブジェクトのリスト
        """
        from vertexai.generative_models import Image, Part

        images = []

        try:
            for image_path in image_paths:
                if os.path.exists(image_path):
                    image = Image.load_from_file(image_path)
                    images.append(image)
                else:
                    logger.warning(f"画像ファイルが見つかりません: {image_path}")

        except Exception as e:
            logger.error(f"画像準備エラー: {e}")

        return images
    
    async def _call_vertex_ai_api(self, images: List, prompt: str) -> Dict:
        """
        Vertex AIを非同期で呼び出し

        Args:
            images: Vertex AI用画像オブジェクトのリスト
            prompt: プロンプト

        Returns:
            Dict: API応答結果
        """
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel, GenerationConfig

            # Vertex AI初期化
            vertexai.init(project=self.project_id, location=self.location)
            model = GenerativeModel(self.model)

            # リクエスト内容を構築（プロンプト + 複数画像）
            content = [prompt] + images

            # 生成設定
            generation_config = GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens
            )

            # API呼び出しを非同期で実行
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.generate_content(
                    content,
                    generation_config=generation_config
                )
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
    
    def _parse_ocr_response(self, response_text: str) -> Dict:
        """
        OCR応答からJSON部分を抽出・パース
        
        Args:
            response_text: Geminiの応答テキスト
            
        Returns:
            Dict: パースされたOCR結果
        """
        try:
            import re
            
            # 複数のJSONパターンを試行
            json_patterns = [
                r'```json\s*(.*?)\s*```',      # ```json ... ``` 形式
                r'```\s*(.*?)\s*```',          # ``` ... ``` 形式（jsonなし）
                r'\{.*\}',                     # { ... } 形式（改行含む）
            ]
            
            json_text = None
            for pattern in json_patterns:
                match = re.search(pattern, response_text, re.DOTALL)
                if match:
                    json_text = match.group(1) if pattern.startswith(r'```') else match.group(0)
                    break
            
            # JSONが見つからない場合は全文をJSONとして試行
            if not json_text:
                json_text = response_text.strip()
            
            # JSONパース
            parsed_result = json.loads(json_text)
            
            # extracted_textフィールドが存在することを確認
            if isinstance(parsed_result, dict) and "extracted_text" in parsed_result:
                logger.debug("OCR結果のJSON解析成功")
                return {
                    "success": True,
                    "ocr_result": parsed_result,
                    "raw_response": response_text
                }
            else:
                # 期待されたフォーマットではない場合
                logger.warning("JSON形式だが期待されたフィールドがありません")
                return {
                    "success": True,
                    "ocr_result": {
                        "extracted_text": json.dumps(parsed_result, ensure_ascii=False, indent=2)
                    },
                    "raw_response": response_text,
                    "parse_warning": "JSONフォーマット不一致、内容を文字列化"
                }
            
        except json.JSONDecodeError as e:
            logger.debug(f"OCR結果JSON解析エラー、生テキストとして処理: {e}")
            # JSONパースに失敗した場合、テキストをそのまま返す（警告レベルを下げる）
            return {
                "success": True,
                "ocr_result": {
                    "extracted_text": response_text.strip()
                },
                "raw_response": response_text,
                "parse_note": f"生テキストとして処理（JSON解析失敗）"
            }
        except Exception as e:
            logger.error(f"OCR応答解析エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_response": response_text
            }
    
    async def extract_text_from_images(self, image_paths: List[str], 
                                     prompts: Dict, retry_count: int = 0) -> Dict:
        """
        複数画像からテキストを抽出
        
        Args:
            image_paths: 画像パスのリスト（[元画像, 分割画像1, 分割画像2, ...]）
            prompts: プロンプト設定（system_prompt, user_prompt）
            retry_count: リトライ回数
            
        Returns:
            Dict: OCR結果
        """
        if not image_paths:
            return {
                "success": False,
                "error": "画像パスが指定されていません"
            }
        
        # 存在する画像のみをフィルタ
        valid_image_paths = [path for path in image_paths if os.path.exists(path)]
        if not valid_image_paths:
            return {
                "success": False,
                "error": "有効な画像ファイルが見つかりません"
            }
        
        try:
            # 画像をAPI用に準備
            images = self._prepare_images_for_api(valid_image_paths)
            if not images:
                return {
                    "success": False,
                    "error": "画像の準備に失敗しました"
                }
            
            # プロンプト構築
            system_prompt = prompts.get('system_prompt', '')
            user_prompt = prompts.get('user_prompt', '')
            full_prompt = system_prompt + "\n\n" + user_prompt

            # Vertex AI API呼び出し
            api_result = await self._call_vertex_ai_api(images, full_prompt)
            
            if not api_result["success"]:
                # リトライ処理
                if retry_count < self.max_retries:
                    logger.warning(f"OCR処理失敗、リトライ {retry_count + 1}/{self.max_retries}")
                    await asyncio.sleep(2 ** retry_count)  # 指数バックオフ
                    return await self.extract_text_from_images(
                        image_paths, prompts, retry_count + 1
                    )
                else:
                    return api_result
            
            # OCR結果を解析
            ocr_result = self._parse_ocr_response(api_result["response_text"])
            
            # メタデータ追加
            ocr_result["api_info"] = {
                "model": self.model,
                "image_count": len(valid_image_paths),
                "image_paths": valid_image_paths
            }
            
            logger.debug(f"OCR完了: {len(valid_image_paths)}画像 -> テキスト抽出")
            return ocr_result
            
        except Exception as e:
            logger.error(f"OCR処理エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "image_paths": image_paths
            }
    
    async def extract_text_from_single_group(self, group_data: Dict, 
                                           prompts: Dict) -> Dict:
        """
        単一画像グループからテキストを抽出
        
        Args:
            group_data: 画像グループデータ（OCRグループ）
            prompts: プロンプト設定
            
        Returns:
            Dict: OCR結果
        """
        # 画像パスを抽出（元画像 + 分割画像の順序）
        images = group_data.get("images", [])
        
        # 元画像を最初に、分割画像を順序通りに配列
        original_images = [img for img in images if img.get("image_type") == "original"]
        split_images = [img for img in images if img.get("image_type") == "split"]
        
        # 分割画像を分割インデックス順にソート
        split_images.sort(key=lambda x: x.get("split_index", 0))
        
        # 画像パスリストを構築
        image_paths = []
        if original_images:
            image_paths.append(original_images[0]["image_path"])
        image_paths.extend([img["image_path"] for img in split_images])
        
        # OCR実行
        ocr_result = await self.extract_text_from_images(image_paths, prompts)
        
        # グループ情報を追加
        if ocr_result["success"]:
            ocr_result["group_info"] = {
                "page_number": group_data.get("page_number"),
                "source_mask_index": group_data.get("source_mask_index"),
                "source_dewarped_image": group_data.get("source_dewarped_image"),
                "total_images_processed": len(image_paths)
            }
        
        return ocr_result