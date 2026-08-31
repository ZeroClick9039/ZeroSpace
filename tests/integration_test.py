import os
import sys
import time

# Ensure workspace is on the python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from zerospace.manager import ToolManager

def run_integration_test():
    print("==========================================")
    print("      ZEROSPACE INTEGRATION TEST RUN     ")
    print("==========================================")
    
    manager = ToolManager()
    mock_path = os.path.join(BASE_DIR, "mock_tools", "sandbox_verify")
    
    print(f"Adding local mock tool from: {mock_path}")
    try:
        tool_id = manager.add_tool(
            name="Sandbox Verification Tool",
            source=mock_path,
            description="Verifies folder isolation and environment variables sandboxing in ZeroSpace."
        )
        print(f"Tool successfully registered with ID: {tool_id}")
    except Exception as e:
        print(f"[ERROR] Failed to add tool: {e}")
        return
        
    print("\nMonitoring background environment builder thread...")
    setup_ok = False
    
    # Wait for setup thread (creating venv and installing requests)
    for step in range(30):
        status = manager.get_tool_status(tool_id)
        print(f"[{step*2}s] Setup Status: {status}")
        
        if status == "Installed":
            setup_ok = True
            break
        elif status == "Setup Error":
            break
            
        time.sleep(2)
        
    if not setup_ok:
        print("\n[FAIL] Setup failed to build virtual environment. Check logs:")
        print(manager.get_logs(tool_id, log_type="setup"))
        return
        
    print("\n[SUCCESS] Sandbox environment created successfully!")
    print("\nExecuting tool in background sandbox container...")
    
    run_ok = manager.run_tool(tool_id, args="--test-run")
    if not run_ok:
        print("[FAIL] Manager rejected running the tool.")
        return
        
    print("Tool is running. Waiting for process completion and output capture...")
    
    # Wait for process execution output
    for _ in range(5):
        time.sleep(1)
        status = manager.get_tool_status(tool_id)
        if status != "Running":
            break
            
    print("\n--- RETRIEVING SANDBOX RUN LOGS ---")
    logs = manager.get_logs(tool_id, log_type="run")
    print(logs)
    print("-----------------------------------")
    
    # Ensure tool is stopped
    manager.stop_tool(tool_id)
    
    if "[SUCCESS]" in logs:
        print("\n=== INTEGRATION TEST: PASSED ===")
    else:
        print("\n=== INTEGRATION TEST: FAILED ===")

if __name__ == "__main__":
    run_integration_test()
