FROM python:3.13-slim AS runner

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project