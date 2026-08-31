import os
import sys
import requests

def main():
    print("==========================================")
    print("      ZEROSPACE SANDBOX TEST UTILITY     ")
    print("==========================================")
    print(f"Current Python Interpreter: {sys.executable}")
    print(f"Current Working Directory: {os.getcwd()}")
    print("\n--- Package Verification ---")
    print(f"Successfully imported requests library: {requests.__version__}")
    
    print("\n--- Sandbox Environment Redirection Reports ---")
    redirects = ["USERPROFILE", "HOMEPATH", "HOMEDRIVE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"]
    all_clean = True
    
    for var in redirects:
        val = os.environ.get(var, "NOT SET")
        print(f"{var}: {val}")
        
        # Check if they point to the sandboxed path inside containers/
        if "containers" not in val.lower() and var not in ["HOMEDRIVE"]:
            all_clean = False
            
    print("\n--- Restricted System PATH Check ---")
    path_val = os.environ.get("PATH", "")
    print(f"PATH: {path_val}")
    
    # Path should have venv/Scripts and system32 only, not other host executables
    path_parts = path_val.split(os.pathsep)
    print(f"PATH Entry Count: {len(path_parts)}")
    
    print("\n--- Summary ---")
    if all_clean:
        print("[SUCCESS] Environment folders isolated inside ZeroSpace containers!")
    else:
        print("[WARNING] File path redirection variables contain raw host paths.")

if __name__ == "__main__":
    main()
