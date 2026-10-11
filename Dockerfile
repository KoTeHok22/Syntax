FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install --with-deps chromium

COPY backend backend
COPY scripts scripts
COPY migrations migrations
COPY docs/assets/fonts docs/assets/fonts
COPY alembic.ini .
COPY prompts.json .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
