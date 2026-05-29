#!/bin/bash

# Remove PostgreSQL Docker container and volume
# This script removes the PostgreSQL container and optionally the volume

set -e

# Load environment variables from .env
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    exit 1
fi

# Source .env file
export $(cat .env | grep -v '^#' | xargs)

# Set defaults
PG_CONTAINER_NAME=${PG_CONTAINER_NAME:-local-postgresql-db}
PG_VOLUME_NAME=${PG_VOLUME_NAME:-krudb_data}

echo "🗑️  Removing PostgreSQL container and volume..."
echo "   Container Name: $PG_CONTAINER_NAME"
echo "   Volume Name: $PG_VOLUME_NAME"
echo ""

# Stop container if running
if docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER_NAME}$"; then
    echo "⏳ Stopping container..."
    docker stop "$PG_CONTAINER_NAME"
fi

# Remove container if exists
if docker ps -a --format '{{.Names}}' | grep -q "^${PG_CONTAINER_NAME}$"; then
    echo "🗑️  Removing container..."
    docker rm "$PG_CONTAINER_NAME"
    echo "✅ Container removed"
else
    echo "ℹ️  Container does not exist"
fi

# Ask about removing volume
echo ""
echo "⚠️  WARNING: Removing the volume will delete all database data!"
read -p "Do you want to remove the volume '$PG_VOLUME_NAME'? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    if docker volume ls --format '{{.Name}}' | grep -q "^${PG_VOLUME_NAME}$"; then
        echo "🗑️  Removing volume..."
        docker volume rm "$PG_VOLUME_NAME"
        echo "✅ Volume removed"
    else
        echo "ℹ️  Volume does not exist"
    fi
else
    echo "ℹ️  Volume preserved"
fi

echo ""
echo "✅ Cleanup complete"
exit 0
