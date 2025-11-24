#!/bin/bash

# Linux Build Script for GoLive Studio (GPU-Accelerated)
echo "Building GoLive Studio for Linux with GPU acceleration..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    echo "Install with: sudo apt-get install python3 python3-pip"
    exit 1
fi

# Check system dependencies
echo "Checking system dependencies..."
MISSING_DEPS=()

# Check for OpenGL development libraries
if ! pkg-config --exists gl; then
    MISSING_DEPS+=("libgl1-mesa-dev")
fi

# Check for audio libraries
if ! pkg-config --exists alsa; then
    MISSING_DEPS+=("libasound2-dev")
fi

if ! pkg-config --exists libpulse; then
    MISSING_DEPS+=("libpulse-dev")
fi

# Check for FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    MISSING_DEPS+=("ffmpeg")
fi

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    echo "Missing system dependencies: ${MISSING_DEPS[*]}"
    echo "Install with: sudo apt-get install ${MISSING_DEPS[*]}"
    echo "Or equivalent for your distribution"
    exit 1
fi

# Check Python dependencies
echo "Checking Python dependencies..."
python3 -c "
import sys
missing = []
try:
    import PyQt6
except ImportError:
    missing.append('PyQt6')
try:
    import OpenGL
except ImportError:
    missing.append('PyOpenGL')
try:
    import numpy
except ImportError:
    missing.append('numpy')

if missing:
    print(f'Missing Python dependencies: {missing}')
    print('Install with: pip3 install -r requirements.txt')
    sys.exit(1)
else:
    print('All Python dependencies satisfied')
"

if [ $? -ne 0 ]; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Auto-detect GPU capabilities
echo "Detecting GPU capabilities..."
python3 -c "
try:
    from renderer.migration_helper import check_gpu_support
    from encoder import check_encoder_support
    
    gpu_info = check_gpu_support()
    encoder_info = check_encoder_support()
    
    print(f'GPU Support: {gpu_info}')
    print(f'Encoder Support: {encoder_info}')
    
    if gpu_info.get('opengl_available'):
        print('✓ OpenGL renderer available')
    if encoder_info.get('nvenc'):
        print('✓ NVENC encoder available')
    if encoder_info.get('x264'):
        print('✓ x264 software encoder available')
        
except Exception as e:
    print(f'Capability check failed: {e}')
    print('Building with basic support only')
"

# Create the Linux executable
echo "Creating Linux executable..."
pyinstaller --onefile \
    --add-data "icons:icons" \
    --add-data "effects:effects" \
    --add-data "renderer:renderer" \
    --add-data "encoder:encoder" \
    --add-data "audio:audio" \
    --name "golive-studio" \
    --hidden-import "OpenGL" \
    --hidden-import "OpenGL.GL" \
    --hidden-import "numpy" \
    --hidden-import "renderer" \
    --hidden-import "encoder" \
    --hidden-import "audio" \
    main.py

# Check build success
if [ $? -eq 0 ]; then
    echo "✓ Build complete! Executable created in dist/"
    echo "  GPU acceleration: Auto-detected"
    echo "  Renderer backend: OpenGL (Linux)"
    echo "  Encoder support: NVENC + x264"
    echo ""
    echo "To run: ./dist/golive-studio"
    
    # Create desktop entry
    echo "Creating desktop entry..."
    cat > "dist/golive-studio.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=GoLive Studio
Comment=Cross-platform live streaming and recording application
Exec=$(pwd)/dist/golive-studio
Icon=$(pwd)/icons/Record.png
Terminal=false
Categories=AudioVideo;Video;
EOF
    
    echo "Desktop entry created: dist/golive-studio.desktop"
    echo "To install system-wide: sudo cp dist/golive-studio.desktop /usr/share/applications/"
    
else
    echo "✗ Build failed!"
    exit 1
fi
