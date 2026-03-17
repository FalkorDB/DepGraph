FROM python:3.13-slim AS base

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

COPY data/ data/

EXPOSE 8000

CMD ["uvicorn", "depgraph.api:app", "--host", "0.0.0.0", "--port", "8000"]
