import os
import subprocess
from zerospace.environments.base import BaseEnvironment

class PlaceholderEnvironment(BaseEnvironment):
    def __init__(self, name: str):
        self.name = name

    def setup(self, src_dir: str, container_dir: str, log_filepath: str) -> bool:
        with open(log_filepath, "w", encoding="utf-8") as f:
            f.write(f"[ZEROSPACE ERROR] Setup failed: The '{self.name}' runtime environment is not installed/enabled.\n")
            f.write(f"ZeroSpace currently supports Python virtual environments out-of-the-box.\n")
            f.write(f"Please check back when '{self.name}' support is integrated.\n")
        return False

    def run(self, src_dir: str, container_dir: str, entrypoint: str, args: str, log_filepath: str) -> subprocess.Popen:
        log_file = open(log_filepath, "w", encoding="utf-8")
        log_file.write(f"[ZEROSPACE ERROR] Run failed: The '{self.name}' runtime environment is not active.\n")
        log_file.close()
        raise NotImplementedError(f"The '{self.name}' environment is not implemented yet.")

    def run_command(self, src_dir: str, container_dir: str, command: str, log_filepath: str) -> bool:
        with open(log_filepath, "a", encoding="utf-8") as f:
            f.write(f"[ZEROSPACE ERROR] Command execution failed: The '{self.name}' runtime environment is not active.\n")
        return False


class NodeJsEnvironment(PlaceholderEnvironment):
    def __init__(self):
        super().__init__("Node.js / package.json")

class MakefileEnvironment(PlaceholderEnvironment):
    def __init__(self):
        super().__init__("Makefile / Native Compiler")

class DockerEnvironment(PlaceholderEnvironment):
    def __init__(self):
        super().__init__("Docker / Container Engine")
