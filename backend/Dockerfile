FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embeddings to cache model weights in the image layer.
# Prevents ~100MB download on cold starts.
RUN python -c "\
from langchain_huggingface import HuggingFaceEmbeddings; \
print('Downloading and caching all-MiniLM-L6-v2 model...'); \
embeddings = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2'); \
print('Model successfully cached in the Docker image!')\
"

# Pre-download cross-encoder model to prevent runtime downloads
RUN python -c "\
from sentence_transformers import CrossEncoder; \
print('Downloading and caching cross-encoder...'); \
encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512); \
print('Cross-encoder successfully cached in the Docker image!')\
"

COPY . .

EXPOSE 8080

CMD ["./start.sh"]
