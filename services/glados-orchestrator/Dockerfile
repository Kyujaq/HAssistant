# Use a slim Python base image
FROM python:3.11-slim

# Install wget for the Docker healthcheck and curl for debugging
RUN apt-get update \
    && apt-get install -y --no-install-recommends wget curl \
    && rm -rf /var/lib/apt/lists/*
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