"""
Step7-03: Step7統合プロセッサー
GeminiとDocument AIの結果統合・最終出力処理
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

import importlib

# importlibを使って数字プレフィックス付きモジュールを読み込み
_text_integration_engine_module = importlib.import_module('src.modules.step7.01_text_integration_engine')
_result_output_manager_module = importlib.import_module('src.modules.step7.02_result_output_manager')

TextIntegrationEngine = _text_integration_engine_module.TextIntegrationEngine
ResultOutputManager = _result_output_manager_module.ResultOutputManager

logger = logging.getLogger(__name__)


class Step7Processor:
    """Step7統合プロセッサー"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Step7設定
        """
        self.config = config
        self.step7_config = config.get('step7', {})
        
        # コンポーネント初期化
        self.integration_engine = TextIntegrationEngine(config)
        self.output_manager = ResultOutputManager(config)
        
        logger.debug("Step7プロセッサー初期化完了")
    
    def process_step6_results(self, step6_results: Dict, session_dirs: Dict) -> Dict:
        """
        Step6の結果を受け取って統合処理を実行
        
        Args:
            step6_results: Step6からの処理結果
            session_dirs: セッションディレクトリ情報
            
        Returns:
            Dict: Step7処理結果
        """
        logger.info("--- Step7: 結果統合・最終出力 開始 ---")
        
        try:
            # OCR結果ディレクトリを取得
            ocr_results_dir = session_dirs.get("ocr_results")
            document_ai_results_dir = session_dirs.get("document_ai_results")

            logger.info(f"🔍 DEBUG: Step7が探すディレクトリ")
            logger.info(f"🔍 DEBUG: ocr_results_dir: {ocr_results_dir}")
            logger.info(f"🔍 DEBUG: document_ai_results_dir: {document_ai_results_dir}")
            logger.info(f"🔍 DEBUG: session_dirs keys: {list(session_dirs.keys())}")

            if not ocr_results_dir or not os.path.exists(ocr_results_dir):
                logger.error(f"OCR結果ディレクトリが見つかりません: {ocr_results_dir}")
                return self._create_error_result("OCR結果ディレクトリが見つかりません")
            
            if not document_ai_results_dir or not os.path.exists(document_ai_results_dir):
                logger.error(f"Document AI結果ディレクトリが見つかりません: {document_ai_results_dir}")
                return self._create_error_result("Document AI結果ディレクトリが見つかりません")
            
            # Step7-01: Geminiテキスト収集
            logger.info("Step7-01: Geminiテキスト収集")
            gemini_collection_result = self.integration_engine.collect_gemini_texts(ocr_results_dir)
            
            if not gemini_collection_result["success"]:
                logger.error(f"Geminiテキスト収集失敗: {gemini_collection_result.get('error', 'unknown error')}")
            else:
                logger.info(f"Step7-01: 完了!! (Gemini: {gemini_collection_result['total_files']}ファイル・{gemini_collection_result['total_characters']}文字)")
            
            # Step7-01: Document AIテキスト収集
            logger.info("Step7-01: Document AIテキスト収集")
            document_ai_collection_result = self.integration_engine.collect_document_ai_texts(document_ai_results_dir)
            
            if not document_ai_collection_result["success"]:
                logger.error(f"Document AIテキスト収集失敗: {document_ai_collection_result.get('error', 'unknown error')}")
            else:
                logger.info(f"Step7-01: 完了!! (Document AI: {document_ai_collection_result['total_files']}ファイル・{document_ai_collection_result['total_characters']}文字)")
            
            # 収集結果確認
            if not gemini_collection_result["success"] and not document_ai_collection_result["success"]:
                logger.error("GeminiとDocument AI両方のテキスト収集に失敗")
                return self._create_error_result("テキスト収集に失敗しました")
            
            # Step7-02: テキスト統合
            logger.info("Step7-02: テキスト統合")
            integration_result = self.integration_engine.integrate_texts(
                gemini_collection_result, document_ai_collection_result
            )
            
            if not integration_result["success"]:
                logger.error(f"テキスト統合失敗: {integration_result.get('error', 'unknown error')}")
                return self._create_error_result(f"テキスト統合エラー: {integration_result.get('error')}")
            
            logger.info(f"Step7-02: 完了!! (統合: Gemini={integration_result['gemini_total_characters']}文字, Document AI={integration_result['document_ai_total_characters']}文字)")
            
            # Step7-03: 結果出力
            logger.info("Step7-03: 結果出力")
            session_id = session_dirs.get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
            
            save_result = self.output_manager.save_integrated_results(
                integration_result, session_dirs, session_id
            )
            
            if not save_result["success"]:
                logger.error(f"結果出力失敗: {save_result.get('errors', [])}")
                return self._create_error_result(f"結果出力エラー: {save_result.get('errors')}")
            
            logger.info(f"Step7-03: 完了!! (出力: {save_result['total_files']}ファイル)")
            
            # 統合サマリー作成
            summary = self.output_manager.create_integration_summary(integration_result, save_result)
            
            logger.info(f"--- Step7: 完了!! Gemini={summary['gemini_files_processed']}ファイル・{summary['gemini_total_characters']}文字, Document AI={summary['document_ai_files_processed']}ファイル・{summary['document_ai_total_characters']}文字 → result/{save_result['total_files']}ファイル出力 ---")
            
            return {
                "step7_results": {
                    "integration_result": integration_result,
                    "save_result": save_result,
                    "summary": summary
                },
                "statistics": {
                    "gemini_files_processed": summary["gemini_files_processed"],
                    "document_ai_files_processed": summary["document_ai_files_processed"],
                    "gemini_total_characters": summary["gemini_total_characters"],
                    "document_ai_total_characters": summary["document_ai_total_characters"],
                    "output_files_created": summary["output_files_created"],
                    "total_errors": summary["total_errors"]
                },
                "output_files": save_result.get("saved_files", [])
            }
            
        except Exception as e:
            logger.error(f"Step7処理エラー: {e}")
            import traceback
            traceback.print_exc()
            return self._create_error_result(f"Step7処理エラー: {e}")
    
    def _create_error_result(self, error_message: str) -> Dict:
        """
        エラー結果を作成
        
        Args:
            error_message: エラーメッセージ
            
        Returns:
            Dict: エラー結果
        """
        return {
            "step7_results": {
                "integration_result": {"success": False, "error": error_message},
                "save_result": {"success": False, "error": error_message},
                "summary": {
                    "integration_success": False,
                    "save_success": False,
                    "gemini_files_processed": 0,
                    "document_ai_files_processed": 0,
                    "gemini_total_characters": 0,
                    "document_ai_total_characters": 0,
                    "output_files_created": 0,
                    "total_errors": 1
                }
            },
            "statistics": {
                "gemini_files_processed": 0,
                "document_ai_files_processed": 0,
                "gemini_total_characters": 0,
                "document_ai_total_characters": 0,
                "output_files_created": 0,
                "total_errors": 1
            },
            "output_files": [],
            "error": error_message
        }
    
    def get_integration_status(self, step7_results: Dict) -> Dict:
        """
        統合ステータスを取得
        
        Args:
            step7_results: Step7処理結果
            
        Returns:
            Dict: ステータス情報
        """
        statistics = step7_results.get("statistics", {})
        summary = step7_results.get("step7_results", {}).get("summary", {})
        
        return {
            "integration_success": summary.get("integration_success", False),
            "save_success": summary.get("save_success", False),
            "gemini_files_processed": statistics.get("gemini_files_processed", 0),
            "document_ai_files_processed": statistics.get("document_ai_files_processed", 0),
            "total_characters_integrated": statistics.get("gemini_total_characters", 0) + statistics.get("document_ai_total_characters", 0),
            "output_files_created": statistics.get("output_files_created", 0),
            "success_rate": 100.0 if summary.get("integration_success") and summary.get("save_success") else 0.0
        }