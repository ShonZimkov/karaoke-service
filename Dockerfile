FROM python:3.11-slim

# System deps needed by aeneas + audio handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Upgrade build tooling
RUN pip install --upgrade pip setuptools wheel

# 1) Install numpy FIRST (in the real env)
RUN pip install numpy==1.26.4

# 2) Install aeneas WITHOUT build isolation (so it can see numpy)
RUN pip install --no-build-isolation aeneas==1.7.3.0

# 3) Install the rest (remove numpy from requirements.txt to avoid duplicates)
RUN pip install -r requirements.txt

COPY . .

# Railway usually provides PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
