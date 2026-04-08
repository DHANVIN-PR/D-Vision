# ─── Stage: Production Image ───────────────────────────────────────────────
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Create the uploads folder (in case it's not tracked by git)
RUN mkdir -p static/uploads

# Expose the port Azure App Service will use
EXPOSE 8000

# Start the app with Gunicorn (production WSGI server, NOT flask dev server)
# --workers 2        → 2 worker processes
# --bind 0.0.0.0     → listen on all interfaces
# app:app            → module:flask_app_variable
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "--timeout", "120", "app:app"]
