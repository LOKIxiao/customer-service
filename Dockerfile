FROM python:3.13-slim

WORKDIR /app

# onnxruntime（chromadb 的间接依赖）在部分精简镜像上需要 libgomp1 才能加载
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY data/ ./data/
COPY pytest.ini .

RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
