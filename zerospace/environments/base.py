import abc
import os
import sys
import shutil
import subprocess
from typing import List

def find_host_python() -> str:
    """Locates the host system's actual Python interpreter by searching the
    system PATH and common installation directories.
    """
    # 1. Try search in PATH
    for name in ["python", "python3", "python.exe", "python3.exe"]:
        path = shutil.which(name)
        if path and os.path.exists(path):
            return path
            
    # 2. Check common Windows paths if on Windows
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            py_dir = os.path.join(local_appdata, "Programs", "Python")
            if os.path.exists(py_dir):
                try:
                    for folder in os.listdir(py_dir):
                        exe_path = os.path.join(py_dir, folder, "python.exe")
                        if os.path.exists(exe_path):
                            return exe_path
                except Exception:
                    pass
        for pf in ["ProgramFiles", "ProgramFiles(x86)"]:
            pf_dir = os.environ.get(pf, "")
            if pf_dir:
                exe_path = os.path.join(pf_dir, "Python", "python.exe")
                if os.path.exists(exe_path):
                    return exe_path
                    
    # 3. Fallback to sys.executable if it is a python interpreter (not a bundle)
    if "zerospace" not in os.path.basename(sys.executable).lower():
        return sys.executable
        
    return "python"

def create_venv(venv_dir: str, log_file) -> bool:
    """Creates a virtual environment by invoking the host python interpreter as a subprocess.
    This avoids the PyInstaller sys.executable hijack where venv.create would copy the bundled
    zerospace.exe instead of python.exe.
    """
    python_path = find_host_python()
    log_file.write(f"[ZEROSPACE] Creating virtual environment using interpreter: {python_path}\n")
    try:
        # Run python -m venv venv_dir --clear
        process = subprocess.Popen(
            [python_path, "-m", "venv", venv_dir, "--clear"],
            stdout=log_file,
            stderr=log_file,
            text=True
        )
        process.wait()
        return process.returncode == 0
    except Exception as e:
        log_file.write(f"[ZEROSPACE ERROR] Failed to create venv: {e}\n")
        return False

class BaseEnvironment(abc.ABC):
    @abc.abstractmethod
    def setup(self, src_dir: str, container_dir: str, log_filepath: str) -> bool:
        """Create the isolated container/environment and install dependencies.
        Returns True if successful, False otherwise.
        """
        pass

    @abc.abstractmethod
    def run(self, src_dir: str, container_dir: str, entrypoint: str, args: str, log_filepath: str) -> subprocess.Popen:
        """Execute the tool inside the container using sandboxing policies.
        Returns the spawned subprocess.Popen instance.
        """
        pass

    @abc.abstractmethod
    def run_command(self, src_dir: str, container_dir: str, command: str, log_filepath: str) -> bool:
        """Runs a custom command inside the container/environment and writes output to log_filepath.
        Returns True if successful, False otherwise.
        """
        pass

