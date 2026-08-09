FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
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
        -r apps/worker/requirements.txt

WORKDIR /app/apps/worker

EXPOSE 9100

CMD ["python", "-m", "worker.main"]
