FROM python:3.13-slim AS runner

ARG UID=1000
ARG GID=1000

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid ${GID} appuser \
    && useradd --uid ${UID} --gid ${GID} --create-home appuser \
    && mkdir -p /app /home/appuser/.cache/uv /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /app /home/appuser/.cache

WORKDIR /app
USER appuser

COPY --chown=appuser:appuser pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=${UID},gid=${GID} \
    uv sync --frozen --no-install-project
