#!/usr/bin/env python3
"""
GoLive Studio Launcher
Handles PyQt6 code signing issues on macOS before launching the main application
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def sign_libraries():
    """Sign PyQt6 libraries with ad-hoc signature on macOS"""
    if platform.system() != 'Darwin':
        return True
    
    print("Checking PyQt6 library signatures...")
    
    # Get the site-packages directory
    script_dir = Path(__file__).parent
    venv_path = script_dir / 'venv'
    site_packages = venv_path / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
    pyqt6_path = site_packages / 'PyQt6'
    
    if not pyqt6_path.exists():
        print(f"PyQt6 not found at {pyqt6_path}")
        return False
    
    # Find all .so and .dylib files
    libraries = list(pyqt6_path.rglob('*.so')) + list(pyqt6_path.rglob('*.dylib'))
    
    signed_count = 0
    for lib in libraries:
        try:
            # Check if library is already properly signed
            result = subprocess.run(
                ['codesign', '-v', str(lib)],
                capture_output=True,
                text=True
            )
            
            # If verification fails, sign it
            if result.returncode != 0:
                print(f"Signing: {lib.name}")
                subprocess.run(
                    ['codesign', '--force', '--deep', '--sign', '-', str(lib)],
                    check=False,
                    capture_output=True
                )
                signed_count += 1
        except Exception as e:
            print(f"Warning: Could not process {lib.name}: {e}")
    
    if signed_count > 0:
        print(f"Signed {signed_count} libraries.")
    else:
        print("All libraries already properly signed.")
    
    return True

def main():
    """Main launcher function"""
    print("=" * 50)
    print("GoLive Studio Launcher")
    print("=" * 50)
    
    # Sign libraries if on macOS
    if platform.system() == 'Darwin':
        if not sign_libraries():
            print("Warning: Some libraries could not be signed.")
            print("The application may not work properly.")
    
    # Import and run the main application
    print("\nLaunching GoLive Studio...")
    print("-" * 50)
    
    # Add current directory to path
    sys.path.insert(0, str(Path(__file__).parent))
    
    # Import main module
    try:
        import main as golive_main
        # The main module will handle the rest
    except ImportError as e:
        print(f"Error importing main module: {e}")
        print("\nTrying alternative launch method...")
        
        # Alternative: Execute main.py as a subprocess
        script_dir = Path(__file__).parent
        main_py = script_dir / 'main.py'
        
        if main_py.exists():
            subprocess.run([sys.executable, str(main_py)])
        else:
            print(f"Error: main.py not found at {main_py}")
            sys.exit(1)

if __name__ == '__main__':
    main()
