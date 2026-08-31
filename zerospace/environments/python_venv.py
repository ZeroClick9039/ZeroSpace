import os
import sys
import venv
import subprocess
import logging
from zerospace.environments.base import BaseEnvironment, create_venv

logger = logging.getLogger("zerospace.environments.python")

class PythonVenvEnvironment(BaseEnvironment):
    def setup(self, src_dir: str, container_dir: str, log_filepath: str) -> bool:
        """Creates a Python virtual environment and installs dependencies from requirements.txt."""
        venv_dir = os.path.join(container_dir, "venv")
        os.makedirs(venv_dir, exist_ok=True)
        
        # 1. Open setup log file
        with open(log_filepath, "w", encoding="utf-8", buffering=1) as log_file:
            log_file.write("[ZEROSPACE] Starting Python venv creation...\n")
            
            try:
                # 2. Create virtual environment
                if not create_venv(venv_dir, log_file):
                    return False
                log_file.write("[ZEROSPACE] Virtual environment created successfully.\n")
            except Exception as e:
                log_file.write(f"[ZEROSPACE ERROR] Failed to create virtual environment: {e}\n")
                logger.error(f"Failed to create virtual environment: {e}")
                return False
            
            # Determine path to pip inside venv based on platform
            # On Windows it's Scripts/pip.exe, on Unix it's bin/pip
            pip_path = os.path.join(venv_dir, "Scripts", "pip.exe")
            if not os.path.exists(pip_path):
                # Fallback to Unix just in case (though target OS is Windows)
                pip_path = os.path.join(venv_dir, "bin", "pip")
                
            requirements_path = os.path.join(src_dir, "requirements.txt")
            if os.path.exists(requirements_path):
                log_file.write(f"[ZEROSPACE] Found requirements.txt. Installing dependencies...\n")
                try:
                    # Run pip install command inside the created venv
                    process = subprocess.Popen(
                        [pip_path, "install", "-r", requirements_path],
                        stdout=log_file,
                        stderr=log_file,
                        cwd=src_dir,
                        text=True
                    )
                    process.wait()
                    
                    if process.returncode == 0:
                        log_file.write("[ZEROSPACE] Dependencies installed successfully.\n")
                    else:
                        log_file.write(f"[ZEROSPACE ERROR] pip install failed with return code {process.returncode}\n")
                        return False
                except Exception as e:
                    log_file.write(f"[ZEROSPACE ERROR] Exception running pip: {e}\n")
                    return False
            else:
                log_file.write("[ZEROSPACE] No requirements.txt found. Skipping dependency installation.\n")
                
        return True

    def run(self, src_dir: str, container_dir: str, entrypoint: str, args: str, log_filepath: str) -> subprocess.Popen:
        """Launches the Python tool inside the virtual environment with sandbox filesystem redirections."""
        venv_dir = os.path.join(container_dir, "venv")
        
        # Paths to executables
        python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = os.path.join(venv_dir, "bin", "python")
            
        script_path = os.path.join(src_dir, entrypoint)
        
        # Prepare argument list
        cmd_args = [python_exe, script_path]
        if args:
            # Simple space splitting of arguments, protecting quoted paths is not required for basic scanning inputs
            cmd_args.extend(args.split())
            
        # Sandbox paths configuration inside container_dir
        sandbox_dir = os.path.join(container_dir, "sandbox")
        home_dir = os.path.join(sandbox_dir, "home")
        appdata_dir = os.path.join(sandbox_dir, "appdata")
        temp_dir = os.path.join(sandbox_dir, "temp")
        
        # Ensure directories exist
        for d in [home_dir, appdata_dir, temp_dir]:
            os.makedirs(d, exist_ok=True)
            
        # Build sandboxed environment variables dictionary
        # We start with basic system environment variables to preserve OS functionality
        clean_env = {}
        preserve_keys = [
            "SystemRoot", "SystemDrive", "windir", "COMSPEC", "PATHEXT", 
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
            "PROCESSOR_LEVEL", "PROCESSOR_REVISION",
            # Linux graphical display & terminal variables
            "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "TERM"
        ]
        for key in preserve_keys:
            if key in os.environ:
                clean_env[key] = os.environ[key]
                
        # Redirect user and temporary folders to the container's sandbox
        drive, path = os.path.splitdrive(home_dir)
        clean_env["USERPROFILE"] = home_dir
        clean_env["HOMEPATH"] = path
        clean_env["HOMEDRIVE"] = drive if drive else "C:"
        clean_env["HOME"] = home_dir  # Linux home directory mapping
        clean_env["APPDATA"] = appdata_dir
        clean_env["LOCALAPPDATA"] = os.path.join(appdata_dir, "Local")
        clean_env["TEMP"] = temp_dir
        clean_env["TMP"] = temp_dir
        
        # Restrict PATH to only venv binaries, system utilities, and base python
        venv_scripts = os.path.join(venv_dir, "Scripts")
        if not os.path.exists(venv_scripts):
            venv_scripts = os.path.join(venv_dir, "bin")
            
        sys_path = os.environ.get("PATH", "")
        # Add basic system paths so shell utilities can work
        system_paths = []
        for path in sys_path.split(os.pathsep):
            path_normalized = path.replace("\\", "/")
            if "system32" in path_normalized.lower() or "syswow64" in path_normalized.lower():
                system_paths.append(path)
            elif "windows" in path_normalized.lower():
                system_paths.append(path)
            elif any(x in path_normalized.lower() for x in ["/bin", "/usr/bin", "/sbin", "/usr/sbin", "/usr/local/bin"]):
                system_paths.append(path)
                
        clean_env["PATH"] = os.pathsep.join([venv_scripts] + system_paths)
        
        # Open execution log file
        log_file = open(log_filepath, "w", encoding="utf-8", buffering=1)
        log_file.write(f"[ZEROSPACE] Starting process: {' '.join(cmd_args)}\n")
        log_file.write(f"[ZEROSPACE] Sandboxed USERPROFILE: {home_dir}\n\n")
        
        # Launch tool process
        process = subprocess.Popen(
            cmd_args,
            stdout=log_file,
            stderr=log_file,
            cwd=src_dir,
            env=clean_env,
            text=True
        )
        
        # Save a reference to the log file handle on the process object so we can close it when stopping the process
        process.log_file_handle = log_file # type: ignore
        return process

    def run_command(self, src_dir: str, container_dir: str, command: str, log_filepath: str) -> bool:
        """Runs a custom command inside the virtual environment."""
        venv_dir = os.path.join(container_dir, "venv")
        
        # Sandbox paths configuration inside container_dir
        sandbox_dir = os.path.join(container_dir, "sandbox")
        home_dir = os.path.join(sandbox_dir, "home")
        appdata_dir = os.path.join(sandbox_dir, "appdata")
        temp_dir = os.path.join(sandbox_dir, "temp")
        
        # Ensure directories exist
        for d in [home_dir, appdata_dir, temp_dir]:
            os.makedirs(d, exist_ok=True)
            
        # Build sandboxed environment variables dictionary
        clean_env = {}
        preserve_keys = [
            "SystemRoot", "SystemDrive", "windir", "COMSPEC", "PATHEXT", 
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
            "PROCESSOR_LEVEL", "PROCESSOR_REVISION",
            # Linux graphical display & terminal variables
            "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "TERM"
        ]
        for key in preserve_keys:
            if key in os.environ:
                clean_env[key] = os.environ[key]
                
        # Redirect user and temporary folders to the container's sandbox
        drive, path = os.path.splitdrive(home_dir)
        clean_env["USERPROFILE"] = home_dir
        clean_env["HOMEPATH"] = path
        clean_env["HOMEDRIVE"] = drive if drive else "C:"
        clean_env["HOME"] = home_dir  # Linux home directory mapping
        clean_env["APPDATA"] = appdata_dir
        clean_env["LOCALAPPDATA"] = os.path.join(appdata_dir, "Local")
        clean_env["TEMP"] = temp_dir
        clean_env["TMP"] = temp_dir
        
        # Restrict PATH to only venv binaries, system utilities, and base python
        venv_scripts = os.path.join(venv_dir, "Scripts")
        if not os.path.exists(venv_scripts):
            venv_scripts = os.path.join(venv_dir, "bin")
            
        sys_path = os.environ.get("PATH", "")
        # Add basic system paths so shell utilities can work
        system_paths = []
        for path in sys_path.split(os.pathsep):
            path_normalized = path.replace("\\", "/")
            if "system32" in path_normalized.lower() or "syswow64" in path_normalized.lower():
                system_paths.append(path)
            elif "windows" in path_normalized.lower():
                system_paths.append(path)
            elif any(x in path_normalized.lower() for x in ["/bin", "/usr/bin", "/sbin", "/usr/sbin", "/usr/local/bin"]):
                system_paths.append(path)
                
        clean_env["PATH"] = os.pathsep.join([venv_scripts] + system_paths)
        
        try:
            with open(log_filepath, "a", encoding="utf-8", buffering=1) as log_file:
                process = subprocess.Popen(
                    command,
                    stdout=log_file,
                    stderr=log_file,
                    cwd=src_dir,
                    env=clean_env,
                    shell=True,
                    text=True
                )
                process.wait()
                log_file.write(f"\n[ZEROSPACE CLI] Command finished with exit status: {process.returncode}\n")
                return process.returncode == 0
        except Exception as e:
            try:
                with open(log_filepath, "a", encoding="utf-8") as log_file:
                    log_file.write(f"[ZEROSPACE ERROR] Exception running CLI command: {e}\n")
            except Exception:
                pass
            return False

