FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
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

COPY . .

EXPOSE 8080

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
