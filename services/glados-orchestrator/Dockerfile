# Use a slim Python base image
FROM python:3.11-slim

# THE FIX: Install curl so the healthcheck command can run
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8082

# The command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]