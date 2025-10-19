import os
import json
import base64
import logging
import shutil
from flask import Flask, request, jsonify
from datetime import datetime
import traceback
from typing import Dict, Any, Optional
from google.cloud import storage
import subprocess
import sys
from pathlib import Path

# UTF-8エンコーディングを確実にする
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('LANG', 'ja_JP.UTF-8')
os.environ.setdefault('LC_ALL', 'ja_JP.UTF-8')
from src.api.model_downloader import ensure_models_available

app = Flask(__name__)

# UTF-8エンコーディングを確実にする
app.config['JSON_AS_ASCII'] = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cloud Run起動時にモデルをダウンロード
def initialize_models():
    """起動時にモデルをダウンロード（512MB構成用に軽量化）"""
    logger.info("🚀 Initializing models (lightweight mode)...")
    
    # メモリ制約がある場合はモデルダウンロードをスキップ
    memory_limit = os.environ.get('CLOUD_RUN_MEMORY', '512Mi')
    if '512' in memory_limit:
        logger.info("💡 512MB構成検出 - モデルダウンロードをスキップします")
        logger.info("🔧 モデルは処理時に動的にダウンロードされます")
        return
    
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

def get_project_root():
    """プロジェクトのルートディレクトリを取得"""
    # Cloud Runでは/app配下にプロジェクトが配置される
    if Path("/app").exists():
        return Path("/app")
    else:
        # ローカル開発環境
        return Path(__file__).parent.parent.parent

def run_main_pipeline(pdf_path: str) -> Dict[str, Any]:
    """
    main_pipeline.pyを実行してOCR処理を行う
    
    Args:
        pdf_path: 処理対象のPDFファイルパス
        
    Returns:
        Dict: 処理結果
    """
    try:
        project_root = get_project_root()
        main_pipeline_path = project_root / "src" / "main_pipeline.py"
        
        if not main_pipeline_path.exists():
            raise FileNotFoundError(f"main_pipeline.py not found: {main_pipeline_path}")
        
        # main_pipeline.pyを実行
        cmd = [
            sys.executable,
            str(main_pipeline_path),
            "--input", pdf_path
        ]
        
        logger.info(f"🚀 Running main_pipeline.py with command: {' '.join(cmd)}")
        logger.info(f"🔍 Working directory for subprocess: {project_root}")

        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            logger.info("✅ main_pipeline.py executed successfully")
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        else:
            logger.error(f"❌ main_pipeline.py failed with return code: {result.returncode}")
            logger.error(f"❌ STDOUT: {result.stdout}")
            logger.error(f"❌ STDERR: {result.stderr}")
            return {
                "success": False,
                "error": f"Pipeline execution failed: {result.stderr}",
                "stdout": result.stdout,
                "stderr": result.stderr
            }

    except Exception as e:
        logger.error(f"❌ Error running main_pipeline.py: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200

@app.route('/debug-blobs', methods=['GET'])
def debug_blobs():
    """GCS内のblobをデバッグ用にリストする"""
    try:
        
        prefix = request.args.get('prefix', '')
        bucket_name = 'app_contracts_staging'
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        blob_info = []
        for blob in blobs:
            blob_info.append({
                'name': blob.name,
                'size': blob.size,
                'created': blob.time_created.isoformat() if blob.time_created else None,
                'content_type': blob.content_type
            })
        
        return jsonify({
            'bucket': bucket_name,
            'prefix': prefix,
            'total_blobs': len(blob_info),
            'blobs': blob_info
        }), 200
        
    except Exception as e:
        logger.error(f"Debug blobs error: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def root():
    """
    ルートエンドポイント - API情報を返す
    """
    return jsonify({
        'service': 'DD-OPS OCR API',
        'version': '1.0.0',
        'endpoints': {
            '/health': 'Health check',
            '/ocr [GET]': 'Test OCR with local PDF files',
            '/ocr [POST]': 'OCR with GCS PDF URL',
            '/pubsub/push [POST]': 'PubSub webhook for automatic processing'
        },
        'usage': {
            'GET /ocr': 'Process PDF from /pdf/ directory',
            'GET /ocr?file=test.pdf': 'Process specific PDF file',
            'POST /ocr': 'Send {"pdf_url": "gs://bucket/file.pdf", "workspace_id": "ws", "project_id": "proj"}'
        },
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@app.route('/ocr', methods=['GET'])
def ocr_test():
    """
    GETメソッドでOCR処理をテスト実行するエンドポイント
    
    クエリパラメータ:
        file: PDFファイル名 (オプション、デフォルトは自動検出)
        
    例: /ocr?file=test.pdf
    """
    try:
        logger.info("🚀 GET /ocr endpoint called")
        
        # クエリパラメータからファイル名を取得
        pdf_filename = request.args.get('file')
        
        # テスト用のOCR処理を実行
        result = process_test_pdf(pdf_filename)
        
        response = {
            "status": "completed",
            "method": "GET",
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"OCR test endpoint error: {str(e)}")
        return jsonify({
            "status": "error",
            "method": "GET",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }), 500

@app.route('/ocr', methods=['POST'])
def ocr_upload():
    """
    POSTメソッドでOCR処理を実行するエンドポイント
    
    JSON body:
        {
            "pdf_url": "gs://bucket/path/to/file.pdf",
            "workspace_id": "workspace123",
            "project_id": "project456"
        }
    """
    try:
        logger.info("🚀 POST /ocr endpoint called")
        
        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "error": "JSON body required"
            }), 400
        
        pdf_url = data.get('pdf_url')
        workspace_id = data.get('workspace_id', 'test_workspace')
        project_id = data.get('project_id', 'test_project')
        
        if not pdf_url:
            return jsonify({
                "status": "error",
                "error": "pdf_url is required"
            }), 400
        
        # GCS URIの場合
        if pdf_url.startswith('gs://'):
            bucket_name = pdf_url.replace('gs://', '').split('/')[0]
            object_name = '/'.join(pdf_url.replace('gs://', '').split('/')[1:])
            
            result = process_single_pdf(bucket_name, object_name, workspace_id, project_id)
        else:
            return jsonify({
                "status": "error",
                "error": "Only gs:// URLs are supported"
            }), 400
        
        response = {
            "status": "completed",
            "method": "POST",
            "timestamp": datetime.now().isoformat(),
            "workspace_id": workspace_id,
            "project_id": project_id,
            "result": result
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"OCR upload endpoint error: {str(e)}")
        return jsonify({
            "status": "error",
            "method": "POST",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }), 500

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

        # Check delivery attempt and skip if too many retries
        delivery_attempt = envelope.get('deliveryAttempt', 0)
        logger.info(f"📬 Delivery attempt: {delivery_attempt}")

        if delivery_attempt > 2:
            logger.warning(f"⚠️ Skipping message after {delivery_attempt} delivery attempts")
            return jsonify({"status": "skipped", "reason": f"Too many retries ({delivery_attempt})"}), 200
            
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
            
        if not isinstance(storage_object, dict):
            logger.error(f"❌ Invalid Storage Object format - type: {type(storage_object)}")
            return jsonify({"error": "Bad Request: invalid Storage Object"}), 400

        # Test用でidが無い場合は自動生成
        if "id" not in storage_object:
            logger.warning("⚠️ Storage Object has no 'id' field, generating one for testing...")
            storage_object["id"] = f"test-{storage_object.get('name', 'unknown')}-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
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

def process_test_pdf(pdf_filename: Optional[str] = None) -> Dict[str, Any]:
    """
    テスト用のPDF処理（ローカルのpdf/ディレクトリから）
    
    Args:
        pdf_filename: 処理するPDFファイル名（オプション）
        
    Returns:
        処理結果を含む辞書
    """
    try:
        project_root = get_project_root()
        
        # ローカルのpdf/ディレクトリからPDFを検索
        local_pdf_dir = project_root / "pdf"
        
        if not local_pdf_dir.exists():
            return {
                'success': False,
                'error': 'PDF directory not found. Please place PDF files in /pdf/ directory.'
            }
        
        # PDFファイルの決定
        if pdf_filename:
            pdf_path = local_pdf_dir / pdf_filename
            if not pdf_path.exists():
                return {
                    'success': False,
                    'error': f'PDF file not found: {pdf_filename}'
                }
        else:
            # 自動検出：最初に見つかったPDFファイルを使用
            pdf_files = list(local_pdf_dir.glob("*.pdf"))
            if not pdf_files:
                return {
                    'success': False,
                    'error': 'No PDF files found in /pdf/ directory'
                }
            pdf_path = pdf_files[0]
            pdf_filename = pdf_path.name
        
        logger.info(f"Processing local PDF: {pdf_path}")
        
        # main_pipeline.pyを実行
        pipeline_result = run_main_pipeline(str(pdf_path))
        
        if not pipeline_result["success"]:
            logger.error(f"Pipeline execution failed: {pipeline_result.get('error')}")
            return {
                'success': False,
                'error': pipeline_result.get('error', 'Pipeline execution failed'),
                'pipeline_output': pipeline_result
            }
        
        # 結果ファイルを収集
        basename = os.path.splitext(pdf_filename)[0]
        result_files = []
        contract_data = None
        
        # resultディレクトリをスキャン
        result_dir = project_root / "result"
        if not result_dir.exists():
            result_dir = Path("/tmp/result")
        
        if result_dir.exists():
            for result_file in result_dir.glob("*"):
                if result_file.is_file():
                    file_info = {
                        "filename": result_file.name,
                        "size": result_file.stat().st_size,
                        "path": str(result_file)
                    }
                    
                    # JSONファイルの場合は内容も読み取り
                    if result_file.suffix == '.json':
                        try:
                            with open(result_file, 'r', encoding='utf-8') as f:
                                json_content = json.load(f)
                            file_info["content"] = json_content
                            
                            # integration_metadataの場合は契約データとして扱う
                            if 'integration_metadata' in result_file.name:
                                contract_data = json_content
                        except Exception as e:
                            logger.warning(f"Failed to read JSON file {result_file.name}: {e}")
                    
                    result_files.append(file_info)
        
        return {
            'success': True,
            'pdf_file': pdf_filename,
            'pdf_path': str(pdf_path),
            'result_files': result_files,
            'contract_data': contract_data,
            'pipeline_result': pipeline_result,
            'processing_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing test PDF: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

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
        
        # Cloud Run対応：書き込み可能ディレクトリを使用
        pdf_dir = Path("/tmp/pdf")
        pdf_dir.mkdir(exist_ok=True)
        
        # GCSからPDFを一時ディレクトリにダウンロード
        filename = os.path.basename(object_name)
        local_file_path = pdf_dir / filename
        download_from_gcs(gcs_uri, str(local_file_path))

        # 処理開始前にresultディレクトリをクリーンアップ
        project_root = get_project_root()
        result_dir = project_root / "result"
        if not result_dir.exists():
            result_dir = Path("/tmp/result")

        # 詳細ログ追加でデバッグ
        logger.info(f"🔍 project_root: {project_root}")
        logger.info(f"🔍 result_dir: {result_dir}")
        logger.info(f"🔍 result_dir.exists(): {result_dir.exists()}")

        # 重要: Cloud Runでは毎回新しいインスタンスが起動されるはずだが、
        # Dockerイメージに古いresultファイルが含まれている可能性があるため、
        # 処理開始前に必ずresultディレクトリをクリーンアップ
        if result_dir.exists():
            logger.info(f"🧹 Cleaning up result directory before processing: {result_dir}")
            for old_file in result_dir.glob("*"):
                if old_file.is_file():
                    try:
                        old_file.unlink()
                        logger.info(f"🗑️ Deleted old file: {old_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete old file {old_file.name}: {e}")

        logger.info(f"Starting OCR pipeline for: {local_file_path}")

        # main_pipeline.pyを実行
        pipeline_result = run_main_pipeline(str(local_file_path))

        # パイプライン実行後の詳細ログ
        logger.info(f"🔍 After pipeline execution:")
        logger.info(f"🔍 result_dir.exists(): {result_dir.exists()}")
        if result_dir.exists():
            all_files = list(result_dir.glob("*"))
            logger.info(f"🔍 Files in result_dir: {[f.name for f in all_files]}")
        else:
            logger.warning(f"⚠️ result_dir does not exist: {result_dir}")

        # 追加の候補パスもチェック
        alternative_paths = [
            Path("/app/result"),
            project_root / "src" / "result",
            Path.cwd() / "result",
            Path("/tmp/result"),
            Path("/app/src/result")
        ]

        for alt_path in alternative_paths:
            logger.info(f"🔍 Checking alternative path: {alt_path}")
            logger.info(f"🔍 Path exists: {alt_path.exists()}")
            if alt_path.exists():
                files = list(alt_path.glob("*"))
                logger.info(f"🔍 Files in {alt_path}: {[f.name for f in files]}")
                if files:
                    logger.info(f"📁 Found {len(files)} files in {alt_path} - using this as result directory")
                    result_dir = alt_path  # 実際にファイルがある場所を使用
                    break

        if not pipeline_result["success"]:
            logger.error(f"Pipeline execution failed: {pipeline_result.get('error')}")
            return {
                'success': False,
                'error': pipeline_result.get('error', 'Pipeline execution failed')
            }

        # 処理後にPDFファイルを削除
        if local_file_path.exists():
            local_file_path.unlink()
            logger.info(f"Cleaned up local PDF file: {local_file_path}")

        output_bucket = os.environ.get('GCS_BUCKET_NAME', bucket_name)

        # 結果ファイルをGCSにアップロード - パイプライン実行後にファイルを処理
        basename = os.path.splitext(filename)[0]
        output_files = []
        
        txt_files_to_delete = []  # 削除予定のtxtファイルを追跡

        if result_dir.exists():
            # 最新のファイルを検索（タイムスタンプ付きファイル）
            # 重要: 現在のセッションのファイルのみを処理する
            all_files = list(result_dir.glob("*"))
            logger.info(f"📂 Found {len(all_files)} files in result directory for basename '{basename}'")
            for result_file in all_files:
                if result_file.is_file():
                    logger.info(f"🔍 Processing file: {result_file.name}")
                    # ファイル名の基本チェックのみ実行
                    # 古いファイル判定は削除し、現在のPDFに関連するファイルのみ処理

                    # ファイル名に現在のPDFのbasenameが含まれているかチェック
                    if basename not in result_file.name:
                        logger.info(f"⏭️ Skipping file from different PDF: {result_file.name}")
                        continue
                    # 契約書メタデータJSONは保存しない
                    if result_file.suffix == '.json' and 'integration_metadata' in result_file.name:
                        logger.info(f"🚫 Skipping contract metadata JSON: {result_file.name}")
                        continue

                    # txtファイルは構造化処理で使用し、その後削除
                    if result_file.suffix == '.txt':
                        logger.info(f"📝 Found txt file for local processing: {result_file.name}")
                        txt_files_to_delete.append(result_file)
                        # GCSにはアップロードせず、ローカルで処理
                        continue

                    # その他のファイルをocr_resultsに保存
                    output_prefix = f"{workspace_id}/{project_id}/ocr_results/"
                    gcs_path = upload_file_to_gcs(
                        str(result_file),
                        output_bucket,
                        output_prefix + result_file.name
                    )
                    output_files.append(gcs_path)
                    logger.info(f"✅ Result file uploaded to: {gcs_path}")

        # ローカルのtxtファイルを使用してGeminiで構造化
        structured_json_path = None
        logger.info(f"🔍 Looking for local txt files to structure. Found {len(txt_files_to_delete)} txt files")
        for txt_file in txt_files_to_delete:
            # 統合されたファイル（integratedを含む）を特定
            if 'integrated' in txt_file.name:
                logger.info(f"🎯 Found integrated file for structuring: {txt_file.name}")
                try:
                    logger.info(f"🧠 Starting Gemini structured output for local file: {txt_file.name}")
                    # ローカルファイルから直接テキストを読み込み
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        file_content = f.read()

                    # Geminiの構造化出力を使用（ローカルファイル版）
                    structured_result = convert_local_text_to_contract_schema(file_content, basename, workspace_id, project_id, output_bucket)
                    if structured_result:
                        # 構造化されたJSONをafter_ocrに保存
                        json_output_path = f"{workspace_id}/{project_id}/after_ocr/{basename}.json"
                        structured_json_path = upload_json_to_gcs(
                            structured_result,
                            output_bucket,
                            json_output_path
                        )
                        logger.info(f"✅ Structured contract JSON saved to: {structured_json_path}")
                        break
                    else:
                        logger.warning(f"⚠️ Gemini structured output returned None for: {txt_file.name}")
                except Exception as e:
                    logger.error(f"❌ Failed to structure contract data for {txt_file.name}: {str(e)}")
                    logger.error(f"❌ Stack trace: {traceback.format_exc()}")
                    continue

        # 構造化処理が完了したら、ローカルのtxtファイルを削除
        for txt_file in txt_files_to_delete:
            try:
                txt_file.unlink()
                logger.info(f"🗑️ Deleted local txt file: {txt_file.name}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to delete txt file {txt_file.name}: {e}")

        # GCS上にtxtファイルはアップロードしていないため、削除処理は不要
        
        return {
            'success': True,
            'output_files': output_files,
            'structured_json': structured_json_path,
            'pipeline_result': pipeline_result
        }
        
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e)
        }

def convert_local_text_to_contract_schema(file_content: str, basename: str, workspace_id: str, project_id: str, bucket_name: str) -> Optional[Dict[str, Any]]:
    """
    ローカルのテキストをVertex AIの構造化出力を使って契約書スキーマに変換

    Args:
        file_content: テキスト内容
        basename: ファイルのベース名
        workspace_id: ワークスペースID
        project_id: プロジェクトID
        bucket_name: GCSバケット名

    Returns:
        構造化された契約書データまたはNone
    """
    try:
        # Vertex AI設定
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        project_id = os.getenv('GCP_PROJECT_ID')
        location = os.getenv('GCP_LOCATION', 'us-central1')
        if not project_id:
            logger.error("GCP_PROJECT_ID環境変数が設定されていません")
            return None

        vertexai.init(project=project_id, location=location)

        # 契約書スキーマの定義
        contract_schema = {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "info": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "party": {"type": "string"},  # カンマ区切りの当事者名
                        "start_date": {"type": "string"},  # 空文字列で対応
                        "end_date": {"type": "string"},  # 空文字列で対応
                        "conclusion_date": {"type": "string"}  # 空文字列で対応
                    },
                    "required": ["title", "party"]
                },
                "result": {
                    "type": "object",
                    "properties": {
                        "articles": {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {
                                        "type": "object",
                                        "properties": {
                                            "article_number": {"type": "string"},
                                            "title": {"type": "string"},
                                            "content": {"type": "string"},
                                            "table_number": {"type": "string"}
                                        },
                                        "required": ["content", "title"]
                                    },
                                    {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "party": {"type": "string"},
                                            "start_date": {"type": "string"},
                                            "end_date": {"type": "string"},
                                            "conclusion_date": {"type": "string"}
                                        },
                                        "required": ["title", "party"]
                                    }
                                ]
                            }
                        }
                    },
                    "required": ["articles"]
                }
            },
            "required": ["success", "info", "result"]
        }

        if not file_content:
            logger.warning(f"Empty content provided")
            return None

        # Vertex AIモデルの初期化（構造化出力対応）
        model = GenerativeModel('gemini-2.5-flash')
        generation_config = GenerationConfig(
            response_mime_type="application/json",
            response_schema=contract_schema,
            max_output_tokens=65535
        )

        # プロンプトの作成
        prompt = f"""
以下のOCR処理済みテキストを解析し、契約書の構造化データとして抽出してください。

ファイル名: {basename}

テキスト内容:
{file_content}

抽出指示:
1. success: 常にtrue
2. info部分（1つ目の契約書の情報のみ）:
   - title: 契約書のタイトル（見つからない場合はファイル名を使用）
   - party: 契約当事者をカンマ区切りで記載（例: "株式会社A,株式会社B"）
   - start_date: 契約開始日（YYYY-MM-DD形式、見つからない場合は空文字列）
   - end_date: 契約終了日（YYYY-MM-DD形式、見つからない場合は空文字列）
   - conclusion_date: 契約締結日（YYYY-MM-DD形式、見つからない場合は空文字列）

3. result部分:
   - articles: 契約条項の配列（全ての条項を漏れなく抽出）
     - article_number: 条項番号（例: "第1条"、"第2条"、番号がない場合は"署名欄"等）
     - title: 条項のタイトル（見出しがない場合は内容から要約）
     - content: 条項の完全な内容（省略禁止）
     - table_number: 表がある場合のみ表番号

重要な注意事項:
- テキスト内の全ての条項を必ず抽出してください（第1条から最後まで）
- 各条項のcontentは完全にコピーし、省略や要約は行わないでください
- 条項番号が明記されていない部分（前文、署名欄、付記等）も独立した条項として扱ってください
- 日付は可能な限りYYYY-MM-DD形式に変換してください
- 表や図がある場合はHTML形式でcontentに含めてください
- 署名欄も必ず1つの条項として扱ってください
- 出力は必ず完全なJSON形式で、途中で切れることなく最後まで出力してください

【複数契約書がある場合の特別ルール】:
1. 契約書内部ドキュメントと契約書の区切りを正確に判別:
   - 「頭書」「要項」「契約書本文」「用紙」「条件表」「概要」「特約」「細則」「別紙」「仕様書」「別添」「図面」「約款」「派遣個別契約票契約基本情報」「定義一覧表」などは契約書の内部ドキュメントであり、区切りではありません
   - これらは1つの契約書を構成する要素として、同じarticles配列内に含めてください
   - ドキュメントごとのタイトル、契約当事者、契約条項、署名などの重要な情報が分割後も完全に保持されるように調査してください
   - 分割により情報の欠如や漏れが発生しないよう、慎重に分析してください

2. 契約書の終了を示す箇所（「以上」等）は、以下の形式で統一:
   {{
     "article_number": "",
     "title": "契約書終了",
     "content": "----------",
     "table_number": ""
   }}

3. 2つ目以降の契約書が始まる場合、契約書終了の直後に契約書基本情報をそのまま挿入:
   {{
     "title": "[契約書タイトル]",
     "party": "[当事者をカンマ区切り]",
     "start_date": "[YYYY-MM-DD または空文字列]",
     "end_date": "[YYYY-MM-DD または空文字列]",
     "conclusion_date": "[YYYY-MM-DD または空文字列]"
   }}

4. その後、2つ目の契約書の条項を続けて記載
"""

        # Vertex AIに送信して構造化出力を取得
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        # JSONとしてパース
        try:
            structured_data = json.loads(response.text)
            logger.info(f"Successfully structured contract data with {len(structured_data.get('result', {}).get('articles', []))} articles")
            return structured_data
        except json.JSONDecodeError as json_error:
            logger.error(f"Error in Vertex AI structured output: {str(json_error)}")

            # エラー時にレスポンスをGCSに保存
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            error_path = f"{workspace_id}/{project_id}/err/{basename}_error_{timestamp}.txt"

            try:
                upload_json_to_gcs(
                    {"error": str(json_error), "response": response.text},
                    bucket_name,
                    error_path.replace('.txt', '.json')
                )
                logger.info(f"📝 Error response saved to: gs://{bucket_name}/{error_path.replace('.txt', '.json')}")
            except Exception as upload_error:
                logger.error(f"Failed to save error response: {upload_error}")

            return None

    except Exception as e:
        logger.error(f"Error in Vertex AI structured output: {str(e)}")
        return None


def convert_to_contract_schema(gcs_file_path: str, basename: str) -> Optional[Dict[str, Any]]:
    """
    GCSに保存されたテキストファイルをVertex AIの構造化出力を使って契約書スキーマに変換

    Args:
        gcs_file_path: GCSのファイルパス
        basename: ファイルのベース名

    Returns:
        構造化された契約書データまたはNone
    """
    try:
        # Vertex AI設定
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        project_id = os.getenv('GCP_PROJECT_ID')
        location = os.getenv('GCP_LOCATION', 'us-central1')
        if not project_id:
            logger.error("GCP_PROJECT_ID環境変数が設定されていません")
            return None

        vertexai.init(project=project_id, location=location)
        
        # 契約書スキーマの定義
        contract_schema = {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "info": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "party": {"type": "string"},  # カンマ区切りの当事者名
                        "start_date": {"type": "string"},  # 空文字列で対応
                        "end_date": {"type": "string"},  # 空文字列で対応
                        "conclusion_date": {"type": "string"}  # 空文字列で対応
                    },
                    "required": ["title", "party"]
                },
                "result": {
                    "type": "object",
                    "properties": {
                        "articles": {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {
                                        "type": "object",
                                        "properties": {
                                            "article_number": {"type": "string"},
                                            "title": {"type": "string"},
                                            "content": {"type": "string"},
                                            "table_number": {"type": "string"}
                                        },
                                        "required": ["content", "title"]
                                    },
                                    {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "party": {"type": "string"},
                                            "start_date": {"type": "string"},
                                            "end_date": {"type": "string"},
                                            "conclusion_date": {"type": "string"}
                                        },
                                        "required": ["title", "party"]
                                    }
                                ]
                            }
                        }
                    },
                    "required": ["articles"]
                }
            },
            "required": ["success", "info", "result"]
        }
        
        # GCSからファイル内容を読み取り
        file_content = download_text_from_gcs(gcs_file_path)
        if not file_content:
            logger.warning(f"Could not read content from: {gcs_file_path}")
            return None
        
        # Vertex AIモデルの初期化（構造化出力対応）
        model = GenerativeModel('gemini-2.5-flash')
        generation_config = GenerationConfig(
            response_mime_type="application/json",
            response_schema=contract_schema,
            max_output_tokens=65535
        )

        # プロンプトの作成
        prompt = f"""
以下のOCR処理済みテキストを解析し、契約書の構造化データとして抽出してください。

ファイル名: {basename}

テキスト内容:
{file_content}

抽出指示:
1. success: 常にtrue
2. info部分（1つ目の契約書の情報のみ）:
   - title: 契約書のタイトル（見つからない場合はファイル名を使用）
   - party: 契約当事者をカンマ区切りで記載（例: "株式会社A,株式会社B"）
   - start_date: 契約開始日（YYYY-MM-DD形式、見つからない場合は空文字列）
   - end_date: 契約終了日（YYYY-MM-DD形式、見つからない場合は空文字列）
   - conclusion_date: 契約締結日（YYYY-MM-DD形式、見つからない場合は空文字列）

3. result部分:
   - articles: 契約条項の配列（全ての条項を漏れなく抽出）
     - article_number: 条項番号（例: "第1条"、"第2条"、番号がない場合は"署名欄"等）
     - title: 条項のタイトル（見出しがない場合は内容から要約）
     - content: 条項の完全な内容（省略禁止）
     - table_number: 表がある場合のみ表番号

重要な注意事項:
- テキスト内の全ての条項を必ず抽出してください（第1条から最後まで）
- 各条項のcontentは完全にコピーし、省略や要約は行わないでください
- 条項番号が明記されていない部分（前文、署名欄、付記等）も独立した条項として扱ってください
- 日付は可能な限りYYYY-MM-DD形式に変換してください
- 表や図がある場合はHTML形式でcontentに含めてください
- 署名欄も必ず1つの条項として扱ってください
- 出力は必ず完全なJSON形式で、途中で切れることなく最後まで出力してください

【複数契約書がある場合の特別ルール】:
1. 契約書内部ドキュメントと契約書の区切りを正確に判別:
   - 「頭書」「要項」「契約書本文」「用紙」「条件表」「概要」「特約」「細則」「別紙」「仕様書」「別添」「図面」「約款」「派遣個別契約票契約基本情報」「定義一覧表」などは契約書の内部ドキュメントであり、区切りではありません
   - これらは1つの契約書を構成する要素として、同じarticles配列内に含めてください
   - ドキュメントごとのタイトル、契約当事者、契約条項、署名などの重要な情報が分割後も完全に保持されるように調査してください
   - 分割により情報の欠如や漏れが発生しないよう、慎重に分析してください

2. 契約書の終了を示す箇所（「以上」等）は、以下の形式で統一:
   {{
     "article_number": "",
     "title": "契約書終了",
     "content": "----------",
     "table_number": ""
   }}

3. 2つ目以降の契約書が始まる場合、契約書終了の直後に契約書基本情報をそのまま挿入:
   {{
     "title": "[契約書タイトル]",
     "party": "[当事者をカンマ区切り]",
     "start_date": "[YYYY-MM-DD または空文字列]",
     "end_date": "[YYYY-MM-DD または空文字列]",
     "conclusion_date": "[YYYY-MM-DD または空文字列]"
   }}

4. その後、2つ目の契約書の条項を続けて記載
"""

        # Vertex AIに送信して構造化出力を取得
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        # JSONとしてパース
        structured_data = json.loads(response.text)

        logger.info(f"Successfully structured contract data with {len(structured_data.get('result', {}).get('articles', []))} articles")

        return structured_data

    except Exception as e:
        logger.error(f"Error in Vertex AI structured output: {str(e)}")
        return None


def download_text_from_gcs(gcs_path: str) -> Optional[str]:
    """
    GCSからテキストファイルの内容を読み取り

    Args:
        gcs_path: GCSのファイルパス (gs://bucket/path/to/file.txt)

    Returns:
        ファイル内容またはNone
    """
    try:
        
        # GCS URIをパース
        if not gcs_path.startswith('gs://'):
            return None
            
        path_parts = gcs_path.replace('gs://', '').split('/', 1)
        bucket_name = path_parts[0]
        blob_name = path_parts[1]
        
        # GCSクライアントでファイルを読み取り
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # テキストとして読み取り
        content = blob.download_as_text(encoding='utf-8')
        
        return content
        
    except Exception as e:
        logger.error(f"Error downloading text from GCS: {str(e)}")
        return None

def download_from_gcs(gcs_uri: str, local_path: str) -> str:
    """
    GCSからファイルをダウンロード
    """
    import urllib.parse
    
    if not gcs_uri.startswith('gs://'):
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")
    
    path_parts = gcs_uri[5:].split('/', 1)
    if len(path_parts) != 2:
        raise ValueError(f"Invalid GCS URI format: {gcs_uri}")
    
    bucket_name, blob_path = path_parts
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    
    # Try to find the blob directly first
    try:
        blob = bucket.blob(blob_path)
        logger.info(f"Downloading {gcs_uri} to {local_path}")
        blob.download_to_filename(local_path)
        return local_path
    except Exception as e:
        logger.warning(f"Direct download failed: {e}")
        
        # If direct access fails, try to list and find matching blobs
        logger.info(f"Searching for blobs matching: {blob_path}")
        
        # Get the directory path and filename
        path_parts = blob_path.split('/')
        if len(path_parts) > 1:
            prefix = '/'.join(path_parts[:-1]) + '/'
            target_filename = path_parts[-1]
        else:
            prefix = ''
            target_filename = blob_path
            
        logger.info(f"Listing blobs with prefix: {prefix}")
        blobs = list(bucket.list_blobs(prefix=prefix))
        logger.info(f"Found {len(blobs)} blobs with prefix")
        
        # Look for exact or partial matches
        for blob in blobs:
            blob_filename = blob.name.split('/')[-1]
            logger.info(f"Checking blob: {blob.name} (filename: {blob_filename})")
            
            # Normalize Unicode for comparison
            import unicodedata
            normalized_blob_name = unicodedata.normalize('NFC', blob.name)
            normalized_blob_filename = unicodedata.normalize('NFC', blob_filename)
            normalized_target_filename = unicodedata.normalize('NFC', target_filename)
            normalized_blob_path = unicodedata.normalize('NFC', blob_path)
            
            # Try multiple matching strategies with normalized strings
            match_found = (
                normalized_blob_filename == normalized_target_filename or  # Exact match
                normalized_target_filename in normalized_blob_filename or  # Target is substring of blob
                normalized_blob_filename in normalized_target_filename or  # Blob is substring of target
                normalized_blob_name == normalized_blob_path or           # Full path exact match
                normalized_blob_name.endswith(normalized_target_filename) or  # Ends with target filename
                # Also try without normalization for backward compatibility
                blob_filename == target_filename or
                target_filename in blob_filename or
                blob_filename in target_filename or
                blob.name == blob_path or
                blob.name.endswith(target_filename)
            )
            
            if match_found:
                logger.info(f"Found matching blob: {blob.name}")
                try:
                    blob.download_to_filename(local_path)
                    return local_path
                except Exception as download_error:
                    logger.warning(f"Failed to download {blob.name}: {download_error}")
                    continue
                    
        raise FileNotFoundError(f"Could not find or download blob matching: {blob_path}")
    
    return local_path

def upload_file_to_gcs(local_path: str, bucket_name: str, blob_name: str) -> str:
    """
    ファイルをGCSにアップロード
    """
    
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