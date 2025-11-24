@echo off
REM Windows Build Script for GoLive Studio
REM Creates a complete Windows executable and installer

echo ========================================
echo GoLive Studio - Windows Build Script
echo ========================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if we're in a virtual environment (recommended)
python -c "import sys; exit(0 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 1)" >nul 2>&1
if errorlevel 1 (
    echo WARNING: Not running in a virtual environment
    echo It's recommended to use a virtual environment
    echo.
    set /p continue="Continue anyway? (y/N): "
    if /i not "%continue%"=="y" (
        echo Build cancelled
        pause
        exit /b 1
    )
)

echo.
echo Starting build process...
echo.

REM Run the Windows-specific build script
python build_windows_complete.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED!
    echo Check the error messages above
    pause
    exit /b 1
)

echo.
echo ========================================
echo BUILD COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo Your executable is ready in the dist folder
echo If an installer was created, you can find it in the project root
echo.
pause