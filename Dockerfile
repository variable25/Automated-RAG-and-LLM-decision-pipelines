# Dashboard image: FastAPI serves results/*.csv as JSON plus the built React app.
# No GPU, model or database needed. Cloud Run sets $PORT (8080 by default).

FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src PORT=8080
WORKDIR /app
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt
COPY src/ src/
COPY results/ results/
COPY --from=web /web/dist web/dist
RUN useradd --create-home app
USER app
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn rag_pipeline.api:app --host 0.0.0.0 --port ${PORT}"]
