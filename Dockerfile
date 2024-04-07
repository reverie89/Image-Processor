# Use a lightweight Python image
FROM python:alpine

# Copy the current directory contents into the container at /app
COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY app /app

# Expose the port the app runs on
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
