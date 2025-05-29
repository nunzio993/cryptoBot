FROM python:3.10-slim

WORKDIR /app

ENV PYTHONPATH="/app"

# 1) installa dipendenze
COPY requirements.txt .

RUN apt-get update \
    && apt-get install -y procps \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*


# 2) copia il tuo codice
COPY src/ ./src/
COPY src/core_and_scheduler.py src/scheduler.py ./src/
COPY symbols.py ./
COPY credentials.yaml ./
COPY models.py ./
COPY telegram_bot.py ./
# se hai altri script di entrypoint, copiali qui

# 3) monta i log
VOLUME [ "/app/logs" ]

# 4) comando di avvio
CMD ["python", "-m", "src.scheduler"]


