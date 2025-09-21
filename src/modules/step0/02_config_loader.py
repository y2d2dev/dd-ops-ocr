"""
設定ファイルローダーモジュール
YAMLファイルから設定を読み込み、処理オプションを適用する機能を提供
"""

import os
import yaml
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict:
    """
    設定ファイルを読み込み
    
    Args:
        config_path (str): 設定ファイルのパス
        
    Returns:
        Dict: 設定データ
        
    Raises:
        RuntimeError: 設定ファイル読み込み失敗時
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config
        
    except Exception as e:
        raise RuntimeError(f"設定ファイル読み込みエラー: {e}")


def apply_processing_options(config: Dict, processing_options: Optional[Dict] = None):
    """
    処理オプションを設定に適用
    
    Args:
        config (Dict): 設定データ
        processing_options (Optional[Dict]): 処理オプション
            - skip_super_resolution (bool): 超解像処理をスキップ
            - skip_dewarping (bool): 歪み補正をスキップ  
            - skip_ocr (bool): OCR処理をスキップ
    """
    if not processing_options:
        return
        
    if processing_options.get('skip_super_resolution'):
        # 超解像設定を無効化
        if 'super_resolution' not in config:
            config['super_resolution'] = {}
        config['super_resolution']['enabled'] = False
        logger.info("⚡ 超解像処理がスキップされます")
    
    if processing_options.get('skip_dewarping'):
        # 歪み補正設定を無効化
        if 'dewarping' not in config:
            config['dewarping'] = {}
        config['dewarping']['enabled'] = False
        logger.info("⚡ 歪み補正処理がスキップされます")
    
    if processing_options.get('skip_ocr'):
        # OCR設定を無効化
        if 'llm_evaluation' not in config:
            config['llm_evaluation'] = {}
        config['llm_evaluation']['ocr_enabled'] = False
        logger.info("⚡ OCR処理がスキップされます")