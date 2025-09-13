# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port (Cloud Run uses 8080)
ENV PORT 8080
ENV PYTHONUNBUFFERED=1

# Command to run FastAPI with uvicorn
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT