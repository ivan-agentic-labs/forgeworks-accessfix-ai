FROM public.ecr.aws/docker/library/python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/apps/api/src
WORKDIR /app
COPY requirements-runtime.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-runtime.lock && useradd --uid 10001 --create-home app
COPY --chown=10001:10001 . .
RUN mkdir -p /app/.runtime && chown -R 10001:10001 /app/.runtime
RUN install -m 0644 infra/environments/staging/supabase-prod-ca-2021.crt /usr/local/share/ca-certificates/supabase-prod-ca-2021.crt && update-ca-certificates
USER 10001:10001
CMD ["python", "scripts/start_staging.py"]
