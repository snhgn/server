FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
COPY wheels/ ./wheels/
RUN pip install --no-cache-dir --no-index --find-links=/app/wheels -r requirements.txt

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
