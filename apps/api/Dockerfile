FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
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
        -r apps/api/requirements.txt \
    && addgroup --system securedox \
    && adduser --system --ingroup securedox --home /home/securedox securedox \
    && mkdir -p /var/lib/securedox/storage \
    && chown -R securedox:securedox /app /var/lib/securedox /home/securedox

WORKDIR /app/apps/api

EXPOSE 8000

USER securedox

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
