FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

WORKDIR /app/backend
ENV PORT=8080
EXPOSE 8080

# 2 workers (chacun ~190 Mo au pire, voix Piper chargee) pour tenir dans les
# 512 Mo de Render ; recyclage periodique contre la fragmentation memoire.
CMD ["sh", "-c", "gunicorn -w 2 --worker-class gthread --threads 8 --timeout 60 --max-requests 1000 --max-requests-jitter 100 -b 0.0.0.0:${PORT} app:app"]
