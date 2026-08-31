import os
import logging
from flask import Flask, jsonify, request, render_template, send_from_directory
from zerospace.manager import ToolManager
from zerospace.config import BASE_DIR

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("zerospace.app")

# Initialize Flask app
# Set static and templates directories inside zerospace package
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "zerospace", "templates"),
    static_folder=os.path.join(BASE_DIR, "zerospace", "static")
)

# Instantiate tool manager
manager = ToolManager()

def get_dir_size(path: str) -> int:
    """Returns size of directory in bytes."""
    total_size = 0
    if not os.path.exists(path):
        return 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # Skip if link breaks or permissions issue
            try:
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
            except Exception:
                pass
    return total_size

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/tools", methods=["GET"])
def list_tools():
    # Sync statuses
    tools = manager.db.list_tools()
    for tool in tools:
        manager.get_tool_status(tool["id"])
    # Re-fetch synced list
    return jsonify(manager.db.list_tools())

@app.route("/api/tools/<tool_id>", methods=["GET"])
def get_tool(tool_id):
    manager.get_tool_status(tool_id)
    tool = manager.db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "Tool not found"}), 404
    return jsonify(tool)

@app.route("/api/tools", methods=["POST"])
def add_tool():
    data = request.get_json() or {}
    name = data.get("name")
    source = data.get("source")
    description = data.get("description", "")
    language = data.get("language")  # Optional override
    container_path = data.get("container_path")  # Optional override
    
    if not name or not source:
        return jsonify({"error": "Name and Source URL/path are required"}), 400
        
    try:
        tool_id = manager.add_tool(name, source, description, language, container_path)
        return jsonify({
            "message": "Tool added and download completed. Environment setup initiated.",
            "tool_id": tool_id
        }), 201
    except Exception as e:
        logger.error(f"Failed to add tool: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/tools/<tool_id>/run", methods=["POST"])
def run_tool(tool_id):
    data = request.get_json() or {}
    args = data.get("args", "")
    
    success = manager.run_tool(tool_id, args)
    if success:
        return jsonify({"message": f"Tool started successfully.", "status": "Running"})
    else:
        return jsonify({"error": "Failed to start tool. Check setup status and run logs."}), 500

@app.route("/api/tools/<tool_id>/stop", methods=["POST"])
def stop_tool(tool_id):
    success = manager.stop_tool(tool_id)
    if success:
        return jsonify({"message": "Tool stopped.", "status": "Stopped"})
    else:
        return jsonify({"error": "Failed to stop tool (might not be running)."}), 400

@app.route("/api/tools/<tool_id>/restart", methods=["POST"])
def restart_tool(tool_id):
    success = manager.restart_tool(tool_id)
    if success:
        return jsonify({"message": "Tool restarted.", "status": "Running"})
    else:
        return jsonify({"error": "Failed to restart tool."}), 500

@app.route("/api/tools/<tool_id>/update", methods=["POST"])
def update_tool(tool_id):
    success = manager.update_tool(tool_id)
    if success:
        return jsonify({"message": "Tool update and rebuild started."})
    else:
        return jsonify({"error": "Failed to update tool."}), 500

@app.route("/api/tools/<tool_id>", methods=["DELETE"])
def remove_tool(tool_id):
    success = manager.remove_tool(tool_id)
    if success:
        return jsonify({"message": "Tool deleted."})
    else:
        return jsonify({"error": "Failed to delete tool."}), 404

@app.route("/api/tools/<tool_id>/logs/<log_type>", methods=["GET"])
def get_logs(tool_id, log_type):
    if log_type not in ["run", "setup"]:
        return jsonify({"error": "Invalid log type. Must be 'run' or 'setup'."}), 400
    logs = manager.get_logs(tool_id, log_type)
    return jsonify({"logs": logs})

@app.route("/api/tools/<tool_id>/cli", methods=["POST"])
def run_cli_command(tool_id):
    data = request.get_json() or {}
    command = data.get("command")
    if not command:
        return jsonify({"error": "Command is required"}), 400
        
    success = manager.run_cli_command(tool_id, command)
    if success:
        return jsonify({"message": "Command execution started in sandboxed environment."})
    else:
        return jsonify({"error": "Failed to trigger command. Check tool setup status (is another setup/cli task active?)."}), 400

@app.route("/api/containers", methods=["GET"])
def get_containers():
    """Gets details about each tool's isolated container on disk."""
    containers_info = []
    for tool in manager.db.list_tools():
        tool_id = tool["id"]
        c_path = tool["container_path"]
        
        # Calculate size on disk
        size_bytes = get_dir_size(c_path)
        size_mb = round(size_bytes / (1024 * 1024), 2)
        
        containers_info.append({
            "tool_id": tool_id,
            "tool_name": tool["name"],
            "language": tool["language"],
            "container_path": c_path,
            "size_mb": size_mb,
            "status": tool["status"]
        })
    return jsonify(containers_info)

@app.route("/api/settings", methods=["GET"])
def get_settings():
    from zerospace.config import get_tools_dir, get_containers_dir, get_logs_dir
    settings = manager.db.get_settings()
    return jsonify({
        "tools_path": settings.get("tools_path", get_tools_dir()),
        "containers_path": settings.get("containers_path", get_containers_dir()),
        "logs_path": settings.get("logs_path", get_logs_dir())
    })

@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json() or {}
    tools_path = data.get("tools_path")
    containers_path = data.get("containers_path")
    logs_path = data.get("logs_path")
    
    if not tools_path or not containers_path or not logs_path:
        return jsonify({"error": "All paths must be specified."}), 400
        
    try:
        # Create directories if they do not exist
        for d in [tools_path, containers_path, logs_path]:
            os.makedirs(d, exist_ok=True)
            
        manager.db.update_settings({
            "tools_path": tools_path,
            "containers_path": containers_path,
            "logs_path": logs_path
        })
        return jsonify({"message": "Paths configuration saved successfully. Directory overrides are active."})
    except Exception as e:
        return jsonify({"error": f"Failed to create directories or save settings: {e}"}), 500
