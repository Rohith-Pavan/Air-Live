#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Application Builder for GoLive Studio
Creates fully functional EXE and DMG builds with all dependencies
"""

import os
import sys
import subprocess
import shutil
import platform
import requests
import zipfile
import tarfile
import tempfile
from pathlib import Path
import json
import time


class CompleteApplicationBuilder:
    """Comprehensive builder for GoLive Studio applications."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.is_windows = sys.platform.startswith('win')
        self.is_macos = sys.platform == 'darwin'
        self.is_linux = sys.platform.startswith('linux')
        
        # Build directories
        self.build_dir = self.project_root / 'build'
        self.dist_dir = self.project_root / 'dist'
        self.ffmpeg_dir = self.project_root / 'ffmpeg'
        
        print(f"🚀 GoLive Studio Complete Builder")
        print(f"📁 Project root: {self.project_root}")
        print(f"💻 Platform: {platform.system()} {platform.machine()}")
        
    def setup_environment(self):
        """Set up the build environment."""
        print("\n🔧 Setting up build environment...")
        
        # Clean previous builds
        self.clean_build()
        
        # Install/upgrade build dependencies
        self.install_build_dependencies()
        
        # Download and setup FFmpeg
        self.setup_ffmpeg()
        
        # Verify all dependencies
        self.verify_dependencies()
        
    def clean_build(self):
        """Clean previous build artifacts."""
        print("🧹 Cleaning previous build artifacts...")
        
        # Remove build directories
        for dir_path in [self.build_dir, self.dist_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"   Removed {dir_path}")
        
        # Remove Python cache
        for cache_dir in self.project_root.rglob('__pycache__'):
            shutil.rmtree(cache_dir)
        
        for pyc_file in self.project_root.rglob('*.pyc'):
            pyc_file.unlink()
        
        print("✅ Build environment cleaned")
    
    def install_build_dependencies(self):
        """Install all required build dependencies."""
        print("📦 Installing build dependencies...")
        
        # Core build tools
        build_packages = [
            'PyInstaller>=5.13.0',
            'setuptools>=65.0.0',
            'wheel>=0.38.0',
        ]
        
        # Platform-specific packages
        if self.is_macos:
            build_packages.extend([
                'dmgbuild>=1.6.0',
                'biplist>=1.0.3',
            ])
        elif self.is_windows:
            build_packages.extend([
                'pywin32>=227',
                'pywin32-ctypes>=0.2.0',
            ])
        
        for package in build_packages:
            try:
                subprocess.run([
                    sys.executable, '-m', 'pip', 'install', '--upgrade', package
                ], check=True, capture_output=True)
                print(f"   ✅ {package}")
            except subprocess.CalledProcessError as e:
                print(f"   ⚠️ Failed to install {package}: {e}")
    
    def setup_ffmpeg(self):
        """Download and setup FFmpeg binaries."""
        print("🎬 Setting up FFmpeg...")
        
        # Create FFmpeg directory
        self.ffmpeg_dir.mkdir(exist_ok=True)
        
        # Check if FFmpeg already exists
        if self.is_macos:
            ffmpeg_binary = self.ffmpeg_dir / 'ffmpeg'
        elif self.is_windows:
            ffmpeg_binary = self.ffmpeg_dir / 'ffmpeg.exe'
        else:
            ffmpeg_binary = self.ffmpeg_dir / 'ffmpeg'
        
        if ffmpeg_binary.exists():
            print(f"   ✅ FFmpeg already exists: {ffmpeg_binary}")
            return
        
        # Download FFmpeg
        try:
            if self.is_macos:
                self.download_ffmpeg_macos()
            elif self.is_windows:
                self.download_ffmpeg_windows()
            else:
                self.download_ffmpeg_linux()
        except Exception as e:
            print(f"   ⚠️ FFmpeg download failed: {e}")
            print("   📝 Please manually place FFmpeg binary in ffmpeg/ directory")
    
    def download_ffmpeg_macos(self):
        """Download FFmpeg for macOS."""
        print("   📥 Downloading FFmpeg for macOS...")
        
        # Use Homebrew if available, otherwise download static build
        try:
            # Try to copy from Homebrew
            homebrew_paths = [
                '/opt/homebrew/bin/ffmpeg',
                '/usr/local/bin/ffmpeg'
            ]
            
            for path in homebrew_paths:
                if os.path.exists(path):
                    shutil.copy2(path, self.ffmpeg_dir / 'ffmpeg')
                    os.chmod(self.ffmpeg_dir / 'ffmpeg', 0o755)
                    print(f"   ✅ Copied FFmpeg from {path}")
                    return
            
            # Download static build if Homebrew not available
            url = "https://evermeet.cx/ffmpeg/getrelease/zip"
            self.download_and_extract_ffmpeg(url, 'zip')
            
        except Exception as e:
            print(f"   ⚠️ macOS FFmpeg setup failed: {e}")
    
    def download_ffmpeg_windows(self):
        """Download FFmpeg for Windows."""
        print("   📥 Downloading FFmpeg for Windows...")
        
        try:
            # Download from official builds
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            self.download_and_extract_ffmpeg(url, 'zip')
            
        except Exception as e:
            print(f"   ⚠️ Windows FFmpeg setup failed: {e}")
    
    def download_ffmpeg_linux(self):
        """Download FFmpeg for Linux."""
        print("   📥 Downloading FFmpeg for Linux...")
        
        try:
            # Try to use system FFmpeg first
            result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
            if result.returncode == 0:
                ffmpeg_path = result.stdout.strip()
                shutil.copy2(ffmpeg_path, self.ffmpeg_dir / 'ffmpeg')
                os.chmod(self.ffmpeg_dir / 'ffmpeg', 0o755)
                print(f"   ✅ Copied system FFmpeg from {ffmpeg_path}")
                return
            
            # Download static build
            url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            self.download_and_extract_ffmpeg(url, 'tar.xz')
            
        except Exception as e:
            print(f"   ⚠️ Linux FFmpeg setup failed: {e}")
    
    def download_and_extract_ffmpeg(self, url: str, archive_type: str):
        """Download and extract FFmpeg from URL."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download
            print(f"   📥 Downloading from {url}")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            if archive_type == 'zip':
                archive_path = temp_path / 'ffmpeg.zip'
                with open(archive_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Extract
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_path)
            
            elif archive_type == 'tar.xz':
                archive_path = temp_path / 'ffmpeg.tar.xz'
                with open(archive_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Extract
                with tarfile.open(archive_path, 'r:xz') as tar_ref:
                    tar_ref.extractall(temp_path)
            
            # Find and copy FFmpeg binary
            for ffmpeg_file in temp_path.rglob('ffmpeg*'):
                if ffmpeg_file.is_file() and 'ffmpeg' in ffmpeg_file.name:
                    if not ffmpeg_file.name.endswith(('.txt', '.md', '.html')):
                        target_name = 'ffmpeg.exe' if self.is_windows else 'ffmpeg'
                        shutil.copy2(ffmpeg_file, self.ffmpeg_dir / target_name)
                        os.chmod(self.ffmpeg_dir / target_name, 0o755)
                        print(f"   ✅ Extracted FFmpeg: {ffmpeg_file.name}")
                        return
    
    def verify_dependencies(self):
        """Verify all dependencies are available."""
        print("🔍 Verifying dependencies...")
        
        # Check Python modules
        required_modules = [
            'PyQt6', 'numpy', 'cv2', 'PIL', 'av', 'psutil', 'requests'
        ]
        
        missing_modules = []
        for module in required_modules:
            try:
                __import__(module)
                print(f"   ✅ {module}")
            except ImportError:
                missing_modules.append(module)
                print(f"   ❌ {module}")
        
        if missing_modules:
            print(f"⚠️ Missing modules: {missing_modules}")
            print("📝 Please install missing dependencies with:")
            print(f"   pip install {' '.join(missing_modules)}")
            return False
        
        # Check FFmpeg
        ffmpeg_binary = self.ffmpeg_dir / ('ffmpeg.exe' if self.is_windows else 'ffmpeg')
        if ffmpeg_binary.exists():
            print(f"   ✅ FFmpeg: {ffmpeg_binary}")
        else:
            print(f"   ❌ FFmpeg not found: {ffmpeg_binary}")
            return False
        
        print("✅ All dependencies verified")
        return True
    
    def build_application(self):
        """Build the application using PyInstaller."""
        print("\n🔨 Building application...")
        
        # Use the comprehensive spec file
        spec_file = self.project_root / 'GoLive_Studio_Complete.spec'
        
        if not spec_file.exists():
            print(f"❌ Spec file not found: {spec_file}")
            return False
        
        # Build command
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--noconfirm',
            str(spec_file)
        ]
        
        print(f"🔨 Running: {' '.join(cmd)}")
        
        try:
            # Run PyInstaller
            result = subprocess.run(cmd, cwd=self.project_root, check=True)
            print("✅ Application build completed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Build failed: {e}")
            return False
    
    def create_installer(self):
        """Create platform-specific installer."""
        print("\n📦 Creating installer...")
        
        if self.is_macos:
            return self.create_dmg()
        elif self.is_windows:
            return self.create_windows_installer()
        else:
            return self.create_linux_package()
    
    def create_dmg(self):
        """Create DMG for macOS."""
        print("🍎 Creating DMG for macOS...")
        
        app_path = self.dist_dir / 'GoLive Studio.app'
        if not app_path.exists():
            print(f"❌ App not found: {app_path}")
            return False
        
        dmg_path = self.dist_dir / 'GoLive Studio.dmg'
        
        try:
            # Create DMG using hdiutil
            cmd = [
                'hdiutil', 'create',
                '-volname', 'GoLive Studio',
                '-srcfolder', str(app_path),
                '-ov', '-format', 'UDZO',
                str(dmg_path)
            ]
            
            subprocess.run(cmd, check=True)
            print(f"✅ DMG created: {dmg_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ DMG creation failed: {e}")
            return False
    
    def create_windows_installer(self):
        """Create Windows installer."""
        print("🪟 Creating Windows installer...")
        
        exe_path = self.dist_dir / 'GoLive Studio.exe'
        if not exe_path.exists():
            print(f"❌ EXE not found: {exe_path}")
            return False
        
        # For now, just create a ZIP package
        # You can integrate NSIS or Inno Setup here
        zip_path = self.dist_dir / 'GoLive Studio Windows.zip'
        
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(exe_path, exe_path.name)
            
            print(f"✅ Windows package created: {zip_path}")
            return True
            
        except Exception as e:
            print(f"❌ Windows installer creation failed: {e}")
            return False
    
    def create_linux_package(self):
        """Create Linux package."""
        print("🐧 Creating Linux package...")
        
        exe_path = self.dist_dir / 'GoLive Studio'
        if not exe_path.exists():
            print(f"❌ Binary not found: {exe_path}")
            return False
        
        # Create AppImage or tar.gz package
        tar_path = self.dist_dir / 'GoLive Studio Linux.tar.gz'
        
        try:
            import tarfile
            with tarfile.open(tar_path, 'w:gz') as tar:
                tar.add(exe_path, exe_path.name)
            
            print(f"✅ Linux package created: {tar_path}")
            return True
            
        except Exception as e:
            print(f"❌ Linux package creation failed: {e}")
            return False
    
    def run_complete_build(self):
        """Run the complete build process."""
        print("🚀 Starting complete build process...")
        start_time = time.time()
        
        try:
            # Step 1: Setup environment
            self.setup_environment()
            
            # Step 2: Build application
            if not self.build_application():
                print("❌ Build process failed")
                return False
            
            # Step 3: Create installer
            if not self.create_installer():
                print("❌ Installer creation failed")
                return False
            
            # Success
            elapsed_time = time.time() - start_time
            print(f"\n🎉 Build completed successfully in {elapsed_time:.1f} seconds!")
            print(f"📁 Output directory: {self.dist_dir}")
            
            # List created files
            print("\n📋 Created files:")
            for file_path in self.dist_dir.iterdir():
                if file_path.is_file():
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    print(f"   📄 {file_path.name} ({size_mb:.1f} MB)")
            
            return True
            
        except Exception as e:
            print(f"❌ Build process failed: {e}")
            return False


def main():
    """Main build function."""
    builder = CompleteApplicationBuilder()
    success = builder.run_complete_build()
    
    if success:
        print("\n✅ GoLive Studio build completed successfully!")
        print("🚀 Your application is ready for distribution!")
    else:
        print("\n❌ Build failed. Please check the errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
