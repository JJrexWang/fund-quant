FROM python:3.12-slim
ENV TZ=Asia/Shanghai PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --extra-index-url https://pypi.org/simple
COPY backend/app/ /app/
COPY frontend/ /app/frontend/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
