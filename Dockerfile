# Use the latest Python image
FROM python:latest

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    apt-utils \
    yt-dlp \
    build-essential \
    libmagic-dev \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libffi-dev \
    liblzma-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python -m pip install --upgrade pip

# Set working directory
WORKDIR /app

# Copy local project files into container
COPY . .

# Install required Python packages
RUN pip install -r requirements.txt

# Start script
CMD ["python", "main.py"]
