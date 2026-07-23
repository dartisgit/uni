FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install build tools (useful if your Python deps need compilation)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt ./

# Install Python dependencies if requirements.txt exists
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy repository files
COPY . .

# Recommended env
ENV PYTHONUNBUFFERED=1

# Expose a typical web port (adjust if your app uses another)
EXPOSE 8000

# Default command: try app.py, then main.py, otherwise keep container running and warn
CMD ["sh", "-c", "if [ -f app.py ]; then python app.py; elif [ -f main.py ]; then python main.py; else echo 'No entrypoint found (app.py or main.py). Override CMD in the Dockerfile or configure workflow inputs.' && sleep infinity; fi"]
