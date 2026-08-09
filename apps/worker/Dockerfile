FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/apps/api:/app/apps/worker:/app/packages/shared/python:/app/packages/observability/python

WORKDIR /app

COPY packages/shared/python packages/shared/python
COPY packages/observability/python packages/observability/python
COPY apps/api apps/api
COPY apps/worker/requirements.txt apps/worker/requirements.txt
COPY apps/worker apps/worker

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        -e packages/shared/python \
        -e packages/observability/python \
        -r apps/api/requirements.txt \
        -r apps/worker/requirements.txt \
    && addgroup --system securedox \
    && adduser --system --ingroup securedox --home /home/securedox securedox \
    && mkdir -p /var/lib/securedox/storage \
    && chown -R securedox:securedox /app /var/lib/securedox /home/securedox

WORKDIR /app/apps/worker

EXPOSE 9100

USER securedox

CMD ["python", "-m", "worker.main"]
