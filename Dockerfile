FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# CPU wheels; quote version specifiers so the shell cannot treat them as redirection.
RUN pip install --no-cache-dir 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home research \
    && mkdir -p /app/runtime \
    && chown research:research /app/runtime
USER research
ENV RESEARCH_DB=/app/runtime/research.sqlite3 \
    ENABLE_LEGACY_ANALYSIS=false \
    LANGCHAIN_TRACING_V2=false \
    LANGSMITH_TRACING=false \
    HF_HUB_OFFLINE=1
# Model weights are not downloaded or silently substituted during image build.
# For local use publish only: -p 127.0.0.1:8000:8000
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
