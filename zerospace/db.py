import os
import json
import logging
from typing import Dict, List, Any, Optional
from zerospace.config import DB_FILE

logger = logging.getLogger("zerospace.db")

class ToolDatabase:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._load()

    def _load(self):
        if not os.path.exists(self.db_path):
            self.data = {"tools": {}, "settings": {}}
            self.tools = self.data["tools"]
            self._save()
        else:
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict) and "tools" in loaded and "settings" in loaded:
                        self.data = loaded
                        self.tools = self.data["tools"]
                    else:
                        # Migrate old schema
                        self.data = {
                            "tools": loaded if isinstance(loaded, dict) else {},
                            "settings": {}
                        }
                        self.tools = self.data["tools"]
            except Exception as e:
                logger.error(f"Failed to load database: {e}")
                self.data = {"tools": {}, "settings": {}}
                self.tools = self.data["tools"]

    def _save(self):
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save database: {e}")

    def get_settings(self) -> Dict[str, Any]:
        return self.data.get("settings", {})

    def update_settings(self, new_settings: Dict[str, Any]):
        if "settings" not in self.data:
            self.data["settings"] = {}
        self.data["settings"].update(new_settings)
        self._save()

    def add_tool(self, tool_id: str, tool_data: Dict[str, Any]) -> bool:
        if tool_id in self.tools:
            return False
        self.tools[tool_id] = tool_data
        self._save()
        return True

    def update_tool(self, tool_id: str, updates: Dict[str, Any]) -> bool:
        if tool_id not in self.tools:
            return False
        self.tools[tool_id].update(updates)
        self._save()
        return True

    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        return self.tools.get(tool_id)

    def delete_tool(self, tool_id: str) -> bool:
        if tool_id in self.tools:
            del self.tools[tool_id]
            self._save()
            return True
        return False

    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self.tools.values())
