@echo off
REM Windows Build Script for GoLive Studio (GPU-Accelerated)
echo Building GoLive Studio for Windows with GPU acceleration...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is required but not installed.
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check dependencies
echo Checking dependencies...
python -c "import sys; missing = []; [missing.append(m) for m in ['PyQt6', 'OpenGL', 'numpy'] if __import__('importlib').util.find_spec(m) is None]; print(f'Missing: {missing}') if missing else print('All dependencies satisfied'); sys.exit(1) if missing else sys.exit(0)" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Auto-detect GPU capabilities
echo Detecting GPU capabilities...
python -c "try: from renderer.migration_helper import check_gpu_support; from encoder import check_encoder_support; gpu_info = check_gpu_support(); encoder_info = check_encoder_support(); print(f'GPU Support: {gpu_info}'); print(f'Encoder Support: {encoder_info}'); [print('✓ OpenGL renderer available') if gpu_info.get('opengl_available') else None]; [print('✓ D3D renderer available') if gpu_info.get('d3d_available') else None]; [print('✓ NVENC encoder available') if encoder_info.get('nvenc') else None]; [print('✓ x264 software encoder available') if encoder_info.get('x264') else None]; except Exception as e: print(f'Capability check failed: {e}'); print('Building with basic support only')"

REM Ensure bundled ffmpeg exists for Windows
echo Ensuring bundled ffmpeg exists...
if not exist "build\ffmpeg" mkdir "build\ffmpeg"

if not exist "build\ffmpeg\ffmpeg.exe" (
    echo FFmpeg not found. Attempting to download...
    
    REM Try to download FFmpeg from gyan.dev (Windows builds)
    where curl >nul 2>&1
    if %errorlevel% equ 0 (
        echo Downloading FFmpeg for Windows...
        curl -L "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-6.1-essentials_build.zip" -o "ffmpeg_temp.zip"
        
        REM Extract using PowerShell (available on Windows 10+)
        powershell -command "Expand-Archive -Path 'ffmpeg_temp.zip' -DestinationPath 'ffmpeg_temp' -Force"
        
        REM Find and copy the ffmpeg.exe binary
        for /r "ffmpeg_temp" %%i in (ffmpeg.exe) do (
            copy "%%i" "build\ffmpeg\ffmpeg.exe"
            echo ✓ Downloaded and installed FFmpeg
            goto :ffmpeg_found
        )
        
        :ffmpeg_found
        REM Cleanup
        del /q "ffmpeg_temp.zip" >nul 2>&1
        rmdir /s /q "ffmpeg_temp" >nul 2>&1
    ) else (
        echo curl not available. Please install FFmpeg manually:
        echo 1. Download from: https://www.gyan.dev/ffmpeg/builds/
        echo 2. Extract ffmpeg.exe to build\ffmpeg\ffmpeg.exe
        echo ERROR: Build will fail without FFmpeg - streaming/recording features require it.
        pause
        exit /b 1
    )
)

REM Verify FFmpeg works
if exist "build\ffmpeg\ffmpeg.exe" (
    echo ✓ FFmpeg found at build\ffmpeg\ffmpeg.exe
    "build\ffmpeg\ffmpeg.exe" -version >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✓ FFmpeg is working correctly
    ) else (
        echo ⚠ FFmpeg binary exists but may not work properly
    )
) else (
    echo ERROR: FFmpeg still not found after download attempt
    pause
    exit /b 1
)

REM Create the Windows executable
echo Creating Windows executable...
pyinstaller --windowed --onedir ^
    --add-data "icons;icons" ^
    --add-data "effects;effects" ^
    --add-data "renderer;renderer" ^
    --add-data "encoder;encoder" ^
    --add-data "audio;audio" ^
    --add-data "mainwindow.ui;." ^
    --add-data "resources_rc.py;." ^
    --add-data "resources.qrc;." ^
    --add-binary "build\ffmpeg\ffmpeg.exe;ffmpeg" ^
    --collect-submodules PyQt6.QtCore ^
    --collect-submodules PyQt6.QtGui ^
    --collect-submodules PyQt6.QtWidgets ^
    --collect-submodules PyQt6.QtOpenGL ^
    --collect-submodules PyQt6.QtOpenGLWidgets ^
    --collect-submodules PyQt6.QtMultimedia ^
    --collect-submodules PyQt6.QtMultimediaWidgets ^
    --collect-all cv2 ^
    --collect-all numpy ^
    --collect-all av ^
    --collect-all PIL ^
    --collect-all OpenGL ^
    --exclude-module PyQt6.QtBluetooth ^
    --exclude-module PyQt6.QtWebEngineCore ^
    --exclude-module PyQt6.QtWebEngineWidgets ^
    --exclude-module PyQt6.QtWebEngineQuick ^
    --exclude-module PyQt6.Qt3DCore ^
    --exclude-module PyQt6.Qt3DRender ^
    --exclude-module PyQt6.Qt3DInput ^
    --exclude-module PyQt6.Qt3DAnimation ^
    --exclude-module PyQt6.QtQml ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --name "GoLive Studio" ^
    --icon "icons\Record.png" ^
    --hidden-import "OpenGL" ^
    --hidden-import "OpenGL.GL" ^
    --hidden-import "OpenGL.arrays" ^
    --hidden-import "numpy" ^
    --hidden-import "numpy.core" ^
    --hidden-import "numpy.core.multiarray" ^
    --hidden-import "renderer" ^
    --hidden-import "encoder" ^
    --hidden-import "audio" ^
    --hidden-import "cv2" ^
    --hidden-import "av" ^
    --hidden-import "av.audio" ^
    --hidden-import "av.video" ^
    --hidden-import "av.codec" ^
    --hidden-import "transitions" ^
    --hidden-import "overlay_manager" ^
    --hidden-import "text_overlay" ^
    --hidden-import "config" ^
    --hidden-import "streaming" ^
    --hidden-import "recording" ^
    --hidden-import "external_display" ^
    --hidden-import "enhanced_external_display" ^
    --hidden-import "graphics_output" ^
    --hidden-import "enhanced_graphics_output" ^
    --hidden-import "recording_settings_dialog" ^
    --hidden-import "streaming_settings_dialog_improved" ^
    --hidden-import "gpu_streaming" ^
    --hidden-import "av_streamer" ^
    --hidden-import "ffmpeg_utils" ^
    main.py

REM Check build success
if %errorlevel% equ 0 (
    echo ✓ Build complete! Executable created in dist\
    echo   GPU acceleration: Auto-detected
    echo   Renderer backend: OpenGL/D3D ^(Windows^)
    echo   Encoder support: NVENC + x264
    echo.
    echo To run: dist\"GoLive Studio.exe"
) else (
    echo ✗ Build failed!
    pause
    exit /b 1
)

pause
