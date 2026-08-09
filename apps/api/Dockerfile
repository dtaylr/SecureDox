FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api:/app/packages/shared/python:/app/packages/observability/python

WORKDIR /app

COPY packages/shared/python packages/shared/python
COPY packages/observability/python packages/observability/python
COPY apps/api/requirements.txt apps/api/requirements.txt
COPY apps/api apps/api

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        -e packages/shared/python \
        -e packages/observability/python \
        -r apps/api/requirements.txt

WORKDIR /app/apps/api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
