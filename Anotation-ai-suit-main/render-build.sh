#!/bin/bash
set -e

echo "Installing backend dependencies..."
cd backend
pip install --no-cache-dir -r requirements.txt

echo "Installing frontend dependencies..."
cd ../frontend
# Try yarn first, fallback to npm
if command -v yarn &> /dev/null; then
    yarn install --frozen-lockfile || npm install
else
    npm install
fi

echo "Building frontend..."
if command -v yarn &> /dev/null && [ -f yarn.lock ]; then
    yarn build
else
    npm run build
fi

echo "Build complete!"
