import os
import shutil
import logging
import threading
import subprocess
import datetime
from typing import Dict, List, Any, Optional
from zerospace.config import get_tools_dir, get_containers_dir, get_logs_dir
from zerospace.db import ToolDatabase
from zerospace.downloader import download_and_extract_tool
from zerospace.analyzer import analyze_source_directory
from zerospace.environments import get_environment_handler

logger = logging.getLogger("zerospace.manager")

class ToolManager:
    def __init__(self):
        self.db = ToolDatabase()
        # In-memory map of active processes: { tool_id: subprocess.Popen }
        self.active_processes: Dict[str, subprocess.Popen] = {}
        # In-memory map of active setup threads: { tool_id: threading.Thread }
        self.active_setups: Dict[str, threading.Thread] = {}
        
        # Reset any tools marked "Running" or "Installing..." to "Stopped" or "Setup Error" on boot
        # because process handles are lost.
        self._sync_db_on_startup()

    def _sync_db_on_startup(self):
        for tool in self.db.list_tools():
            tool_id = tool["id"]
            if tool.get("status") == "Running":
                self.db.update_tool(tool_id, {"status": "Stopped"})
            elif tool.get("status") in ["Installing", "Updating"]:
                self.db.update_tool(tool_id, {"status": "Setup Error"})

    def add_tool(self, name: str, source: str, description: str = "", language_override: str = None, container_path: str = None) -> str:
        """Adds a tool by downloading/copying source code, analyzing it, and saving to database."""
        # Create a unique URL-friendly ID
        clean_name = "".join(c if c.isalnum() else "_" for c in name.lower())
        tool_id = f"{clean_name}_{int(datetime.datetime.now().timestamp())}"
        
        # 1. Download and extract
        logger.info(f"Adding tool '{name}' from source: {source}")
        src_dir = download_and_extract_tool(source, tool_id)
        
        # 2. Analyze source files
        analysis = analyze_source_directory(src_dir)
        
        if language_override == "auto":
            language_override = None
        language = language_override or analysis["language"]
        desc = description or analysis["description"] or f"Cybersecurity tool: {name}"
        
        container_dir = container_path if container_path else os.path.join(get_containers_dir(), tool_id)
        
        tool_data = {
            "id": tool_id,
            "name": name,
            "description": desc,
            "source": source,
            "language": language,
            "entrypoint": analysis["entrypoint"] or "main.py",
            "dependencies": analysis["dependencies"],
            "dependencies_file": analysis["dependencies_file"],
            "container_path": os.path.abspath(container_dir),
            "src_path": src_dir,
            "status": "Installed",
            "last_args": "",
            "created_at": datetime.datetime.now().isoformat()
        }
        
        self.db.add_tool(tool_id, tool_data)
        
        # 3. Start setup asynchronously
        self.start_setup_thread(tool_id)
        
        return tool_id

    def start_setup_thread(self, tool_id: str):
        """Builds environment and installs dependencies in a background thread."""
        if tool_id in self.active_setups and self.active_setups[tool_id].is_alive():
            return
            
        self.db.update_tool(tool_id, {"status": "Installing"})
        
        thread = threading.Thread(target=self._run_setup, args=(tool_id,), daemon=True)
        self.active_setups[tool_id] = thread
        thread.start()

    def _run_setup(self, tool_id: str):
        tool = self.db.get_tool(tool_id)
        if not tool:
            return
            
        src_dir = tool["src_path"]
        container_dir = tool["container_path"]
        language = tool["language"]
        
        setup_log = os.path.join(get_logs_dir(), f"{tool_id}_setup.log")
        env_handler = get_environment_handler(language)
        
        success = env_handler.setup(src_dir, container_dir, setup_log)
        
        if success:
            self.db.update_tool(tool_id, {"status": "Installed"})
            logger.info(f"Setup succeeded for tool: {tool_id}")
        else:
            self.db.update_tool(tool_id, {"status": "Setup Error"})
            logger.error(f"Setup failed for tool: {tool_id}")

    def run_tool(self, tool_id: str, args: str = "") -> bool:
        """Runs the tool in background container."""
        # Sync process state first
        self.get_tool_status(tool_id)
        
        tool = self.db.get_tool(tool_id)
        if not tool:
            return False
            
        if tool["status"] == "Running":
            return False
            
        src_dir = tool["src_path"]
        container_dir = tool["container_path"]
        entrypoint = tool["entrypoint"]
        language = tool["language"]
        
        run_log = os.path.join(get_logs_dir(), f"{tool_id}_run.log")
        env_handler = get_environment_handler(language)
        
        try:
            process = env_handler.run(src_dir, container_dir, entrypoint, args, run_log)
            self.active_processes[tool_id] = process
            self.db.update_tool(tool_id, {
                "status": "Running",
                "last_args": args
            })
            logger.info(f"Tool {tool_id} started. PID: {process.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to start tool {tool_id}: {e}")
            with open(run_log, "a", encoding="utf-8") as f:
                f.write(f"\n[ZEROSPACE ERROR] Failed to start tool process: {e}\n")
            self.db.update_tool(tool_id, {"status": "Stopped"})
            return False

    def stop_tool(self, tool_id: str) -> bool:
        """Terminates the running tool process."""
        process = self.active_processes.get(tool_id)
        
        if not process:
            # Check if it was marked running in DB but process isn't in manager memory
            tool = self.db.get_tool(tool_id)
            if tool and tool["status"] == "Running":
                self.db.update_tool(tool_id, {"status": "Stopped"})
                return True
            return False
            
        try:
            # Terminate and clean up handle
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                
            # Close log file handle if reference was stored
            if hasattr(process, 'log_file_handle'):
                try:
                    process.log_file_handle.close()
                except Exception:
                    pass
                    
            logger.info(f"Tool {tool_id} stopped.")
        except Exception as e:
            logger.error(f"Error stopping tool {tool_id}: {e}")
            
        if tool_id in self.active_processes:
            del self.active_processes[tool_id]
            
        self.db.update_tool(tool_id, {"status": "Stopped"})
        return True

    def restart_tool(self, tool_id: str) -> bool:
        """Stops and runs the tool with the same arguments."""
        tool = self.db.get_tool(tool_id)
        if not tool:
            return False
        args = tool.get("last_args", "")
        self.stop_tool(tool_id)
        return self.run_tool(tool_id, args)

    def update_tool(self, tool_id: str) -> bool:
        """Pulls changes and rebuilds the environment."""
        tool = self.db.get_tool(tool_id)
        if not tool:
            return False
            
        # 1. Stop if running
        self.stop_tool(tool_id)
        
        # 2. Re-download and install in thread
        self.db.update_tool(tool_id, {"status": "Updating"})
        
        def _async_update():
            try:
                # Re-download
                download_and_extract_tool(tool["source"], tool_id)
                # Analyze again to capture any new dependencies
                analysis = analyze_source_directory(tool["src_path"])
                self.db.update_tool(tool_id, {
                    "dependencies": analysis["dependencies"],
                    "dependencies_file": analysis["dependencies_file"],
                    "entrypoint": analysis["entrypoint"] or tool["entrypoint"]
                })
                # Re-run setup
                self._run_setup(tool_id)
            except Exception as e:
                logger.error(f"Failed to update tool {tool_id}: {e}")
                self.db.update_tool(tool_id, {"status": "Setup Error"})
                
        thread = threading.Thread(target=_async_update, daemon=True)
        self.active_setups[tool_id] = thread
        thread.start()
        return True

    def remove_tool(self, tool_id: str) -> bool:
        """Deletes the tool source, containers, database entries, and logs."""
        self.stop_tool(tool_id)
        
        tool = self.db.get_tool(tool_id)
        if not tool:
            return False
            
        # Delete source directory
        if os.path.exists(tool["src_path"]):
            try:
                shutil.rmtree(os.path.dirname(tool["src_path"])) # deletes root tool folder tools/<id>
            except Exception as e:
                logger.warning(f"Error removing source dir for {tool_id}: {e}")
                
        # Delete container directory
        if os.path.exists(tool["container_path"]):
            try:
                shutil.rmtree(tool["container_path"])
            except Exception as e:
                logger.warning(f"Error removing container dir for {tool_id}: {e}")
                
        # Delete log files
        for suffix in ["_run.log", "_setup.log"]:
            log_path = os.path.join(get_logs_dir(), f"{tool_id}{suffix}")
            if os.path.exists(log_path):
                try:
                    os.remove(log_path)
                except Exception:
                    pass
                    
        # Remove from database
        self.db.delete_tool(tool_id)
        logger.info(f"Tool {tool_id} removed.")
        return True

    def get_tool_status(self, tool_id: str) -> str:
        """Synchronizes and returns the current status of the tool."""
        tool = self.db.get_tool(tool_id)
        if not tool:
            return "Stopped"
            
        status = tool["status"]
        process = self.active_processes.get(tool_id)
        
        if status == "Running":
            if process is None:
                # If marked running but no process handle exists, update status
                self.db.update_tool(tool_id, {"status": "Stopped"})
                return "Stopped"
            
            # Check if subprocess has exited
            exit_code = process.poll()
            if exit_code is not None:
                # Process finished
                # Close log file handle
                if hasattr(process, 'log_file_handle'):
                    try:
                        process.log_file_handle.close()
                    except Exception:
                        pass
                # Remove active process reference
                del self.active_processes[tool_id]
                
                # Check exit code
                new_status = "Stopped" if exit_code == 0 or exit_code == -15 else "Error"
                self.db.update_tool(tool_id, {"status": new_status})
                return new_status
                
        return status

    def get_logs(self, tool_id: str, log_type: str = "run", max_lines: int = 150) -> str:
        """Gets the tail of logs of log_type ('run' or 'setup')."""
        log_path = os.path.join(get_logs_dir(), f"{tool_id}_{log_type}.log")
        if not os.path.exists(log_path):
            return f"Log file for '{log_type}' does not exist yet."
            
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                tail = lines[-max_lines:]
                return "".join(tail)
        except Exception as e:
            return f"Failed to read logs: {e}"

    def run_cli_command(self, tool_id: str, command: str) -> bool:
        """Runs a custom command in the tool's sandboxed environment asynchronously,
        appending output to the setup log.
        """
        tool = self.db.get_tool(tool_id)
        if not tool:
            return False

        if tool_id in self.active_setups and self.active_setups[tool_id].is_alive():
            return False

        self.db.update_tool(tool_id, {"status": "Installing"})

        def _async_cli_run():
            src_dir = tool["src_path"]
            container_dir = tool["container_path"]
            language = tool["language"]
            setup_log = os.path.join(get_logs_dir(), f"{tool_id}_setup.log")

            # Append CLI execution prefix
            with open(setup_log, "a", encoding="utf-8", buffering=1) as f:
                f.write(f"\n[ZEROSPACE CLI] Executing command: {command}\n")

            env_handler = get_environment_handler(language)
            success = False
            try:
                success = env_handler.run_command(src_dir, container_dir, command, setup_log)
            except Exception as e:
                with open(setup_log, "a", encoding="utf-8") as f:
                    f.write(f"[ZEROSPACE ERROR] Exception running command: {e}\n")

            if success:
                self.db.update_tool(tool_id, {"status": "Installed"})
            else:
                self.db.update_tool(tool_id, {"status": "Setup Error"})

        thread = threading.Thread(target=_async_cli_run, daemon=True)
        self.active_setups[tool_id] = thread
        thread.start()
        return True

    def run_cli_command_sync(self, tool_id: str, command: str) -> bool:
        """Runs a custom command inside the tool's sandboxed environment,
        printing stdout/stderr directly to the terminal.
        """
        tool = self.db.get_tool(tool_id)
        if not tool:
            print(f"Tool with ID '{tool_id}' not found.")
            return False

        src_dir = tool["src_path"]
        container_dir = tool["container_path"]
        language = tool["language"]

        env_handler = get_environment_handler(language)
        if hasattr(env_handler, "run_command_terminal"):
            return env_handler.run_command_terminal(src_dir, container_dir, command)
        else:
            setup_log = os.path.join(get_logs_dir(), f"{tool_id}_setup.log")
            return env_handler.run_command(src_dir, container_dir, command, setup_log)

