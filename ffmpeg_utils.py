#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg Utilities for GoLive Studio
Provides centralized FFmpeg path resolution for bundled applications
"""

import os
import sys
import shutil
from typing import Optional


def get_ffmpeg_path() -> str:
    """
    Get the path to FFmpeg binary (bundled or system)
    
    Returns:
        str: Path to FFmpeg executable
    """
    # Check environment variable set by main.py
    env_path = os.environ.get('GOLIVE_FFMPEG_PATH')
    if env_path and os.path.exists(env_path):
        # Only use env path if it works
        try:
            if verify_ffmpeg(env_path):
                return env_path
        except Exception:
            pass
    
    # Prefer system/Homebrew FFmpeg first: resolve absolute path if possible
    try:
        which_path = shutil.which('ffmpeg')
        if which_path and os.path.exists(which_path):
            try:
                if verify_ffmpeg(which_path):
                    return which_path
            except Exception:
                pass
        # Check common install locations (macOS/Homebrew and others)
        common_candidates = [
            '/opt/homebrew/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/usr/bin/ffmpeg',
        ]
        for p in common_candidates:
            if os.path.exists(p) and os.access(p, os.X_OK):
                try:
                    if verify_ffmpeg(p):
                        return p
                except Exception:
                    pass
    except Exception:
        pass

    # Try to find bundled FFmpeg as a fallback
    bundled_path = _find_bundled_ffmpeg()
    if bundled_path:
        # Reject if quarantined (Gatekeeper) or fails verification
        try:
            # If xattr is available, treat com.apple.quarantine as not working
            try:
                import subprocess as _sub
                attrs = _sub.run(['xattr', '-l', bundled_path], capture_output=True, text=True)
                if attrs.returncode == 0 and 'com.apple.quarantine' in (attrs.stdout or ''):
                    raise RuntimeError('Bundled FFmpeg is quarantined')
            except Exception:
                # Best effort only
                pass
            if verify_ffmpeg(bundled_path):
                return bundled_path
        except Exception:
            pass
    # As a last resort, return the bare command (may fail with QProcess if PATH lacks ffmpeg)
    return 'ffmpeg'


def _find_bundled_ffmpeg() -> Optional[str]:
    """
    Find bundled FFmpeg binary in various possible locations
    
    Returns:
        Optional[str]: Path to bundled FFmpeg if found, None otherwise
    """
    try:
        # Get base directory
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller onefile mode
                base_dir = sys._MEIPASS
            else:
                # PyInstaller onedir mode
                base_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        candidates = []
        
        # Platform-specific FFmpeg binary names and locations
        if sys.platform.startswith('win'):
            # Windows: ffmpeg.exe in various locations
            candidates.extend([
                os.path.join(base_dir, 'ffmpeg', 'ffmpeg.exe'),
                os.path.join(base_dir, 'ffmpeg.exe'),
                os.path.join(os.path.dirname(base_dir), 'ffmpeg', 'ffmpeg.exe'),
            ])
        else:
            # macOS/Linux: ffmpeg binary
            candidates.extend([
                os.path.join(base_dir, 'ffmpeg', 'ffmpeg'),
                os.path.join(base_dir, 'ffmpeg'),
                os.path.join(base_dir, '..', 'Resources', 'ffmpeg', 'ffmpeg'),  # macOS .app bundle
                os.path.join(os.path.dirname(base_dir), 'ffmpeg', 'ffmpeg'),
            ])
        
        # Find first existing FFmpeg binary
        for candidate in candidates:
            if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate
        
        return None
    except Exception:
        return None


def verify_ffmpeg(ffmpeg_path: str) -> bool:
    """
    Verify that FFmpeg binary works
    
    Args:
        ffmpeg_path (str): Path to FFmpeg binary
        
    Returns:
        bool: True if FFmpeg works, False otherwise
    """
    try:
        import subprocess
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def setup_ffmpeg_environment() -> Optional[str]:
    """
    Setup FFmpeg environment and return the path being used
    
    Returns:
        Optional[str]: Path to FFmpeg if found and working, None otherwise
    """
    ffmpeg_path = get_ffmpeg_path()
    
    if verify_ffmpeg(ffmpeg_path):
        # Set environment variable for other modules
        os.environ['GOLIVE_FFMPEG_PATH'] = ffmpeg_path
        
        # Add directory to PATH if it's a full path
        if os.path.dirname(ffmpeg_path):
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            current_path = os.environ.get('PATH', '')
            if ffmpeg_dir not in current_path:
                os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
        
        return ffmpeg_path
    
    return None


if __name__ == '__main__':
    # Test the FFmpeg detection
    print("Testing FFmpeg detection...")
    
    ffmpeg_path = setup_ffmpeg_environment()
    if ffmpeg_path:
        print(f"✓ FFmpeg found and working: {ffmpeg_path}")
        
        # Test version
        try:
            import subprocess
            result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True)
            if result.stdout:
                version_line = result.stdout.split('\n')[0]
                print(f"  Version: {version_line}")
        except Exception as e:
            print(f"  Could not get version: {e}")
    else:
        print("✗ FFmpeg not found or not working")
        print("  Please ensure FFmpeg is installed or bundled with the application")
