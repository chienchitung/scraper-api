FROM python:3.9-slim

WORKDIR /app

# 安裝編譯工具和依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製並安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 複製應用程式代碼
COPY . .

# 設置環境變數
ENV PYTHONUNBUFFERED=1

# 創建啟動腳本
RUN echo '#!/bin/bash\nPORT="${PORT:-8000}"\necho "Starting server on port $PORT"\nuvicorn main:app --host 0.0.0.0 --port $PORT' > start.sh && \
    chmod +x start.sh

# 運行應用
CMD ["./start.sh"]