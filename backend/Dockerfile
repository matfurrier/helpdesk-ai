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
COPY pyproject.toml .
RUN pip install .
COPY app/ ./app/
EXPOSE 8004

RUN addgroup --system app && adduser --system --ingroup app app
USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "2"]
