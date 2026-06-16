FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend /app/frontend
RUN npm run build

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7.13 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    FRONTEND_STATIC_DIR=/app/frontend-out

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock /app/backend/
RUN uv sync --project backend --no-dev --locked

COPY backend /app/backend
COPY --from=frontend-builder /app/frontend/out /app/frontend-out

EXPOSE 8000

CMD ["uv", "run", "--project", "backend", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
