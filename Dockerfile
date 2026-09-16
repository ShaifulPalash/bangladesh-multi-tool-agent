# Simple, small image for running the Streamlit UI.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so Docker can cache this layer across rebuilds
# when only application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project.
COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8501

# Healthcheck matches Streamlit's default health endpoint (pure Python, so
# we don't need to install curl in this slim base image).
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
