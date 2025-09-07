"""
Step6-04: Google Document AI OCRエンジン
Google Document AIを使用してOCR処理を実行
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentAIOCREngine:
    """Document AI OCRエンジン"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Document AI設定
                - location: リージョン（デフォルト: us）
                - field_mask: フィールドマスク（デフォルト: text,pages.pageNumber）
                - max_retries: リトライ回数（デフォルト: 3）
                - timeout: タイムアウト秒（デフォルト: 60）
        """
        self.config = config.get('document_ai', {})
        
        # 環境変数からDocument AI設定を読み込み
        self.project_id = os.getenv('DOCUMENT_AI_PROJECT_ID')
        self.location = self.config.get('location', os.getenv('DOCUMENT_AI_LOCATION', 'us'))
        self.processor_id = os.getenv('DOCUMENT_AI_PROCESSOR_ID')
        
        # 処理設定
        self.field_mask = self.config.get('field_mask', 'text,pages.pageNumber')
        self.max_retries = self.config.get('max_retries', 3)
        self.timeout = self.config.get('timeout', 60)
        
        # API設定検証
        if not all([self.project_id, self.processor_id]):
            logger.warning("Document AI環境変数が設定されていません（DOCUMENT_AI_PROJECT_ID, DOCUMENT_AI_PROCESSOR_ID）")
            logger.warning("Document AI処理はスキップされます")
            self.enabled = False
        else:
            self.enabled = True
            logger.debug(f"DocumentAIOCREngine初期化: project={self.project_id}, location={self.location}")
    
    def _is_available(self) -> bool:
        """Document AIが利用可能かチェック"""
        if not self.enabled:
            return False
        
        try:
            from google.cloud import documentai
            from google.api_core.client_options import ClientOptions
            return True
        except ImportError as e:
            logger.warning(f"google-cloud-documentai ライブラリが利用できません: {e}")
            return False
    
    async def _process_single_image(self, image_path: str, retry_count: int = 0) -> Dict:
        """
        単一画像をDocument AIで処理
        
        Args:
            image_path: 画像ファイルパス
            retry_count: リトライ回数
            
        Returns:
            Dict: Document AI処理結果
        """
        if not self._is_available():
            return {
                "success": False,
                "error": "Document AI利用不可",
                "text": "",
                "confidence": 0.0
            }
        
        try:
            from google.cloud import documentai
            from google.api_core.client_options import ClientOptions
            from google.auth import default
            
            # Cloud Runのデフォルト認証を明示的に使用
            credentials, project = default()
            
            # クライアント設定
            opts = ClientOptions(api_endpoint=f"{self.location}-documentai.googleapis.com")
            client = documentai.DocumentProcessorServiceClient(
                client_options=opts,
                credentials=credentials
            )
            
            # プロセッサー名を構築
            name = client.processor_path(self.project_id, self.location, self.processor_id)
            
            # 画像ファイルを読み込み
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "error": f"ファイルが存在しません: {image_path}",
                    "text": "",
                    "confidence": 0.0
                }
            
            with open(image_path, "rb") as image_file:
                image_content = image_file.read()
            
            # MIME typeを判定
            mime_type = "image/jpeg"
            if image_path.lower().endswith('.png'):
                mime_type = "image/png"
            elif image_path.lower().endswith('.pdf'):
                mime_type = "application/pdf"
            
            # Document AI リクエスト構築
            raw_document = documentai.RawDocument(content=image_content, mime_type=mime_type)
            
            request = documentai.ProcessRequest(
                name=name,
                raw_document=raw_document,
                field_mask=self.field_mask,
            )
            
            # 非同期でDocument AI API呼び出し
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.process_document(request=request)
            )
            
            document = result.document
            
            # 信頼度を計算（ページの平均信頼度）
            confidence = 0.0
            if document.pages:
                confidences = []
                for page in document.pages:
                    if hasattr(page, 'tokens') and page.tokens:
                        page_confidences = [token.layout.confidence for token in page.tokens 
                                          if hasattr(token.layout, 'confidence')]
                        if page_confidences:
                            confidences.extend(page_confidences)
                
                if confidences:
                    confidence = sum(confidences) / len(confidences)
            
            logger.debug(f"Document AI処理完了: {image_path} (信頼度: {confidence:.3f})")
            
            return {
                "success": True,
                "text": document.text,
                "confidence": confidence,
                "page_count": len(document.pages) if document.pages else 0,
                "api_info": {
                    "project_id": self.project_id,
                    "location": self.location,
                    "processor_id": self.processor_id
                }
            }
            
        except Exception as e:
            logger.error(f"Document AI処理エラー ({image_path}): {e}")
            
            # リトライ処理
            if retry_count < self.max_retries:
                logger.warning(f"Document AI処理リトライ {retry_count + 1}/{self.max_retries}")
                await asyncio.sleep(2 ** retry_count)  # 指数バックオフ
                return await self._process_single_image(image_path, retry_count + 1)
            
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0.0
            }
    
    async def process_group_images(self, group_data: Dict) -> Dict:
        """
        グループ画像（元画像+分割画像）をDocument AIで処理
        
        Args:
            group_data: 画像グループデータ（OCRグループ）
            
        Returns:
            Dict: Document AI処理結果
        """
        if not self._is_available():
            return {
                "success": False,
                "error": "Document AI利用不可",
                "results": []
            }
        
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
        
        if not image_paths:
            return {
                "success": False,
                "error": "処理対象画像がありません",
                "results": []
            }
        
        try:
            # 各画像を並行処理
            tasks = [self._process_single_image(image_path) for image_path in image_paths]
            image_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 結果を整理
            processed_results = []
            successful_results = 0
            total_confidence = 0.0
            combined_text_parts = []
            
            for i, result in enumerate(image_results):
                if isinstance(result, Exception):
                    logger.error(f"画像処理でエラー: {image_paths[i]} - {result}")
                    processed_results.append({
                        "image_path": image_paths[i],
                        "image_type": "original" if i == 0 else "split",
                        "split_index": 0 if i == 0 else i,
                        "success": False,
                        "error": str(result),
                        "text": "",
                        "confidence": 0.0
                    })
                elif result.get("success"):
                    processed_results.append({
                        "image_path": image_paths[i],
                        "image_type": "original" if i == 0 else "split",
                        "split_index": 0 if i == 0 else i,
                        "success": True,
                        "text": result.get("text", ""),
                        "confidence": result.get("confidence", 0.0),
                        "page_count": result.get("page_count", 0)
                    })
                    successful_results += 1
                    total_confidence += result.get("confidence", 0.0)
                    
                    # テキストを結合用リストに追加
                    text = result.get("text", "").strip()
                    if text:
                        combined_text_parts.append(text)
                else:
                    processed_results.append({
                        "image_path": image_paths[i],
                        "image_type": "original" if i == 0 else "split",
                        "split_index": 0 if i == 0 else i,
                        "success": False,
                        "error": result.get("error", "未知のエラー"),
                        "text": "",
                        "confidence": 0.0
                    })
            
            # 統計情報を計算
            average_confidence = total_confidence / successful_results if successful_results > 0 else 0.0
            combined_text = "\n\n".join(combined_text_parts)
            
            # グループ情報を追加
            group_result = {
                "success": successful_results > 0,
                "processed_images": len(image_paths),
                "successful_images": successful_results,
                "failed_images": len(image_paths) - successful_results,
                "combined_text": combined_text,
                "average_confidence": average_confidence,
                "individual_results": processed_results,
                "group_info": {
                    "page_number": group_data.get("page_number"),
                    "source_mask_index": group_data.get("source_mask_index"),
                    "source_dewarped_image": group_data.get("source_dewarped_image"),
                    "total_images_processed": len(image_paths)
                }
            }
            
            logger.debug(f"Document AI グループ処理完了: {successful_results}/{len(image_paths)}画像成功")
            return group_result
            
        except Exception as e:
            logger.error(f"Document AI グループ処理エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }