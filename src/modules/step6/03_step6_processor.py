"""
Step6-03: Step6統合プロセッサー
Gemini OCR処理の統合管理
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

import importlib

# importlibを使って数字プレフィックス付きモジュールを読み込み
_gemini_ocr_engine_module = importlib.import_module('src.modules.step6.01_gemini_ocr_engine')
_text_result_manager_module = importlib.import_module('src.modules.step6.02_text_result_manager')
_document_ai_ocr_engine_module = importlib.import_module('src.modules.step6.04_document_ai_ocr_engine')
_document_ai_result_manager_module = importlib.import_module('src.modules.step6.05_document_ai_result_manager')

GeminiOCREngine = _gemini_ocr_engine_module.GeminiOCREngine
TextResultManager = _text_result_manager_module.TextResultManager
DocumentAIOCREngine = _document_ai_ocr_engine_module.DocumentAIOCREngine
DocumentAIResultManager = _document_ai_result_manager_module.DocumentAIResultManager

logger = logging.getLogger(__name__)


class Step6Processor:
    """Step6統合プロセッサー"""
    def __init__(self, config: Dict, prompts: Dict):
        """
        Args:
            config: Step6設定
            prompts: プロンプト設定
        """
        self.config = config
        self.prompts = prompts
        # OCRプロンプト取得
        self.ocr_prompts = prompts.get('multi_image_ocr', {})
        if not self.ocr_prompts:
            # フォールバック：単一プロンプト
            self.ocr_prompts = prompts.get('ocr_extraction', {})
        # コンポーネント初期化
        self.ocr_engine = GeminiOCREngine(config)
        self.text_manager = TextResultManager(config)
        self.document_ai_engine = DocumentAIOCREngine(config)
        self.document_ai_manager = DocumentAIResultManager(config)
        # 並列処理設定
        self.max_concurrent_ocr = config.get('step6', {}).get('max_concurrent_ocr', 3)
        logger.debug("Step6プロセッサー初期化完了")
    
    async def process_single_group_gemini(self, group_key: str, group_data: Dict,
                                          session_dirs: Dict, group_index: int,
                                          total_groups: int) -> Dict:
        """
        単一グループのGemini OCR処理
        Args:
            group_key: グループキー（page_001_mask1など）
            group_data: グループデータ
            session_dirs: セッションディレクトリ情報
            group_index: グループインデックス（1から開始）
            total_groups: 総グループ数

        Returns:
            Dict: Gemini OCR処理結果
        """
        logger.info(
            f"Step6-01: OCR処理 ({group_index}/{total_groups}) {group_key}")

        try:
            # グループからOCRを実行
            ocr_result = await self.ocr_engine.extract_text_from_single_group(
                group_data, self.ocr_prompts
            )

            if not ocr_result.get("success"):
                logger.warning(
                    f"OCR処理失敗: {group_key} - {ocr_result.get('error', 'unknown error')}")
                return {
                    "group_key": group_key,
                    "success": False,
                    "error": ocr_result.get('error', 'OCR処理失敗'),
                    "ocr_result": None,
                    "saved_files": []
                }

            # テキスト結果を保存
            ocr_output_dir = session_dirs.get(
                "ocr_results", session_dirs["final_results"])

            # 追加メタデータ
            additional_metadata = {
                "group_key": group_key,
                "processing_timestamp": datetime.now().isoformat(),
                "session_id": session_dirs.get("session_id", "unknown")
            }

            save_result = self.text_manager.save_ocr_result(
                ocr_result, ocr_output_dir, group_key, additional_metadata
            )

            if save_result["success"]:
                logger.info(f"Step6-01: 完了!! ({group_key}: テキスト保存完了)")
            else:
                logger.warning(
                    f"Step6-01: テキスト保存で一部エラー ({group_key}): {save_result['errors']}")

            return {
                "group_key": group_key,
                "success": True,
                "ocr_result": ocr_result,
                "saved_files": save_result["saved_files"],
                "save_errors": save_result.get("errors", [])
            }

        except Exception as e:
            logger.error(f"グループ処理エラー ({group_key}): {e}")
            return {
                "group_key": group_key,
                "success": False,
                "error": str(e),
                "ocr_result": None,
                "saved_files": []
            }

    async def process_single_group_document_ai(self, group_key: str, group_data: Dict,
                                               session_dirs: Dict, group_index: int,
                                               total_groups: int) -> Dict:
        """
        単一グループのDocument AI OCR処理

        Args:
            group_key: グループキー（page_001_mask1など）
            group_data: グループデータ
            session_dirs: セッションディレクトリ情報
            group_index: グループインデックス（1から開始）
            total_groups: 総グループ数

        Returns:
            Dict: Document AI OCR処理結果
        """
        logger.info(
            f"Step6-04: Document AI OCR処理 ({group_index}/{total_groups}) {group_key}")

        try:
            # Document AI OCR実行
            doc_ai_result = await self.document_ai_engine.process_group_images(group_data)

            if not doc_ai_result.get("success"):
                logger.warning(
                    f"Document AI OCR処理失敗: {group_key} - {doc_ai_result.get('error', 'unknown error')}")
                return {
                    "group_key": group_key,
                    "success": False,
                    "error": doc_ai_result.get('error', 'Document AI OCR処理失敗'),
                    "doc_ai_result": None,
                    "saved_files": []
                }

            # Document AI結果を保存
            doc_ai_output_dir = session_dirs.get(
                "document_ai_results", session_dirs["final_results"])

            # 追加メタデータ
            additional_metadata = {
                "group_key": group_key,
                "processing_timestamp": datetime.now().isoformat(),
                "session_id": session_dirs.get("session_id", "unknown")
            }

            save_result = self.document_ai_manager.save_document_ai_result(
                doc_ai_result, doc_ai_output_dir, group_key, additional_metadata
            )

            if save_result["success"]:
                logger.info(
                    f"Step6-04: 完了!! ({group_key}: Document AIテキスト保存完了)")
            else:
                logger.warning(
                    f"Step6-04: Document AIテキスト保存で一部エラー ({group_key}): {save_result['errors']}")

            return {
                "group_key": group_key,
                "success": True,
                "doc_ai_result": doc_ai_result,
                "saved_files": save_result["saved_files"],
                "save_errors": save_result.get("errors", [])
            }

        except Exception as e:
            logger.error(f"Document AIグループ処理エラー ({group_key}): {e}")
            return {
                "group_key": group_key,
                "success": False,
                "error": str(e),
                "doc_ai_result": None,
                "saved_files": []
            }

    async def process_ocr_groups(self, ocr_groups: Dict, session_dirs: Dict) -> Dict:
        """
        全OCRグループを並列処理

        Args:
            ocr_groups: Step5からのOCRグループ情報
            session_dirs: セッションディレクトリ情報

        Returns:
            Dict: Step6処理結果
        """
        logger.info("--- Step6: Gemini OCR処理 開始 ---")

        groups = ocr_groups.get("groups", {})
        if not groups:
            logger.warning("処理対象のOCRグループがありません")
            return {
                "step6_results": {
                    "ocr_results": [],
                    "failed_results": [],
                    "processing_summary": {}
                },
                "statistics": {
                    "total_groups_processed": 0,
                    "total_groups_failed": 0,
                    "total_text_files_created": 0
                }
            }

        logger.info(
            f"Step6処理開始: {len(groups)}グループ対象 (Gemini + Document AI並行処理、最大{self.max_concurrent_ocr}並列)")

        # Document AIディレクトリの作成
        if "document_ai_results" not in session_dirs:
            # final_results/{session_id}/document_ai_results の形式で作成
            final_results_dir = session_dirs.get("final_results", "")
            session_id = session_dirs.get("session_id", "")
            if final_results_dir and session_id:
                base_dir = os.path.join(final_results_dir, session_id)
                session_dirs["document_ai_results"] = os.path.join(
                    base_dir, "document_ai_results")
            elif final_results_dir:
                session_dirs["document_ai_results"] = os.path.join(
                    final_results_dir, "document_ai_results")
            else:
                logger.warning(
                    "Document AIディレクトリの作成に失敗しました。final_resultsディレクトリを使用します")
                session_dirs["document_ai_results"] = session_dirs.get(
                    "final_results", "")

        # 並列処理でGeminiとDocument AI OCRを実行
        # セマフォで同時実行数を制限
        semaphore = asyncio.Semaphore(self.max_concurrent_ocr)

        async def process_group_with_both_engines(item):
            group_key, group_data = item
            group_index = list(groups.keys()).index(group_key) + 1

            async with semaphore:
                # GeminiとDocument AIを並行実行
                gemini_task = self.process_single_group_gemini(
                    group_key, group_data, session_dirs, group_index, len(
                        groups)
                )
                document_ai_task = self.process_single_group_document_ai(
                    group_key, group_data, session_dirs, group_index, len(
                        groups)
                )

                # 両方の処理を並行実行
                gemini_result, document_ai_result = await asyncio.gather(
                    gemini_task, document_ai_task, return_exceptions=True
                )

                return {
                    "group_key": group_key,
                    "gemini_result": gemini_result,
                    "document_ai_result": document_ai_result
                }

        # 全グループを並列処理
        tasks = [process_group_with_both_engines(
            item) for item in groups.items()]
        combined_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 結果の整理
        gemini_successful_results = []
        gemini_failed_results = []
        document_ai_successful_results = []
        document_ai_failed_results = []
        total_gemini_files = []
        total_document_ai_files = []

        for i, combined_result in enumerate(combined_results):
            if isinstance(combined_result, Exception):
                group_key = list(groups.keys())[i]
                logger.error(f"グループ{group_key}: 並列処理でエラー - {combined_result}")
                gemini_failed_results.append(
                    {"group_key": group_key, "error": str(combined_result)})
                document_ai_failed_results.append(
                    {"group_key": group_key, "error": str(combined_result)})
                continue

            group_key = combined_result.get("group_key")
            gemini_result = combined_result.get("gemini_result")
            document_ai_result = combined_result.get("document_ai_result")

            # Gemini結果の処理
            if isinstance(gemini_result, Exception):
                logger.error(
                    f"グループ{group_key}: Gemini処理でエラー - {gemini_result}")
                gemini_failed_results.append(
                    {"group_key": group_key, "error": str(gemini_result)})
            elif gemini_result and gemini_result.get("success"):
                gemini_successful_results.append(gemini_result)
                total_gemini_files.extend(gemini_result.get("saved_files", []))
            else:
                gemini_failed_results.append(
                    gemini_result or {"group_key": group_key, "error": "Gemini処理失敗"})

            # Document AI結果の処理
            if isinstance(document_ai_result, Exception):
                logger.error(
                    f"グループ{group_key}: Document AI処理でエラー - {document_ai_result}")
                document_ai_failed_results.append(
                    {"group_key": group_key, "error": str(document_ai_result)})
            elif document_ai_result and document_ai_result.get("success"):
                document_ai_successful_results.append(document_ai_result)
                total_document_ai_files.extend(
                    document_ai_result.get("saved_files", []))
            else:
                document_ai_failed_results.append(
                    document_ai_result or {"group_key": group_key, "error": "Document AI処理失敗"})

        # Gemini OCR結果のサマリー作成
        gemini_ocr_summary_data = []
        for result in gemini_successful_results:
            if result.get("ocr_result"):
                gemini_ocr_summary_data.append(result["ocr_result"])

        gemini_processing_summary = self.text_manager.create_group_summary(
            gemini_ocr_summary_data)

        # Document AI結果のサマリー作成
        document_ai_summary_data = []
        for result in document_ai_successful_results:
            if result.get("doc_ai_result"):
                document_ai_summary_data.append(result["doc_ai_result"])

        document_ai_processing_summary = self.document_ai_manager.create_processing_summary(
            document_ai_summary_data)

        # 処理サマリーを保存
        session_id = session_dirs.get(
            "session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))

        # Geminiサマリーを保存
        gemini_summary_data = {
            "processing_summary": gemini_processing_summary,
            "successful_groups": len(gemini_successful_results),
            "failed_groups": len(gemini_failed_results),
            "total_text_files": len(total_gemini_files),
            "failed_results": gemini_failed_results
        }

        ocr_output_dir = session_dirs.get(
            "ocr_results", session_dirs["final_results"])
        gemini_summary_save_result = self.text_manager.save_processing_summary(
            gemini_summary_data, ocr_output_dir, session_id
        )

        # Document AIサマリーを保存
        document_ai_summary_data = {
            "processing_summary": document_ai_processing_summary,
            "successful_groups": len(document_ai_successful_results),
            "failed_groups": len(document_ai_failed_results),
            "total_text_files": len(total_document_ai_files),
            "failed_results": document_ai_failed_results
        }

        doc_ai_output_dir = session_dirs.get(
            "document_ai_results", session_dirs["final_results"])
        document_ai_summary_save_result = self.document_ai_manager.save_processing_summary(
            document_ai_summary_data, doc_ai_output_dir, session_id
        )

        logger.info(f"Step6-02: 結果整理完了")

        # 統計情報
        gemini_successful_groups = len(gemini_successful_results)
        document_ai_successful_groups = len(document_ai_successful_results)
        total_gemini_text_files = len(total_gemini_files)
        total_document_ai_text_files = len(total_document_ai_files)

        logger.info(
            f"--- Step6: 完了!! Gemini={gemini_successful_groups}グループ・{total_gemini_text_files}ファイル, Document AI={document_ai_successful_groups}グループ・{total_document_ai_text_files}ファイル ---")

        return {
            "step6_results": {
                "gemini_results": {
                    "ocr_results": gemini_successful_results,
                    "failed_results": gemini_failed_results,
                    "processing_summary": gemini_processing_summary,
                    "summary_file": gemini_summary_save_result.get("summary_path")
                },
                "document_ai_results": {
                    "ocr_results": document_ai_successful_results,
                    "failed_results": document_ai_failed_results,
                    "processing_summary": document_ai_processing_summary,
                    "summary_file": document_ai_summary_save_result.get("summary_path")
                }
            },
            "statistics": {
                "gemini": {
                    "total_groups_processed": gemini_successful_groups,
                    "total_groups_failed": len(gemini_failed_results),
                    "total_text_files_created": total_gemini_text_files,
                    "average_text_length": gemini_processing_summary.get("average_text_length", 0)
                },
                "document_ai": {
                    "total_groups_processed": document_ai_successful_groups,
                    "total_groups_failed": len(document_ai_failed_results),
                    "total_text_files_created": total_document_ai_text_files,
                    "success_rate": document_ai_processing_summary.get("success_rate", 0)
                },
                "combined": {
                    "total_groups": len(groups),
                    "total_files_created": total_gemini_text_files + total_document_ai_text_files
                }
            },
            # 次のステップ用データ
            "text_extraction_results": {
                "gemini": gemini_successful_results,
                "document_ai": document_ai_successful_results
            },
            "text_files": {
                "gemini": total_gemini_files,
                "document_ai": total_document_ai_files
            }
        }

    async def process_step5_results(self, step5_results: Dict, session_dirs: Dict) -> Dict:
        """
        Step5の結果を受け取ってOCR処理を実行

        Args:
            step5_results: Step5からの処理結果
            session_dirs: セッションディレクトリ情報

        Returns:
            Dict: Step6処理結果
        """
        # OCRグループを取得
        ocr_groups = step5_results.get("ocr_processing_groups", {})

        # OCRディレクトリを作成
        if "ocr_results" not in session_dirs:
            # final_results/{session_id}/ocr_results の形式で作成
            final_results_dir = session_dirs.get("final_results", "")
            session_id = session_dirs.get("session_id", "")
            if final_results_dir and session_id:
                base_dir = os.path.join(final_results_dir, session_id)
                session_dirs["ocr_results"] = os.path.join(
                    base_dir, "ocr_results")
            elif final_results_dir:
                session_dirs["ocr_results"] = os.path.join(
                    final_results_dir, "ocr_results")
            else:
                logger.warning("OCRディレクトリの作成に失敗しました。final_resultsディレクトリを使用します")
                session_dirs["ocr_results"] = session_dirs.get(
                    "final_results", "")

        # OCR処理実行
        return await self.process_ocr_groups(ocr_groups, session_dirs)

    def get_text_extraction_status(self, step6_results: Dict) -> Dict:
        """
        テキスト抽出ステータスを取得

        Args:
            step6_results: Step6処理結果

        Returns:
            Dict: ステータス情報
        """
        statistics = step6_results.get("statistics", {})
        processing_summary = step6_results.get(
            "step6_results", {}).get("processing_summary", {})

        return {
            "total_groups": statistics.get("total_groups_processed", 0) + statistics.get("total_groups_failed", 0),
            "successful_groups": statistics.get("total_groups_processed", 0),
            "failed_groups": statistics.get("total_groups_failed", 0),
            "total_text_files": statistics.get("total_text_files_created", 0),
            "total_text_length": processing_summary.get("total_text_length", 0),
            "average_text_length": processing_summary.get("average_text_length", 0),
            "success_rate": (
                statistics.get("total_groups_processed", 0) /
                max(1, statistics.get("total_groups_processed", 0) +
                    statistics.get("total_groups_failed", 0))
            ) * 100
        }
