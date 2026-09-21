FROM python:3.13.15-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY api ./api
COPY core ./core
COPY ingestion ./ingestion
COPY providers ./providers
COPY storage ./storage
RUN python -m pip install --prefix=/install .

FROM python:3.13.15-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/uttg/.local/bin:$PATH

RUN groupadd --gid 10001 uttg \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin uttg

WORKDIR /app
COPY --from=builder /install /usr/local
COPY alembic.ini ./alembic.ini

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
