# Use a slim Python 3.12 image for a smaller attack surface and faster deployments
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables to ensure Python output is logged immediately and no pyc files are written
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (if needed by any underlying C-extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# CRITICAL: Pre-download the HuggingFace embeddings model during the build phase!
# By running this script now, the model weights are baked directly into the Docker image layer.
# If we didn't do this, Cloud Run would attempt to download a ~100MB model on every single cold start,
# causing massive latency spikes (or timeouts) for the first user request.
RUN python -c "\
from langchain_huggingface import HuggingFaceEmbeddings; \
print('Downloading and caching all-MiniLM-L6-v2 model...'); \
embeddings = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2'); \
print('Model successfully cached in the Docker image!')\
"

# Copy the application source code
COPY . .

# Expose port 8080 (the default port Cloud Run routes traffic to)
EXPOSE 8080

# Command to run the FastAPI app via Uvicorn.
# Note: We use 'api:app' instead of 'main:app' because our FastAPI instance is defined in api.py.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
