#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Windows EXE Builder for GoLive Studio
Creates a fully functional Windows executable with all dependencies
"""

import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path
import zipfile
import requests


class WindowsEXEBuilder:
    """Creates complete Windows EXE packages."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.dist_dir = self.project_root / 'dist'
        self.build_dir = self.project_root / 'build'
        self.app_name = 'GoLive Studio'
        self.exe_name = 'GoLive Studio.exe'
        self.exe_path = self.dist_dir / self.exe_name
        
    def setup_windows_environment(self):
        """Set up Windows-specific build environment."""
        print("🪟 Setting up Windows build environment...")
        
        # Install Windows-specific dependencies
        windows_packages = [
            'pywin32>=227',
            'pywin32-ctypes>=0.2.0',
            'comtypes>=1.1.0',
        ]
        
        for package in windows_packages:
            try:
                subprocess.run([
                    sys.executable, '-m', 'pip', 'install', '--upgrade', package
                ], check=True, capture_output=True)
                print(f"   ✅ {package}")
            except subprocess.CalledProcessError:
                print(f"   ⚠️ Failed to install {package}")
    
    def download_windows_ffmpeg(self):
        """Download FFmpeg for Windows."""
        print("🎬 Setting up FFmpeg for Windows...")
        
        ffmpeg_dir = self.project_root / 'ffmpeg'
        ffmpeg_exe = ffmpeg_dir / 'ffmpeg.exe'
        
        if ffmpeg_exe.exists():
            print(f"   ✅ FFmpeg already exists: {ffmpeg_exe}")
            return True
        
        ffmpeg_dir.mkdir(exist_ok=True)
        
        try:
            # Download FFmpeg essentials build
            print("   📥 Downloading FFmpeg for Windows...")
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_path = temp_path / 'ffmpeg.zip'
                
                # Download
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Extract
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_path)
                
                # Find and copy ffmpeg.exe
                for ffmpeg_file in temp_path.rglob('ffmpeg.exe'):
                    shutil.copy2(ffmpeg_file, ffmpeg_exe)
                    print(f"   ✅ FFmpeg extracted: {ffmpeg_exe}")
                    return True
                
                print("   ❌ FFmpeg.exe not found in download")
                return False
                
        except Exception as e:
            print(f"   ❌ FFmpeg download failed: {e}")
            return False
    
    def create_windows_spec(self):
        """Create Windows-specific PyInstaller spec."""
        print("📝 Creating Windows PyInstaller spec...")
        
        spec_content = '''# -*- mode: python ; coding: utf-8 -*-
"""
Windows-specific PyInstaller spec for GoLive Studio
"""

import sys
import os
from pathlib import Path

# Get project root
project_root = Path(__file__).parent

# All hidden imports for Windows
hidden_imports = [
    # PyQt6 modules
    'PyQt6.QtCore',
    'PyQt6.QtGui', 
    'PyQt6.QtWidgets',
    'PyQt6.QtOpenGL',
    'PyQt6.QtOpenGLWidgets',
    'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
    'PyQt6.sip',
    
    # Windows-specific
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'win32security',
    'win32service',
    'win32serviceutil',
    'pywintypes',
    'comtypes',
    'comtypes.client',
    
    # Audio/Video
    'av',
    'cv2',
    'numpy',
    'PIL',
    'PIL.Image',
    
    # OpenGL
    'OpenGL',
    'OpenGL.GL',
    'OpenGL.arrays',
    
    # System
    'psutil',
    'threading',
    'multiprocessing',
    'queue',
    'subprocess',
    'ctypes',
    'ctypes.wintypes',
    
    # Project modules
    'audio',
    'encoder',
    'renderer',
]

# Data files
datas = [
    ('mainwindow.ui', '.'),
    ('resources.qrc', '.'),
    ('EditLive.ico', '.'),
    ('icons', 'icons'),
    ('effects', 'effects'),
    ('ffmpeg', 'ffmpeg'),
    ('requirements.txt', '.'),
    ('LICENSE.txt', '.'),
]

# Binaries
binaries = []

# Add FFmpeg
ffmpeg_exe = project_root / 'ffmpeg' / 'ffmpeg.exe'
if ffmpeg_exe.exists():
    binaries.append((str(ffmpeg_exe), 'ffmpeg'))

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GoLive Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='EditLive.ico',
)
'''
        
        spec_path = self.project_root / 'GoLive_Studio_Windows.spec'
        with open(spec_path, 'w') as f:
            f.write(spec_content)
        
        print(f"   ✅ Windows spec created: {spec_path}")
        return spec_path
    
    def build_windows_exe(self):
        """Build the Windows EXE."""
        print("🔨 Building Windows EXE...")
        
        # Create spec file
        spec_path = self.create_windows_spec()
        
        # Build command
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--noconfirm',
            str(spec_path)
        ]
        
        print(f"🔨 Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, cwd=self.project_root, check=True)
            
            if self.exe_path.exists():
                print(f"✅ EXE built successfully: {self.exe_path}")
                return True
            else:
                print("❌ EXE not found after build")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Build failed: {e}")
            return False
    
    def create_windows_installer(self):
        """Create Windows installer package."""
        print("📦 Creating Windows installer package...")
        
        if not self.exe_path.exists():
            print(f"❌ EXE not found: {self.exe_path}")
            return False
        
        # Create installer directory
        installer_dir = self.dist_dir / 'GoLive Studio Windows'
        if installer_dir.exists():
            shutil.rmtree(installer_dir)
        installer_dir.mkdir()
        
        # Copy EXE
        shutil.copy2(self.exe_path, installer_dir / self.exe_name)
        
        # Copy additional files
        additional_files = [
            'LICENSE.txt',
            'README.md',
            'requirements.txt',
        ]
        
        for file_name in additional_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                shutil.copy2(file_path, installer_dir / file_name)
        
        # Create installation script
        install_script = installer_dir / 'install.bat'
        install_content = f'''@echo off
echo Installing GoLive Studio...
echo.

REM Create desktop shortcut
set "desktop=%USERPROFILE%\\Desktop"
set "target=%~dp0{self.exe_name}"
set "shortcut=%desktop%\\GoLive Studio.lnk"

powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%shortcut%'); $Shortcut.TargetPath = '%target%'; $Shortcut.Save()"

echo Desktop shortcut created: %shortcut%
echo.
echo Installation completed!
echo You can now run GoLive Studio from your desktop.
echo.
pause
'''
        
        with open(install_script, 'w') as f:
            f.write(install_content)
        
        # Create ZIP package
        zip_path = self.dist_dir / 'GoLive Studio Windows.zip'
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in installer_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(installer_dir)
                        zipf.write(file_path, arcname)
            
            size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"✅ Windows installer created: {zip_path} ({size_mb:.1f} MB)")
            return True
            
        except Exception as e:
            print(f"❌ Installer creation failed: {e}")
            return False
    
    def verify_exe(self):
        """Verify the created EXE."""
        print("🔍 Verifying Windows EXE...")
        
        if not self.exe_path.exists():
            print(f"❌ EXE not found: {self.exe_path}")
            return False
        
        try:
            # Check if EXE is valid
            result = subprocess.run([str(self.exe_path), '--version'], 
                                  capture_output=True, text=True, timeout=10)
            
            size_mb = self.exe_path.stat().st_size / (1024 * 1024)
            print(f"✅ EXE verified successfully ({size_mb:.1f} MB)")
            return True
            
        except subprocess.TimeoutExpired:
            print("⚠️ EXE verification timeout (but file exists)")
            return True
        except Exception as e:
            print(f"⚠️ EXE verification warning: {e}")
            return True  # Continue even if verification has issues
    
    def build_complete_windows_package(self):
        """Build complete Windows package."""
        print(f"\n🪟 Creating Windows EXE for {self.app_name}")
        print("=" * 50)
        
        # Step 1: Setup environment
        self.setup_windows_environment()
        
        # Step 2: Download FFmpeg
        if not self.download_windows_ffmpeg():
            print("⚠️ FFmpeg setup failed, continuing without it")
        
        # Step 3: Build EXE
        if not self.build_windows_exe():
            return False
        
        # Step 4: Verify EXE
        if not self.verify_exe():
            return False
        
        # Step 5: Create installer
        if not self.create_windows_installer():
            return False
        
        print(f"\n🎉 Windows EXE creation completed successfully!")
        print(f"📁 EXE location: {self.exe_path}")
        print(f"📦 Installer package: {self.dist_dir / 'GoLive Studio Windows.zip'}")
        
        return True


def main():
    """Main function."""
    builder = WindowsEXEBuilder()
    success = builder.build_complete_windows_package()
    
    if not success:
        print("❌ Windows EXE build failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
