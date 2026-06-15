FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ---------- dev stage (hot-reload, mounted volume) ----------
FROM base AS dev
COPY pyproject.toml .
RUN pip install -e ".[dev]"
EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004", "--reload"]

# ---------- prod stage ----------
FROM base AS prod
RUN addgroup --system app && adduser --system --ingroup app app
COPY --chown=app:app pyproject.toml .
RUN pip install .
COPY --chown=app:app app/ ./app/
# Alembic must be in the image so migration can run as a one-off container
# before the service goes live (see `make migrate-swarm` / `make migrate-prod`).
COPY --chown=app:app alembic/ ./alembic/
COPY --chown=app:app alembic.ini .
EXPOSE 8004
USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "2"]
