# syntax=docker/dockerfile:1.7
FROM python:3.13.13-slim-bookworm AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.13.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN addgroup --system --gid 65532 app && \
    adduser --system --uid 65532 --ingroup app --home /nonexistent --no-create-home app
COPY --from=builder /wheels /wheels
RUN python -m pip install /wheels/*.whl && rm -rf /wheels

USER 65532:65532
WORKDIR /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 8000), 2).close()"]
ENTRYPOINT []
CMD ["bring-shopping-mcp-http"]
