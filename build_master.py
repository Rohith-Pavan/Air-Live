#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Master Build Script for GoLive Studio
Handles building for all platforms with comprehensive dependency management
"""

import os
import sys
import subprocess
import platform
import time
from pathlib import Path


class MasterBuilder:
    """Master builder that coordinates all build processes."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.platform = platform.system().lower()
        self.is_macos = self.platform == 'darwin'
        self.is_windows = self.platform == 'windows'
        self.is_linux = self.platform == 'linux'
        
        print("🚀 GoLive Studio Master Builder")
        print("=" * 50)
        print(f"📁 Project: {self.project_root}")
        print(f"💻 Platform: {platform.system()} {platform.machine()}")
        print(f"🐍 Python: {sys.version}")
        
    def check_prerequisites(self):
        """Check all prerequisites for building."""
        print("\n🔍 Checking prerequisites...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            print("❌ Python 3.8+ required")
            return False
        print(f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor}")
        
        # Check pip
        try:
            subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                         check=True, capture_output=True)
            print("   ✅ pip available")
        except:
            print("   ❌ pip not available")
            return False
        
        # Check main.py exists
        main_py = self.project_root / 'main.py'
        if not main_py.exists():
            print(f"   ❌ main.py not found: {main_py}")
            return False
        print("   ✅ main.py found")
        
        # Check requirements.txt
        requirements = self.project_root / 'requirements.txt'
        if not requirements.exists():
            print(f"   ❌ requirements.txt not found: {requirements}")
            return False
        print("   ✅ requirements.txt found")
        
        return True
    
    def install_dependencies(self):
        """Install all required dependencies."""
        print("\n📦 Installing dependencies...")
        
        # Upgrade pip first
        try:
            subprocess.run([
                sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'
            ], check=True)
            print("   ✅ pip upgraded")
        except:
            print("   ⚠️ pip upgrade failed")
        
        # Install from requirements.txt
        requirements = self.project_root / 'requirements.txt'
        try:
            subprocess.run([
                sys.executable, '-m', 'pip', 'install', '-r', str(requirements)
            ], check=True)
            print("   ✅ Requirements installed")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Requirements installation failed: {e}")
            return False
        
        # Install build-specific dependencies
        build_deps = ['PyInstaller>=5.13.0']
        
        if self.is_macos:
            build_deps.extend([
                'dmgbuild>=1.6.0',
                'biplist>=1.0.3',
            ])
        elif self.is_windows:
            build_deps.extend([
                'pywin32>=227',
            ])
        
        for dep in build_deps:
            try:
                subprocess.run([
                    sys.executable, '-m', 'pip', 'install', dep
                ], check=True, capture_output=True)
                print(f"   ✅ {dep}")
            except:
                print(f"   ⚠️ {dep} installation failed")
        
        return True
    
    def run_tests(self):
        """Run basic tests to ensure the application works."""
        print("\n🧪 Running basic tests...")
        
        try:
            # Test import of main modules
            test_script = '''
import sys
sys.path.insert(0, ".")

try:
    import main
    print("✅ Main module imports successfully")
except Exception as e:
    print(f"❌ Main module import failed: {e}")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import QApplication
    print("✅ PyQt6 available")
except Exception as e:
    print(f"❌ PyQt6 not available: {e}")
    sys.exit(1)

try:
    import numpy
    print("✅ NumPy available")
except Exception as e:
    print(f"❌ NumPy not available: {e}")
    sys.exit(1)

try:
    import cv2
    print("✅ OpenCV available")
except Exception as e:
    print(f"❌ OpenCV not available: {e}")
    sys.exit(1)

print("✅ All basic tests passed")
'''
            
            result = subprocess.run([
                sys.executable, '-c', test_script
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("   ✅ All tests passed")
                return True
            else:
                print(f"   ❌ Tests failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"   ❌ Test execution failed: {e}")
            return False
    
    def build_for_platform(self):
        """Build for the current platform."""
        print(f"\n🔨 Building for {self.platform}...")
        
        if self.is_macos:
            return self.build_macos()
        elif self.is_windows:
            return self.build_windows()
        else:
            return self.build_linux()
    
    def build_macos(self):
        """Build for macOS."""
        print("🍎 Building macOS application...")
        
        try:
            # Use the complete build script
            result = subprocess.run([
                sys.executable, 'build_complete_application.py'
            ], cwd=self.project_root)
            
            if result.returncode == 0:
                # Create DMG
                dmg_result = subprocess.run([
                    sys.executable, 'create_macos_dmg.py'
                ], cwd=self.project_root)
                
                return dmg_result.returncode == 0
            
            return False
            
        except Exception as e:
            print(f"❌ macOS build failed: {e}")
            return False
    
    def build_windows(self):
        """Build for Windows."""
        print("🪟 Building Windows application...")
        
        try:
            result = subprocess.run([
                sys.executable, 'create_windows_exe_complete.py'
            ], cwd=self.project_root)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ Windows build failed: {e}")
            return False
    
    def build_linux(self):
        """Build for Linux."""
        print("🐧 Building Linux application...")
        
        try:
            # Use PyInstaller directly for Linux
            spec_file = self.project_root / 'GoLive_Studio_Complete.spec'
            
            cmd = [
                sys.executable, '-m', 'PyInstaller',
                '--clean', '--noconfirm', str(spec_file)
            ]
            
            result = subprocess.run(cmd, cwd=self.project_root)
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ Linux build failed: {e}")
            return False
    
    def show_build_results(self):
        """Show the build results."""
        print("\n📋 Build Results:")
        print("=" * 30)
        
        dist_dir = self.project_root / 'dist'
        if not dist_dir.exists():
            print("❌ No dist directory found")
            return
        
        total_size = 0
        file_count = 0
        
        for file_path in dist_dir.rglob('*'):
            if file_path.is_file():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                total_size += size_mb
                file_count += 1
                
                # Show main output files
                if any(ext in file_path.suffix.lower() 
                      for ext in ['.app', '.exe', '.dmg', '.zip']):
                    print(f"📄 {file_path.name} ({size_mb:.1f} MB)")
        
        print(f"\n📊 Total: {file_count} files, {total_size:.1f} MB")
        print(f"📁 Location: {dist_dir}")
    
    def run_complete_build(self):
        """Run the complete build process."""
        start_time = time.time()
        
        try:
            # Step 1: Check prerequisites
            if not self.check_prerequisites():
                print("❌ Prerequisites check failed")
                return False
            
            # Step 2: Install dependencies
            if not self.install_dependencies():
                print("❌ Dependencies installation failed")
                return False
            
            # Step 3: Run tests
            if not self.run_tests():
                print("❌ Tests failed")
                return False
            
            # Step 4: Build for platform
            if not self.build_for_platform():
                print("❌ Build failed")
                return False
            
            # Step 5: Show results
            self.show_build_results()
            
            elapsed_time = time.time() - start_time
            print(f"\n🎉 Build completed successfully in {elapsed_time:.1f} seconds!")
            
            return True
            
        except KeyboardInterrupt:
            print("\n⚠️ Build interrupted by user")
            return False
        except Exception as e:
            print(f"\n❌ Build failed with error: {e}")
            return False


def main():
    """Main function with user interaction."""
    builder = MasterBuilder()
    
    print(f"\n🎯 Building GoLive Studio for {builder.platform}")
    print("This will:")
    print("  1. Check prerequisites")
    print("  2. Install dependencies") 
    print("  3. Run basic tests")
    print("  4. Build the application")
    print("  5. Create distribution package")
    
    try:
        response = input("\nProceed with build? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Build cancelled.")
            return
    except KeyboardInterrupt:
        print("\nBuild cancelled.")
        return
    
    success = builder.run_complete_build()
    
    if success:
        print("\n✅ GoLive Studio build completed successfully!")
        print("🚀 Your application is ready for distribution!")
    else:
        print("\n❌ Build failed. Please check the errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
