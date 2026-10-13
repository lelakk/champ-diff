FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml .
COPY app/ app/
COPY services/ services/
RUN pip install .

FROM base AS test

RUN pip install ".[dev]"
COPY tests/ tests/

CMD ["pytest", "-q"]

FROM base AS runtime

RUN useradd --create-home --uid 10001 appuser
USER appuser

CMD ["python", "-m", "app.main"]