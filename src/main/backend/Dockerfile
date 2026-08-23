FROM python:3.9-slim-bookworm

WORKDIR /netrapi

COPY backend/requirements.txt /netrapi/backend/requirements.txt
RUN pip install --no-cache-dir -r /netrapi/backend/requirements.txt

COPY db /netrapi/db
COPY backend /netrapi/backend

WORKDIR /netrapi/backend
ENV PYTHONPATH=/netrapi:/netrapi/backend

EXPOSE 8000
CMD ["sh", "-c", "python -m alembic -c /netrapi/db/alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
