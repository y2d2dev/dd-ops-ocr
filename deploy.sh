#!/bin/bash

# Cloud Run デプロイスクリプト (README.md準拠版)

# 設定
PROJECT_ID="reflected-flux-462908-s6"
SERVICE_NAME="dd-ops-ocr"
REGION="asia-northeast1"  # 東京リージョン
IMAGE_NAME="gcr.io/$PROJECT_ID/dd-ops-ocr-api"

echo "🚀 Cloud Run デプロイを開始します..."

# 1. Dockerイメージをビルド（linux/amd64プラットフォーム指定）
echo "📦 Dockerイメージをビルド中 (linux/amd64)..."
docker build --platform linux/amd64 -t $IMAGE_NAME \
  --build-arg INSTALL_ULTRALYTICS=false \
  .

# 2. Container Registryにプッシュ
echo "⬆️  Container Registryにプッシュ中..."
docker push $IMAGE_NAME

# 3. Cloud Runサービスを作成/更新
echo "🌐 Cloud Runにデプロイ中..."
gcloud run deploy $SERVICE_NAME \
  --region $REGION \
  --image $IMAGE_NAME \
  --memory 2Gi \
  --timeout 3600 \
  --concurrency 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCS_BUCKET_NAME=app_contracts_staging,DD_OPS_MODELS_BUCKET=dd_ops_models,PYTHONDONTWRITEBYTECODE=1,PYTHONUNBUFFERED=1,GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=us-central1,DOCUMENT_AI_PROJECT_ID=75499681521,DOCUMENT_AI_PROCESSOR_ID=599b6ebb19fa1478,DOCUMENT_AI_LOCATION=us"

echo "✅ デプロイ完了！"
echo "🔗 サービスURL: https://$SERVICE_NAME-$REGION.run.app"