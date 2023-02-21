# Use an official Python runtime as a parent image
FROM python:3.10-slim-buster

# Set the working directory to /app
WORKDIR /app

ENV PYTHONPATH=/app

# Copy the rest of the application code into the container
COPY ./ ./

WORKDIR /app/server

# Install any needed packages specified in requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Expose the port that the application will be running on
EXPOSE 8000

# ENV WORKER_CNT $(expr $(grep -c ^processor /proc/cpuinfo || 1) \* 2)

# Start the FastAPI application with uvicorn
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "server.main:app"]