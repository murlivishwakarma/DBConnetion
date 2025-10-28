# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# system deps for some packages (psycopg2)
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# copy & install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source
COPY . .

# expose port FastAPI will run on
EXPOSE 8000

# run uvicorn (adjust module name if main.py uses different variable)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
