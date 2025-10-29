#!/usr/bin/env bash
# Build script for Render deployment
# This helps optimize the build time

echo "🚀 Starting optimized build..."

# Upgrade pip first
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies with caching
echo "📥 Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "✅ Build complete!"
