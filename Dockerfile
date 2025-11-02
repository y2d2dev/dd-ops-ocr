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
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 必要なPythonパッケージをインストール（メモリ効率を考慮）
RUN pip install --no-cache-dir --compile \
    pyyaml \
    python-dotenv \
    PyMuPDF \
    Pillow \
    opencv-python-headless \
    numpy \
    google-cloud-aiplatform \
    vertexai \
    google-cloud-documentai \
    flask \
    gunicorn \
    google-cloud-storage \
    psycopg2-binary \
    && pip cache purge

# ultralytics は重いので条件付きでインストール（環境変数で制御）
ARG INSTALL_ULTRALYTICS=false
RUN if [ "$INSTALL_ULTRALYTICS" = "true" ] ; then pip install --no-cache-dir ultralytics ; fi

# プロジェクトファイルをコピー
COPY . /app/

# 書き込み可能ディレクトリを作成
RUN mkdir -p /tmp/pdf /tmp/result /tmp/data/models

# 環境変数設定
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Cloud Run用：メモリ効率を重視したGunicorn設定
CMD exec gunicorn --bind :$PORT \
    --workers 1 \
    --threads 2 \
    --worker-class sync \
    --max-requests 100 \
    --max-requests-jitter 10 \
    --preload \
    --timeout 540 \
    --worker-tmp-dir /dev/shm \
    src.api.main:app