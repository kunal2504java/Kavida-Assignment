FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create data directory for SQLite database
RUN mkdir -p /data

# Expose API port
EXPOSE 8000

# Run the DQ report service
CMD ["python", "-m", "app"]
