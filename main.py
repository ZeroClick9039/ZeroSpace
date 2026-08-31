import sys
import os
import time
import threading
import webbrowser
import logging

# Ensure the root folder is on the python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from zerospace.app import app

logger = logging.getLogger("zerospace.main")

def open_browser_async():
    """Wait for Flask server to boot, then launch the browser."""
    logger.info("Starting browser launcher thread...")
    time.sleep(1.5)
    url = "http://127.0.0.1:5000"
    logger.info(f"Opening default web browser to: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Failed to automatically open browser: {e}")
        print(f"\n[ZEROSPACE SERVER ACTIVE] Please open your browser manually and visit: {url}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "cli":
            if len(sys.argv) < 4:
                print("Usage: zerospace cli <tool_id> <command>")
                sys.exit(1)
            tool_id = sys.argv[2]
            command = " ".join(sys.argv[3:])
            
            from zerospace.manager import ToolManager
            manager = ToolManager()
            success = manager.run_cli_command_sync(tool_id, command)
            sys.exit(0 if success else 1)
            
        elif cmd == "list":
            from zerospace.manager import ToolManager
            manager = ToolManager()
            tools = manager.db.list_tools()
            print("\nInstalled ZeroSpace Tools:")
            print("=========================")
            for t in tools:
                print(f"ID: {t['id']:<35} Name: {t['name']:<30} Languages: {t['language']}")
            print("")
            sys.exit(0)
            
        elif cmd in ["help", "--help", "-h"]:
            print("\nZeroSpace CLI Usage:")
            print("====================")
            print("Run web interface:     zerospace")
            print("List installed tools:  zerospace list")
            print("Run sandboxed command: zerospace cli <tool_id> <command>")
            print("                       (e.g., zerospace cli python_tool \"pip install colorama\")")
            print("")
            sys.exit(0)
            
    print("==========================================")
    print("               ZEROSPACE                  ")
    print("       Cybersecurity Tool Manager        ")
    print("==========================================")
    print("Booting local secure sandboxed layers...")
    
    # Run browser launch asynchronously
    threading.Thread(target=open_browser_async, daemon=True).start()
    
    # Start Flask Web Server
    try:
        app.run(host="127.0.0.1", port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nZeroSpace server shutting down. Sandbox environments secured.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Server startup failed: {e}")
        sys.exit(1)
