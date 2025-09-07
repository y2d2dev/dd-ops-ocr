import os
import json
import base64
import logging
import shutil
from flask import Flask, request, jsonify
from datetime import datetime
import traceback
from typing import Dict, Any

from ..pipeline.main_pipeline_v2 import DocumentOCRPipeline
from ..utils.logger import setup_logger
from .model_downloader import ensure_models_available

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = setup_logger(__name__)

pipeline = None

# Cloud Run起動時にモデルをダウンロード
def initialize_models():
    """起動時にモデルをダウンロード"""
    logger.info("🚀 Initializing models...")
    try:
        success = ensure_models_available()
        if success:
            logger.info("✅ Models initialized successfully")
        else:
            logger.warning("⚠️ Some models may be missing")
    except Exception as e:
        logger.error(f"❌ Failed to initialize models: {e}")
        logger.warning("⚠️ Continuing without models - OCR features may be limited")

# アプリケーション起動時にモデルを初期化
initialize_models()

def get_pipeline():
    global pipeline
    if pipeline is None:
        config_path = os.environ.get('CONFIG_PATH', 'config/config.yaml')
        pipeline = DocumentOCRPipeline(config_path)
    return pipeline

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200

@app.route('/pubsub/push', methods=['POST'])
def pubsub_push():
    """
    Cloud PubSub Push通知を受け取るエンドポイント
    GCS Storage Object notificationを処理
    """
    try:
        logger.info("="*80)
        logger.info("🔵 PUBSUB PUSH REQUEST RECEIVED")
        logger.info("="*80)
        
        logger.info(f"📌 Request Method: {request.method}")
        logger.info(f"📌 Request URL: {request.url}")
        logger.info(f"📌 Request Path: {request.path}")
        
        logger.info("📋 REQUEST HEADERS:")
        for key, value in request.headers:
            logger.info(f"  - {key}: {value}")
        
        logger.info(f"📝 Content-Type: {request.content_type}")
        logger.info(f"📝 Content-Length: {request.content_length}")
        
        logger.info(f"📦 Raw Request Data: {request.data}")
        logger.info(f"📦 Request Data Type: {type(request.data)}")
        logger.info(f"📦 Request Data Length: {len(request.data) if request.data else 0}")
        
        logger.info("🔍 Attempting to parse JSON...")
        envelope = None
        try:
            envelope = request.get_json()
            logger.info(f"✅ JSON parsed successfully")
            logger.info(f"📊 Envelope type: {type(envelope)}")
            logger.info(f"📊 Envelope keys: {list(envelope.keys()) if envelope else 'None'}")
            logger.info(f"📊 Full envelope content: {json.dumps(envelope, indent=2) if envelope else 'None'}")
        except Exception as json_error:
            logger.error(f"❌ JSON parsing failed: {str(json_error)}")
            logger.error(f"❌ Error type: {type(json_error).__name__}")
        
        if not envelope:
            logger.error("❌ No PubSub message received (envelope is None or empty)")
            return jsonify({"error": "Bad Request: no PubSub message received"}), 400
            
        if not isinstance(envelope, dict) or "message" not in envelope:
            logger.error(f"❌ Invalid PubSub message format - envelope type: {type(envelope)}, has 'message' key: {'message' in envelope if isinstance(envelope, dict) else 'N/A'}")
            return jsonify({"error": "Bad Request: invalid PubSub message format"}), 400
            
        pubsub_message = envelope["message"]
        logger.info("📨 PUBSUB MESSAGE:")
        logger.info(f"  - Message type: {type(pubsub_message)}")
        logger.info(f"  - Message keys: {list(pubsub_message.keys()) if isinstance(pubsub_message, dict) else 'Not a dict'}")
        logger.info(f"  - Full message: {json.dumps(pubsub_message, indent=2)}")
        
        if isinstance(pubsub_message.get("data"), str):
            try:
                logger.info("🔓 Attempting Base64 decode...")
                logger.info(f"  - Data length (encoded): {len(pubsub_message['data'])}")
                logger.info(f"  - First 100 chars: {pubsub_message['data'][:100]}...")
                
                message_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
                logger.info(f"✅ Base64 decode successful")
                logger.info(f"  - Decoded length: {len(message_data)}")
                logger.info(f"  - First 200 chars: {message_data[:200] if message_data else 'Empty'}...")
                
                if not message_data or not message_data.strip():
                    logger.warning(f"⚠️ Decoded message is empty or whitespace only")
                    return jsonify({"status": "ignored", "reason": "Empty message"}), 200
                
                storage_object = json.loads(message_data)
                logger.info(f"✅ JSON parse of decoded data successful")
                logger.info(f"📄 Storage Object keys: {list(storage_object.keys())}")
                logger.info(f"📄 Full Storage Object: {json.dumps(storage_object, indent=2)}")
            except Exception as e:
                logger.error(f"❌ Failed to decode PubSub message: {str(e)}")
                logger.error(f"❌ Error type: {type(e).__name__}")
                logger.error(f"❌ Stack trace: {traceback.format_exc()}")
                return jsonify({"error": "Bad Request: invalid message data"}), 400
        else:
            logger.error(f"❌ PubSub message data is not a string, type: {type(pubsub_message.get('data'))}")
            return jsonify({"error": "Bad Request: message data must be base64 encoded"}), 400
            
        if not isinstance(storage_object, dict) or "id" not in storage_object:
            logger.error(f"❌ Invalid Storage Object format - type: {type(storage_object)}, has 'id': {'id' in storage_object if isinstance(storage_object, dict) else 'N/A'}")
            return jsonify({"error": "Bad Request: invalid Storage Object"}), 400
            
        object_id = storage_object.get("id", "")
        object_name = storage_object.get("name", "")
        object_bucket = storage_object.get("bucket", "")
        
        logger.info("🗂️ STORAGE OBJECT INFO:")
        logger.info(f"  - Object ID: {object_id}")
        logger.info(f"  - Object Name: {object_name}")
        logger.info(f"  - Bucket: {object_bucket}")
        logger.info(f"  - Content Type: {storage_object.get('contentType', 'N/A')}")
        logger.info(f"  - Size: {storage_object.get('size', 'N/A')} bytes")
        
        name_parts = object_name.split("/")
        logger.info(f"📂 Name parts: {name_parts}")
        logger.info(f"📂 Number of parts: {len(name_parts)}")
        
        if len(name_parts) < 3:
            logger.error(f"❌ Invalid object name format: {object_name} - expected at least 3 parts")
            return jsonify({"error": "Invalid object name format"}), 400
            
        workspace_id = name_parts[0]
        project_id = name_parts[1]
        filename = "/".join(name_parts[2:])
        
        logger.info("✨ EXTRACTED INFO:")
        logger.info(f"  - Workspace ID: {workspace_id}")
        logger.info(f"  - Project ID: {project_id}")
        logger.info(f"  - Filename: {filename}")
        
        if not filename.lower().endswith('.pdf'):
            logger.info(f"⚠️ Ignoring non-PDF file: {filename}")
            return jsonify({"message": "File ignored (not a PDF)"}), 200
            
        logger.info(f"🚀 Starting PDF processing - workspace: {workspace_id}, project: {project_id}, file: {filename}")
        
        result = process_single_pdf(object_bucket, object_name, workspace_id, project_id)
        
        response = {
            "workspace_id": workspace_id,
            "project_id": project_id,
            "file": filename,
            "success": result["success"],
            "timestamp": datetime.now().isoformat()
        }
        
        if result["success"]:
            response["contract_json"] = result.get("contract_json", "")
            response["output_files"] = result.get("output_files", [])
            logger.info(f"Successfully processed PDF: {filename}")
        else:
            response["error"] = result.get("error", "Processing failed")
            logger.error(f"Failed to process PDF: {filename} - {result.get('error')}")
            
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Unexpected error in PubSub handler: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 200

def process_single_pdf(bucket_name: str, object_name: str, workspace_id: str, project_id: str) -> Dict[str, Any]:
    """
    単一のPDFファイルを処理
    
    Args:
        bucket_name: GCSバケット名
        object_name: オブジェクトパス (workspace_id/project_id/filename.pdf)
        workspace_id: ワークスペースID
        project_id: プロジェクトID
    
    Returns:
        処理結果を含む辞書
    """
    try:
        gcs_uri = f"gs://{bucket_name}/{object_name}"
        logger.info(f"Processing PDF from: {gcs_uri}")
        
        pipeline = get_pipeline()
        
        temp_dir = os.environ.get('TEMP_DIR', '/tmp/ocr_processing')
        workspace_dir = os.path.join(temp_dir, workspace_id, project_id)
        os.makedirs(workspace_dir, exist_ok=True)
        
        local_file_path = download_from_gcs(gcs_uri, workspace_dir)
        
        output_dir = os.path.join(workspace_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"Starting OCR pipeline for: {local_file_path}")
        result = pipeline.process_pdf(local_file_path, output_session_id=f"{workspace_id}_{project_id}")
        
        output_bucket = os.environ.get('GCS_BUCKET_NAME', bucket_name)
        
        # 契約書JSONを抽出（既にGeminiから正しい形式で返されている）
        basename = os.path.splitext(os.path.basename(object_name.split('/')[-1]))[0]
        
        # OCR結果から契約書JSONを直接取得
        contract_json = None
        if result and "final_results" in result:
            final_results = result["final_results"]
            if isinstance(final_results, dict) and "ocr_results" in final_results:
                ocr_results_list = final_results["ocr_results"]
                if isinstance(ocr_results_list, list):
                    logger.info(f"📋 ocr_results_list length: {len(ocr_results_list)}")
                    for i, ocr_item in enumerate(ocr_results_list):
                        logger.info(f"  - Item {i}: type={type(ocr_item)}, keys={list(ocr_item.keys()) if isinstance(ocr_item, dict) else 'Not a dict'}")
                        if isinstance(ocr_item, dict):
                            # 様々なキーを試す
                            if "ocr_data" in ocr_item:
                                contract_json = ocr_item["ocr_data"]
                                logger.info(f"    ✅ Found ocr_data in item {i}")
                                break
                            elif "ocr_result" in ocr_item:
                                ocr_result = ocr_item["ocr_result"]
                                if isinstance(ocr_result, dict) and "ocr_data" in ocr_result:
                                    contract_json = ocr_result["ocr_data"]
                                    logger.info(f"    ✅ Found ocr_data in ocr_result of item {i}")
                                    break
                            # 直接契約書の構造を持っている可能性
                            elif "success" in ocr_item and "info" in ocr_item and "result" in ocr_item:
                                contract_json = ocr_item
                                logger.info(f"    ✅ Item {i} is already in contract JSON format")
                                break
        
        # フォールバック：契約書JSONが取得できない場合
        if not contract_json:
            logger.warning(f"⚠️ 契約書JSONが取得できませんでした: {basename}")
            logger.warning(f"   - OCR結果があるか: {bool(result)}")
            if result:
                logger.warning(f"   - final_resultsがあるか: {'final_results' in result}")
                if "final_results" in result:
                    logger.warning(f"   - ocr_resultsがあるか: {'ocr_results' in result['final_results']}")
            
            contract_json = {
                "success": False,
                "info": {
                    "title": basename,
                    "party": "",
                    "start_date": "",
                    "end_date": "",
                    "conclusion_date": ""
                },
                "result": {
                    "articles": []
                },
                "error": "OCR処理が実行されなかったか、結果の取得に失敗しました"
            }
        
        # JSONをafter_ocr配下に保存
        json_output_path = f"{workspace_id}/{project_id}/after_ocr/{basename}.json"
        json_gcs_path = upload_json_to_gcs(
            contract_json,
            output_bucket,
            json_output_path
        )
        logger.info(f"✅ Contract JSON saved to: gs://{output_bucket}/{json_output_path}")
        
        # 追加の出力ファイル（画像など）を保存
        output_prefix = f"{workspace_id}/{project_id}/ocr_results/"
        output_files = []
        if result and 'output_files' in result:
            for output_file in result.get('output_files', []):
                if os.path.exists(output_file):
                    gcs_path = upload_file_to_gcs(
                        output_file,
                        output_bucket,
                        output_prefix + os.path.basename(output_file)
                    )
                    output_files.append(gcs_path)
        
        
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
        
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        
        return {
            'success': True,
            'contract_json': json_gcs_path,
            'output_files': output_files,
            'ocr_results': result
        }
        
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e)
        }

def download_from_gcs(gcs_uri: str, temp_dir: str) -> str:
    """
    GCSからファイルをダウンロード
    """
    from google.cloud import storage
    
    if not gcs_uri.startswith('gs://'):
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")
    
    path_parts = gcs_uri[5:].split('/', 1)
    if len(path_parts) != 2:
        raise ValueError(f"Invalid GCS URI format: {gcs_uri}")
    
    bucket_name, blob_path = path_parts
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    local_filename = os.path.basename(blob_path)
    local_path = os.path.join(temp_dir, local_filename)
    
    logger.info(f"Downloading {gcs_uri} to {local_path}")
    blob.download_to_filename(local_path)
    
    return local_path

def upload_file_to_gcs(local_path: str, bucket_name: str, blob_name: str) -> str:
    """
    ファイルをGCSにアップロード
    """
    from google.cloud import storage
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    logger.info(f"Uploading {local_path} to gs://{bucket_name}/{blob_name}")
    blob.upload_from_filename(local_path)
    
    return f"gs://{bucket_name}/{blob_name}"

def upload_json_to_gcs(json_data: Dict[str, Any], bucket_name: str, blob_path: str) -> str:
    """
    JSONデータをGCSにアップロード
    """
    from google.cloud import storage
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
    
    logger.info(f"Uploading JSON to gs://{bucket_name}/{blob_path}")
    blob.upload_from_string(json_str, content_type='application/json')
    
    return f"gs://{bucket_name}/{blob_path}"

def upload_results_to_gcs(result: Dict[str, Any], bucket_name: str, prefix: str) -> str:
    """
    処理結果をGCSにアップロード
    """
    from google.cloud import storage
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    
    result_json = json.dumps(result, ensure_ascii=False, indent=2)
    blob_name = f"{prefix}result.json"
    blob = bucket.blob(blob_name)
    
    logger.info(f"Uploading results to gs://{bucket_name}/{blob_name}")
    blob.upload_from_string(result_json, content_type='application/json')
    
    return f"gs://{bucket_name}/{blob_name}"


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)