FROM python:3.11-slim

WORKDIR /app

# システムパッケージの更新とOpenCV依存関係をインストール
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 必要なPythonパッケージをインストール
RUN pip install --no-cache-dir \
    pyyaml \
    python-dotenv \
    PyMuPDF \
    Pillow \
    opencv-python-headless \
    numpy \
    google-cloud-aiplatform \
    google-cloud-documentai \
    ultralytics \
    vertexai

# プロジェクトファイルをコピー
COPY . /app/

# 環境変数設定
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["bash"]