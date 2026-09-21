FROM python:3.11-slim

WORKDIR /app/services

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy requirements manifest
COPY api/requirements.txt ./requirements.txt

# Install dependencies using uv into system site-packages
RUN uv pip install --system --no-cache -r requirements.txt

# Copy remaining services source code
COPY . .

# Expose backend API port
EXPOSE 8000

# Start Uvicorn server with --reload enabled
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
