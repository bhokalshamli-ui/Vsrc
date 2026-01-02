FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app/ ./app/

# Expose dynamic port
EXPOSE 8000

# Use exec form + env substitution
CMD exec uvicorn "app.main:app" --host 0.0.0.0 --port "${PORT:-8000}"
