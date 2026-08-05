#!/bin/bash

echo "==========================================="
echo "🚀 Starting Trust Agent Backend Services"
echo "==========================================="

# 1. Check and start Redis
if ! pgrep -x "redis-server" > /dev/null
then
    echo "[1/3] 🟡 Redis is not running. Starting Redis daemon..."
    redis-server --daemonize yes
    sleep 1
else
    echo "[1/3] 🟢 Redis is already running."
fi

# 2. Start the RQ Worker in the background
echo "[2/3] 🟢 Starting Ingestion Worker (Background)..."
# We run it in the background and redirect output to a log file
python backend/ingest_worker.py > worker.log 2>&1 &
WORKER_PID=$!

# 3. Start the FastAPI server in the foreground
echo "[3/3] 🟢 Starting FastAPI Server..."
cd backend && uvicorn api:app --reload --port 8000

# Cleanup on exit (when user presses Ctrl+C to stop the API)
trap "echo 'Stopping worker...'; kill $WORKER_PID; exit" INT TERM
