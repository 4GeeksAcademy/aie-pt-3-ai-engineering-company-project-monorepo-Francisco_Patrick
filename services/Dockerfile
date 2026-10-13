FROM python:3.11-slim

WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy requirements manifest for efficient Docker layer caching
COPY services/api/requirements.txt ./services/requirements.txt

# Install dependencies using uv into system site-packages
RUN uv pip install --system --no-cache -r ./services/requirements.txt

# Copy shared modules (required by services/api/main.py for CSV analyzer engine) and services source code
COPY shared/ ./shared/
COPY services/ ./services/

WORKDIR /app/services

# Ensure /app and /app/services are on the Python search path
ENV PYTHONPATH=/app:/app/services

# Expose backend API port
EXPOSE 8000

# Start Uvicorn server with --reload enabled for development
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
