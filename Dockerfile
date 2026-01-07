FROM python:3.13.2

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # ADD THIS: Prevents apt from waiting for user input
    DEBIAN_FRONTEND=noninteractive 

# Install system dependencies
RUN apt-get update && \
    # ADD apt-utils here to resolve the configuration warning
    apt-get install -y --no-install-recommends apt-utils && \
    apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
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
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

# Start script
CMD ["python", "main.py"]
