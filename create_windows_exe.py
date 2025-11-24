#!/usr/bin/env python3
"""
Windows EXE Builder for GoLive Studio
Creates a complete Windows executable installer with all dependencies
"""

import os
import sys
import subprocess
import shutil
import requests
import zipfile
import tempfile
from pathlib import Path

class WindowsEXEBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.build_dir = self.project_root / "build"
        self.dist_dir = self.project_root / "dist"
        self.windows_dir = self.project_root / "windows_build"
        
    def setup_directories(self):
        """Create build directories"""
        print("📁 Setting up directories...")
        for directory in [self.build_dir, self.dist_dir, self.windows_dir]:
            directory.mkdir(exist_ok=True)
            
    def download_ffmpeg_windows(self):
        """Download FFmpeg for Windows"""
        print("📦 Downloading FFmpeg for Windows...")
        
        ffmpeg_dir = self.build_dir / "ffmpeg_windows"
        ffmpeg_dir.mkdir(exist_ok=True)
        ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"
        
        if ffmpeg_exe.exists():
            print("✅ FFmpeg already exists")
            return str(ffmpeg_exe)
            
        try:
            # Download FFmpeg
            ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            
            print("⬇️ Downloading FFmpeg...")
            response = requests.get(ffmpeg_url, stream=True)
            response.raise_for_status()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
                zip_path = tmp_file.name
            
            print("📂 Extracting FFmpeg...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                temp_extract = self.build_dir / "temp_ffmpeg"
                zip_ref.extractall(temp_extract)
                
                # Find ffmpeg.exe
                for root, dirs, files in os.walk(temp_extract):
                    if "ffmpeg.exe" in files:
                        src = Path(root) / "ffmpeg.exe"
                        shutil.copy2(src, ffmpeg_exe)
                        break
                
                # Cleanup
                shutil.rmtree(temp_extract)
            
            os.unlink(zip_path)
            print("✅ FFmpeg downloaded successfully")
            return str(ffmpeg_exe)
            
        except Exception as e:
            print(f"❌ Failed to download FFmpeg: {e}")
            return None
            
    def create_windows_pyinstaller_spec(self):
        """Create PyInstaller spec for Windows EXE"""
        print("📝 Creating Windows PyInstaller spec...")
        
        ffmpeg_path = self.download_ffmpeg_windows()
        if not ffmpeg_path:
            print("❌ Cannot create spec without FFmpeg")
            return None
            
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
"""
Windows EXE PyInstaller spec for GoLive Studio
Creates a single executable with all dependencies
"""

import sys
import os
from pathlib import Path

# Project root
project_root = Path(__file__).parent

# Data files to include
datas = [
    ('icons', 'icons'),
    ('effects', 'effects'),
    ('renderer', 'renderer'),
    ('encoder', 'encoder'),
    ('audio', 'audio'),
    ('mainwindow.ui', '.'),
    ('resources_rc.py', '.'),
    ('resources.qrc', '.'),
]

# Binary files to include
binaries = [
    (r'{ffmpeg_path}', 'ffmpeg'),
]

# Hidden imports for Windows
hiddenimports = [
    # Core modules
    'OpenGL',
    'OpenGL.GL',
    'OpenGL.arrays',
    'numpy',
    'numpy.core',
    'numpy.core.multiarray',
    'cv2',
    
    # Audio/Video processing
    'av',
    'av.audio',
    'av.video',
    'av.codec',
    'av.container',
    'av.stream',
    
    # Project modules
    'renderer',
    'renderer.base_renderer',
    'renderer.opengl_renderer',
    'renderer.gpu_graphics_output',
    'renderer.migration_helper',
    'encoder',
    'encoder.base_encoder',
    'encoder.x264_encoder',
    'encoder.nvenc_encoder',
    'encoder.vt_encoder',
    'audio',
    'audio.base_audio',
    'audio.qt_audio',
    'transitions',
    'overlay_manager',
    'text_overlay',
    'config',
    'streaming',
    'recording',
    'external_display',
    'enhanced_external_display',
    'graphics_output',
    'enhanced_graphics_output',
    'recording_settings_dialog',
    'streaming_settings_dialog_improved',
    'gpu_streaming',
    'av_streamer',
    'ffmpeg_utils',
    
    # Windows specific
    'win32api',
    'win32con',
    'win32gui',
    'pywintypes',
    'win32clipboard',
    'win32process',
]

# Modules to exclude (reduce size)
excludes = [
    'PyQt6.QtBluetooth',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineQuick',
    'PyQt6.Qt3DCore',
    'PyQt6.Qt3DRender',
    'PyQt6.Qt3DInput',
    'PyQt6.Qt3DAnimation',
    'PyQt6.QtQml',
    'matplotlib',
    'scipy',
    'pandas',
    'tkinter',
    'unittest',
    'test',
    'distutils',
]

# Analysis
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create single EXE file
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GoLive_Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon='EditLive.ico',
    version='version_info.txt'
)
'''
        
        spec_path = self.project_root / "GoLive_Studio_Windows.spec"
        with open(spec_path, 'w') as f:
            f.write(spec_content)
            
        return spec_path
        
    def create_version_info(self):
        """Create version info file for Windows EXE"""
        version_info = '''# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=(1,0,0,0),
    prodvers=(1,0,0,0),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x4,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'GoLive Studio Team'),
        StringStruct(u'FileDescription', u'GoLive Studio - Live Streaming and Recording Application'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'GoLive Studio'),
        StringStruct(u'LegalCopyright', u'Copyright © 2024 GoLive Studio Team'),
        StringStruct(u'OriginalFilename', u'GoLive_Studio.exe'),
        StringStruct(u'ProductName', u'GoLive Studio'),
        StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
        
        version_path = self.project_root / "version_info.txt"
        with open(version_path, 'w') as f:
            f.write(version_info)
            
        return version_path
        
    def create_windows_build_script(self):
        """Create comprehensive Windows build script"""
        build_script = '''@echo off
echo ========================================
echo GoLive Studio Windows EXE Builder
echo ========================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo Installing required packages...
pip install --upgrade pip
pip install PyInstaller>=6.0.0
pip install PyQt6>=6.6.0
pip install Pillow>=10.0.0
pip install opencv-python>=4.8.0
pip install numpy>=1.21.0
pip install av>=10.0.0
pip install PyOpenGL>=3.1.6
pip install PyOpenGL-accelerate>=3.1.6
pip install pywin32>=227
pip install requests>=2.25.0
pip install packaging>=21.0

if errorlevel 1 (
    echo ERROR: Failed to install required packages
    pause
    exit /b 1
)

echo Building Windows EXE...
python create_windows_exe.py

if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo ========================================
echo Build completed successfully!
echo Check the dist folder for your EXE file
echo ========================================
pause
'''
        
        script_path = self.project_root / "build_windows_exe.bat"
        with open(script_path, 'w') as f:
            f.write(build_script)
            
        return script_path
        
    def create_nsis_exe_installer(self):
        """Create NSIS script for EXE installer"""
        nsis_script = '''
; GoLive Studio EXE Installer
; Creates a professional installer for the single EXE

!define APP_NAME "GoLive Studio"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "GoLive Studio Team"
!define APP_URL "https://golivestudio.com"
!define APP_EXECUTABLE "GoLive_Studio.exe"

Name "${APP_NAME}"
OutFile "GoLive_Studio_Installer.exe"
InstallDir "$PROGRAMFILES64\\${APP_NAME}"
RequestExecutionLevel admin

!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "EditLive.ico"
!define MUI_UNICON "EditLive.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\\${APP_EXECUTABLE}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey "FileVersion" "${APP_VERSION}"

Section "Main Application" SecMain
    SectionIn RO
    
    SetOutPath "$INSTDIR"
    
    ; Install the EXE file
    File "dist\\${APP_EXECUTABLE}"
    
    ; Create shortcuts
    CreateDirectory "$SMPROGRAMS\\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXECUTABLE}"
    CreateShortcut "$SMPROGRAMS\\${APP_NAME}\\Uninstall.lnk" "$INSTDIR\\Uninstall.exe"
    CreateShortcut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXECUTABLE}"
    
    ; Registry entries
    WriteRegStr HKLM "Software\\${APP_NAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "UninstallString" "$INSTDIR\\Uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayIcon" "$INSTDIR\\${APP_EXECUTABLE}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "NoRepair" 1
    
    WriteUninstaller "$INSTDIR\\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\${APP_EXECUTABLE}"
    Delete "$INSTDIR\\Uninstall.exe"
    RMDir "$INSTDIR"
    
    Delete "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\\${APP_NAME}\\Uninstall.lnk"
    RMDir "$SMPROGRAMS\\${APP_NAME}"
    Delete "$DESKTOP\\${APP_NAME}.lnk"
    
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}"
    DeleteRegKey HKLM "Software\\${APP_NAME}"
SectionEnd
'''
        
        nsis_path = self.project_root / "exe_installer.nsi"
        with open(nsis_path, 'w') as f:
            f.write(nsis_script)
            
        return nsis_path
        
    def build_windows_exe(self):
        """Build the Windows EXE (if on Windows) or prepare build files"""
        print("🔨 Building Windows EXE...")
        
        if sys.platform != "win32":
            print("⚠️ Not on Windows - creating build files for Windows execution")
            return self.create_build_files_for_windows()
            
        # Windows-specific build
        spec_path = self.create_windows_pyinstaller_spec()
        if not spec_path:
            return False
            
        self.create_version_info()
        
        # Run PyInstaller
        cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_path)]
        result = subprocess.run(cmd, cwd=self.project_root)
        
        if result.returncode == 0:
            exe_path = self.dist_dir / "GoLive_Studio.exe"
            if exe_path.exists():
                exe_size = exe_path.stat().st_size / (1024 * 1024)  # MB
                print(f"✅ Windows EXE created: {exe_path} ({exe_size:.1f} MB)")
                return True
            else:
                print("❌ EXE file not found after build")
                return False
        else:
            print("❌ PyInstaller build failed")
            return False
            
    def create_build_files_for_windows(self):
        """Create all necessary files for Windows build"""
        print("📝 Creating Windows build files...")
        
        # Create all build files
        self.create_windows_pyinstaller_spec()
        self.create_version_info()
        self.create_windows_build_script()
        self.create_nsis_exe_installer()
        
        # Create comprehensive README
        readme_content = '''# GoLive Studio Windows EXE Builder

## Quick Start (Windows)
1. Run: build_windows_exe.bat
2. Wait for build to complete
3. Find GoLive_Studio.exe in dist/ folder

## Manual Build (Windows)
1. Install Python 3.8+ from https://python.org
2. Install dependencies: pip install -r requirements.txt
3. Run: python create_windows_exe.py
4. Optional: Create installer with NSIS

## Output Files
- GoLive_Studio.exe - Single executable file (all-in-one)
- GoLive_Studio_Installer.exe - Professional installer (with NSIS)

## Features
- Single EXE file with all dependencies
- FFmpeg bundled internally
- No external requirements
- Professional Windows installer available

## System Requirements
- Windows 10 (64-bit) or later
- 4GB RAM minimum, 8GB recommended
- DirectX 11 compatible graphics
- 2GB free disk space

## Troubleshooting
- Ensure Python is in PATH
- Run as Administrator if needed
- Check Windows Defender exclusions
- Verify all dependencies installed

For support: https://golivestudio.com
'''
        
        readme_path = self.project_root / "WINDOWS_EXE_README.md"
        with open(readme_path, 'w') as f:
            f.write(readme_content)
            
        print("✅ Windows build files created!")
        print("📁 Files created:")
        print("   - GoLive_Studio_Windows.spec (PyInstaller spec)")
        print("   - version_info.txt (Version information)")
        print("   - build_windows_exe.bat (Automated build script)")
        print("   - exe_installer.nsi (NSIS installer script)")
        print("   - WINDOWS_EXE_README.md (Documentation)")
        print("")
        print("🪟 To build EXE on Windows:")
        print("   1. Copy all files to Windows machine")
        print("   2. Run: build_windows_exe.bat")
        print("   3. Find GoLive_Studio.exe in dist/ folder")
        
        return True
        
    def build(self):
        """Main build process"""
        print("🚀 GoLive Studio Windows EXE Builder")
        print("=" * 50)
        
        self.setup_directories()
        success = self.build_windows_exe()
        
        if success:
            print("\n🎉 Windows EXE build system ready!")
            if sys.platform == "win32":
                print("✅ EXE file created and ready for distribution")
            else:
                print("✅ Build files created - ready for Windows execution")
        else:
            print("\n❌ Build process failed")
            
        return success

if __name__ == "__main__":
    builder = WindowsEXEBuilder()
    builder.build()
