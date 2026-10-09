#!/usr/bin/env bash
set -e

echo "=== BurstOps Demo Service Build ==="
echo "1. Installing Python dependencies..."
pip install -r requirements-demo.txt

echo "2. Building React frontend..."
cd frontend
npm install
npm run build
cd ..

echo "=== Build Complete! Ready for startCommand ==="
