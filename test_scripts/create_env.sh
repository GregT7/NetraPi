#!/bin/bash
set -e

echo "==> Creating Python 3.9 venv in current directory..."

# Remove existing venv if it exists
if [ -d "venv" ]; then
    echo "Removing existing venv..."
    rm -rf venv
fi

# Create venv with system site packages
python3.9 -m venv venv --system-site-packages

# Activate venv
echo "==> Activating venv..."
source venv/bin/activate

echo "==> Python version:"
python --version

# Upgrade pip tools
echo "==> Upgrading pip..."
python -m pip install --upgrade pip setuptools wheel

# Install packages (order matters)
echo "==> Installing dependencies..."
python -m pip install "numpy<2"
python -m pip install opencv-python==4.8.1.78
python -m pip install pillow
python -m pip install "tflite-runtime==2.11.0"

echo "==> Setup complete!"
echo ""
echo "To activate later, run:"
echo "source venv/bin/activate"