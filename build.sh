#!/bin/bash

# Eco Fusion Chatbot Build Script for Render
echo "🚀 Starting Eco Fusion Chatbot build process..."

# Set Python version
export PYTHON_VERSION=3.10.12

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Verify installation
echo "✅ Verifying installation..."
python --version
pip list | grep rasa

# Train Rasa model
echo "🤖 Training Rasa model..."
rasa train

# Verify model training
echo "✅ Verifying model training..."
if [ -d "models" ] && [ "$(ls -A models)" ]; then
    echo "✅ Model trained successfully"
    ls -la models/
else
    echo "❌ Model training failed"
    exit 1
fi

# Test Rasa server startup
echo "🧪 Testing Rasa server startup..."
timeout 30s rasa run --enable-api --cors "*" --port 5005 &
RASA_PID=$!
sleep 10

if curl -f http://localhost:5005/status; then
    echo "✅ Rasa server started successfully"
    kill $RASA_PID
else
    echo "❌ Rasa server startup failed"
    kill $RASA_PID
    exit 1
fi

echo "🎉 Build completed successfully!"
