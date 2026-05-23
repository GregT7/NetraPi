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
python -m pip install "numpy==1.23.2"
python -m pip install opencv-python==4.8.1.78
python -m pip install pillow==11.3.0
pip install --extra-index-url https://google-coral.github.io/py-repo/ "tflite-runtime==2.5.0.post1"
python -m pip install scikit-learn joblib
# Pi GPIO for buzzer (BCM 18). System python3-rpi-lgpio is often invisible to a
# pyenv/local 3.9 venv even with --system-site-packages.
python -m pip install rpi-lgpio

echo "==> Setup complete!"
echo ""
echo "To activate later, run:"
echo "source venv/bin/activate"