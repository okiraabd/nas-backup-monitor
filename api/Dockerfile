FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps (bcrypt/psycopg wheels are prebuilt, but keep build-essential minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh && mkdir -p /app/generated_reports

EXPOSE 8000

CMD ["./entrypoint.sh"]
