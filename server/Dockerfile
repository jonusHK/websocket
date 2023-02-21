# Use an official Python runtime as a parent image
FROM python:3.10-slim-buster

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port that the application will be running on
EXPOSE 8000

ENV WORKER_CNT ${WORKER_CNT:-$(expr $(grep -c ^processor /proc/cpuinfo || 1) \* 2)}

# Start the FastAPI application with uvicorn
CMD ["gunicorn", "-w", "${WORKER_CNT}", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "main:app"]