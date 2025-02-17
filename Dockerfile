# TODO: should make this so that the frontend is built in a builder container
# FROM npm? as builder

FROM python:3.12-slim

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Copy backend and frontend files
COPY backend /app
COPY frontend/build /app/frontend/build

# Run the application
WORKDIR /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
