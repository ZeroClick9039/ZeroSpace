import os
import sys

# Check if running in a PyInstaller bundle
IS_BUNDLE = hasattr(sys, "_MEIPASS")

if IS_BUNDLE:
    # PyInstaller extracts files to sys._MEIPASS
    BASE_DIR = sys._MEIPASS
    DATA_DIR = os.path.expanduser("~/.zerospace")
else:
    # Normal development run
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    def is_writable(path: str) -> bool:
        try:
            if not os.path.exists(path):
                parent = os.path.dirname(path)
                return os.access(parent, os.W_OK) if parent else False
            test_file = os.path.join(path, ".write_test")
            with open(test_file, "w") as f:
                pass
            os.remove(test_file)
            return True
        except Exception:
            return False

    DATA_DIR = os.path.expanduser("~/.zerospace")

import json

# Database filepath
DB_FILE = os.path.join(DATA_DIR, "database.json")

# Default directories
DEFAULT_TOOLS_DIR = os.path.join(DATA_DIR, "tools")
DEFAULT_CONTAINERS_DIR = os.path.join(DATA_DIR, "containers")
DEFAULT_LOGS_DIR = os.path.join(DATA_DIR, "logs")

def get_path_from_db(key: str, default_val: str) -> str:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "settings" in data:
                    val = data["settings"].get(key, default_val)
                    if val:
                        return val
        except Exception:
            pass
    return default_val

def get_tools_dir() -> str:
    path = get_path_from_db("tools_path", DEFAULT_TOOLS_DIR)
    os.makedirs(path, exist_ok=True)
    return path

def get_containers_dir() -> str:
    path = get_path_from_db("containers_path", DEFAULT_CONTAINERS_DIR)
    os.makedirs(path, exist_ok=True)
    return path

def get_logs_dir() -> str:
    path = get_path_from_db("logs_path", DEFAULT_LOGS_DIR)
    os.makedirs(path, exist_ok=True)
    return path

# Keep static variables for backward compatibility
TOOLS_DIR = get_tools_dir()
CONTAINERS_DIR = get_containers_dir()
LOGS_DIR = get_logs_dir()


