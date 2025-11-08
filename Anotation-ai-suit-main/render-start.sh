#!/bin/bash
set -e

echo "Starting application on port $PORT..."
cd /opt/render/project/src/backend

# Reduce glibc allocator arenas (helps low-RAM)
export MALLOC_ARENA_MAX=2

# Ensure uploads directory exists
mkdir -p uploads

# Start the backend server (single worker, lower keepalive, no access logs for lower RAM)
python -m uvicorn server:app \
  --host 0.0.0.0 \
  --port $PORT \
  --workers 1 \
  --timeout-keep-alive 5 \
  --no-access-log
