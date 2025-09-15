"""
ディレクトリ管理モジュール
作業ディレクトリの設定と管理機能を提供
"""

import os
import logging
from typing import Dict
# from src.utils.file_utils import ensure_directory  # 一旦コメントアウト


def ensure_directory(path: str):
    """ディレクトリが存在しない場合は作成"""
    os.makedirs(path, exist_ok=True)

logger = logging.getLogger(__name__)


class DirectoryManager:
    """作業ディレクトリを管理するクラス"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config (Dict): 設定データ（directoriesセクションを含む）
        """
        self.config = config
        self.dirs = {}
    
    def setup_directories(self) -> Dict[str, str]:
        """
        作業ディレクトリの設定
        
        Returns:
            Dict[str, str]: 設定されたディレクトリのパス
        """
        self.dirs = self.config.get('directories', {})
        
        # 必要なディレクトリを作成
        for dir_key, dir_path in self.dirs.items():
            ensure_directory(dir_path)
            logger.debug(f"ディレクトリ確認: {dir_key} -> {dir_path}")
        
        return self.dirs
    
    def create_session_directories(self, session_id: str) -> Dict[str, str]:
        """
        セッション用ディレクトリを作成
        
        Args:
            session_id (str): セッションID
            
        Returns:
            Dict[str, str]: 作成されたディレクトリのパス
        """
        base_output = self.dirs.get("output", "data/output")
        session_dirs = {}
        
        dir_names = [
            "converted_images",
            "llm_judgments",
            "dewarped",
            "split_images",
            "super_resolved",
            "final_results"
        ]
        
        for dir_name in dir_names:
            dir_path = os.path.join(base_output, dir_name, session_id)
            ensure_directory(dir_path)
            session_dirs[dir_name] = dir_path
            logger.debug(f"セッションディレクトリ作成: {dir_name} -> {dir_path}")

        # session_id自体も辞書に追加（Step7等で使用）
        session_dirs["session_id"] = session_id

        return session_dirs