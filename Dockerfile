FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/apps/api/src
WORKDIR /app
COPY requirements-runtime.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-runtime.lock && useradd --uid 10001 --create-home app
COPY --chown=10001:10001 . .
RUN mkdir -p /app/.runtime && chown -R 10001:10001 /app/.runtime
USER 10001:10001
CMD ["python", "scripts/start_staging.py"]
