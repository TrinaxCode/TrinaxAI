FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

WORKDIR /app

COPY requirements.lock ./
RUN python -m pip install --require-hashes -r requirements.lock

# The backend imports the CLI agent and the indexer, so both stay in the image.
COPY app ./app
COPY trinaxai_cli ./trinaxai_cli
COPY config.py index.py rag_api.py trinaxai_core.py trinaxai_index_storage.py pyproject.toml ./

EXPOSE 3333

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3333/health', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3333"]
