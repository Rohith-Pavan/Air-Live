#!/usr/bin/env python3
"""
macOS Installer Builder for GoLive Studio
Creates a professional DMG installer with proper installation flow and FFmpeg bundling
"""

import os
import sys
import subprocess
import shutil
import requests
import tarfile
from pathlib import Path
import plistlib

class MacOSInstallerBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.build_dir = self.project_root / "build"
        self.dist_dir = self.project_root / "dist"
        self.ffmpeg_dir = self.build_dir / "ffmpeg"
        self.dmg_staging = self.build_dir / "dmg_staging"
        
    def setup_directories(self):
        """Create necessary build directories"""
        print("📁 Setting up build directories...")
        for directory in [self.build_dir, self.dist_dir, self.ffmpeg_dir, self.dmg_staging]:
            directory.mkdir(exist_ok=True)
            
    def download_ffmpeg_macos(self):
        """Download and extract FFmpeg for macOS"""
        print("📦 Setting up FFmpeg for macOS...")
        
        ffmpeg_exe = self.ffmpeg_dir / "ffmpeg"
        if ffmpeg_exe.exists():
            print("✅ FFmpeg already exists")
            return
            
        # Try to use system FFmpeg first
        try:
            system_ffmpeg = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
            if system_ffmpeg.returncode == 0:
                ffmpeg_path = system_ffmpeg.stdout.strip()
                print(f"✅ Found system FFmpeg at: {ffmpeg_path}")
                shutil.copy2(ffmpeg_path, ffmpeg_exe)
                os.chmod(ffmpeg_exe, 0o755)
                return
        except Exception:
            pass
            
        # Download FFmpeg if not available
        print("⬇️ Downloading FFmpeg for macOS...")
        try:
            # Use a reliable FFmpeg build for macOS
            ffmpeg_url = "https://evermeet.cx/ffmpeg/getrelease/zip"
            
            response = requests.get(ffmpeg_url, stream=True)
            response.raise_for_status()
            
            zip_path = self.build_dir / "ffmpeg.zip"
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            print("📂 Extracting FFmpeg...")
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.ffmpeg_dir)
                
            # Make executable
            os.chmod(ffmpeg_exe, 0o755)
            
            # Cleanup
            zip_path.unlink()
            
            print("✅ FFmpeg downloaded and extracted")
            
        except Exception as e:
            print(f"❌ Failed to download FFmpeg: {e}")
            print("Please install FFmpeg manually: brew install ffmpeg")
            sys.exit(1)
            
    def create_enhanced_spec(self):
        """Create enhanced PyInstaller spec for macOS"""
        print("📝 Creating enhanced PyInstaller spec...")
        
        spec_content = '''# -*- mode: python ; coding: utf-8 -*-
"""
Enhanced PyInstaller spec for GoLive Studio macOS
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
ffmpeg_exe = project_root / 'build' / 'ffmpeg' / 'ffmpeg'
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
    
    # macOS specific
    'objc',
    'Foundation',
    'AVFoundation',
    'CoreMedia',
    'CoreVideo',
    'Quartz',
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
    target_arch='arm64',  # Change to 'x86_64' for Intel Macs
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

# Create macOS app bundle
app = BUNDLE(
    coll,
    name='GoLive Studio.app',
    icon=str(project_root / 'EditLive.ico'),
    bundle_identifier='com.golivestudio.app',
    info_plist={
        'CFBundleName': 'GoLive Studio',
        'CFBundleDisplayName': 'GoLive Studio',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleIdentifier': 'com.golivestudio.app',
        'NSCameraUsageDescription': 'GoLive Studio needs camera access to capture video from your inputs.',
        'NSMicrophoneUsageDescription': 'GoLive Studio needs microphone access to capture audio from your inputs.',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15.0',
        'LSApplicationCategoryType': 'public.app-category.video',
        'NSRequiresAquaSystemAppearance': False,
        'NSSupportsAutomaticGraphicsSwitching': True,
    },
)
'''
        
        spec_path = self.project_root / "GoLive_Studio_Enhanced.spec"
        with open(spec_path, 'w') as f:
            f.write(spec_content)
            
        return spec_path
        
    def build_application(self):
        """Build the application using PyInstaller"""
        print("🔨 Building macOS application...")
        
        spec_path = self.create_enhanced_spec()
        
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
        
    def sign_application(self):
        """Code sign the application"""
        print("✍️ Code signing application...")
        
        app_path = self.dist_dir / "GoLive Studio.app"
        if not app_path.exists():
            print("❌ Application not found for signing")
            return
            
        try:
            # Ad-hoc signing (for development)
            cmd = ["codesign", "--force", "--deep", "--sign", "-", str(app_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Application signed successfully")
            else:
                print("⚠️ Code signing failed (non-critical for development)")
                print(f"Error: {result.stderr}")
                
        except Exception as e:
            print(f"⚠️ Code signing error: {e}")
            
    def create_installer_script(self):
        """Create installer script for the DMG"""
        installer_script = '''#!/bin/bash
# GoLive Studio Installer Script

echo "Installing GoLive Studio..."

# Check if running as admin
if [[ $EUID -eq 0 ]]; then
   echo "Please do not run this installer as root/sudo"
   exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_PATH="$SCRIPT_DIR/GoLive Studio.app"

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "Error: GoLive Studio.app not found"
    exit 1
fi

# Create Applications directory if it doesn't exist
mkdir -p "/Applications"

# Remove existing installation
if [ -d "/Applications/GoLive Studio.app" ]; then
    echo "Removing existing installation..."
    rm -rf "/Applications/GoLive Studio.app"
fi

# Copy application to Applications folder
echo "Installing GoLive Studio to Applications folder..."
cp -R "$APP_PATH" "/Applications/"

# Set proper permissions
chmod -R 755 "/Applications/GoLive Studio.app"

# Create desktop shortcut (optional)
read -p "Create desktop shortcut? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ln -sf "/Applications/GoLive Studio.app" "$HOME/Desktop/GoLive Studio.app"
    echo "Desktop shortcut created"
fi

echo "Installation complete!"
echo "You can now launch GoLive Studio from your Applications folder"
'''
        
        script_path = self.dmg_staging / "Install GoLive Studio.command"
        with open(script_path, 'w') as f:
            f.write(installer_script)
            
        # Make executable
        os.chmod(script_path, 0o755)
        
        return script_path
        
    def create_dmg_background(self):
        """Create a simple DMG background image"""
        print("🎨 Creating DMG background...")
        
        # For now, we'll skip creating a custom background
        # In a real implementation, you'd use PIL or similar to create an image
        pass
        
    def create_dmg(self):
        """Create the DMG installer"""
        print("📀 Creating DMG installer...")
        
        # Clean staging directory
        if self.dmg_staging.exists():
            shutil.rmtree(self.dmg_staging)
        self.dmg_staging.mkdir(exist_ok=True)
        
        # Copy application to staging
        app_src = self.dist_dir / "GoLive Studio.app"
        app_dst = self.dmg_staging / "GoLive Studio.app"
        
        if not app_src.exists():
            print("❌ Application not found for DMG creation")
            return
            
        print("📁 Copying application to staging...")
        shutil.copytree(app_src, app_dst)
        
        # Create installer script
        self.create_installer_script()
        
        # Create Applications symlink
        applications_link = self.dmg_staging / "Applications"
        if applications_link.exists():
            applications_link.unlink()
        applications_link.symlink_to("/Applications")
        
        # Copy README if exists
        readme_src = self.project_root / "README.md"
        if readme_src.exists():
            shutil.copy2(readme_src, self.dmg_staging / "README.txt")
            
        # Calculate DMG size
        size_mb = int(subprocess.check_output(
            ["du", "-sm", str(self.dmg_staging)], 
            text=True
        ).split()[0]) * 2 + 100  # Double size plus buffer
        
        # Create DMG
        dmg_name = "GoLive_Studio_Installer.dmg"
        dmg_path = self.dist_dir / dmg_name
        
        if dmg_path.exists():
            dmg_path.unlink()
            
        print(f"📦 Creating DMG (estimated size: {size_mb}MB)...")
        
        cmd = [
            "hdiutil", "create",
            "-volname", "GoLive Studio Installer",
            "-srcfolder", str(self.dmg_staging),
            "-ov",
            "-fs", "HFS+",
            "-format", "UDZO",
            "-imagekey", "zlib-level=9",
            "-size", f"{size_mb}m",
            str(dmg_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Get final size
            dmg_size = subprocess.check_output(
                ["du", "-h", str(dmg_path)], 
                text=True
            ).split()[0]
            
            print(f"✅ DMG created successfully: {dmg_path} ({dmg_size})")
            return dmg_path
        else:
            print(f"❌ DMG creation failed: {result.stderr}")
            return None
            
    def create_pkg_installer(self):
        """Create a PKG installer as an alternative"""
        print("📦 Creating PKG installer...")
        
        try:
            app_path = self.dist_dir / "GoLive Studio.app"
            pkg_path = self.dist_dir / "GoLive_Studio_Installer.pkg"
            
            if not app_path.exists():
                print("❌ Application not found for PKG creation")
                return
                
            # Create component package
            cmd = [
                "pkgbuild",
                "--root", str(app_path.parent),
                "--identifier", "com.golivestudio.app",
                "--version", "1.0.0",
                "--install-location", "/Applications",
                str(pkg_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                pkg_size = subprocess.check_output(
                    ["du", "-h", str(pkg_path)], 
                    text=True
                ).split()[0]
                print(f"✅ PKG created successfully: {pkg_path} ({pkg_size})")
            else:
                print(f"⚠️ PKG creation failed: {result.stderr}")
                
        except Exception as e:
            print(f"⚠️ PKG creation error: {e}")
            
    def build(self):
        """Main build process"""
        print("🚀 Building GoLive Studio macOS Installer...")
        print("=" * 50)
        
        self.setup_directories()
        self.download_ffmpeg_macos()
        self.build_application()
        self.sign_application()
        
        dmg_path = self.create_dmg()
        self.create_pkg_installer()
        
        print("\n🎉 macOS build complete!")
        print("=" * 50)
        print(f"📁 Application: {self.dist_dir / 'GoLive Studio.app'}")
        if dmg_path:
            print(f"📀 DMG Installer: {dmg_path}")
        pkg_path = self.dist_dir / "GoLive_Studio_Installer.pkg"
        if pkg_path.exists():
            print(f"📦 PKG Installer: {pkg_path}")
        print("✅ Ready for distribution!")

if __name__ == "__main__":
    builder = MacOSInstallerBuilder()
    builder.build()
