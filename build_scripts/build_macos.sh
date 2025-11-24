#!/bin/bash

# macOS Build Script for GoLive Studio (GPU-Accelerated)
echo "Building GoLive Studio for macOS with GPU acceleration..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    exit 1
fi

# Check dependencies
echo "Checking dependencies..."
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
    print(f'Missing dependencies: {missing}')
    print('Install with: pip install -r requirements.txt')
    sys.exit(1)
else:
    print('All dependencies satisfied')
"

if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Auto-detect renderer and encoder support
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
    if encoder_info.get('videotoolbox'):
        print('✓ VideoToolbox encoder available')
    if encoder_info.get('x264'):
        print('✓ x264 software encoder available')
        
except Exception as e:
    print(f'Capability check failed: {e}')
    print('Building with basic support only')
"

# Ensure bundled ffmpeg exists
echo "Ensuring bundled ffmpeg exists..."
mkdir -p build/ffmpeg

# Try multiple methods to get ffmpeg
FFMPEG_FOUND=false

if [ ! -x build/ffmpeg/ffmpeg ]; then
  # Method 1: Check if we already have a local copy
  if [ -x "ffmpeg/ffmpeg" ]; then
    echo "Found local ffmpeg in project directory"
    cp "ffmpeg/ffmpeg" build/ffmpeg/
    chmod +x build/ffmpeg/ffmpeg
    FFMPEG_FOUND=true
  # Method 2: Check system PATH
  elif command -v ffmpeg >/dev/null 2>&1; then
    FFMPEG_PATH=$(command -v ffmpeg)
    echo "Found system ffmpeg at: $FFMPEG_PATH"
    rm -f build/ffmpeg/ffmpeg
    cp "$FFMPEG_PATH" build/ffmpeg/ffmpeg
    chmod +x build/ffmpeg/ffmpeg
    echo "✓ Copied system ffmpeg into build/ffmpeg/ffmpeg"
    FFMPEG_FOUND=true
  fi
  
  # Method 3: Check Homebrew locations
  if [ "$FFMPEG_FOUND" = false ]; then
    for brew_path in "/usr/local/bin/ffmpeg" "/opt/homebrew/bin/ffmpeg"; do
      if [ -x "$brew_path" ]; then
        echo "Found Homebrew ffmpeg at: $brew_path"
        rm -f build/ffmpeg/ffmpeg
        cp "$brew_path" build/ffmpeg/ffmpeg
        chmod +x build/ffmpeg/ffmpeg
        echo "✓ Copied Homebrew ffmpeg into build/ffmpeg/ffmpeg"
        FFMPEG_FOUND=true
        break
      fi
    done
  fi
  
  # Method 3: Download static build if not found
  if [ "$FFMPEG_FOUND" = false ]; then
    echo "FFmpeg not found locally. Attempting to download static build..."
    
    # Try to download FFmpeg from evermeet.cx (macOS static builds)
    if command -v curl >/dev/null 2>&1; then
      echo "Downloading FFmpeg static build for macOS..."
      TEMP_DIR=$(mktemp -d)
      
      # Download the latest FFmpeg release
      if curl -L "https://evermeet.cx/ffmpeg/ffmpeg-6.1.zip" -o "$TEMP_DIR/ffmpeg.zip" 2>/dev/null; then
        echo "Downloaded FFmpeg archive"
        
        # Extract the binary
        if command -v unzip >/dev/null 2>&1; then
          cd "$TEMP_DIR"
          if unzip -q ffmpeg.zip && [ -f ffmpeg ]; then
            cp ffmpeg "$(pwd | sed 's|/tmp.*||')/build/ffmpeg/ffmpeg"
            chmod +x "$(pwd | sed 's|/tmp.*||')/build/ffmpeg/ffmpeg"
            echo "✓ Downloaded and installed FFmpeg static build"
            FFMPEG_FOUND=true
          fi
          cd - >/dev/null
        fi
      fi
      
      # Cleanup
      rm -rf "$TEMP_DIR"
    fi
    
    # If download failed, show manual instructions
    if [ "$FFMPEG_FOUND" = false ]; then
      echo "⚠ FFmpeg download failed. Please install manually:"
      echo "  brew install ffmpeg"
      echo "Or download from: https://evermeet.cx/ffmpeg/"
      echo "ERROR: Build will fail without FFmpeg - streaming/recording features require it."
      exit 1
    fi
  fi
else
  echo "✓ FFmpeg already exists at build/ffmpeg/ffmpeg"
  FFMPEG_FOUND=true
fi

# Verify ffmpeg works
if [ "$FFMPEG_FOUND" = true ] && [ -x build/ffmpeg/ffmpeg ]; then
  echo "Testing bundled ffmpeg..."
  if build/ffmpeg/ffmpeg -version >/dev/null 2>&1; then
    echo "✓ FFmpeg is working correctly"
  else
    echo "⚠ FFmpeg binary exists but may not work properly"
  fi
fi

# Clean previous artifacts to avoid symlink collisions
echo "Cleaning previous build artifacts..."
rm -rf build/GoLive\ Studio dist/GoLive\ Studio dist/GoLive\ Studio.app dist/GoLive\ Studio.dmg "GoLive Studio.spec" || true
mkdir -p build

# Workaround PyInstaller macOS framework symlink collisions
export PYINSTALLER_OSX_FRAMEWORK_SYMLINKS=0

# Locate PyQt6 Qt6 plugins directory (multimedia/plugins)
QT_PLUGINS_DIR=$(python3 - <<'PY'
import sys, os, pathlib
try:
    import PyQt6
    p = pathlib.Path(PyQt6.__file__).parent / 'Qt6' / 'plugins'
    print(p)
except Exception:
    print('')
PY
)

PLUGIN_ARGS=()
if [ -n "$QT_PLUGINS_DIR" ] && [ -d "$QT_PLUGINS_DIR" ]; then
  [ -d "$QT_PLUGINS_DIR/mediaservice" ] && PLUGIN_ARGS+=( --add-data "$QT_PLUGINS_DIR/mediaservice:PyQt6/Qt6/plugins/mediaservice" )
  [ -d "$QT_PLUGINS_DIR/imageformats" ] && PLUGIN_ARGS+=( --add-data "$QT_PLUGINS_DIR/imageformats:PyQt6/Qt6/plugins/imageformats" )
  [ -d "$QT_PLUGINS_DIR/platforms" ] && PLUGIN_ARGS+=( --add-data "$QT_PLUGINS_DIR/platforms:PyQt6/Qt6/plugins/platforms" )
fi

# Create the application bundle
echo "Creating application bundle (onedir .app)..."
pyinstaller --clean --noconfirm "../golive.spec" \
    --add-data "icons:icons" \
    --add-data "effects:effects" \
    --add-data "renderer:renderer" \
    --add-data "encoder:encoder" \
    --add-data "audio:audio" \
    --add-data "resources_rc.py:." \
    --add-data "resources.qrc:." \
    --add-binary "build/ffmpeg/ffmpeg:ffmpeg" \
    "${PLUGIN_ARGS[@]}" \
    --collect-submodules PyQt6.QtCore \
    --collect-submodules PyQt6.QtGui \
    --collect-submodules PyQt6.QtWidgets \
    --collect-submodules PyQt6.QtOpenGL \
    --collect-submodules PyQt6.QtOpenGLWidgets \
    --collect-submodules PyQt6.QtMultimedia \
    --collect-submodules PyQt6.QtMultimediaWidgets \
    --collect-all cv2 \
    --collect-all numpy \
    --collect-all av \
    --collect-all PIL \
    --collect-all OpenGL \
    --exclude-module PyQt6.QtBluetooth \
    --exclude-module PyQt6.QtWebEngineCore \
    --exclude-module PyQt6.QtWebEngineWidgets \
    --exclude-module PyQt6.QtWebEngineQuick \
    --exclude-module PyQt6.Qt3DCore \
    --exclude-module PyQt6.Qt3DRender \
    --exclude-module PyQt6.Qt3DInput \
    --exclude-module PyQt6.Qt3DAnimation \
    --exclude-module PyQt6.QtQml \
    --exclude-module matplotlib \
    --exclude-module scipy \
    --exclude-module pandas \
    --osx-bundle-identifier com.golivestudio.app \
    --target-arch arm64 \
    --name "GoLive Studio" \
    --icon "EditLive.ico" \
    --hidden-import "OpenGL" \
    --hidden-import "OpenGL.GL" \
    --hidden-import "OpenGL.arrays" \
    --hidden-import "numpy" \
    --hidden-import "numpy.core" \
    --hidden-import "numpy.core.multiarray" \
    --hidden-import "renderer" \
    --hidden-import "encoder" \
    --hidden-import "audio" \
    --hidden-import "cv2" \
    --hidden-import "av" \
    --hidden-import "av.audio" \
    --hidden-import "av.video" \
    --hidden-import "av.codec" \
    --hidden-import "transitions" \
    --hidden-import "overlay_manager" \
    --hidden-import "text_overlay" \
    --hidden-import "config" \
    --hidden-import "streaming" \
    --hidden-import "recording" \
    --hidden-import "external_display" \
    --hidden-import "enhanced_external_display" \
    --hidden-import "graphics_output" \
    --hidden-import "enhanced_graphics_output" \
    --hidden-import "recording_settings_dialog" \
    --hidden-import "streaming_settings_dialog_improved" \
    --hidden-import "gpu_streaming" \
    --hidden-import "av_streamer" \
    --hidden-import "ffmpeg_utils" \
    main.py

# Check build success
if [ $? -eq 0 ]; then
    echo "✓ Build complete! Application bundle created in dist/"
    echo "  GPU acceleration: Auto-detected"
    echo "  Renderer backend: OpenGL (macOS)"
    echo "  Encoder support: VideoToolbox + x264"
    echo ""
    echo "To run: ./dist/GoLive\ Studio.app/Contents/MacOS/GoLive\ Studio"
else
    echo "✗ Build failed!"
    exit 1
fi

APP_NAME="GoLive Studio"
APP_PATH="dist/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo "Build failed: $APP_PATH not found."
    exit 1
fi

INFO_PLIST="$APP_PATH/Contents/Info.plist"
echo "Adding camera/microphone usage descriptions to Info.plist..."
if [ -f "$INFO_PLIST" ]; then
  /usr/libexec/PlistBuddy -c "Delete :NSCameraUsageDescription" "$INFO_PLIST" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c "Delete :NSMicrophoneUsageDescription" "$INFO_PLIST" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c "Add :NSCameraUsageDescription string 'GoLive Studio needs camera access to capture video from your inputs.'" "$INFO_PLIST" || true
  /usr/libexec/PlistBuddy -c "Add :NSMicrophoneUsageDescription string 'GoLive Studio needs microphone access to capture audio from your inputs.'" "$INFO_PLIST" || true
else
  echo "WARNING: Info.plist not found at $INFO_PLIST"
fi

echo "Ad-hoc codesigning app bundle..."
codesign --force --deep --sign - "$APP_PATH" || true

echo "App bundle ready at $APP_PATH"

# Create DMG
VOLUME_NAME="${APP_NAME}"
DMG_NAME="${APP_NAME}.dmg"
STAGING_DIR="build/dmg_staging"
mkdir -p "$STAGING_DIR"
rm -rf "$STAGING_DIR"/*
cp -R "$APP_PATH" "$STAGING_DIR/"
[ -e "$STAGING_DIR/Applications" ] || ln -s /Applications "$STAGING_DIR/Applications"

# Calculate size (in MB) with buffer
SIZE_MB=$(du -sm "$STAGING_DIR" | awk '{print $1 + 50}')

mkdir -p dist

echo "Creating DMG ${DMG_NAME} (size ${SIZE_MB}MB)..."
hdiutil create -volname "$VOLUME_NAME" -srcfolder "$STAGING_DIR" -ov -fs HFS+ -format UDZO -size ${SIZE_MB}m "dist/${DMG_NAME}"

echo "DMG created at dist/${DMG_NAME}"
