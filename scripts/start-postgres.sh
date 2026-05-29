#!/bin/bash

# Start PostgreSQL Docker container with environment variables from .env
# This script reads PG_* variables from .env and starts a PostgreSQL container

set -e

# Load environment variables from .env
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Source .env file
export $(cat .env | grep -v '^#' | xargs)

# Validate required variables
if [ -z "$PG_ADMIN_PASSWORD" ]; then
    echo "❌ Error: PG_ADMIN_PASSWORD not set in .env"
    exit 1
fi

if [ -z "$POSTGRESQL_DATA_DIR" ]; then
    echo "❌ Error: POSTGRESQL_DATA_DIR not set in .env"
    exit 1
fi

# Set defaults for optional variables
PG_CONTAINER_NAME=${PG_CONTAINER_NAME:-local-postgresql-db}
PG_IMAGE=${PG_IMAGE:-pgvector/pgvector:pg17}
PG_DATABASE_NAME=${PG_DATABASE_NAME:-krudb}
PG_PORT=${PG_PORT:-5432}
PG_VOLUME_NAME=${PG_VOLUME_NAME:-krudb_data}

echo "🚀 Starting PostgreSQL container..."
echo "   Container Name: $PG_CONTAINER_NAME"
echo "   Image: $PG_IMAGE"
echo "   Database: $PG_DATABASE_NAME"
echo "   Port: $PG_PORT"
echo "   Volume: $PG_VOLUME_NAME"
echo ""

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${PG_CONTAINER_NAME}$"; then
    echo "⚠️  Container '$PG_CONTAINER_NAME' already exists"
    
    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER_NAME}$"; then
        echo "✅ Container is already running"
        exit 0
    else
        echo "🔄 Starting existing container..."
        docker start "$PG_CONTAINER_NAME"
        echo "✅ Container started"
        exit 0
    fi
fi

# Create volume if it doesn't exist
if ! docker volume ls --format '{{.Name}}' | grep -q "^${PG_VOLUME_NAME}$"; then
    echo "📦 Creating Docker volume: $PG_VOLUME_NAME"
    docker volume create "$PG_VOLUME_NAME"
fi

# Start the container
docker run -d \
    --name "$PG_CONTAINER_NAME" \
    -e POSTGRES_PASSWORD="$PG_ADMIN_PASSWORD" \
    -e POSTGRES_DB="$PG_DATABASE_NAME" \
    -p "$PG_PORT:5432" \
    -v "$PG_VOLUME_NAME:$POSTGRESQL_DATA_DIR" \
    "$PG_IMAGE"

echo "✅ PostgreSQL container started successfully"
echo ""
echo "📝 Connection details:"
echo "   Host: localhost"
echo "   Port: $PG_PORT"
echo "   Database: $PG_DATABASE_NAME"
echo "   Admin User: postgres"
echo "   Admin Password: (from PG_ADMIN_PASSWORD in .env)"
echo ""
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 3

# Wait for PostgreSQL to be ready
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec "$PG_CONTAINER_NAME" pg_isready -U postgres > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        exit 0
    fi
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts..."
    sleep 1
done

echo "❌ PostgreSQL failed to start within timeout"
exit 1
