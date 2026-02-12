"""
AutoPost - PyInstaller Wrapper
This script allows the Streamlit app to be compiled into an executable.

Usage:
    1. Run directly: python run_app.py
    2. Compile with PyInstaller:
       pyinstaller --onefile --add-data "Template Audi;Template Audi" --add-data "Template Porsche;Template Porsche" --add-data "Template Jeep;Template Jeep" --add-data "Template BEXP;Template BEXP" run_app.py
"""

import subprocess
import sys
import os
from pathlib import Path


def get_app_path() -> Path:
    """Get the path to app.py (works with PyInstaller)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = Path(sys._MEIPASS)
    else:
        # Running as script
        base_path = Path(__file__).parent
    
    return base_path / "app.py"


def main():
    """Launch the Streamlit application."""
    app_path = get_app_path()
    
    if not app_path.exists():
        print(f"Error: app.py not found at {app_path}")
        sys.exit(1)
    
    # Build the streamlit command
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ]
    
    print("=" * 50)
    print("AutoPost - Multi-Brand Social Media Generator")
    print("=" * 50)
    print()
    print("Starting Streamlit server...")
    print("The browser will open automatically.")
    print("Press Ctrl+C to stop the server.")
    print()
    
    try:
        # Run streamlit
        process = subprocess.run(cmd, cwd=str(app_path.parent))
        sys.exit(process.returncode)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting Streamlit: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
