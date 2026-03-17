FROM python:3.13-slim AS backend

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

COPY data/ data/

# --- Frontend build stage ---
FROM node:22-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# --- Final image ---
FROM python:3.13-slim

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=backend /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=backend /usr/local/bin/ /usr/local/bin/
COPY --from=backend /app/ /app/
COPY --from=frontend-build /frontend/dist/ /app/static/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "depgraph.api:app", "--host", "0.0.0.0", "--port", "8000"]
