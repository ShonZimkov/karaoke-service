FROM python:3.10-slim

# System dependencies required by aeneas
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel

# numpy MUST be installed first
RUN pip install numpy==1.26.4

# install aeneas (works on py3.10)
RUN pip install --no-build-isolation aeneas==1.7.3.0

# install rest of deps (DO NOT include numpy or aeneas here)
RUN pip install -r requirements.txt

COPY . .

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
