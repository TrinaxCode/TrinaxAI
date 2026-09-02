FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

WORKDIR /app

COPY requirements.lock ./
RUN python -m pip install --require-hashes -r requirements.lock

ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid "${APP_GID}" trinaxai \
  && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --home-dir /tmp/trinaxai --shell /usr/sbin/nologin trinaxai

# The backend imports the shared agent core and the indexer.
COPY app ./app
COPY trinaxai_agent ./trinaxai_agent
COPY trinaxai_cli ./trinaxai_cli
COPY config.py index.py rag_api.py recovery_server.py service_manager.py trinaxai_core.py trinaxai_errors.py trinaxai_index_documents.py trinaxai_index_state.py trinaxai_index_storage.py pyproject.toml ./
RUN mkdir -p /app/storage /data/projects \
  && chown -R trinaxai:trinaxai /app /data /tmp/trinaxai

USER trinaxai

EXPOSE 3333

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3333/ready', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3333"]
