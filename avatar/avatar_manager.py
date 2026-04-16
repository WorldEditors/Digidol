import os
import json
from typing import Dict, List, Optional

class AvatarManager:
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.join(os.path.dirname(__file__), "..", "avatar")
        self.available_avatars = self._scan_avatars()
    
    def _scan_avatars(self) -> Dict:
        avatars = {}
        if not os.path.exists(self.base_dir):
            return avatars
        
        for avatar_name in os.listdir(self.base_dir):
            avatar_path = os.path.join(self.base_dir, avatar_name)
            if os.path.isdir(avatar_path):
                config_path = os.path.join(avatar_path, "config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        avatars[avatar_name] = json.load(f)
        return avatars
    
    def get_avatar_list(self) -> List[Dict]:
        result = []
        for name, config in self.available_avatars.items():
            result.append({
                "name": name,
                "display_name": config.get("display_name", name),
                "type": config.get("type", "2d"),
                "description": config.get("description", "")
            })
        return result
    
    def get_avatar_config(self, avatar_name: str) -> Optional[Dict]:
        return self.available_avatars.get(avatar_name)
    
    def get_motions(self, avatar_name: str) -> List[str]:
        config = self.get_avatar_config(avatar_name)
        if config and "motions" in config:
            return list(config["motions"].keys())
        return []
    
    def get_expressions(self, avatar_name: str) -> List[str]:
        config = self.get_avatar_config(avatar_name)
        if config and "expressions" in config:
            return list(config["expressions"].keys())
        return []
    
    def add_avatar(self, avatar_name: str, config: Dict) -> bool:
        try:
            avatar_path = os.path.join(self.base_dir, avatar_name)
            os.makedirs(avatar_path, exist_ok=True)
            
            config_path = os.path.join(avatar_path, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            os.makedirs(os.path.join(avatar_path, "motions"), exist_ok=True)
            os.makedirs(os.path.join(avatar_path, "expressions"), exist_ok=True)
            
            self.available_avatars[avatar_name] = config
            return True
        except Exception as e:
            print(f"添加Avatar失败: {e}")
            return False
    
    def update_avatar_config(self, avatar_name: str, config: Dict) -> bool:
        if avatar_name not in self.available_avatars:
            return False
        
        try:
            avatar_path = os.path.join(self.base_dir, avatar_name)
            config_path = os.path.join(avatar_path, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.available_avatars[avatar_name] = config
            return True
        except Exception as e:
            print(f"更新Avatar配置失败: {e}")
            return False
    
    def delete_avatar(self, avatar_name: str) -> bool:
        if avatar_name not in self.available_avatars:
            return False
        
        try:
            import shutil
            avatar_path = os.path.join(self.base_dir, avatar_name)
            shutil.rmtree(avatar_path)
            del self.available_avatars[avatar_name]
            return True
        except Exception as e:
            print(f"删除Avatar失败: {e}")
            return False


class MotionController:
    def __init__(self):
        self.current_motion = "idle"
        self.current_expression = "neutral"
        self.is_animating = False
    
    def play_motion(self, motion_name: str) -> Dict:
        self.current_motion = motion_name
        return {
            "motion": motion_name,
            "type": "animation",
            "loop": motion_name in ["idle", "dance"]
        }
    
    def set_expression(self, expression_name: str) -> Dict:
        self.current_expression = expression_name
        return {
            "expression": expression_name,
            "type": "expression"
        }
    
    def get_current_state(self) -> Dict:
        return {
            "motion": self.current_motion,
            "expression": self.current_expression,
            "animating": self.is_animating
        }