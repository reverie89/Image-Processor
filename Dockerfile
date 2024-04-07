# Use a lightweight Python image
FROM python:3-alpine

ENV GUNICORN_HOST=0.0.0.0
ENV GUNICORN_PORT=8000
ENV GUNICORN_WORKERS=4

# Copy the current directory contents into the container at /app
COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY app /app

# Expose the port the app runs on
EXPOSE ${GUNICORN_PORT}

# Run the application
CMD gunicorn -b ${GUNICORN_HOST}:${GUNICORN_PORT} -w ${GUNICORN_WORKERS} run:app
