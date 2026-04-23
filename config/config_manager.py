import json
import os
from pathlib import Path


class ConfigManager:
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = Path.home() / ".digidol"
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()
        self._ensure_default_config()
        self.config = self._load_config()

    def _ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_default_config(self):
        if not self.config_file.exists():
            default_config = self._get_default_config()
            self._save_config(default_config)

    def _get_default_config(self) -> dict:
        models_json_path = Path(__file__).parent / "models.json"
        if models_json_path.exists():
            with open(models_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "active_model": "kimi",
            "models": {
                "kimi": {
                    "name": "Kimi (Moonshot)",
                    "api_key": "",
                    "model_name": "moonshot-v1-8k",
                    "api_base": "https://api.moonshot.cn/v1",
                    "enabled": True
                }
            }
        }

    def _load_config(self) -> dict:
        if not self.config_file.exists():
            self._ensure_default_config()
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_config(self, config: dict):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def get_active_model(self) -> dict:
        model_name = self.config.get("active_model", "kimi")
        return self.config["models"].get(model_name)

    def set_active_model(self, model_id: str):
        if model_id in self.config["models"]:
            self.config["active_model"] = model_id
            self._save_config(self.config)

    def update_model_config(self, model_id: str, api_key: str = None, model_name: str = None, api_base: str = None, enabled: bool = None):
        if model_id in self.config["models"]:
            if api_key is not None:
                self.config["models"][model_id]["api_key"] = api_key
            if model_name is not None:
                self.config["models"][model_id]["model_name"] = model_name
            if api_base is not None:
                self.config["models"][model_id]["api_base"] = api_base
            if enabled is not None:
                self.config["models"][model_id]["enabled"] = enabled
            self._save_config(self.config)

    def get_all_models(self) -> dict:
        return self.config.get("models", {})

    def get_enabled_models(self) -> dict:
        models = self.get_all_models()
        return {k: v for k, v in models.items() if v.get("enabled", True)}

    def reload(self):
        self.config = self._load_config()