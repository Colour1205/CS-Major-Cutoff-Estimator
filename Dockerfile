# Backend API image — the Flask app served by gunicorn. Build from the repo
# root (imports and data paths are all relative to it):
#
#   docker build -t cs-cutoff-backend .
#   docker run -p 5000:5000 -e ADMIN_PASSWORD=... -e SECRET_KEY=... cs-cutoff-backend
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so code changes don't re-install them.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt gunicorn

COPY backend/ backend/

# backend/data is where all runtime state lives (grades.db, the CSVs,
# backtest_results.json) and gets a persistent volume mounted over it on
# Kubernetes. Keep a pristine copy elsewhere so backend/wsgi.py can seed an
# empty volume from it on first start.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && cp -r backend/data /app/seed-data \
    && chown -R app:app backend/data
ENV SEED_DATA_DIR=/app/seed-data

USER app
EXPOSE 5000

# One worker process on purpose (see backend/wsgi.py); threads handle
# concurrent requests. Long timeout for the admin AI-extract call to OpenAI.
CMD ["gunicorn", "backend.wsgi:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", "--threads", "8", \
     "--timeout", "120", \
     "--access-logfile", "-"]
