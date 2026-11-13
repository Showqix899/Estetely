FROM python:3.12-slim

# Don't write .pyc files, and print logs straight away
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install the Python packages first (Docker caches this step)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the project code
COPY . .
