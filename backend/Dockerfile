FROM python:3.10-slim

WORKDIR /workspace

# Install system dependencies needed for PostgreSQL client compiling
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend files
COPY . ./backend/

EXPOSE 8000

# Configure PYTHONPATH so python resolves backend imports correctly
ENV PYTHONPATH=/workspace

# Run migrations and start server on boot
CMD ["sh", "-c", "cd backend && alembic upgrade head && python seed.py && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
