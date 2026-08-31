import os
import sys
import time

# Ensure workspace is on the python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from zerospace.manager import ToolManager

def test_tool(manager, name, path, runtime_override="auto"):
    print(f"\n--- Testing Tool: {name} (Override: {runtime_override}) ---")
    print(f"Adding local mock tool from: {path}")
    try:
        tool_id = manager.add_tool(
            name=name,
            source=path,
            description=f"Multi-language check tool for {name}.",
            language_override=runtime_override
        )
        print(f"Tool registered with ID: {tool_id}")
    except Exception as e:
        print(f"[ERROR] Failed to add tool: {e}")
        return False

    print("Monitoring setup/compilation thread...")
    setup_ok = False
    
    # Wait for setup (compilation, cargo download, pip venv)
    # Give it up to 60 seconds since Cargo build and pip install requests might take time
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
        print(f"\n[FAIL] Setup failed to build environment for {name}. Check setup logs:")
        print(manager.get_logs(tool_id, log_type="setup"))
        return False

    print(f"[SUCCESS] Sandbox environment created successfully for {name}!")
    print("Executing tool in background sandbox container...")
    
    run_ok = manager.run_tool(tool_id, args="")
    if not run_ok:
        print(f"[FAIL] Manager rejected running the tool {name}.")
        return False

    print("Tool is running. Waiting for process completion and output capture...")
    
    # Wait for process execution output
    for _ in range(10):
        time.sleep(1)
        status = manager.get_tool_status(tool_id)
        if status != "Running":
            break

    print("\n--- RETRIEVING RUN LOGS ---")
    logs = manager.get_logs(tool_id, log_type="run")
    print(logs)
    print("---------------------------")
    
    # Ensure tool is stopped
    manager.stop_tool(tool_id)
    
    passed = "[SUCCESS]" in logs
    if passed:
        print(f"=== {name} TEST: PASSED ===")
    else:
        print(f"=== {name} TEST: FAILED ===")
    return passed

def run_all_tests():
    print("==========================================")
    print(" ZEROSPACE MULTI-LANGUAGE TEST RUN       ")
    print("==========================================")
    
    manager = ToolManager()
    
    c_path = os.path.join(BASE_DIR, "mock_tools", "c_verify")
    rust_path = os.path.join(BASE_DIR, "mock_tools", "rust_verify")
    multi_path = os.path.join(BASE_DIR, "mock_tools", "multi_verify")
    
    c_passed = test_tool(manager, "C Mock Tool", c_path, "auto")
    rust_passed = test_tool(manager, "Rust Mock Tool", rust_path, "auto")
    multi_passed = test_tool(manager, "Python+C Multi-Language Mock Tool", multi_path, "auto")
    
    print("\n==========================================")
    print("             TEST SUMMARY                ")
    print("==========================================")
    print(f"C Tool Build & Run: {'PASSED' if c_passed else 'FAILED'}")
    print(f"Rust Tool Build & Run: {'PASSED' if rust_passed else 'FAILED'}")
    print(f"Python+C Multi-Language Build & Run: {'PASSED' if multi_passed else 'FAILED'}")
    print("==========================================")
    
    if c_passed and rust_passed and multi_passed:
        print("ALL TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
