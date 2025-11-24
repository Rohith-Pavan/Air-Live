#!/usr/bin/env python3
"""
GoLive Studio Dependency Installation Script
Automatically installs all required dependencies for GoLive Studio
"""

import sys
import subprocess
import platform
import os
from pathlib import Path

def run_command(cmd, check=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python {version.major}.{version.minor} is not supported")
        print("GoLive Studio requires Python 3.8 or higher")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def install_pip_packages():
    """Install Python packages from requirements.txt"""
    print("\n📦 Installing Python dependencies...")
    
    # Upgrade pip first
    print("Upgrading pip...")
    success, stdout, stderr = run_command(f"{sys.executable} -m pip install --upgrade pip")
    if not success:
        print(f"⚠️  Warning: Failed to upgrade pip: {stderr}")
    
    # Install requirements
    requirements_file = Path(__file__).parent / "requirements.txt"
    if not requirements_file.exists():
        print("❌ requirements.txt not found!")
        return False
    
    print("Installing packages from requirements.txt...")
    success, stdout, stderr = run_command(f'{sys.executable} -m pip install -r "{requirements_file}"')
    
    if success:
        print("✅ Python dependencies installed successfully")
        return True
    else:
        print(f"❌ Failed to install dependencies: {stderr}")
        return False

def check_ffmpeg():
    """Check if FFmpeg is available"""
    print("\n🎬 Checking FFmpeg...")
    
    success, stdout, stderr = run_command("ffmpeg -version", check=False)
    if success:
        version_line = stdout.split('\n')[0]
        print(f"✅ {version_line}")
        return True
    else:
        print("❌ FFmpeg not found")
        system = platform.system().lower()
        
        if system == "darwin":
            print("Install FFmpeg on macOS:")
            print("  brew install ffmpeg")
        elif system == "windows":
            print("Install FFmpeg on Windows:")
            print("  1. Download from: https://www.gyan.dev/ffmpeg/builds/")
            print("  2. Extract and add to PATH")
            print("  3. Or use chocolatey: choco install ffmpeg")
        elif system == "linux":
            print("Install FFmpeg on Linux:")
            print("  Ubuntu/Debian: sudo apt install ffmpeg")
            print("  CentOS/RHEL: sudo yum install ffmpeg")
            print("  Arch: sudo pacman -S ffmpeg")
        
        return False

def check_system_requirements():
    """Check system-specific requirements"""
    print(f"\n🖥️  System: {platform.system()} {platform.release()}")
    
    system = platform.system().lower()
    
    if system == "darwin":
        # Check macOS version
        version = platform.mac_ver()[0]
        major, minor = map(int, version.split('.')[:2])
        if major < 10 or (major == 10 and minor < 15):
            print(f"⚠️  macOS {version} may not be fully supported")
            print("Recommended: macOS 10.15 (Catalina) or higher")
        else:
            print(f"✅ macOS {version} is supported")
    
    elif system == "windows":
        # Check Windows version
        version = platform.version()
        print(f"✅ Windows version: {version}")
    
    elif system == "linux":
        # Check Linux distribution
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = f.read()
            print(f"✅ Linux distribution detected")
        except:
            print("✅ Linux system detected")

def test_imports():
    """Test if all critical modules can be imported"""
    print("\n🧪 Testing module imports...")
    
    critical_modules = [
        ('PyQt6', 'PyQt6.QtWidgets'),
        ('OpenGL', 'OpenGL.GL'),
        ('numpy', 'numpy'),
        ('cv2', 'cv2'),
        ('PIL', 'PIL'),
    ]
    
    optional_modules = [
        ('av', 'av'),
    ]
    
    all_good = True
    
    for name, import_path in critical_modules:
        try:
            __import__(import_path)
            print(f"✅ {name}")
        except ImportError as e:
            print(f"❌ {name}: {e}")
            all_good = False
    
    for name, import_path in optional_modules:
        try:
            __import__(import_path)
            print(f"✅ {name} (optional)")
        except ImportError:
            print(f"⚠️  {name} (optional): Not available")
    
    return all_good

def main():
    """Main installation process"""
    print("🚀 GoLive Studio Dependency Installer")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check system requirements
    check_system_requirements()
    
    # Install pip packages
    if not install_pip_packages():
        print("\n❌ Failed to install Python dependencies")
        sys.exit(1)
    
    # Check FFmpeg
    ffmpeg_ok = check_ffmpeg()
    
    # Test imports
    if not test_imports():
        print("\n❌ Some critical modules failed to import")
        sys.exit(1)
    
    # Final status
    print("\n" + "=" * 50)
    if ffmpeg_ok:
        print("🎉 All dependencies installed successfully!")
        print("You can now run GoLive Studio with: python main.py")
    else:
        print("⚠️  Python dependencies installed, but FFmpeg is missing")
        print("Install FFmpeg to enable streaming and recording features")
        print("You can still run GoLive Studio with: python main.py")

if __name__ == "__main__":
    main()
