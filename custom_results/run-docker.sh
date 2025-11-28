#!/bin/bash

# Docker run script for single-folder project

set -e

echo "🚀 Starting Indic Translation Project in Docker..."

# Check if large model files exist
if [ ! -f "*.gguf" ] && [ ! -f "*.bin" ]; then
    echo "⚠️  Warning: No large model files found in current directory."
    echo "   Please ensure your model files are in this folder."
fi

# Build the image
echo "📦 Building Docker image..."
docker-compose build

# Run the container
echo "🐳 Starting container..."
docker-compose up indic-project

echo "✅ Container stopped. Outputs should be in ./outputs/ directory"
