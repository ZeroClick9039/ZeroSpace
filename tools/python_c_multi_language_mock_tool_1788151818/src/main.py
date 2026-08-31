import os
import subprocess
import sys
import requests

def main():
    print("==========================================")
    print("      ZEROSPACE MULTI-LANGUAGE TEST      ")
    print("==========================================")
    print(f"Current Python Interpreter: {sys.executable}")
    print(f"Successfully imported requests library: {requests.__version__}")
    
    # Call compiled helper.exe
    helper_path = os.path.join(os.path.dirname(__file__), "helper.exe")
    print(f"Calling C helper at: {helper_path}")
    if os.path.exists(helper_path):
        res = subprocess.run([helper_path], capture_output=True, text=True)
        print(res.stdout)
    else:
        print("[ERROR] Compiled helper.exe not found!")
        sys.exit(1)
        
    userprofile = os.environ.get("USERPROFILE", "")
    if "containers" in userprofile.lower():
        print("\n[SUCCESS] Environment folders isolated inside ZeroSpace containers!")
    else:
        print("\n[WARNING] USERPROFILE does not point to containers folder.")

if __name__ == "__main__":
    main()
