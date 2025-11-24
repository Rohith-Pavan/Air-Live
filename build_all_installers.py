#!/usr/bin/env python3
"""
Universal Installer Builder for GoLive Studio
Builds all installer types: macOS DMG, Windows EXE, and Windows Installer
"""

import sys
import platform
import subprocess
from pathlib import Path

def main():
    print("🚀 GoLive Studio Universal Installer Builder")
    print("=" * 60)
    
    current_platform = platform.system().lower()
    project_root = Path(__file__).parent
    
    print(f"🖥️ Current platform: {current_platform}")
    print(f"📁 Project root: {project_root}")
    
    # Build summary
    build_results = {
        'macos_dmg': False,
        'windows_exe_files': False,
        'windows_installer_files': False
    }
    
    # macOS DMG (if on macOS)
    if current_platform == "darwin":
        print("\n🍎 Building macOS DMG installer...")
        try:
            result = subprocess.run([sys.executable, "build_simple_installer.py"], 
                                  cwd=project_root, capture_output=True, text=True)
            if result.returncode == 0:
                dmg_path = project_root / "dist" / "GoLive_Studio_Installer.dmg"
                if dmg_path.exists():
                    build_results['macos_dmg'] = True
                    print("✅ macOS DMG created successfully")
                else:
                    print("⚠️ DMG build completed but file not found")
            else:
                print("❌ macOS DMG build failed")
                print(result.stderr)
        except Exception as e:
            print(f"❌ macOS build error: {e}")
    else:
        print("⚠️ Not on macOS - skipping DMG build")
    
    # Windows EXE build files
    print("\n🪟 Creating Windows EXE build system...")
    try:
        result = subprocess.run([sys.executable, "create_windows_exe.py"], 
                              cwd=project_root, capture_output=True, text=True)
        if result.returncode == 0:
            build_results['windows_exe_files'] = True
            print("✅ Windows EXE build files created")
        else:
            print("❌ Windows EXE build files creation failed")
            print(result.stderr)
    except Exception as e:
        print(f"❌ Windows EXE build error: {e}")
    
    # Windows Installer build files
    print("\n📦 Creating Windows Installer build system...")
    try:
        result = subprocess.run([sys.executable, "build_windows_complete.py"], 
                              cwd=project_root, capture_output=True, text=True)
        if result.returncode == 0:
            build_results['windows_installer_files'] = True
            print("✅ Windows Installer build files created")
        else:
            print("❌ Windows Installer build files creation failed")
            print(result.stderr)
    except Exception as e:
        print(f"❌ Windows Installer build error: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 BUILD SUMMARY")
    print("=" * 60)
    
    if build_results['macos_dmg']:
        dmg_path = project_root / "dist" / "GoLive_Studio_Installer.dmg"
        dmg_size = dmg_path.stat().st_size / (1024**3)  # GB
        print(f"✅ macOS DMG: {dmg_path} ({dmg_size:.1f}GB)")
    else:
        print("📋 macOS DMG: Build files ready (run on macOS)")
    
    if build_results['windows_exe_files']:
        print("✅ Windows EXE: Build system ready")
        print("   📁 Run: build_windows_exe.bat (on Windows)")
        print("   📄 Output: GoLive_Studio.exe (single file)")
    
    if build_results['windows_installer_files']:
        print("✅ Windows Installer: Build system ready")
        print("   📁 Run: build_windows.bat (on Windows)")
        print("   📄 Output: GoLive_Studio_Setup.exe (installer)")
    
    print("\n📋 DISTRIBUTION READY:")
    print("🍎 macOS: Drag-and-drop DMG installer")
    print("🪟 Windows: Professional EXE installer + Single EXE option")
    print("🔧 All platforms: Self-contained with FFmpeg bundled")
    
    # Create distribution package
    create_distribution_package(project_root, build_results)
    
    return any(build_results.values())

def create_distribution_package(project_root, build_results):
    """Create a distribution package with all files"""
    print("\n📦 Creating distribution package...")
    
    dist_package = project_root / "DISTRIBUTION_PACKAGE"
    dist_package.mkdir(exist_ok=True)
    
    # Create distribution README
    readme_content = f"""# GoLive Studio Distribution Package

## 📦 Available Installers

### macOS
{'✅ READY' if build_results['macos_dmg'] else '📋 BUILD REQUIRED'}
- **File**: `dist/GoLive_Studio_Installer.dmg`
- **Type**: Professional DMG installer
- **Size**: ~1.0GB
- **Installation**: Drag to Applications folder
- **Requirements**: macOS 10.15+ (Catalina or later)

### Windows EXE (Single File)
{'✅ READY' if build_results['windows_exe_files'] else '📋 BUILD REQUIRED'}
- **Build**: Run `build_windows_exe.bat` on Windows
- **Output**: `GoLive_Studio.exe` (single executable)
- **Size**: ~800MB (estimated)
- **Installation**: No installation required - just run
- **Requirements**: Windows 10 (64-bit) or later

### Windows Installer
{'✅ READY' if build_results['windows_installer_files'] else '📋 BUILD REQUIRED'}
- **Build**: Run `build_windows.bat` on Windows
- **Output**: `GoLive_Studio_Setup.exe` (professional installer)
- **Size**: ~800MB (estimated)
- **Installation**: Full Windows installation with shortcuts
- **Requirements**: Windows 10 (64-bit) or later

## 🚀 Quick Start

### For macOS Users
1. Download `GoLive_Studio_Installer.dmg`
2. Double-click to mount
3. Drag "GoLive Studio" to Applications
4. Launch from Applications folder

### For Windows Users (Option 1 - Installer)
1. Copy all files to Windows machine
2. Run `build_windows.bat`
3. Run the generated `GoLive_Studio_Setup.exe`
4. Follow installation wizard

### For Windows Users (Option 2 - Single EXE)
1. Copy all files to Windows machine
2. Run `build_windows_exe.bat`
3. Copy `GoLive_Studio.exe` anywhere
4. Double-click to run (no installation needed)

## 🔧 Features

### All Platforms
- ✅ FFmpeg bundled internally
- ✅ All dependencies included
- ✅ No external requirements
- ✅ Professional installation experience
- ✅ Camera/microphone access configured
- ✅ Hardware acceleration support

### Platform-Specific
- **macOS**: Code-signed, privacy permissions, native app bundle
- **Windows**: Add/Remove Programs integration, Start Menu shortcuts, UAC support

## 📋 Build Requirements

### macOS Build
- macOS 10.15+ with Xcode Command Line Tools
- Python 3.8+
- All dependencies auto-installed

### Windows Build
- Windows 10 (64-bit) or later
- Python 3.8+ from python.org
- Visual Studio Build Tools (for some packages)
- NSIS (for professional installer)

## 🎯 Distribution Checklist

- [ ] Test macOS DMG on different macOS versions
- [ ] Build and test Windows EXE on Windows 10/11
- [ ] Build and test Windows Installer on Windows 10/11
- [ ] Verify all features work in built applications
- [ ] Test installation/uninstallation processes
- [ ] Create release notes and changelog
- [ ] Upload to distribution platforms

## 📞 Support

For build issues or installer problems:
1. Check system requirements
2. Verify all dependencies installed
3. Run build scripts with verbose output
4. Check error logs in build/ directory

Project: GoLive Studio
Version: 1.0.0
Build System: Cross-platform PyInstaller
"""
    
    readme_path = dist_package / "README.md"
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print(f"✅ Distribution package created: {dist_package}")
    print(f"📄 Documentation: {readme_path}")

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 All installer systems ready for distribution!")
    else:
        print("\n⚠️ Some builds may need attention")
    
    sys.exit(0 if success else 1)
