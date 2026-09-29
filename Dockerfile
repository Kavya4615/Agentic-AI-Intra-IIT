FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code
COPY backend/ /app/

# Hugging Face Spaces requires port 7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn ingestion.main:app --host 0.0.0.0 --port 7860"]
