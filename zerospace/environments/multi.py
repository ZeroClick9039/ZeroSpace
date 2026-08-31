import os
import sys
import venv
import shutil
import abc
import subprocess
import logging
from typing import Dict, List, Any
from zerospace.environments.base import BaseEnvironment, create_venv

logger = logging.getLogger("zerospace.environments.multi")

class BaseLanguageHandler(abc.ABC):
    @abc.abstractmethod
    def setup(self, src_dir: str, container_dir: str, log_file) -> bool:
        """Runs compile/install commands. Outputs to log_file."""
        pass

    @abc.abstractmethod
    def get_env_vars(self, container_dir: str) -> Dict[str, str]:
        """Returns environment variables to set for sandboxing."""
        pass

    @abc.abstractmethod
    def get_path_dirs(self, container_dir: str) -> List[str]:
        """Returns directories to prepend/append to the sandboxed PATH."""
        pass


class PythonLanguageHandler(BaseLanguageHandler):
    def setup(self, src_dir: str, container_dir: str, log_file) -> bool:
        venv_dir = os.path.join(container_dir, "venv")
        os.makedirs(venv_dir, exist_ok=True)
        log_file.write("[ZEROSPACE] Starting Python venv creation...\n")
        try:
            if not create_venv(venv_dir, log_file):
                return False
            log_file.write("[ZEROSPACE] Virtual environment created successfully.\n")
        except Exception as e:
            log_file.write(f"[ZEROSPACE ERROR] Failed to create virtual environment: {e}\n")
            logger.error(f"Failed to create virtual environment: {e}")
            return False

        # Determine path to pip inside venv based on platform
        pip_path = os.path.join(venv_dir, "Scripts", "pip.exe")
        if not os.path.exists(pip_path):
            pip_path = os.path.join(venv_dir, "bin", "pip")

        # 1. Check requirements.txt
        requirements_path = os.path.join(src_dir, "requirements.txt")
        if os.path.exists(requirements_path):
            log_file.write("[ZEROSPACE] Found requirements.txt. Installing dependencies...\n")
            try:
                process = subprocess.Popen(
                    [pip_path, "install", "-r", requirements_path],
                    stdout=log_file,
                    stderr=log_file,
                    cwd=src_dir,
                    text=True
                )
                process.wait()
                if process.returncode == 0:
                    log_file.write("[ZEROSPACE] Python requirements installed successfully.\n")
                else:
                    log_file.write(f"[ZEROSPACE ERROR] pip install -r requirements.txt failed with exit code {process.returncode}\n")
                    return False
            except Exception as e:
                log_file.write(f"[ZEROSPACE ERROR] Exception running pip: {e}\n")
                return False

        # 2. Check pyproject.toml / setup.py
        pyproject_path = os.path.join(src_dir, "pyproject.toml")
        setup_py_path = os.path.join(src_dir, "setup.py")
        if os.path.exists(pyproject_path) or os.path.exists(setup_py_path):
            log_file.write("[ZEROSPACE] Found pyproject.toml/setup.py. Installing package...\n")
            try:
                process = subprocess.Popen(
                    [pip_path, "install", "."],
                    stdout=log_file,
                    stderr=log_file,
                    cwd=src_dir,
                    text=True
                )
                process.wait()
                if process.returncode == 0:
                    log_file.write("[ZEROSPACE] Python package installed successfully.\n")
                else:
                    log_file.write(f"[ZEROSPACE ERROR] pip install . failed with exit code {process.returncode}\n")
                    return False
            except Exception as e:
                log_file.write(f"[ZEROSPACE ERROR] Exception running pip install .: {e}\n")
                return False

        return True

    def get_env_vars(self, container_dir: str) -> Dict[str, str]:
        venv_dir = os.path.join(container_dir, "venv")
        return {"VIRTUAL_ENV": venv_dir}

    def get_path_dirs(self, container_dir: str) -> List[str]:
        venv_dir = os.path.join(container_dir, "venv")
        venv_scripts = os.path.join(venv_dir, "Scripts")
        if not os.path.exists(venv_scripts):
            venv_scripts = os.path.join(venv_dir, "bin")
        return [venv_scripts]


class RustLanguageHandler(BaseLanguageHandler):
    def setup(self, src_dir: str, container_dir: str, log_file) -> bool:
        cargo_toml = os.path.join(src_dir, "Cargo.toml")
        if not os.path.exists(cargo_toml):
            log_file.write("[ZEROSPACE] No Cargo.toml found. Skipping Rust compilation.\n")
            return True

        log_file.write("[ZEROSPACE] Starting Rust compilation via cargo...\n")

        cargo_path = shutil.which("cargo")
        if not cargo_path:
            log_file.write("[ZEROSPACE ERROR] Failed to locate 'cargo' on host. Rust environment cannot be set up.\n")
            return False

        build_env = os.environ.copy()
        cargo_home = os.path.join(container_dir, "cargo_home")
        cargo_target = os.path.join(container_dir, "target")
        os.makedirs(cargo_home, exist_ok=True)
        os.makedirs(cargo_target, exist_ok=True)

        build_env["CARGO_HOME"] = cargo_home
        build_env["CARGO_TARGET_DIR"] = cargo_target

        try:
            process = subprocess.Popen(
                [cargo_path, "build", "--release"],
                stdout=log_file,
                stderr=log_file,
                cwd=src_dir,
                env=build_env,
                text=True
            )
            process.wait()
            if process.returncode == 0:
                log_file.write("[ZEROSPACE] Rust cargo build completed successfully.\n")
                return True
            else:
                log_file.write(f"[ZEROSPACE ERROR] Cargo build failed with exit code {process.returncode}\n")
                return False
        except Exception as e:
            log_file.write(f"[ZEROSPACE ERROR] Exception running cargo build: {e}\n")
            return False

    def get_env_vars(self, container_dir: str) -> Dict[str, str]:
        cargo_home = os.path.join(container_dir, "cargo_home")
        cargo_target = os.path.join(container_dir, "target")
        return {
            "CARGO_HOME": cargo_home,
            "CARGO_TARGET_DIR": cargo_target
        }

    def get_path_dirs(self, container_dir: str) -> List[str]:
        paths = []
        cargo_bin = shutil.which("cargo")
        if cargo_bin:
            paths.append(os.path.dirname(cargo_bin))
        rustc_bin = shutil.which("rustc")
        if rustc_bin:
            paths.append(os.path.dirname(rustc_bin))
            
        # Target release and debug folders
        paths.append(os.path.join(container_dir, "target", "release"))
        paths.append(os.path.join(container_dir, "target", "debug"))
        return paths


class CLanguageHandler(BaseLanguageHandler):
    def setup(self, src_dir: str, container_dir: str, log_file) -> bool:
        has_makefile = os.path.exists(os.path.join(src_dir, "Makefile"))
        has_cmake = os.path.exists(os.path.join(src_dir, "CMakeLists.txt"))

        c_files = []
        cpp_files = []
        for root, dirs, files in os.walk(src_dir):
            if root != src_dir:
                continue
            for f in files:
                if f.endswith(".c"):
                    c_files.append(f)
                elif f.endswith(".cpp") or f.endswith(".cc") or f.endswith(".cxx"):
                    cpp_files.append(f)

        if not (has_makefile or has_cmake or c_files or cpp_files):
            log_file.write("[ZEROSPACE] No Makefile, CMakeLists.txt, or C/C++ source files found. Skipping C/C++ setup.\n")
            return True

        log_file.write("[ZEROSPACE] Starting C/C++ setup...\n")

        # 1. Makefile
        if has_makefile:
            log_file.write("[ZEROSPACE] Makefile found. Running make...\n")
            make_path = shutil.which("mingw32-make") or shutil.which("make")
            if not make_path:
                log_file.write("[ZEROSPACE ERROR] Failed to locate 'make' or 'mingw32-make' on host.\n")
                return False
            try:
                process = subprocess.Popen(
                    [make_path],
                    stdout=log_file,
                    stderr=log_file,
                    cwd=src_dir,
                    text=True
                )
                process.wait()
                if process.returncode == 0:
                    log_file.write("[ZEROSPACE] Make compilation completed successfully.\n")
                    return True
                else:
                    log_file.write(f"[ZEROSPACE ERROR] Make compilation failed with exit code {process.returncode}\n")
                    return False
            except Exception as e:
                log_file.write(f"[ZEROSPACE ERROR] Exception running make: {e}\n")
                return False

        # 2. CMake
        if has_cmake:
            log_file.write("[ZEROSPACE] CMakeLists.txt found. Running cmake...\n")
            cmake_path = shutil.which("cmake")
            if not cmake_path:
                log_file.write("[ZEROSPACE WARNING] Failed to locate 'cmake' on host. Attempting fallback to source file compilation.\n")
            else:
                try:
                    process = subprocess.Popen(
                        [cmake_path, "."],
                        stdout=log_file,
                        stderr=log_file,
                        cwd=src_dir,
                        text=True
                    )
                    process.wait()
                    if process.returncode == 0:
                        log_file.write("[ZEROSPACE] CMake configuration succeeded. Running make...\n")
                        make_path = shutil.which("mingw32-make") or shutil.which("make")
                        if not make_path:
                            log_file.write("[ZEROSPACE ERROR] Failed to locate 'make' or 'mingw32-make' on host.\n")
                            return False
                        process2 = subprocess.Popen(
                            [make_path],
                            stdout=log_file,
                            stderr=log_file,
                            cwd=src_dir,
                            text=True
                        )
                        process2.wait()
                        if process2.returncode == 0:
                            log_file.write("[ZEROSPACE] CMake and Make compilation completed successfully.\n")
                            return True
                        else:
                            log_file.write(f"[ZEROSPACE ERROR] Make compilation failed with exit code {process2.returncode}\n")
                            return False
                    else:
                        log_file.write(f"[ZEROSPACE ERROR] CMake configuration failed with exit code {process.returncode}\n")
                        return False
                except Exception as e:
                    log_file.write(f"[ZEROSPACE ERROR] Exception running CMake: {e}\n")
                    return False

        # 3. Direct compilation fallback
        if cpp_files:
            log_file.write(f"[ZEROSPACE] Compiling C++ source files directly: {cpp_files}\n")
            gxx_path = shutil.which("g++") or shutil.which("clang++")
            if not gxx_path:
                log_file.write("[ZEROSPACE ERROR] Failed to locate C++ compiler (g++/clang++) on host.\n")
                return False
            
            # Extract main or fallback to first file
            out_exe = "main.exe"
            main_src = next((f for f in cpp_files if "main" in f.lower()), None)
            if main_src:
                out_exe = os.path.splitext(main_src)[0] + ".exe"
            else:
                out_exe = os.path.splitext(cpp_files[0])[0] + ".exe"

            cmd = [gxx_path, "-o", out_exe] + cpp_files
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=log_file,
                    cwd=src_dir,
                    text=True
                )
                process.wait()
                if process.returncode == 0:
                    log_file.write(f"[ZEROSPACE] Direct C++ compilation completed successfully. Output: {out_exe}\n")
                    return True
                else:
                    log_file.write(f"[ZEROSPACE ERROR] C++ compilation failed with exit code {process.returncode}\n")
                    return False
            except Exception as e:
                log_file.write(f"[ZEROSPACE ERROR] Exception during direct C++ compilation: {e}\n")
                return False

        elif c_files:
            log_file.write(f"[ZEROSPACE] Compiling C source files directly: {c_files}\n")
            gcc_path = shutil.which("gcc") or shutil.which("clang")
            if not gcc_path:
                log_file.write("[ZEROSPACE ERROR] Failed to locate C compiler (gcc/clang) on host.\n")
                return False

            out_exe = "main.exe"
            main_src = next((f for f in c_files if "main" in f.lower()), None)
            if main_src:
                out_exe = os.path.splitext(main_src)[0] + ".exe"
            else:
                out_exe = os.path.splitext(c_files[0])[0] + ".exe"

            cmd = [gcc_path, "-o", out_exe] + c_files
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=log_file,
                    cwd=src_dir,
                    text=True
                )
                process.wait()
                if process.returncode == 0:
                    log_file.write(f"[ZEROSPACE] Direct C compilation completed successfully. Output: {out_exe}\n")
                    return True
                else:
                    log_file.write(f"[ZEROSPACE ERROR] C compilation failed with exit code {process.returncode}\n")
                    return False
            except Exception as e:
                log_file.write(f"[ZEROSPACE ERROR] Exception during direct C compilation: {e}\n")
                return False

        return True

    def get_env_vars(self, container_dir: str) -> Dict[str, str]:
        return {}

    def get_path_dirs(self, container_dir: str) -> List[str]:
        paths = []
        gcc_bin = shutil.which("gcc")
        if gcc_bin:
            paths.append(os.path.dirname(gcc_bin))
        clang_bin = shutil.which("clang")
        if clang_bin:
            paths.append(os.path.dirname(clang_bin))
        return paths


class PlaceholderLanguageHandler(BaseLanguageHandler):
    def __init__(self, name: str):
        self.name = name

    def setup(self, src_dir: str, container_dir: str, log_file) -> bool:
        log_file.write(f"[ZEROSPACE ERROR] Setup failed: The '{self.name}' runtime environment is not integrated/enabled.\n")
        log_file.write("Please check back when this handler is fully implemented.\n")
        return False

    def get_env_vars(self, container_dir: str) -> Dict[str, str]:
        return {}

    def get_path_dirs(self, container_dir: str) -> List[str]:
        return []


# Register supported language handlers
LANGUAGE_HANDLERS = {
    "python": PythonLanguageHandler(),
    "rust": RustLanguageHandler(),
    "c": CLanguageHandler(),
    "c++": CLanguageHandler(),
    "nodejs": PlaceholderLanguageHandler("Node.js"),
    "javascript": PlaceholderLanguageHandler("Node.js"),
    "node": PlaceholderLanguageHandler("Node.js"),
    "docker": PlaceholderLanguageHandler("Docker"),
    "make": CLanguageHandler(),  # Map make to C/C++ compiler handler
    "go": PlaceholderLanguageHandler("Go"),
    "java": PlaceholderLanguageHandler("Java"),
}


class MultiLanguageEnvironment(BaseEnvironment):
    def __init__(self, languages: List[str]):
        self.languages = [lang.strip().lower() for lang in languages]
        self.handlers = []
        for lang in self.languages:
            if lang in LANGUAGE_HANDLERS:
                self.handlers.append(LANGUAGE_HANDLERS[lang])
            else:
                logger.warning(f"Unknown language requested: {lang}")

    def setup(self, src_dir: str, container_dir: str, log_filepath: str) -> bool:
        os.makedirs(container_dir, exist_ok=True)
        
        with open(log_filepath, "w", encoding="utf-8", buffering=1) as log_file:
            log_file.write(f"[ZEROSPACE] Initializing Multi-Language Setup for: {', '.join(self.languages)}\n")
            
            if not self.handlers:
                log_file.write("[ZEROSPACE ERROR] No valid language handlers resolved.\n")
                return False

            for lang, handler in zip(self.languages, self.handlers):
                log_file.write(f"\n[ZEROSPACE] Setting up environment for language: {lang}...\n")
                success = handler.setup(src_dir, container_dir, log_file)
                if not success:
                    log_file.write(f"[ZEROSPACE ERROR] Setup failed for language: {lang}\n")
                    return False
                    
            log_file.write("\n[ZEROSPACE] All environment setup completed successfully!\n")
            return True

    def run(self, src_dir: str, container_dir: str, entrypoint: str, args: str, log_filepath: str) -> subprocess.Popen:
        """Launches the tool inside the multi-language environment with sandbox filesystem redirections."""
        sandbox_dir = os.path.join(container_dir, "sandbox")
        home_dir = os.path.join(sandbox_dir, "home")
        appdata_dir = os.path.join(sandbox_dir, "appdata")
        temp_dir = os.path.join(sandbox_dir, "temp")
        
        for d in [home_dir, appdata_dir, temp_dir]:
            os.makedirs(d, exist_ok=True)
            
        clean_env = {}
        preserve_keys = [
            "SystemRoot", "SystemDrive", "windir", "COMSPEC", "PATHEXT", 
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
            "PROCESSOR_LEVEL", "PROCESSOR_REVISION",
            "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "TERM"
        ]
        for key in preserve_keys:
            if key in os.environ:
                clean_env[key] = os.environ[key]
                
        drive, path = os.path.splitdrive(home_dir)
        clean_env["USERPROFILE"] = home_dir
        clean_env["HOMEPATH"] = path
        clean_env["HOMEDRIVE"] = drive if drive else "C:"
        clean_env["HOME"] = home_dir
        clean_env["APPDATA"] = appdata_dir
        clean_env["LOCALAPPDATA"] = os.path.join(appdata_dir, "Local")
        clean_env["TEMP"] = temp_dir
        clean_env["TMP"] = temp_dir

        custom_paths = []
        for handler in self.handlers:
            handler_vars = handler.get_env_vars(container_dir)
            clean_env.update(handler_vars)
            custom_paths.extend(handler.get_path_dirs(container_dir))

        sys_path = os.environ.get("PATH", "")
        system_paths = []
        for path in sys_path.split(os.pathsep):
            path_normalized = path.replace("\\", "/")
            if "system32" in path_normalized.lower() or "syswow64" in path_normalized.lower():
                system_paths.append(path)
            elif "windows" in path_normalized.lower():
                system_paths.append(path)
            elif any(x in path_normalized.lower() for x in ["/bin", "/usr/bin", "/sbin", "/usr/sbin", "/usr/local/bin"]):
                system_paths.append(path)

        clean_env["PATH"] = os.pathsep.join(custom_paths + system_paths)

        # Determine executable and launch args
        cmd_args = []
        if entrypoint.endswith(".py"):
            venv_dir = os.path.join(container_dir, "venv")
            python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
            if not os.path.exists(python_exe):
                python_exe = os.path.join(venv_dir, "bin", "python")
            script_path = os.path.join(src_dir, entrypoint)
            cmd_args = [python_exe, script_path]
        else:
            # Compiled binary check (e.g. Rust or C/C++)
            rust_release = os.path.join(container_dir, "target", "release", entrypoint)
            rust_debug = os.path.join(container_dir, "target", "debug", entrypoint)
            src_exec = os.path.join(src_dir, entrypoint)
            
            # Platform adaptation (.exe)
            rust_release_exe = rust_release if rust_release.endswith(".exe") else f"{rust_release}.exe"
            rust_debug_exe = rust_debug if rust_debug.endswith(".exe") else f"{rust_debug}.exe"
            src_exec_exe = src_exec if src_exec.endswith(".exe") else f"{src_exec}.exe"
            
            if os.path.exists(rust_release_exe):
                cmd_args = [rust_release_exe]
            elif os.path.exists(rust_debug_exe):
                cmd_args = [rust_debug_exe]
            elif os.path.exists(src_exec_exe):
                cmd_args = [src_exec_exe]
            elif os.path.exists(rust_release):
                cmd_args = [rust_release]
            elif os.path.exists(rust_debug):
                cmd_args = [rust_debug]
            elif os.path.exists(src_exec):
                cmd_args = [src_exec]
            else:
                cmd_args = [src_exec_exe]

        if args:
            cmd_args.extend(args.split())

        log_file = open(log_filepath, "w", encoding="utf-8", buffering=1)
        log_file.write(f"[ZEROSPACE] Starting process: {' '.join(cmd_args)}\n")
        log_file.write(f"[ZEROSPACE] Sandboxed USERPROFILE: {home_dir}\n\n")
        
        process = subprocess.Popen(
            cmd_args,
            stdout=log_file,
            stderr=log_file,
            cwd=src_dir,
            env=clean_env,
            text=True
        )
        
        process.log_file_handle = log_file
        return process

    def run_command(self, src_dir: str, container_dir: str, command: str, log_filepath: str) -> bool:
        sandbox_dir = os.path.join(container_dir, "sandbox")
        home_dir = os.path.join(sandbox_dir, "home")
        appdata_dir = os.path.join(sandbox_dir, "appdata")
        temp_dir = os.path.join(sandbox_dir, "temp")
        
        for d in [home_dir, appdata_dir, temp_dir]:
            os.makedirs(d, exist_ok=True)
            
        clean_env = {}
        preserve_keys = [
            "SystemRoot", "SystemDrive", "windir", "COMSPEC", "PATHEXT", 
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
            "PROCESSOR_LEVEL", "PROCESSOR_REVISION",
            "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "TERM"
        ]
        for key in preserve_keys:
            if key in os.environ:
                clean_env[key] = os.environ[key]
                
        drive, path = os.path.splitdrive(home_dir)
        clean_env["USERPROFILE"] = home_dir
        clean_env["HOMEPATH"] = path
        clean_env["HOMEDRIVE"] = drive if drive else "C:"
        clean_env["HOME"] = home_dir
        clean_env["APPDATA"] = appdata_dir
        clean_env["LOCALAPPDATA"] = os.path.join(appdata_dir, "Local")
        clean_env["TEMP"] = temp_dir
        clean_env["TMP"] = temp_dir

        custom_paths = []
        for handler in self.handlers:
            handler_vars = handler.get_env_vars(container_dir)
            clean_env.update(handler_vars)
            custom_paths.extend(handler.get_path_dirs(container_dir))

        sys_path = os.environ.get("PATH", "")
        system_paths = []
        for path in sys_path.split(os.pathsep):
            path_normalized = path.replace("\\", "/")
            if "system32" in path_normalized.lower() or "syswow64" in path_normalized.lower():
                system_paths.append(path)
            elif "windows" in path_normalized.lower():
                system_paths.append(path)
            elif any(x in path_normalized.lower() for x in ["/bin", "/usr/bin", "/sbin", "/usr/sbin", "/usr/local/bin"]):
                system_paths.append(path)

        clean_env["PATH"] = os.pathsep.join(custom_paths + system_paths)

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

    def run_command_terminal(self, src_dir: str, container_dir: str, command: str) -> bool:
        """Runs a custom command inside the environment, streaming output directly to stdout/stderr."""
        sandbox_dir = os.path.join(container_dir, "sandbox")
        home_dir = os.path.join(sandbox_dir, "home")
        appdata_dir = os.path.join(sandbox_dir, "appdata")
        temp_dir = os.path.join(sandbox_dir, "temp")
        
        for d in [home_dir, appdata_dir, temp_dir]:
            os.makedirs(d, exist_ok=True)
            
        clean_env = {}
        preserve_keys = [
            "SystemRoot", "SystemDrive", "windir", "COMSPEC", "PATHEXT", 
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
            "PROCESSOR_LEVEL", "PROCESSOR_REVISION",
            "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "TERM"
        ]
        for key in preserve_keys:
            if key in os.environ:
                clean_env[key] = os.environ[key]
                
        drive, path = os.path.splitdrive(home_dir)
        clean_env["USERPROFILE"] = home_dir
        clean_env["HOMEPATH"] = path
        clean_env["HOMEDRIVE"] = drive if drive else "C:"
        clean_env["HOME"] = home_dir
        clean_env["APPDATA"] = appdata_dir
        clean_env["LOCALAPPDATA"] = os.path.join(appdata_dir, "Local")
        clean_env["TEMP"] = temp_dir
        clean_env["TMP"] = temp_dir

        custom_paths = []
        for handler in self.handlers:
            handler_vars = handler.get_env_vars(container_dir)
            clean_env.update(handler_vars)
            custom_paths.extend(handler.get_path_dirs(container_dir))

        sys_path = os.environ.get("PATH", "")
        system_paths = []
        for path in sys_path.split(os.pathsep):
            path_normalized = path.replace("\\", "/")
            if "system32" in path_normalized.lower() or "syswow64" in path_normalized.lower():
                system_paths.append(path)
            elif "windows" in path_normalized.lower():
                system_paths.append(path)
            elif any(x in path_normalized.lower() for x in ["/bin", "/usr/bin", "/sbin", "/usr/sbin", "/usr/local/bin"]):
                system_paths.append(path)

        clean_env["PATH"] = os.pathsep.join(custom_paths + system_paths)

        try:
            process = subprocess.Popen(
                command,
                cwd=src_dir,
                env=clean_env,
                shell=True
            )
            process.wait()
            return process.returncode == 0
        except Exception as e:
            print(f"[ZEROSPACE ERROR] Exception running CLI command: {e}")
            return False
