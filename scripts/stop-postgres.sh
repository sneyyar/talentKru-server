#!/bin/bash

# Stop PostgreSQL Docker container
# This script stops the PostgreSQL container started by start-postgres.sh

set -e

# Load environment variables from .env
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    exit 1
fi

# Source .env file
export $(cat .env | grep -v '^#' | xargs)

# Set default container name
PG_CONTAINER_NAME=${PG_CONTAINER_NAME:-local-postgresql-db}

echo "🛑 Stopping PostgreSQL container..."
echo "   Container Name: $PG_CONTAINER_NAME"
echo ""

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${PG_CONTAINER_NAME}$"; then
    echo "⚠️  Container '$PG_CONTAINER_NAME' does not exist"
    exit 0
fi

# Check if it's running
if docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER_NAME}$"; then
    echo "⏳ Stopping container..."
    docker stop "$PG_CONTAINER_NAME"
    echo "✅ Container stopped"
else
    echo "ℹ️  Container is not running"
fi

exit 0
