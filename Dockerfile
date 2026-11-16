# One container: the React app is built first, then served by FastAPI.

# ---- 1. Build the frontend ----
FROM node:24-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. Python runtime ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production

WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/migrations ./migrations
# Editable install: runs from this folder, so the exercise data and migrations are found.
RUN pip install -e . && useradd --create-home --uid 10001 vyayam
COPY --from=web /app/frontend/dist /app/frontend/dist

USER vyayam
ENV PORT=8000
EXPOSE 8000
# Apply any new migrations, then start. --proxy-headers so the login rate limiter
# sees the real client IP behind the host's load balancer.
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
