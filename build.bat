@echo off
REM Eco Fusion Chatbot Build Script for Render (Windows)

echo 🚀 Starting Eco Fusion Chatbot build process...

REM Set Python version
set PYTHON_VERSION=3.10.12

REM Upgrade pip
echo 📦 Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo 📦 Installing Python dependencies...
pip install -r requirements.txt

REM Verify installation
echo ✅ Verifying installation...
python --version
pip list | findstr rasa

REM Train Rasa model
echo 🤖 Training Rasa model...
rasa train

REM Verify model training
echo ✅ Verifying model training...
if exist models\*.tar.gz (
    echo ✅ Model trained successfully
    dir models\
) else (
    echo ❌ Model training failed
    exit /b 1
)

echo 🎉 Build completed successfully!
