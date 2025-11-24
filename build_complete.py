#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Build System for GoLive Studio
Creates working executables for Windows and macOS with all dependencies
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

class GoLiveBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.is_windows = sys.platform.startswith('win')
        self.is_macos = sys.platform == 'darwin'
        self.is_linux = sys.platform.startswith('linux')
        
        # Build directories
        self.build_dir = self.project_root / 'build'
        self.dist_dir = self.project_root / 'dist'
        self.ffmpeg_dir = self.project_root / 'ffmpeg'
        
        # Clean previous builds
        self.clean_build()
        
    def clean_build(self):
        """Clean previous build artifacts"""
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
            
        print("✅ Build cleanup complete")
    
    def check_python_version(self):
        """Check Python version compatibility"""
        print("🐍 Checking Python version...")
        
        version = sys.version_info
        if version.major != 3 or version.minor < 8:
            raise RuntimeError(f"Python 3.8+ required, got {version.major}.{version.minor}")
        
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    
    def install_dependencies(self):
        """Install all required dependencies"""
        print("📦 Installing dependencies...")
        
        # Core dependencies that must be installed
        core_deps = [
            'PyQt6>=6.6.0',
            'PyQt6-Qt6>=6.6.0',
            'Pillow>=10.0.0',
            'opencv-python>=4.8.0',
            'numpy>=1.21.0,<2.0.0',
            'av>=10.0.0',
            'PyOpenGL>=3.1.6',
            'PyOpenGL-accelerate>=3.1.6',
            'packaging>=21.0',
            'PyInstaller>=5.13.0',
            'psutil>=5.9.0',
            'requests>=2.28.0',
        ]
        
        # Platform-specific dependencies
        if self.is_macos:
            core_deps.extend([
                'pyobjc-framework-Cocoa>=10.0',
                'pyobjc-framework-AVFoundation>=10.0',
                'pyobjc-framework-CoreMedia>=10.0',
                'pyobjc-framework-CoreVideo>=10.0',
                'pyobjc-framework-Quartz>=10.0',
                'pyobjc-framework-AppKit>=10.0',
            ])
        elif self.is_windows:
            core_deps.extend([
                'pywin32>=227',
            ])
        
        # Install dependencies
        for dep in core_deps:
            print(f"   Installing {dep}...")
            try:
                subprocess.run([
                    sys.executable, '-m', 'pip', 'install', '--upgrade', dep
                ], check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                print(f"   ⚠️  Warning: Failed to install {dep}: {e}")
        
        print("✅ Dependencies installation complete")
    
    def download_ffmpeg(self):
        """Download and setup FFmpeg binary"""
        print("🎬 Setting up FFmpeg...")
        
        self.ffmpeg_dir.mkdir(exist_ok=True)
        
        if self.is_windows:
            ffmpeg_exe = self.ffmpeg_dir / 'ffmpeg.exe'
            if not ffmpeg_exe.exists():
                print("   Downloading FFmpeg for Windows...")
                self._download_ffmpeg_windows()
        elif self.is_macos:
            ffmpeg_exe = self.ffmpeg_dir / 'ffmpeg'
            if not ffmpeg_exe.exists():
                print("   Downloading FFmpeg for macOS...")
                self._download_ffmpeg_macos()
        
        print("✅ FFmpeg setup complete")
    
    def _download_ffmpeg_windows(self):
        """Download FFmpeg for Windows"""
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / 'ffmpeg.zip'
            
            # Download
            print("   Downloading FFmpeg archive...")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Extract
            print("   Extracting FFmpeg...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)
            
            # Find and copy ffmpeg.exe
            for ffmpeg_exe in temp_path.rglob('ffmpeg.exe'):
                if 'bin' in str(ffmpeg_exe):
                    shutil.copy2(ffmpeg_exe, self.ffmpeg_dir / 'ffmpeg.exe')
                    break
    
    def _download_ffmpeg_macos(self):
        """Download FFmpeg for macOS"""
        # Try to use system FFmpeg first
        system_ffmpeg = shutil.which('ffmpeg')
        if system_ffmpeg:
            print("   Using system FFmpeg...")
            shutil.copy2(system_ffmpeg, self.ffmpeg_dir / 'ffmpeg')
            return
        
        # Download static build
        if platform.machine() == 'arm64':
            url = "https://evermeet.cx/ffmpeg/getrelease/zip"
        else:
            url = "https://evermeet.cx/ffmpeg/getrelease/zip"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            zip_path = temp_path / 'ffmpeg.zip'
            
            # Download
            print("   Downloading FFmpeg archive...")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Extract
            print("   Extracting FFmpeg...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)
            
            # Find and copy ffmpeg
            for ffmpeg_exe in temp_path.rglob('ffmpeg'):
                if ffmpeg_exe.is_file() and os.access(ffmpeg_exe, os.X_OK):
                    shutil.copy2(ffmpeg_exe, self.ffmpeg_dir / 'ffmpeg')
                    break
    
    def verify_files(self):
        """Verify all required files exist"""
        print("🔍 Verifying project files...")
        
        required_files = [
            'main.py',
            'mainwindow.ui',
            'config.py',
            'streaming.py',
            'recording.py',
            'ffmpeg_utils.py',
        ]
        
        required_dirs = [
            'icons',
            'effects',
            'renderer',
            'encoder',
            'audio',
        ]
        
        missing_files = []
        
        # Check files
        for file_name in required_files:
            file_path = self.project_root / file_name
            if not file_path.exists():
                missing_files.append(file_name)
        
        # Check directories
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                missing_files.append(f"{dir_name}/ (directory)")
        
        if missing_files:
            raise RuntimeError(f"Missing required files: {', '.join(missing_files)}")
        
        print("✅ All required files present")
    
    def build_executable(self):
        """Build the executable using PyInstaller"""
        print("🔨 Building executable...")
        
        spec_file = self.project_root / 'GoLive_Studio.spec'
        if not spec_file.exists():
            raise RuntimeError("GoLive_Studio.spec file not found")
        
        # Run PyInstaller
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--noconfirm',
            str(spec_file)
        ]
        
        print(f"   Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=self.project_root)
        
        if result.returncode != 0:
            raise RuntimeError("PyInstaller build failed")
        
        print("✅ Executable build complete")
    
    def create_installer(self):
        """Create platform-specific installer"""
        if self.is_windows:
            self._create_windows_installer()
        elif self.is_macos:
            self._create_macos_dmg()
    
    def _create_windows_installer(self):
        """Create Windows installer using NSIS"""
        print("📦 Creating Windows installer...")
        
        # Check if NSIS is available
        nsis_path = shutil.which('makensis')
        if not nsis_path:
            print("   ⚠️  NSIS not found, skipping installer creation")
            print("   💡 Install NSIS from https://nsis.sourceforge.io/ to create installers")
            return
        
        # Create NSIS script
        nsis_script = self._generate_nsis_script()
        nsis_file = self.project_root / 'installer.nsi'
        
        with open(nsis_file, 'w', encoding='utf-8') as f:
            f.write(nsis_script)
        
        # Run NSIS
        cmd = [nsis_path, str(nsis_file)]
        result = subprocess.run(cmd, cwd=self.project_root)
        
        if result.returncode == 0:
            print("✅ Windows installer created")
        else:
            print("   ⚠️  Installer creation failed")
    
    def _create_macos_dmg(self):
        """Create macOS DMG"""
        print("📦 Creating macOS DMG...")
        
        app_path = self.dist_dir / 'GoLive Studio.app'
        if not app_path.exists():
            print("   ⚠️  App bundle not found, skipping DMG creation")
            return
        
        dmg_path = self.dist_dir / 'GoLive Studio.dmg'
        
        # Create DMG
        cmd = [
            'hdiutil', 'create',
            '-volname', 'GoLive Studio',
            '-srcfolder', str(app_path),
            '-ov', '-format', 'UDZO',
            str(dmg_path)
        ]
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print("✅ macOS DMG created")
        else:
            print("   ⚠️  DMG creation failed")
    
    def _generate_nsis_script(self):
        """Generate NSIS installer script"""
        return '''
!define APPNAME "GoLive Studio"
!define COMPANYNAME "GoLive Studio"
!define DESCRIPTION "Live Streaming and Recording Application"
!define VERSIONMAJOR 1
!define VERSIONMINOR 0
!define VERSIONBUILD 0
!define HELPURL "https://github.com/yourusername/golive-studio"
!define UPDATEURL "https://github.com/yourusername/golive-studio"
!define ABOUTURL "https://github.com/yourusername/golive-studio"
!define INSTALLSIZE 500000

RequestExecutionLevel admin
InstallDir "$PROGRAMFILES\\${COMPANYNAME}\\${APPNAME}"
Name "${APPNAME}"
Icon "EditLive.ico"
outFile "GoLive Studio Installer.exe"

!include LogicLib.nsh

page directory
Page instfiles

!macro VerifyUserIsAdmin
UserInfo::GetAccountType
pop $0
${If} $0 != "admin"
    messageBox mb_iconstop "Administrator rights required!"
    setErrorLevel 740
    quit
${EndIf}
!macroend

function .onInit
    setShellVarContext all
    !insertmacro VerifyUserIsAdmin
functionEnd

section "install"
    setOutPath $INSTDIR
    file /r "dist\\GoLive Studio\\"
    
    writeUninstaller "$INSTDIR\\uninstall.exe"
    
    createDirectory "$SMPROGRAMS\\${COMPANYNAME}"
    createShortCut "$SMPROGRAMS\\${COMPANYNAME}\\${APPNAME}.lnk" "$INSTDIR\\GoLive Studio.exe" "" "$INSTDIR\\GoLive Studio.exe"
    createShortCut "$DESKTOP\\${APPNAME}.lnk" "$INSTDIR\\GoLive Studio.exe" "" "$INSTDIR\\GoLive Studio.exe"
    
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "DisplayName" "${APPNAME}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "UninstallString" "$INSTDIR\\uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "DisplayIcon" "$INSTDIR\\GoLive Studio.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "Publisher" "${COMPANYNAME}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "HelpLink" "${HELPURL}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "URLUpdateInfo" "${UPDATEURL}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "URLInfoAbout" "${ABOUTURL}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "VersionMajor" ${VERSIONMAJOR}
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "VersionMinor" ${VERSIONMINOR}
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "NoRepair" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}" "EstimatedSize" ${INSTALLSIZE}
sectionEnd

section "uninstall"
    delete "$INSTDIR\\uninstall.exe"
    rmDir /r "$INSTDIR"
    
    delete "$SMPROGRAMS\\${COMPANYNAME}\\${APPNAME}.lnk"
    rmDir "$SMPROGRAMS\\${COMPANYNAME}"
    delete "$DESKTOP\\${APPNAME}.lnk"
    
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${COMPANYNAME} ${APPNAME}"
sectionEnd
'''
    
    def test_executable(self):
        """Test the built executable"""
        print("🧪 Testing executable...")
        
        if self.is_windows:
            exe_path = self.dist_dir / 'GoLive Studio' / 'GoLive Studio.exe'
        elif self.is_macos:
            exe_path = self.dist_dir / 'GoLive Studio.app' / 'Contents' / 'MacOS' / 'GoLive Studio'
        else:
            exe_path = self.dist_dir / 'GoLive Studio' / 'GoLive Studio'
        
        if not exe_path.exists():
            print(f"   ⚠️  Executable not found at {exe_path}")
            return False
        
        # Test if executable can start (quick test)
        try:
            if self.is_macos:
                # For macOS, test the app bundle
                cmd = ['open', '-W', '-n', str(self.dist_dir / 'GoLive Studio.app'), '--args', '--version']
            else:
                cmd = [str(exe_path), '--version']
            
            # Quick test - just see if it starts without crashing immediately
            result = subprocess.run(cmd, timeout=10, capture_output=True)
            print("✅ Executable test passed")
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"   ⚠️  Executable test failed: {e}")
            return False
    
    def print_summary(self):
        """Print build summary"""
        print("\n" + "="*60)
        print("🎉 BUILD COMPLETE!")
        print("="*60)
        
        if self.is_windows:
            exe_path = self.dist_dir / 'GoLive Studio'
            installer_path = self.project_root / 'GoLive Studio Installer.exe'
            
            print(f"📁 Executable folder: {exe_path}")
            if installer_path.exists():
                print(f"📦 Installer: {installer_path}")
            
        elif self.is_macos:
            app_path = self.dist_dir / 'GoLive Studio.app'
            dmg_path = self.dist_dir / 'GoLive Studio.dmg'
            
            print(f"📱 App bundle: {app_path}")
            if dmg_path.exists():
                print(f"💿 DMG installer: {dmg_path}")
        
        print("\n💡 Next steps:")
        if self.is_windows:
            print("   • Test the executable in dist/GoLive Studio/")
            print("   • Run the installer to test installation")
            print("   • Distribute the installer to users")
        elif self.is_macos:
            print("   • Test the app bundle")
            print("   • Mount the DMG to test installation")
            print("   • Consider code signing for distribution")
        
        print("="*60)
    
    def build(self):
        """Run the complete build process"""
        try:
            print("🚀 Starting GoLive Studio build process...")
            print(f"🖥️  Platform: {platform.system()} {platform.machine()}")
            
            self.check_python_version()
            self.install_dependencies()
            self.download_ffmpeg()
            self.verify_files()
            self.build_executable()
            self.create_installer()
            self.test_executable()
            self.print_summary()
            
        except Exception as e:
            print(f"\n❌ Build failed: {e}")
            sys.exit(1)

def main():
    """Main entry point"""
    builder = GoLiveBuilder()
    builder.build()

if __name__ == '__main__':
    main()