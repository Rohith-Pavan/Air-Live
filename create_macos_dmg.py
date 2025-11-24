#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Professional macOS DMG Creator for GoLive Studio
Creates a beautiful, professional DMG with proper layout and branding
"""

import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path
import plistlib
import json


class MacOSDMGCreator:
    """Creates professional macOS DMG packages."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.dist_dir = self.project_root / 'dist'
        self.app_name = 'GoLive Studio'
        self.app_path = self.dist_dir / f'{self.app_name}.app'
        self.dmg_path = self.dist_dir / f'{self.app_name}.dmg'
        
    def verify_app_bundle(self):
        """Verify the app bundle exists and is valid."""
        print("🔍 Verifying app bundle...")
        
        if not self.app_path.exists():
            print(f"❌ App bundle not found: {self.app_path}")
            return False
        
        # Check essential app bundle structure
        required_paths = [
            self.app_path / 'Contents',
            self.app_path / 'Contents' / 'MacOS',
            self.app_path / 'Contents' / 'Info.plist',
        ]
        
        for path in required_paths:
            if not path.exists():
                print(f"❌ Missing required path: {path}")
                return False
        
        print(f"✅ App bundle verified: {self.app_path}")
        return True
    
    def sign_app_bundle(self):
        """Sign the app bundle with ad-hoc signature."""
        print("🔐 Signing app bundle...")
        
        try:
            # Sign with ad-hoc signature (no developer certificate required)
            cmd = [
                'codesign',
                '--force',
                '--deep',
                '--sign', '-',
                str(self.app_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ App bundle signed successfully")
                return True
            else:
                print(f"⚠️ Code signing failed: {result.stderr}")
                print("📝 Continuing without signature (app will still work)")
                return True  # Continue even if signing fails
                
        except Exception as e:
            print(f"⚠️ Code signing error: {e}")
            print("📝 Continuing without signature")
            return True
    
    def create_dmg_background(self):
        """Create a custom DMG background image."""
        print("🎨 Creating DMG background...")
        
        # For now, we'll use a simple approach without custom background
        # You can enhance this to create a custom background image
        return True
    
    def create_dmg_with_hdiutil(self):
        """Create DMG using hdiutil (built-in macOS tool)."""
        print("📦 Creating DMG with hdiutil...")
        
        try:
            # Remove existing DMG
            if self.dmg_path.exists():
                self.dmg_path.unlink()
            
            # Create temporary directory for DMG contents
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                dmg_contents = temp_path / 'dmg_contents'
                dmg_contents.mkdir()
                
                # Copy app to DMG contents
                app_in_dmg = dmg_contents / f'{self.app_name}.app'
                shutil.copytree(self.app_path, app_in_dmg)
                
                # Create Applications symlink
                applications_link = dmg_contents / 'Applications'
                applications_link.symlink_to('/Applications')
                
                # Create DMG
                cmd = [
                    'hdiutil', 'create',
                    '-volname', self.app_name,
                    '-srcfolder', str(dmg_contents),
                    '-ov',
                    '-format', 'UDZO',
                    '-imagekey', 'zlib-level=9',
                    str(self.dmg_path)
                ]
                
                print(f"🔨 Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"✅ DMG created successfully: {self.dmg_path}")
                    return True
                else:
                    print(f"❌ DMG creation failed: {result.stderr}")
                    return False
                    
        except Exception as e:
            print(f"❌ DMG creation error: {e}")
            return False
    
    def create_professional_dmg(self):
        """Create a professional DMG with custom layout."""
        print("🎨 Creating professional DMG...")
        
        try:
            # Remove existing DMG
            if self.dmg_path.exists():
                self.dmg_path.unlink()
            
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Step 1: Create a writable DMG
                temp_dmg = temp_path / 'temp.dmg'
                cmd = [
                    'hdiutil', 'create',
                    '-srcfolder', str(self.app_path.parent),
                    '-volname', self.app_name,
                    '-fs', 'HFS+',
                    '-fsargs', '-c c=64,a=16,e=16',
                    '-format', 'UDRW',
                    '-size', '500m',
                    str(temp_dmg)
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                # Step 2: Mount the DMG
                mount_result = subprocess.run([
                    'hdiutil', 'attach', str(temp_dmg), '-readwrite', '-noverify', '-noautoopen'
                ], capture_output=True, text=True, check=True)
                
                # Parse mount point
                mount_point = None
                for line in mount_result.stdout.split('\n'):
                    if '/Volumes/' in line:
                        mount_point = line.split('\t')[-1].strip()
                        break
                
                if not mount_point:
                    raise Exception("Could not determine mount point")
                
                mount_path = Path(mount_point)
                print(f"📁 Mounted DMG at: {mount_path}")
                
                try:
                    # Step 3: Customize DMG contents
                    # Remove any existing files
                    for item in mount_path.iterdir():
                        if item.name != f'{self.app_name}.app':
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                    
                    # Create Applications symlink
                    applications_link = mount_path / 'Applications'
                    if not applications_link.exists():
                        applications_link.symlink_to('/Applications')
                    
                    # Set custom icon positions (using AppleScript)
                    applescript = f'''
                    tell application "Finder"
                        tell disk "{self.app_name}"
                            open
                            set current view of container window to icon view
                            set toolbar visible of container window to false
                            set statusbar visible of container window to false
                            set the bounds of container window to {{100, 100, 600, 400}}
                            set viewOptions to the icon view options of container window
                            set arrangement of viewOptions to not arranged
                            set icon size of viewOptions to 128
                            set position of item "{self.app_name}.app" of container window to {{150, 200}}
                            set position of item "Applications" of container window to {{350, 200}}
                            close
                            open
                            update without registering applications
                            delay 2
                        end tell
                    end tell
                    '''
                    
                    # Run AppleScript to set layout
                    try:
                        subprocess.run(['osascript', '-e', applescript], 
                                     capture_output=True, timeout=30)
                        print("✅ DMG layout configured")
                    except:
                        print("⚠️ Could not set custom layout (DMG will still work)")
                    
                finally:
                    # Step 4: Unmount the DMG
                    subprocess.run(['hdiutil', 'detach', str(mount_path)], 
                                 capture_output=True)
                
                # Step 5: Convert to compressed read-only DMG
                cmd = [
                    'hdiutil', 'convert', str(temp_dmg),
                    '-format', 'UDZO',
                    '-imagekey', 'zlib-level=9',
                    '-o', str(self.dmg_path)
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"✅ Professional DMG created: {self.dmg_path}")
                return True
                
        except Exception as e:
            print(f"❌ Professional DMG creation failed: {e}")
            print("🔄 Falling back to simple DMG creation...")
            return self.create_dmg_with_hdiutil()
    
    def verify_dmg(self):
        """Verify the created DMG."""
        print("🔍 Verifying DMG...")
        
        if not self.dmg_path.exists():
            print(f"❌ DMG not found: {self.dmg_path}")
            return False
        
        try:
            # Test mount the DMG
            result = subprocess.run([
                'hdiutil', 'attach', str(self.dmg_path), '-verify', '-readonly'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Find mount point and unmount
                mount_point = None
                for line in result.stdout.split('\n'):
                    if '/Volumes/' in line:
                        mount_point = line.split('\t')[-1].strip()
                        break
                
                if mount_point:
                    subprocess.run(['hdiutil', 'detach', mount_point], 
                                 capture_output=True)
                
                # Get DMG size
                size_mb = self.dmg_path.stat().st_size / (1024 * 1024)
                print(f"✅ DMG verified successfully ({size_mb:.1f} MB)")
                return True
            else:
                print(f"❌ DMG verification failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ DMG verification error: {e}")
            return False
    
    def create_dmg(self):
        """Main DMG creation process."""
        print(f"\n🍎 Creating macOS DMG for {self.app_name}")
        print("=" * 50)
        
        # Step 1: Verify app bundle
        if not self.verify_app_bundle():
            return False
        
        # Step 2: Sign app bundle
        if not self.sign_app_bundle():
            return False
        
        # Step 3: Create DMG background
        self.create_dmg_background()
        
        # Step 4: Create professional DMG
        if not self.create_professional_dmg():
            return False
        
        # Step 5: Verify DMG
        if not self.verify_dmg():
            return False
        
        print(f"\n🎉 DMG creation completed successfully!")
        print(f"📁 DMG location: {self.dmg_path}")
        print(f"📊 DMG size: {self.dmg_path.stat().st_size / (1024 * 1024):.1f} MB")
        
        return True


def main():
    """Main function."""
    if sys.platform != 'darwin':
        print("❌ This script must be run on macOS")
        sys.exit(1)
    
    creator = MacOSDMGCreator()
    success = creator.create_dmg()
    
    if not success:
        print("❌ DMG creation failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
