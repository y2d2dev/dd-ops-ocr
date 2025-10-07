"""
Step7-01: テキスト統合エンジン
GeminiとDocument AIのOCR結果を統合
"""

import os
import glob
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TextIntegrationEngine:
    """テキスト統合エンジン"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Step7設定
        """
        self.config = config
        self.step7_config = config.get('step7', {})
        
        # デフォルト設定
        self.encoding = self.step7_config.get('encoding', 'utf-8')
        self.include_separators = self.step7_config.get('include_separators', True)
        self.sort_by_filename = self.step7_config.get('sort_by_filename', True)
        
        logger.debug("テキスト統合エンジン初期化完了")
    
    def collect_gemini_texts(self, ocr_results_dir: str) -> Dict:
        """
        Gemini OCR結果のテキストファイルを収集
        
        Args:
            ocr_results_dir: OCR結果ディレクトリ
            
        Returns:
            Dict: 収集結果
        """
        logger.debug(f"Gemini OCRテキスト収集開始: {ocr_results_dir}")
        
        try:
            # OCR結果テキストファイルを検索
            txt_pattern = os.path.join(ocr_results_dir, "*_ocr_result.txt")
            logger.info(f"🔍 DEBUG: Gemini検索パターン: {txt_pattern}")
            txt_files = glob.glob(txt_pattern)
            logger.info(f"🔍 DEBUG: Gemini見つかったファイル数: {len(txt_files)}")
            if txt_files:
                logger.info(f"🔍 DEBUG: Gemini最初のファイル: {txt_files[0] if txt_files else 'None'}")
            
            if self.sort_by_filename:
                txt_files.sort()
            
            collected_texts = []
            successful_files = []
            failed_files = []
            
            for txt_file in txt_files:
                try:
                    with open(txt_file, 'r', encoding=self.encoding) as f:
                        content = f.read().strip()
                    
                    if content:
                        filename = os.path.basename(txt_file)
                        collected_texts.append({
                            "filename": filename,
                            "filepath": txt_file,
                            "content": content,
                            "length": len(content)
                        })
                        successful_files.append(txt_file)
                        logger.debug(f"Geminiテキスト読み込み成功: {filename} ({len(content)}文字)")
                    else:
                        logger.warning(f"空のテキストファイル: {txt_file}")
                        failed_files.append(txt_file)
                        
                except Exception as e:
                    logger.error(f"Geminiテキスト読み込みエラー ({txt_file}): {e}")
                    failed_files.append(txt_file)
            
            logger.info(f"Gemini OCRテキスト収集完了: 成功={len(successful_files)}, 失敗={len(failed_files)}")

            # ファイルが見つからない場合の詳細なエラーメッセージ
            if len(txt_files) == 0:
                error_msg = f"OCR結果ファイルが見つかりません。検索パターン: {txt_pattern}, ディレクトリ: {ocr_results_dir}"
                logger.error(error_msg)
                # ディレクトリの内容を確認
                if os.path.exists(ocr_results_dir):
                    all_files = os.listdir(ocr_results_dir)
                    logger.error(f"ディレクトリ内のファイル一覧: {all_files[:10]}")  # 最初の10個のみ表示
                else:
                    logger.error(f"ディレクトリが存在しません: {ocr_results_dir}")
                return {
                    "success": False,
                    "error": error_msg,
                    "collected_texts": [],
                    "successful_files": [],
                    "failed_files": [],
                    "total_files": 0,
                    "total_characters": 0
                }

            # ファイルは見つかったが、全て読み込みに失敗した場合
            if len(successful_files) == 0:
                error_msg = f"{len(txt_files)}個のファイルが見つかりましたが、全て読み込みに失敗しました"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "collected_texts": collected_texts,
                    "successful_files": successful_files,
                    "failed_files": failed_files,
                    "total_files": len(txt_files),
                    "total_characters": 0
                }

            return {
                "success": len(successful_files) > 0,
                "collected_texts": collected_texts,
                "successful_files": successful_files,
                "failed_files": failed_files,
                "total_files": len(txt_files),
                "total_characters": sum(t["length"] for t in collected_texts)
            }
            
        except Exception as e:
            logger.error(f"Gemini OCRテキスト収集エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "collected_texts": [],
                "successful_files": [],
                "failed_files": [],
                "total_files": 0,
                "total_characters": 0
            }
    
    def collect_document_ai_texts(self, document_ai_results_dir: str) -> Dict:
        """
        Document AI OCR結果のテキストファイルを収集
        
        Args:
            document_ai_results_dir: Document AI結果ディレクトリ
            
        Returns:
            Dict: 収集結果
        """
        logger.debug(f"Document AI OCRテキスト収集開始: {document_ai_results_dir}")
        
        try:
            # Document AI結果テキストファイルを検索
            txt_pattern = os.path.join(document_ai_results_dir, "*_documentai_result.txt")
            logger.info(f"🔍 DEBUG: Document AI検索パターン: {txt_pattern}")
            txt_files = glob.glob(txt_pattern)
            logger.info(f"🔍 DEBUG: Document AI見つかったファイル数: {len(txt_files)}")
            if txt_files:
                logger.info(f"🔍 DEBUG: Document AI最初のファイル: {txt_files[0] if txt_files else 'None'}")
            
            if self.sort_by_filename:
                txt_files.sort()
            
            collected_texts = []
            successful_files = []
            failed_files = []
            
            for txt_file in txt_files:
                try:
                    with open(txt_file, 'r', encoding=self.encoding) as f:
                        content = f.read().strip()
                    
                    if content:
                        filename = os.path.basename(txt_file)
                        collected_texts.append({
                            "filename": filename,
                            "filepath": txt_file,
                            "content": content,
                            "length": len(content)
                        })
                        successful_files.append(txt_file)
                        logger.debug(f"Document AIテキスト読み込み成功: {filename} ({len(content)}文字)")
                    else:
                        logger.warning(f"空のテキストファイル: {txt_file}")
                        failed_files.append(txt_file)
                        
                except Exception as e:
                    logger.error(f"Document AIテキスト読み込みエラー ({txt_file}): {e}")
                    failed_files.append(txt_file)
            
            logger.info(f"Document AI OCRテキスト収集完了: 成功={len(successful_files)}, 失敗={len(failed_files)}")

            # ファイルが見つからない場合の詳細なエラーメッセージ
            if len(txt_files) == 0:
                error_msg = f"Document AI結果ファイルが見つかりません。検索パターン: {txt_pattern}, ディレクトリ: {document_ai_results_dir}"
                logger.error(error_msg)
                # ディレクトリの内容を確認
                if os.path.exists(document_ai_results_dir):
                    all_files = os.listdir(document_ai_results_dir)
                    logger.error(f"ディレクトリ内のファイル一覧: {all_files[:10]}")  # 最初の10個のみ表示
                else:
                    logger.error(f"ディレクトリが存在しません: {document_ai_results_dir}")
                return {
                    "success": False,
                    "error": error_msg,
                    "collected_texts": [],
                    "successful_files": [],
                    "failed_files": [],
                    "total_files": 0,
                    "total_characters": 0
                }

            # ファイルは見つかったが、全て読み込みに失敗した場合
            if len(successful_files) == 0:
                error_msg = f"{len(txt_files)}個のファイルが見つかりましたが、全て読み込みに失敗しました"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "collected_texts": collected_texts,
                    "successful_files": successful_files,
                    "failed_files": failed_files,
                    "total_files": len(txt_files),
                    "total_characters": 0
                }

            return {
                "success": len(successful_files) > 0,
                "collected_texts": collected_texts,
                "successful_files": successful_files,
                "failed_files": failed_files,
                "total_files": len(txt_files),
                "total_characters": sum(t["length"] for t in collected_texts)
            }
            
        except Exception as e:
            logger.error(f"Document AI OCRテキスト収集エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "collected_texts": [],
                "successful_files": [],
                "failed_files": [],
                "total_files": 0,
                "total_characters": 0
            }
    
    def integrate_texts(self, gemini_result: Dict, document_ai_result: Dict) -> Dict:
        """
        GeminiとDocument AIのテキストを統合
        
        Args:
            gemini_result: Gemini収集結果
            document_ai_result: Document AI収集結果
            
        Returns:
            Dict: 統合結果
        """
        logger.debug("テキスト統合処理開始")
        
        try:
            # Geminiテキストを統合
            gemini_texts = gemini_result.get("collected_texts", [])
            gemini_integrated = self._integrate_text_list(gemini_texts, "Gemini OCR")
            
            # Document AIテキストを統合
            document_ai_texts = document_ai_result.get("collected_texts", [])
            document_ai_integrated = self._integrate_text_list(document_ai_texts, "Document AI OCR")
            
            logger.info(f"テキスト統合完了: Gemini={len(gemini_texts)}ファイル・{len(gemini_integrated)}文字, Document AI={len(document_ai_texts)}ファイル・{len(document_ai_integrated)}文字")
            
            return {
                "success": True,
                "gemini_integrated_text": gemini_integrated,
                "document_ai_integrated_text": document_ai_integrated,
                "gemini_files_count": len(gemini_texts),
                "document_ai_files_count": len(document_ai_texts),
                "gemini_total_characters": len(gemini_integrated),
                "document_ai_total_characters": len(document_ai_integrated)
            }
            
        except Exception as e:
            logger.error(f"テキスト統合エラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "gemini_integrated_text": "",
                "document_ai_integrated_text": "",
                "gemini_files_count": 0,
                "document_ai_files_count": 0,
                "gemini_total_characters": 0,
                "document_ai_total_characters": 0
            }
    
    def _integrate_text_list(self, text_list: List[Dict], engine_name: str) -> str:
        """
        テキストリストを統合
        
        Args:
            text_list: テキストデータのリスト
            engine_name: エンジン名
            
        Returns:
            str: 統合されたテキスト
        """
        if not text_list:
            return ""
        
        integrated_parts = []
        
        for i, text_data in enumerate(text_list):
            content = text_data.get("content", "").strip()
            if content:
                if self.include_separators and i > 0:
                    integrated_parts.append("\n")
                integrated_parts.append(content)
        
        return "\n".join(integrated_parts) if integrated_parts else ""