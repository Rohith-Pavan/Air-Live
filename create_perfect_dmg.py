#!/usr/bin/env python3
"""
Create a perfect DMG for GoLive Studio
"""

import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

def create_perfect_dmg():
    """Create a professional DMG with Applications folder link"""
    print("🎯 Creating perfect DMG...")
    
    project_root = Path(__file__).parent
    app_path = project_root / 'dist' / 'GoLive Studio.app'
    
    if not app_path.exists():
        print("❌ App bundle not found. Run fix_dmg.py first.")
        return False
    
    # Create temporary directory for DMG contents
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        dmg_contents = temp_path / 'dmg_contents'
        dmg_contents.mkdir()
        
        # Copy app to DMG contents
        print("   Copying app bundle...")
        shutil.copytree(app_path, dmg_contents / 'GoLive Studio.app')
        
        # Create Applications folder symlink
        print("   Creating Applications symlink...")
        applications_link = dmg_contents / 'Applications'
        applications_link.symlink_to('/Applications')
        
        # Create .DS_Store for nice layout (optional)
        ds_store_content = dmg_contents / '.DS_Store'
        
        # Create temporary DMG
        temp_dmg = temp_path / 'temp.dmg'
        
        print("   Creating temporary DMG...")
        cmd = [
            'hdiutil', 'create',
            '-srcfolder', str(dmg_contents),
            '-volname', 'GoLive Studio',
            '-fs', 'HFS+',
            '-fsargs', '-c c=64,a=16,e=16',
            '-format', 'UDRW',
            str(temp_dmg)
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"❌ Failed to create temporary DMG: {result.stderr.decode()}")
            return False
        
        # Mount the temporary DMG
        print("   Mounting temporary DMG...")
        mount_result = subprocess.run([
            'hdiutil', 'attach', str(temp_dmg), '-readwrite', '-noverify', '-noautoopen'
        ], capture_output=True, text=True)
        
        if mount_result.returncode != 0:
            print(f"❌ Failed to mount DMG: {mount_result.stderr}")
            return False
        
        # Find the mount point
        mount_point = None
        for line in mount_result.stdout.split('\n'):
            if 'GoLive Studio' in line and '/Volumes/' in line:
                mount_point = line.split()[-1]
                break
        
        if not mount_point:
            print("❌ Could not find mount point")
            return False
        
        print(f"   Mounted at: {mount_point}")
        
        # Set up the DMG layout using AppleScript
        applescript = f'''
        tell application "Finder"
            tell disk "GoLive Studio"
                open
                set current view of container window to icon view
                set toolbar visible of container window to false
                set statusbar visible of container window to false
                set the bounds of container window to {{100, 100, 600, 400}}
                set viewOptions to the icon view options of container window
                set arrangement of viewOptions to not arranged
                set icon size of viewOptions to 128
                set background picture of viewOptions to file ".background:background.png"
                set position of item "GoLive Studio.app" of container window to {{150, 200}}
                set position of item "Applications" of container window to {{350, 200}}
                close
                open
                update without registering applications
                delay 2
            end tell
        end tell
        '''
        
        # Run AppleScript (optional - for better layout)
        try:
            subprocess.run(['osascript', '-e', applescript], check=False)
        except:
            print("   Skipping AppleScript layout (optional)")
        
        # Unmount the DMG
        print("   Unmounting temporary DMG...")
        subprocess.run(['hdiutil', 'detach', mount_point], check=True)
        
        # Convert to final compressed DMG
        final_dmg = project_root / 'dist' / 'GoLive Studio.dmg'
        if final_dmg.exists():
            final_dmg.unlink()
        
        print("   Creating final compressed DMG...")
        cmd = [
            'hdiutil', 'convert', str(temp_dmg),
            '-format', 'UDZO',
            '-imagekey', 'zlib-level=9',
            '-o', str(final_dmg)
        ]
        
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("❌ Failed to create final DMG")
            return False
    
    print("✅ Perfect DMG created successfully!")
    print(f"📦 DMG location: {final_dmg}")
    
    # Get file size
    size_mb = final_dmg.stat().st_size / (1024 * 1024)
    print(f"📏 DMG size: {size_mb:.1f} MB")
    
    return True

if __name__ == '__main__':
    success = create_perfect_dmg()
    sys.exit(0 if success else 1)