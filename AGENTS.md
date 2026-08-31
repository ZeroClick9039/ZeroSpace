# ZeroSpace Agent Prompt & Reference Guide

You are an AI assistant helping a developer build, run, debug, and maintain **ZeroSpace**—a cybersecurity tool manager that isolates running scripts and compiled binaries in lightweight,red and black theme, multi-language sandbox containers.

---

## 1. System Overview

ZeroSpace is designed to download tools (from GitHub, URLs, or local directories(files)) and run them inside isolated sandboxes. It supports the following runtimes:
- **Python**: Isolated virtual environments (`venv`) created dynamically.
- **Rust**: Built via `cargo` with custom targets and cargo homes.
- **C/C++**: Compiled using local compilers (`gcc`, `g++`, `clang`, `clang++`) via CMake, Makefiles, or direct fallbacks.
- **Multi-Language**: Combination of Python, Rust, and C/C++ runtimes.

---

## 2. Directory & Path Structure

All dynamic paths are resolved via database queries and helper functions in [`config.py`](file:///b:/ZeroSpace/zerospace/config.py):
- **Tools Source Path**: `get_tools_dir()` (defaults to `.zerospace/tools/` or `tools/`). Stores the original extracted source code.
- **Containers Sandbox Path**: `get_containers_dir()` (defaults to `.zerospace/containers/` or `containers/`). Stores virtual environments, builds, and sandboxed file systems.
- **Logs Path**: `get_logs_dir()` (defaults to `.zerospace/logs/` or `logs/`). Stores compilation and stdout/stderr execution logs.

---

## 3. Sandbox Isolation Rules

When launching a tool or running a command inside the sandbox, the environment is strictly isolated. You must preserve the following behaviors:

### File System Redirections
The following environment variables are redirected to the container's `sandbox/` sub-directory:
- `USERPROFILE`: Redirected to `<container_path>/sandbox/home`
- `HOMEDRIVE` & `HOMEPATH`: Split dynamically using `os.path.splitdrive(home_dir)` to prevent path/drive mismatch errors on Windows.
- `APPDATA` / `LOCALAPPDATA`: Redirected to `<container_path>/sandbox/appdata`
- `TEMP` / `TMP`: Redirected to `<container_path>/sandbox/temp`
- `HOME` (Unix): Redirected to `<container_path>/sandbox/home`

### PATH Restrictions
The system `PATH` variable is restricted to prevent the tool from accessing unauthorized host applications. 
- Only basic system folders (`System32`, `SysWOW64`, `C:\Windows`, or Unix standard `/bin` paths) are preserved.
- Any Windows path must be normalized to forward slashes before matching to support backslashes.
- Compiler binaries (`gcc`, `cargo`, etc.) are explicitly located on the host using `shutil.which` and prepended back into the `PATH` during compilation/run tasks.
User can decide path of the containers

---

## 4. API Endpoints Quick Reference

ZeroSpace runs a Flask backend on `http://127.0.0.1:5000` defined in [`app.py`](file:///b:/ZeroSpace/zerospace/app.py):

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/api/tools` | Lists all installed tools with their current statuses. |
| **GET** | `/api/tools/<tool_id>` | Returns details and status for a specific tool. |
| **POST** | `/api/tools` | Installs/compiles a new tool. Optional parameters: `language` override, `container_path` override. |
| **POST** | `/api/tools/<tool_id>/run` | Runs the tool in the sandbox with optional runtime arguments. |
| **POST** | `/api/tools/<tool_id>/stop` | Terminates the running tool's subprocess. |
| **POST** | `/api/tools/<tool_id>/update` | Pulls updates and initiates a rebuild thread. |
| **DELETE** | `/api/tools/<tool_id>` | Uninstalls and deletes all source, build, container, and log files. |
| **GET** | `/api/tools/<tool_id>/logs/<run\|setup>` | Fetches the execution output tail or build/installation logs. |
| **POST** | `/api/tools/<tool_id>/cli` | Runs an interactive installer command (e.g. `pip install`) inside the venv. |
| **GET** | `/api/settings` | Returns active paths for tools, containers, and logs. |
| **POST** | `/api/settings` | Saves new tools, containers, and logs paths to database settings. |

---

## 5. Command Line Interface (CLI)

The ZeroSpace service can be run or controlled via [`main.py`](file:///b:/ZeroSpace/main.py):

- **Start Web UI**: `python main.py`
- **List Installed Tools**: `python main.py list`
- **Run command in sandbox**: `python main.py cli <tool_id> <command>` (e.g., `python main.py cli my_python_tool "pip install colorama"`)

---

## 6. How to Debug & Verify

If you are modifying ZeroSpace or diagnosing compilation issues:
1. **Setup Log**: View `<logs_path>/<tool_id>_setup.log` to inspect `pip install` or compiler compilation output.
2. **Execution Log**: View `<logs_path>/<tool_id>_run.log` to inspect runtime output and stderr messages.
3. **Run Verification Tests**:
   - `python tests/multi_language_test.py` (Tests C, Rust, and multi-language builds/execution)
   - `python tests/integration_test.py` (Tests filesystem sandboxing and path isolation)
