"""
Step6-02: テキスト結果管理
OCR結果のテキスト保存・管理・統計処理
"""

import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class TextResultManager:
    """テキスト結果管理クラス"""
    
    def __init__(self, config: Dict = None):
        """
        Args:
            config: テキスト結果管理設定
                - output_format: 出力形式（txt/json/both、デフォルト: both）
                - encoding: テキストエンコーディング（デフォルト: utf-8）
                - include_metadata: メタデータ含める（デフォルト: True）
        """
        self.config = config.get('text_result_manager', {}) if config else {}
        self.output_format = self.config.get('output_format', 'both')
        self.encoding = self.config.get('encoding', 'utf-8')
        self.include_metadata = self.config.get('include_metadata', True)
        
        logger.debug("TextResultManager初期化完了")
    
    def _create_output_filename(self, base_name: str, file_type: str) -> str:
        """
        出力ファイル名を作成
        
        Args:
            base_name: ベース名（page_001_mask1など）
            file_type: ファイルタイプ（txt/json）
            
        Returns:
            str: ファイル名
        """
        return f"{base_name}_ocr_result.{file_type}"
    
    def _prepare_text_content(self, ocr_result: Dict) -> str:
        """
        テキストファイル用のコンテンツを準備（純粋なOCRテキストのみ）
        
        Args:
            ocr_result: OCR結果
            
        Returns:
            str: テキストコンテンツ（抽出テキストのみ）
        """
        # OCR結果テキストのみを返す
        ocr_data = ocr_result.get("ocr_result", {})
        extracted_text = ocr_data.get("extracted_text", "")
        
        return extracted_text.strip() if extracted_text else ""
    
    def _prepare_json_content(self, ocr_result: Dict, additional_metadata: Dict = None) -> Dict:
        """
        JSONファイル用のコンテンツを準備
        
        Args:
            ocr_result: OCR結果
            additional_metadata: 追加メタデータ
            
        Returns:
            Dict: JSONコンテンツ
        """
        # ベースのOCR結果をコピー
        json_content = {
            "success": ocr_result.get("success", False),
            "ocr_result": ocr_result.get("ocr_result", {}),
            "extraction_timestamp": datetime.now().isoformat()
        }
        
        # メタデータを含める場合
        if self.include_metadata:
            json_content["api_info"] = ocr_result.get("api_info", {})
            json_content["group_info"] = ocr_result.get("group_info", {})
            
            if ocr_result.get("parse_warning"):
                json_content["warnings"] = [ocr_result["parse_warning"]]
            elif ocr_result.get("parse_note"):
                json_content["processing_notes"] = [ocr_result["parse_note"]]
            
            if ocr_result.get("raw_response"):
                json_content["raw_response"] = ocr_result["raw_response"]
        
        # 追加メタデータをマージ
        if additional_metadata:
            json_content.update(additional_metadata)
        
        return json_content
    
    def save_ocr_result(self, ocr_result: Dict, output_dir: str, 
                       base_name: str, additional_metadata: Dict = None) -> Dict:
        """
        OCR結果をファイルに保存
        
        Args:
            ocr_result: OCR結果
            output_dir: 出力ディレクトリ
            base_name: ベース名（page_001_mask1など）
            additional_metadata: 追加メタデータ
            
        Returns:
            Dict: 保存結果
                - success: bool
                - saved_files: List[str] (保存されたファイルパス)
                - errors: List[str] (エラーリスト)
        """
        try:
            # 出力ディレクトリ作成
            os.makedirs(output_dir, exist_ok=True)
            
            saved_files = []
            errors = []
            
            # テキストファイル保存
            if self.output_format in ['txt', 'both']:
                try:
                    txt_filename = self._create_output_filename(base_name, 'txt')
                    txt_path = os.path.join(output_dir, txt_filename)

                    text_content = self._prepare_text_content(ocr_result)

                    # 空のテキストの場合は警告
                    if not text_content:
                        logger.warning(f"⚠️ 空のOCRテキスト: {base_name}")

                    with open(txt_path, 'w', encoding=self.encoding) as f:
                        f.write(text_content)

                    saved_files.append(txt_path)
                    logger.info(f"✅ テキストファイル保存: {txt_path} ({len(text_content)}文字)")

                except Exception as e:
                    error_msg = f"テキストファイル保存エラー: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # JSONファイル保存
            if self.output_format in ['json', 'both']:
                try:
                    json_filename = self._create_output_filename(base_name, 'json')
                    json_path = os.path.join(output_dir, json_filename)
                    
                    json_content = self._prepare_json_content(ocr_result, additional_metadata)
                    
                    with open(json_path, 'w', encoding=self.encoding) as f:
                        json.dump(json_content, f, ensure_ascii=False, indent=2)
                    
                    saved_files.append(json_path)
                    logger.debug(f"JSONファイル保存: {json_path}")
                    
                except Exception as e:
                    error_msg = f"JSONファイル保存エラー: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return {
                "success": len(saved_files) > 0,
                "saved_files": saved_files,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"OCR結果保存エラー ({base_name}): {e}")
            return {
                "success": False,
                "saved_files": [],
                "errors": [str(e)]
            }
    
    def create_group_summary(self, group_results: List[Dict]) -> Dict:
        """
        グループ結果のサマリーを作成
        
        Args:
            group_results: グループOCR結果のリスト
            
        Returns:
            Dict: サマリー情報
        """
        successful_results = [r for r in group_results if r.get("success")]
        failed_results = [r for r in group_results if not r.get("success")]
        
        total_text_length = 0
        total_images_processed = 0
        
        for result in successful_results:
            ocr_data = result.get("ocr_result", {})
            extracted_text = ocr_data.get("extracted_text", "")
            total_text_length += len(extracted_text)
            
            group_info = result.get("group_info", {})
            total_images_processed += group_info.get("total_images_processed", 0)
        
        return {
            "total_groups": len(group_results),
            "successful_groups": len(successful_results),
            "failed_groups": len(failed_results),
            "total_text_length": total_text_length,
            "total_images_processed": total_images_processed,
            "average_text_length": total_text_length / len(successful_results) if successful_results else 0
        }
    
    def save_processing_summary(self, summary_data: Dict, output_dir: str, 
                              session_id: str) -> Dict:
        """
        処理サマリーを保存
        
        Args:
            summary_data: サマリーデータ
            output_dir: 出力ディレクトリ
            session_id: セッションID
            
        Returns:
            Dict: 保存結果
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            summary_filename = f"ocr_processing_summary_{session_id}.json"
            summary_path = os.path.join(output_dir, summary_filename)
            
            # タイムスタンプを追加
            summary_data["generation_timestamp"] = datetime.now().isoformat()
            summary_data["session_id"] = session_id
            
            with open(summary_path, 'w', encoding=self.encoding) as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"処理サマリー保存: {summary_path}")
            
            return {
                "success": True,
                "summary_path": summary_path
            }
            
        except Exception as e:
            logger.error(f"処理サマリー保存エラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_extracted_text_from_file(self, file_path: str) -> Optional[str]:
        """
        保存されたファイルからテキストを読み込み
        
        Args:
            file_path: ファイルパス（.txt または .json）
            
        Returns:
            Optional[str]: 抽出されたテキスト
        """
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.txt':
                with open(file_path, 'r', encoding=self.encoding) as f:
                    content = f.read()
                    
                # メタデータヘッダーを除去してテキスト部分のみ抽出
                if self.include_metadata:
                    lines = content.split('\n')
                    # "---"行を探してそれ以降をテキストとする
                    text_start_idx = 0
                    for i, line in enumerate(lines):
                        if line.startswith('-' * 10):
                            text_start_idx = i + 1
                            break
                    
                    # 空行をスキップ
                    while text_start_idx < len(lines) and not lines[text_start_idx].strip():
                        text_start_idx += 1
                    
                    return '\n'.join(lines[text_start_idx:]).strip()
                else:
                    return content.strip()
                    
            elif file_ext == '.json':
                with open(file_path, 'r', encoding=self.encoding) as f:
                    data = json.load(f)
                    
                ocr_result = data.get("ocr_result", {})
                return ocr_result.get("extracted_text", "")
                
            else:
                logger.warning(f"サポートされていないファイル形式: {file_ext}")
                return None
                
        except Exception as e:
            logger.error(f"ファイル読み込みエラー ({file_path}): {e}")
            return None