import subprocess
import sys
import os
import shutil

def main():
    print("ZeroSpace Windows Build Script")
    print("==============================")
    
    # 1. Install pyinstaller if not present
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing via pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        
    print("Using PyInstaller to build standalone executable...")
    
    # Clean up previous build files to avoid overwriting issues
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    exe_file = os.path.join("dist", "zerospace.exe")
    if os.path.exists(exe_file):
        try:
            os.remove(exe_file)
        except Exception:
            pass

            
    # PyInstaller arguments
    # --add-data "source;destination"
    # Note: On Windows, use semicolon ";" as separator.
    cmd = [
        "pyinstaller",
        "--name=zerospace",
        "--onefile",
        "--add-data=zerospace/templates;zerospace/templates",
        "--add-data=zerospace/static;zerospace/static",
        "--add-data=mock_tools;mock_tools",
        "--clean",
        "main.py"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    
    if res.returncode == 0:
        print("\nSUCCESS: Windows executable built at: dist/zerospace.exe")
    else:
        print("\nERROR: PyInstaller compilation failed.")
        sys.exit(res.returncode)

if __name__ == "__main__":
    main()
