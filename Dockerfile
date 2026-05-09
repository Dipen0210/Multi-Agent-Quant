FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch first (prevents downloading CUDA variant)
RUN pip install --no-cache-dir \
    torch>=2.4.0 \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download fine-tuned FinBERT so first request isn't slow
ARG FINBERT_MODEL=Dipen0210/finbert-finetuned
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='${FINBERT_MODEL}', device=-1)" || true

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
