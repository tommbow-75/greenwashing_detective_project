# 使用你指定的 3.11-slim 版本
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴 (MySQL 連線有時需要)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴清單並安裝
# 提示：請確保 requirements.txt 包含 google-cloud-storage 與 PyMySQL
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有專案內容
COPY . .

# Cloud Run 預設監聽 8080 端口，使用 Gunicorn 啟動
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app