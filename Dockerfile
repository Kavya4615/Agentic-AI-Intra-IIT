FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code
COPY backend/ /app/

# Expose port (Koyeb defaults to 8000, Hugging Face to 7860)
# We will use the $PORT environment variable, falling back to 8000
CMD ["sh", "-c", "uvicorn ingestion.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
