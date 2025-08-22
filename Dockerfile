# Use a Python 3.12 base to ensure compatible wheels for pandas/numpy
FROM python:3.12-slim

# System deps for scientific Python (pandas, numpy), build tools, and timezone
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
     build-essential \
     curl \
     tzdata \
  && rm -rf /var/lib/apt/lists/*

# Set timezone to Asia/Kolkata (IST)
ENV TZ=Asia/Kolkata

# Create app directory
WORKDIR /app

# Copy backend requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
  && pip install -r /app/requirements.txt

# Copy backend source
COPY . /app

# Expose default port (Render will pass $PORT)
EXPOSE 5000

# Default command uses gunicorn with eventlet worker and binds to $PORT
# If you prefer Python directly, replace CMD with: ["python", "app.py"]
CMD ["sh", "-c", "gunicorn -k eventlet -w 1 -b 0.0.0.0:${PORT:-5000} app:app"]
