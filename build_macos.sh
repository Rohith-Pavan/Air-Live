#!/bin/bash
# macOS Build Script for GoLive Studio
# Creates a complete macOS app bundle and DMG installer

set -e  # Exit on any error

echo "========================================"
echo "GoLive Studio - macOS Build Script"
echo "========================================"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8+ from https://python.org or use Homebrew:"
    echo "  brew install python"
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "ERROR: Python $required_version or higher is required, but $python_version is installed"
    exit 1
fi

# Check if we're in a virtual environment (recommended)
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "WARNING: Not running in a virtual environment"
    echo "It's recommended to use a virtual environment"
    echo
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Build cancelled"
        exit 1
    fi
fi

echo
echo "Starting build process..."
echo

# Make sure the build script is executable
chmod +x build_complete.py

# Run the complete build script
python3 build_complete.py

if [ $? -ne 0 ]; then
    echo
    echo "BUILD FAILED!"
    echo "Check the error messages above"
    exit 1
fi

echo
echo "========================================"
echo "BUILD COMPLETED SUCCESSFULLY!"
echo "========================================"
echo
echo "Your app bundle is ready in the dist folder"
echo "If a DMG was created, you can find it in the dist folder"
echo

# Optional: Open the dist folder
if command -v open &> /dev/null; then
    read -p "Open dist folder? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open dist/
    fi
fi