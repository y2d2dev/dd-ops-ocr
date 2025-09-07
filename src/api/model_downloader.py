"""
Cloud Storageからモデルファイルをダウンロード（Cloud Run用）
"""
import os
import logging
from pathlib import Path
from google.cloud import storage
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class ModelDownloader:
    def __init__(self, bucket_name: str = "dd_ops_models"):
        self.bucket_name = bucket_name
        self.storage_client = None
        self.models_dir = Path("/app/data/models")
        
    def _get_storage_client(self):
        """Storage clientの遅延初期化"""
        if self.storage_client is None:
            self.storage_client = storage.Client()
        return self.storage_client
    
    def download_file(self, source_blob_name: str, destination_file: Path) -> bool:
        """
        GCSから単一ファイルをダウンロード
        """
        try:
            if destination_file.exists():
                file_size = destination_file.stat().st_size
                logger.info(f"✅ {destination_file.name} already exists ({file_size:,} bytes)")
                return True
            
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"📥 Downloading {source_blob_name} from GCS...")
            
            client = self._get_storage_client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(source_blob_name)
            
            if not blob.exists():
                logger.error(f"❌ File not found: gs://{self.bucket_name}/{source_blob_name}")
                return False
            
            blob.reload()
            blob_size = blob.size
            logger.info(f"📊 Download size: {blob_size/1024/1024:.1f}MB")
            
            blob.download_to_filename(str(destination_file))
            
            downloaded_size = destination_file.stat().st_size
            logger.info(f"✅ {destination_file.name} downloaded ({downloaded_size/1024/1024:.1f}MB)")
            
            if downloaded_size != blob_size:
                logger.warning(f"⚠️ Size mismatch: expected={blob_size}, actual={downloaded_size}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to download {source_blob_name}: {e}")
            return False
    
    def download_all_models(self) -> bool:
        """
        すべての必要なモデルをダウンロード
        """
        models = {
            "yolo_weights": {
                "dir": self.models_dir / "yolo_weights",
                "files": [
                    {
                        "filename": "best.pt",
                        "gcs_path": "yolo_weights/best.pt"
                    }
                ]
            },
            "drct_weights": {
                "dir": self.models_dir / "drct_weights",
                "files": [
                    {
                        "filename": "DRCT-L.pth",
                        "gcs_path": "drct_weights/DRCT-L.pth"
                    }
                ]
            }
        }
        
        logger.info(f"🚀 Starting model download from gs://{self.bucket_name}")
        logger.info(f"📁 Models directory: {self.models_dir}")
        
        success_count = 0
        total_count = 0
        
        for model_type, config in models.items():
            logger.info(f"📂 Processing {model_type} models")
            
            for file_info in config["files"]:
                total_count += 1
                filepath = config["dir"] / file_info["filename"]
                
                if self.download_file(file_info["gcs_path"], filepath):
                    success_count += 1
                else:
                    logger.error(f"Failed to download {file_info['filename']}")
        
        logger.info(f"📊 Download result: {success_count}/{total_count} successful")
        
        if success_count == total_count:
            logger.info("🎉 All models downloaded successfully")
            return True
        else:
            logger.error(f"❌ {total_count - success_count} files failed to download")
            return False

def ensure_models_available():
    """
    モデルが利用可能であることを確認（Cloud Run起動時に呼び出す）
    """
    try:
        downloader = ModelDownloader()
        success = downloader.download_all_models()
        
        if not success:
            logger.warning("⚠️ Some models failed to download, but continuing...")
        
        return success
    except Exception as e:
        logger.error(f"❌ Model download failed: {e}")
        logger.warning("⚠️ Continuing without models - some features may not work")
        return False