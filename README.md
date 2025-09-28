# DD-OPS-OCR
契約書OCR処理システム

## Docker実行

### 1. 初回ビルド（1回のみ）
```bash
docker build -t y2d2-pipeline .
```

### 2. 開発モード（コード変更してもビルド不要）
```bash
# pdf/ディレクトリのPDFを自動処理（GCP認証付き）
docker run --rm -v $(pwd):/app -v ~/.config/gcloud:/root/.config/gcloud:ro -e GCP_PROJECT_ID=reflected-flux-462908-s6 -e GCP_LOCATION=us-central1 y2d2-pipeline python src/main_pipeline.py

# 指定したPDFを処理（GCP認証付き）
docker run --rm -v $(pwd):/app -v ~/.config/gcloud:/root/.config/gcloud:ro -e GCP_PROJECT_ID=reflected-flux-462908-s6 -e GCP_LOCATION=us-central1 y2d2-pipeline python src/main_pipeline.py --input pdf/test.pdf
```

### 3. 対話モード（開発・デバッグ用）
```bash
# GCP認証付きでコンテナに入る
docker run -it --rm -v $(pwd):/app -v ~/.config/gcloud:/root/.config/gcloud:ro -e GCP_PROJECT_ID=reflected-flux-462908-s6 -e GCP_LOCATION=us-central1 y2d2-pipeline bash

# コンテナ内で自由に実行:
# python src/main_pipeline.py
# python src/main_pipeline.py --input pdf/test.pdf
# python test_vertex_ai.py
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
  --memory 2Gi \
  --timeout 3600 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=reflected-flux-462908-s6,GCS_BUCKET_NAME=app_contracts_staging,DD_OPS_MODELS_BUCKET=dd_ops_models,PYTHONDONTWRITEBYTECODE=1,PYTHONUNBUFFERED=1,DOCUMENT_AI_PROJECT_ID=75499681521,DOCUMENT_AI_PROCESSOR_ID=599b6ebb19fa1478,DOCUMENT_AI_LOCATION=us"
```

### 重要な設定ポイント

- **プラットフォーム指定**: `--platform linux/amd64`（ARM64マシンからデプロイする場合）
- **メモリ**: `2Gi`（OCR処理でメモリ使用量が多いため。1Giでは不足）
- **タイムアウト**: `3600`秒（1時間、OCR処理の完了を待つため最長設定）
- **必須環境変数**:
  - `DOCUMENT_AI_*`: Document AI設定
  - `GOOGLE_APPLICATION_CREDENTIALS`は**設定しない**（Cloud Runデフォルト認証を使用）
  - **Vertex AI認証**: Cloud Runのデフォルトサービスアカウントを使用（GEMINI_API_KEY不要）

### 現在のサービスURL
https://dd-ops-ocr-api-v2-75499681521.asia-northeast1.run.app

## PubSub連携設定

### Cloud Pub/Sub経由での自動OCR処理
Cloud StorageへのPDFアップロードを自動検知してOCR処理を実行するための設定です。

#### 1. エンドポイント
- **PubSub Push エンドポイント**: `/pubsub/push`
- Cloud Storage Object Notificationからのメッセージを受信

#### 2. 必要な権限設定（重要）
PubSubサービスアカウントがCloud Runサービスを呼び出せるように権限を付与する必要があります：

```bash
# プロジェクト番号を取得
gcloud projects describe reflected-flux-462908-s6 --format="value(projectNumber)"
# 結果: 75499681521

# PubSubサービスアカウントにCloud Run Invoker権限を付与
gcloud run services add-iam-policy-binding dd-ops-ocr-api-v2 \
  --region asia-northeast1 \
  --member="serviceAccount:service-75499681521@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

#### 3. 設定済みの権限
- **サービスアカウント**: `service-75499681521@gcp-sa-pubsub.iam.gserviceaccount.com`
- **付与した権限**: `roles/run.invoker`
- **設定日**: 2025年9月9日

この設定により、PubSubからのリクエストが認証エラーなくCloud Runサービスに到達できます。
## Vertex AI統合テスト

このプロジェクトはVertex AIを使用しています。ローカルでのテスト方法：

### 1. 基本テスト（認証なし）
```bash
# Dockerイメージをビルド
docker build -t y2d2-vertex-test .

# 基本動作テスト（ライブラリインポート、モジュール初期化）
docker run --rm y2d2-vertex-test python test_vertex_ai.py
```

### 2. フル機能テスト（環境変数あり）
```bash
# 環境変数を設定してテスト
docker run --rm \
  -e GCP_PROJECT_ID=your-project-id \
  -e GCP_LOCATION=us-central1 \
  y2d2-vertex-test python test_vertex_ai.py
```

### 3. 実際のVertex AI機能テスト
```bash
# GCP認証設定済みの場合（Vertex AI統合テスト）
docker run --rm \
  -v $(pwd):/app \
  -v ~/.config/gcloud:/root/.config/gcloud:ro \
  -e GCP_PROJECT_ID=reflected-flux-462908-s6 \
  -e GCP_LOCATION=us-central1 \
  y2d2-pipeline python test_vertex_ai.py

# 実際のパイプライン実行テストーこれでローカルでもテストできる
docker run --rm \
  -v $(pwd):/app \
  -v ~/.config/gcloud:/root/.config/gcloud:ro \
  -e GCP_PROJECT_ID=reflected-flux-462908-s6 \
  -e GCP_LOCATION=us-central1 \
  y2d2-pipeline python src/main_pipeline.py --input pdf/test.pdf
```

**📝 重要：**
- `GCP_PROJECT_ID`: 使用するGCPプロジェクトID
- `GCP_LOCATION`: Vertex AIのリージョン（デフォルト: us-central1）
- 実際のAPI呼び出しにはGCP認証が必要です

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