# 使用輕量級的 Python 3.10
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴 (PyMySQL 和一些加密套件可能需要 gcc)
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    musl-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements 並安裝
COPY requirements.txt .
# 補上 gunicorn (正式環境用的 Web Server)
RUN pip install --no-cache-dir -r requirements.txt && pip install gunicorn

# 複製所有程式碼
COPY . .

# 設定環境變數 (讓 output 直接顯示在 Log)
ENV PYTHONUNBUFFERED=1

# 開放 8080 port
EXPOSE 8080

# 啟動指令：使用 gunicorn 執行 app:app
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "app:app"]
# 格式：gcloud builds submit --tag gcr.io/[專案ID]/[映像檔名稱]
# gcloud builds submit --tag gcr.io/greenwash-485301/esg-app:test