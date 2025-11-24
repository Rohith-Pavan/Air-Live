#!/usr/bin/env python3
"""
Windows Installer Builder for GoLive Studio
Creates a proper Windows installer with local installation and FFmpeg bundling
"""

import os
import sys
import subprocess
import shutil
import requests
import zipfile
from pathlib import Path

class WindowsInstallerBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.build_dir = self.project_root / "build"
        self.dist_dir = self.project_root / "dist"
        self.ffmpeg_dir = self.build_dir / "ffmpeg"
        self.installer_dir = self.build_dir / "installer"
        
    def setup_directories(self):
        """Create necessary build directories"""
        print("📁 Setting up build directories...")
        for directory in [self.build_dir, self.dist_dir, self.ffmpeg_dir, self.installer_dir]:
            directory.mkdir(exist_ok=True)
            
    def download_ffmpeg_windows(self):
        """Download and extract FFmpeg for Windows"""
        print("📦 Downloading FFmpeg for Windows...")
        
        ffmpeg_exe = self.ffmpeg_dir / "ffmpeg.exe"
        if ffmpeg_exe.exists():
            print("✅ FFmpeg already exists")
            return
            
        # FFmpeg download URL (using a reliable source)
        ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        
        try:
            print("⬇️ Downloading FFmpeg...")
            response = requests.get(ffmpeg_url, stream=True)
            response.raise_for_status()
            
            zip_path = self.build_dir / "ffmpeg.zip"
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            print("📂 Extracting FFmpeg...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.build_dir)
                
            # Find and move ffmpeg.exe
            for root, dirs, files in os.walk(self.build_dir):
                if "ffmpeg.exe" in files:
                    src = Path(root) / "ffmpeg.exe"
                    shutil.copy2(src, ffmpeg_exe)
                    break
                    
            # Cleanup
            zip_path.unlink()
            for item in self.build_dir.iterdir():
                if item.is_dir() and "ffmpeg" in item.name.lower() and item != self.ffmpeg_dir:
                    shutil.rmtree(item)
                    
            print("✅ FFmpeg downloaded and extracted")
            
        except Exception as e:
            print(f"❌ Failed to download FFmpeg: {e}")
            sys.exit(1)
            
    def create_pyinstaller_spec(self):
        """Create enhanced PyInstaller spec for Windows"""
        print("📝 Creating PyInstaller spec...")
        
        spec_content = '''# -*- mode: python ; coding: utf-8 -*-
"""
Enhanced PyInstaller spec for GoLive Studio Windows
"""

import sys
import os
from pathlib import Path

# Get project root
project_root = Path(__file__).parent

# Data files to include
datas = [
    (str(project_root / 'icons'), 'icons'),
    (str(project_root / 'effects'), 'effects'),
    (str(project_root / 'renderer'), 'renderer'),
    (str(project_root / 'encoder'), 'encoder'),
    (str(project_root / 'audio'), 'audio'),
    (str(project_root / 'mainwindow.ui'), '.'),
    (str(project_root / 'resources_rc.py'), '.'),
    (str(project_root / 'resources.qrc'), '.'),
]

# Binary files to include
binaries = []
ffmpeg_exe = project_root / 'build' / 'ffmpeg' / 'ffmpeg.exe'
if ffmpeg_exe.exists():
    binaries.append((str(ffmpeg_exe), 'ffmpeg'))

# Hidden imports
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
]

# Modules to exclude
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
]

# Analysis
a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GoLive Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / 'EditLive.ico'),
)

# Create distribution directory
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GoLive Studio',
)
'''
        
        spec_path = self.project_root / "GoLive_Studio_Windows.spec"
        with open(spec_path, 'w') as f:
            f.write(spec_content)
            
        return spec_path
        
    def build_application(self):
        """Build the application using PyInstaller"""
        print("🔨 Building Windows application...")
        
        spec_path = self.create_pyinstaller_spec()
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(spec_path)
        ]
        
        result = subprocess.run(cmd, cwd=self.project_root)
        if result.returncode != 0:
            print("❌ PyInstaller build failed")
            sys.exit(1)
            
        print("✅ Application built successfully")
        
    def create_installer_script(self):
        """Create NSIS installer script"""
        print("📝 Creating NSIS installer script...")
        
        nsis_script = '''
; GoLive Studio Windows Installer
; Created with NSIS (Nullsoft Scriptable Install System)

!define APP_NAME "GoLive Studio"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "GoLive Studio Team"
!define APP_URL "https://golivestudio.com"
!define APP_EXECUTABLE "GoLive Studio.exe"

; Installer settings
Name "${APP_NAME}"
OutFile "GoLive_Studio_Setup.exe"
InstallDir "$PROGRAMFILES64\\${APP_NAME}"
InstallDirRegKey HKLM "Software\\${APP_NAME}" "InstallDir"
RequestExecutionLevel admin

; Modern UI
!include "MUI2.nsh"

; Interface settings
!define MUI_ABORTWARNING
!define MUI_ICON "EditLive.ico"
!define MUI_UNICON "EditLive.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Languages
!insertmacro MUI_LANGUAGE "English"

; Version information
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey "FileVersion" "${APP_VERSION}"

; Installer sections
Section "Main Application" SecMain
    SectionIn RO
    
    ; Set output path
    SetOutPath "$INSTDIR"
    
    ; Install application files
    File /r "dist\\GoLive Studio\\*"
    
    ; Create shortcuts
    CreateDirectory "$SMPROGRAMS\\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXECUTABLE}"
    CreateShortcut "$SMPROGRAMS\\${APP_NAME}\\Uninstall.lnk" "$INSTDIR\\Uninstall.exe"
    CreateShortcut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXECUTABLE}"
    
    ; Write registry keys
    WriteRegStr HKLM "Software\\${APP_NAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "UninstallString" "$INSTDIR\\Uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayIcon" "$INSTDIR\\${APP_EXECUTABLE}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "URLInfoAbout" "${APP_URL}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "NoRepair" 1
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\\Uninstall.exe"
    
SectionEnd

; Uninstaller section
Section "Uninstall"
    
    ; Remove files
    RMDir /r "$INSTDIR"
    
    ; Remove shortcuts
    Delete "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\\${APP_NAME}\\Uninstall.lnk"
    RMDir "$SMPROGRAMS\\${APP_NAME}"
    Delete "$DESKTOP\\${APP_NAME}.lnk"
    
    ; Remove registry keys
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}"
    DeleteRegKey HKLM "Software\\${APP_NAME}"
    
SectionEnd
'''
        
        nsis_path = self.installer_dir / "installer.nsi"
        with open(nsis_path, 'w') as f:
            f.write(nsis_script)
            
        return nsis_path
        
    def create_license_file(self):
        """Create a simple license file"""
        license_content = """GoLive Studio License Agreement

Copyright (c) 2024 GoLive Studio Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
        
        license_path = self.project_root / "LICENSE.txt"
        with open(license_path, 'w') as f:
            f.write(license_content)
            
    def build_installer(self):
        """Build the Windows installer using NSIS"""
        print("📦 Creating Windows installer...")
        
        # Check if NSIS is available
        try:
            subprocess.run(["makensis", "/VERSION"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ NSIS not found. Please install NSIS to create the installer.")
            print("   Download from: https://nsis.sourceforge.io/")
            print("   The application files are available in: dist/GoLive Studio/")
            return
            
        self.create_license_file()
        nsis_script = self.create_installer_script()
        
        # Copy icon to installer directory
        icon_src = self.project_root / "EditLive.ico"
        if icon_src.exists():
            shutil.copy2(icon_src, self.installer_dir / "EditLive.ico")
            
        cmd = ["makensis", str(nsis_script)]
        result = subprocess.run(cmd, cwd=self.installer_dir)
        
        if result.returncode == 0:
            # Move installer to dist directory
            installer_src = self.installer_dir / "GoLive_Studio_Setup.exe"
            installer_dst = self.dist_dir / "GoLive_Studio_Setup.exe"
            if installer_src.exists():
                shutil.move(str(installer_src), str(installer_dst))
                print(f"✅ Windows installer created: {installer_dst}")
            else:
                print("❌ Installer creation failed")
        else:
            print("❌ NSIS compilation failed")
            
    def build(self):
        """Main build process"""
        print("🚀 Building GoLive Studio Windows Installer...")
        print("=" * 50)
        
        self.setup_directories()
        self.download_ffmpeg_windows()
        self.build_application()
        self.build_installer()
        
        print("\n🎉 Windows build complete!")
        print("=" * 50)
        print(f"📁 Application files: {self.dist_dir / 'GoLive Studio'}")
        installer_path = self.dist_dir / "GoLive_Studio_Setup.exe"
        if installer_path.exists():
            print(f"📦 Installer: {installer_path}")
        print("✅ Ready for distribution!")

if __name__ == "__main__":
    builder = WindowsInstallerBuilder()
    builder.build()
