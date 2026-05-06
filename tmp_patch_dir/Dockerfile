FROM mcr.microsoft.com/devcontainers/python:3.10

# システム依存関係のインストール (FAISSやPDF処理用)
RUN apt-get update && apt-get install -y \
    build-essential \
    libopenblas-dev \
    libomp-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 依存パッケージのインストール
COPY requirements.txt /tmp/pip-tmp/
RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp

# アプリケーションを `WORKDIR` に配置
WORKDIR /app
COPY . /app

# Streamlit が利用するポート
EXPOSE 8501

# デフォルト実行コマンド: Streamlit をフォアグラウンドで起動
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.headless=true"]