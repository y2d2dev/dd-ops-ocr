#!/bin/bash

echo "Dockerでconvert_to_contract_schema関数をテスト中..."

# Dockerイメージをビルド
echo "Dockerイメージをビルド中..."
docker build -t contract-test .

# テストを実行（.envファイルを読み込んでコンテナ内でテストスクリプトを実行）
echo "テストを実行中..."
docker run --rm \
  --env-file .env \
  -v $(pwd)/example.txt:/app/example.txt \
  -v $(pwd):/app/output \
  contract-test \
  python test_contract_schema.py example.txt output/docker_test_result.json

echo "テスト完了！結果はdocker_test_result.jsonに保存されました。"