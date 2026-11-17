FROM python:3.13-slim AS runner

ARG UID=1000
ARG GID=1000

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN groupadd --gid ${GID} appuser \
    && useradd --uid ${UID} --gid ${GID} --create-home appuser \
    && mkdir -p /app \
    && chown appuser:appuser /app

WORKDIR /app
USER appuser

COPY --chown=appuser:appuser pyproject.toml ./

RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=${UID},gid=${GID} \
    uv sync --no-install-project