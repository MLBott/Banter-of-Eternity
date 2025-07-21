#!/usr/bin/env python3
"""
Setup and start script for the Vignette Generator Web Interface.
Installs required packages and starts the web server.
"""

import sys
import subprocess
import os
from pathlib import Path

def install_requirements():
    """Install required Python packages."""
    print("📦 Installing required packages...")
    
    packages = [
        'flask',
        'flask-cors',
        'pathlib',
        'asyncio'
    ]
    
    for package in packages:
        try:
            print(f"   Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"   ✅ {package} installed")
        except subprocess.CalledProcessError:
            print(f"   ❌ Failed to install {package}")
            return False
    
    print("✅ All packages installed successfully!")
    return True

def start_server():
    """Start the web server."""
    print("\n🚀 Starting Vignette Generator Web Interface...")
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Start the web server
    try:
        import web_server
    except ImportError as e:
        print(f"❌ Failed to import web_server: {e}")
        return False
    
    return True

def main():
    """Main setup and start function."""
    print("🎭 Pillars of Eternity II - Vignette Generator Web Interface Setup")
    print("=" * 70)
    
    # Install requirements
    if not install_requirements():
        print("❌ Failed to install requirements. Please install manually:")
        print("   pip install flask flask-cors")
        return False
    
    # Start server
    if not start_server():
        print("❌ Failed to start web server")
        return False
    
    return True

if __name__ == '__main__':
    main()
