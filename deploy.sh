#!/bin/bash

# Cloud Run デプロイスクリプト (512MB最適化版)

# 設定
PROJECT_ID="your-project-id"
SERVICE_NAME="dd-ops-ocr-api"
REGION="asia-northeast1"  # 東京リージョン
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Cloud Run デプロイを開始します (512MB構成)..."

# 1. 軽量Dockerイメージをビルド
echo "📦 軽量Dockerイメージをビルド中..."
docker build -t $IMAGE_NAME \
  --build-arg INSTALL_ULTRALYTICS=false \
  .

# 2. Container Registryにプッシュ
echo "⬆️  Container Registryにプッシュ中..."
docker push $IMAGE_NAME

# 3. Cloud Runにデプロイ (512MB設定)
echo "🌐 Cloud Runにデプロイ中 (512MB構成)..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 540 \
  --concurrency 5 \
  --max-instances 5 \
  --min-instances 0 \
  --cpu-throttling \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --set-env-vars "GCS_BUCKET_NAME=your-bucket-name" \
  --set-env-vars "DD_OPS_MODELS_BUCKET=dd_ops_models" \
  --set-env-vars "PORT=8080" \
  --set-env-vars "PYTHONDONTWRITEBYTECODE=1" \
  --set-env-vars "PYTHONUNBUFFERED=1"

echo "✅ デプロイ完了！"
echo "🔗 サービスURL: https://$SERVICE_NAME-$REGION-$PROJECT_ID.run.app"
echo "💡 512MB構成でデプロイしました。重い処理の場合はタイムアウトする可能性があります。"