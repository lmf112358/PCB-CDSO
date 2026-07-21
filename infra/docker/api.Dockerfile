FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/app/.local/bin:${PATH}"

RUN addgroup --system app && adduser --system --ingroup app --home /home/app app
WORKDIR /app/services/api

COPY services/api/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY services/api/pyproject.toml ./pyproject.toml
COPY services/api/alembic.ini ./alembic.ini
COPY services/api/alembic ./alembic
COPY services/api/src ./src
RUN pip install --no-cache-dir --no-deps . && chown -R app:app /app

USER app
EXPOSE 8000
CMD ["uvicorn", "pcb_cdso.main:app", "--host", "0.0.0.0", "--port", "8000"]
