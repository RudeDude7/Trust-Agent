#!/bin/bash
echo "Starting Redis server..."
redis-server --daemonize yes

echo "Starting Ingestion Worker..."
python ingest_worker.py &

echo "Starting FastAPI Server..."
uvicorn api:app --host 0.0.0.0 --port 8080
