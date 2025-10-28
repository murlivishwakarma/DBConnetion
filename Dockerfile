# Step 1: Use official lightweight Python image
FROM python:3.11-slim

# Step 2: Set working directory
WORKDIR /app

# Step 3: Copy requirements (if you have one) and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Step 4: Copy your FastAPI project code into container
COPY . .

# Step 5: Expose port 8000 (Render uses it for health checks)
EXPOSE 8000

# Step 6: Start FastAPI app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
