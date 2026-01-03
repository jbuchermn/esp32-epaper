#!/usr/bin/env bash

# Configuration
PORT=${1:-/dev/ttyUSB0}  # Default to /dev/ttyUSB0, or use first argument
BAUD=${2:-115200}        # Default baud rate

# Python files to upload
FILES=("code.py" "fronius_api.py" "network.py")

echo "=== CircuitPython Upload Script ==="
echo "Port: $PORT"
echo "Baud: $BAUD"
echo "=================================="

# Check if ampy is installed
if ! command -v ampy &> /dev/null; then
    echo "Error: ampy is not installed."
    echo "Install with: pip install adafruit-ampy"
    exit 1
fi

# Check if port exists
if [ ! -e "$PORT" ]; then
    echo "Error: Port $PORT does not exist."
    echo "Available ports:"
    ls /dev/tty* 2>/dev/null | grep -E "(USB|ACM)" || echo "No serial ports found"
    exit 1
fi

echo "Checking device connection..."
if ! ampy --port $PORT --baud $BAUD ls &> /dev/null; then
    echo "Error: Cannot connect to device on $PORT"
    echo "Make sure:"
    echo "1. Device is connected via USB"
    echo "2. Device is in CircuitPython mode"
    echo "3. No other program is using the port"
    exit 1
fi

echo "Connection successful!"
echo ""

# Upload each file
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Uploading $file..."
        if ampy --port $PORT --baud $BAUD put "$file"; then
            echo "✓ $file uploaded successfully"
        else
            echo "✗ Failed to upload $file"
            exit 1
        fi
    else
        echo "✗ File $file not found"
        exit 1
    fi
    echo ""
done

echo "=== Upload Complete ==="
