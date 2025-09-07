# DD-OPS-OCR
契約書OCR処理システム

## Docker実行

### 1. 初回ビルド（1回のみ）
```bash
docker build -t y2d2-pipeline .
```

### 2. 開発モード（コード変更してもビルド不要）
```bash
# pdf/ディレクトリのPDFを自動処理
docker run --rm -v $(pwd):/app y2d2-pipeline python src/main_pipeline.py

# 指定したPDFを処理
docker run --rm -v $(pwd):/app y2d2-pipeline python src/main_pipeline.py --input pdf/your_file.pdf
```

### 3. 対話モード（開発・デバッグ用）
```bash
docker run -it --rm -v $(pwd):/app y2d2-pipeline bash
# コンテナ内で自由に実行:
# python src/main_pipeline.py
# python src/main_pipeline.py --input pdf/test.pdf
```

**📝 重要：** `-v $(pwd):/app` でローカルコードをマウントするため、**コード変更時にビルド不要**です。

## Cloud Run デプロイ

### 現在のデプロイ手順（2025年9月時点）

```bash
# 1. Dockerイメージをビルド（linux/amd64プラットフォーム指定）
docker build --platform linux/amd64 -t gcr.io/reflected-flux-462908-s6/dd-ops-ocr-api --build-arg INSTALL_ULTRALYTICS=false .

# 2. Container Registryにプッシュ
docker push gcr.io/reflected-flux-462908-s6/dd-ops-ocr-api

# 3. Cloud Runサービスを作成/更新
gcloud run services update dd-ops-ocr-api-v2 \
  --region asia-northeast1 \
  --image gcr.io/reflected-flux-462908-s6/dd-ops-ocr-api \
  --memory 1Gi \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=reflected-flux-462908-s6,GCS_BUCKET_NAME=app_contracts_staging,DD_OPS_MODELS_BUCKET=dd_ops_models,PYTHONDONTWRITEBYTECODE=1,PYTHONUNBUFFERED=1,GEMINI_API_KEY=AIzaSyCCZL0v2FOVqYbWhshAeyETCj0zE3_5m1s,DOCUMENT_AI_PROJECT_ID=75499681521,DOCUMENT_AI_PROCESSOR_ID=599b6ebb19fa1478,DOCUMENT_AI_LOCATION=us"
```

### 重要な設定ポイント

- **プラットフォーム指定**: `--platform linux/amd64`（ARM64マシンからデプロイする場合）
- **メモリ**: `1Gi`（512Miでは不足）
- **必須環境変数**:
  - `GEMINI_API_KEY`: Gemini API認証用
  - `DOCUMENT_AI_*`: Document AI設定
  - `GOOGLE_APPLICATION_CREDENTIALS`は**設定しない**（Cloud Runデフォルト認証を使用）

### 現在のサービスURL
https://dd-ops-ocr-api-v2-75499681521.asia-northeast1.run.app

## 開発者向け情報

詳細な開発ルール・ログフォーマット・トラブルシューティングについては [DEVELOPMENT.md](./DEVELOPMENT.md) を参照してください。








書類OCR前処理の統合パイプラインシステム

process_pdf メソッドにより，パイプラインを実行する

処理フロー:
1. PDF → JPG変換 (DPI自動調整)
2-1. 画像の歪み(および識別困難性の判定) (LLM)
2-2. 最高解像度化 (必要な場合)
2-3. 歪み補正 (必要な場合)
3-1. 回転判定 (LLM)
3-2. 回転補正
4-1. ページ数等判定 (LLM)
4-2. ページ分割 (必要な場合)
5-1. 画像5等分 (オーバーラップ付き)
6-1. 超解像処理 (DRCT)
7-1. OCR実行 (LLM)

DocumetAIを動かす前に必要なこと
https://cloud.google.com/docs/authentication/set-up-adc-local-dev-environment?hl=ja#google-idp
と、~/.config/gcloud/application_default_credentials.jsonここにファイルができる。
gcp-credentials.jsonとしてコピーする。コミットに含めるとPushできなくなるので気をつけ