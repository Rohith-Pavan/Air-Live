#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Build Script for GoLive Studio
One-click build for your platform
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def main():
    """Simple build function."""
    project_root = Path(__file__).parent
    platform_name = platform.system().lower()
    
    print("🚀 GoLive Studio Simple Builder")
    print(f"💻 Platform: {platform.system()}")
    print(f"📁 Project: {project_root}")
    
    # Run the master builder
    try:
        result = subprocess.run([
            sys.executable, 'build_master.py'
        ], cwd=project_root)
        
        if result.returncode == 0:
            print("\n✅ Build completed successfully!")
        else:
            print("\n❌ Build failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Build cancelled by user")
    except Exception as e:
        print(f"\n❌ Build error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
