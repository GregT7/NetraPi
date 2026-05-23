#!/bin/bash

set -e  # Exit immediately on error

echo "========================================"
echo " Coral TPU Full Setup + Validation بدء "
echo "========================================"

########################################
# Step 0: Create working directory
########################################

WORKDIR="$(pwd)/coral_test_env"

echo ""
echo "Creating working directory at:"
echo "$WORKDIR"

mkdir -p "$WORKDIR"
cd "$WORKDIR"

########################################
# Step 1: Check Python
########################################

echo ""
echo "Step 1: Checking Python 3.9..."

if ! command -v python3.9 &> /dev/null; then
    echo "❌ python3.9 not found."
    echo "Install it first (e.g., via make altinstall)."
    exit 1
fi

python3.9 --version

########################################
# Step 2: Create + activate venv
########################################

echo ""
echo "Step 2: Creating virtual environment..."

python3.9 -m venv --system-site-packages NetraPi

echo "Activating virtual environment..."
source NetraPi/bin/activate

python --version

########################################
# Step 3: Install dependencies
########################################

echo ""
echo "Step 3: Installing Coral dependencies..."

echo "Installing compatible pip version..."
pip install "pip<24"

pip install --extra-index-url https://google-coral.github.io/py-repo/ pycoral~=2.0

echo ""
echo "Installing numpy < 2..."
pip install "numpy<2"

########################################
# Step 4: Clone repo
########################################

echo ""
echo "Step 4: Cloning pycoral repo..."

if [ ! -d "pycoral" ]; then
    git clone https://github.com/google-coral/pycoral.git
fi

cd pycoral

########################################
# Step 5: Download test data
########################################

echo ""
echo "Step 5: Downloading model + test data..."

# Run official script (may be incomplete)
bash examples/install_requirements.sh classify_image.py

########################################
# Step 6: USB Detection
########################################

echo ""
echo "Step 6: Checking Coral USB device..."

USB_OUTPUT=$(lsusb)
echo "$USB_OUTPUT"

if echo "$USB_OUTPUT" | grep -Eiq "Global Unichip|Google Inc\.|18d1"; then
    echo "✅ Coral USB detected"
else
    echo "❌ Coral USB NOT detected"
    echo "Troubleshooting:"
    echo "- Replug USB accelerator"
    echo "- Use powered USB hub"
    echo "- Run: dmesg | grep -i usb"
    exit 1
fi

########################################
# Step 7: Run inference tests
########################################

MODEL="test_data/mobilenet_v2_1.0_224_inat_bird_quant_edgetpu.tflite"
LABELS="test_data/inat_bird_labels.txt"

echo ""
echo "Step 7: Running PARROT test..."

PARROT_RESULT=$(python3 examples/classify_image.py \
  --model $MODEL \
  --labels $LABELS \
  --input test_data/parrot.jpg)

echo "$PARROT_RESULT"

########################################
# Step 8: Validate results properly
########################################

echo ""
echo "Step 8: Validating classification results..."

echo "$PARROT_RESULT" > parrot_result.txt

EXPECTED_KEYWORDS="Ara macao|Scarlet Macaw|macaw|parrot"

MATCH=0

for keyword in Ara macao "Scarlet Macaw" macaw parrot; do
    if [[ "$PARROT_RESULT" == *"$keyword"* ]]; then
        MATCH=1
        break
    fi
done

if [ $MATCH -eq 1 ]; then
    echo "✅ Parrot classified correctly (parrot species detected)"
else
    echo "❌ Parrot classification FAILED"
fi

########################################
# Done
########################################

echo ""
echo "========================================"
echo " ✅ Coral TPU Setup + Test COMPLETE"
echo "========================================"

