import json
import os
from typing import Dict, Any, List, Optional

class Character:
    def __init__(self, role_name: str):
        self.role_name = role_name
        self.role_dir = os.path.join(os.path.dirname(__file__), "..", "roles", role_name)
        self.profile = {}
        self.short_term_memory = []
        self.long_term_memory = {}
        self.skills = {}
        self.load_character()
    
    def load_character(self):
        profile_path = os.path.join(self.role_dir, "profile.json")
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                self.profile = json.load(f)
        
        self._load_memory()
        self._load_skills()
    
    def _load_memory(self):
        short_term_path = os.path.join(self.role_dir, "memory", "short_term.json")
        if os.path.exists(short_term_path):
            with open(short_term_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.short_term_memory = data.get("conversation_history", [])
        
        long_term_path = os.path.join(self.role_dir, "memory", "long_term.json")
        if os.path.exists(long_term_path):
            with open(long_term_path, "r", encoding="utf-8") as f:
                self.long_term_memory = json.load(f)
    
    def _load_skills(self):
        skills_path = os.path.join(self.role_dir, "skills.json")
        if os.path.exists(skills_path):
            with open(skills_path, "r", encoding="utf-8") as f:
                self.skills = json.load(f)
    
    def save_short_term_memory(self):
        short_term_path = os.path.join(self.role_dir, "memory", "short_term.json")
        with open(short_term_path, "w", encoding="utf-8") as f:
            json.dump({"conversation_history": self.short_term_memory}, f, ensure_ascii=False, indent=2)
    
    def save_long_term_memory(self):
        long_term_path = os.path.join(self.role_dir, "memory", "long_term.json")
        with open(long_term_path, "w", encoding="utf-8") as f:
            json.dump(self.long_term_memory, f, ensure_ascii=False, indent=2)
    
    def add_conversation(self, role: str, content: str):
        self.short_term_memory.append({
            "role": role,
            "content": content,
            "timestamp": self._get_timestamp()
        })
        if len(self.short_term_memory) > 50:
            self.short_term_memory = self.short_term_memory[-50:]
        self.save_short_term_memory()
    
    def add_long_term_memory(self, content: str, emotion: str = "中性"):
        memory = {
            "content": content,
            "timestamp": self._get_timestamp(),
            "emotion": emotion
        }
        if "important_memories" not in self.long_term_memory:
            self.long_term_memory["important_memories"] = []
        self.long_term_memory["important_memories"].append(memory)
        self.save_long_term_memory()
    
    def update_user_info(self, key: str, value: Any):
        if "user_info" not in self.long_term_memory:
            self.long_term_memory["user_info"] = {}
        self.long_term_memory["user_info"][key] = value
        self.save_long_term_memory()
    
    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_system_prompt(self) -> str:
        name = self.profile.get("display_name", self.role_name)
        personality = self.profile.get("personality", "")
        gender = self.profile.get("gender", "未知")
        age = self.profile.get("age", 18)
        education = self.profile.get("education", "")
        speaking_style = self.profile.get("speaking_style", "")
        likes = self.profile.get("likes", {})
        dislikes = self.profile.get("dislikes", [])
        habits = self.profile.get("habits", [])
        
        prompt = f"""你是{name}，一个虚拟角色。
你的性格：{personality}
性别：{gender}
年龄：{age}
教育程度：{education}
说话风格：{speaking_style}

爱好：
- 喜欢的食物：{', '.join(likes.get('food', []))}
- 喜欢的游戏：{', '.join(likes.get('games', []))}
- 喜欢的音乐：{', '.join(likes.get('music', []))}
- 喜欢的电影：{', '.join(likes.get('movies', []))}

讨厌：{', '.join(dislikes)}

习惯：{', '.join(habits)}

请根据以上角色设定，用符合角色性格的方式回复用户。
你可以使用动作和表情来增强表达，使用动作时用[动作]标记。
例如：[高兴] 我好开心啊！[/动作]"""
        return prompt
    
    def get_tts_config(self) -> Dict[str, str]:
        return self.profile.get("custom_settings", {}).get("tts", {})
    
    def get_conversation_context(self) -> List[Dict]:
        return self.short_term_memory[-10:]
    
    def get_relevant_memories(self, query: str) -> List[Dict]:
        relevant = []
        memories = self.long_term_memory.get("important_memories", [])
        for mem in memories:
            if any(keyword in query or keyword in mem.get("content", "") for keyword in ["喜欢", "讨厌", "名字", "生日", "爱好"]):
                relevant.append(mem)
        return relevant[-5:]
    
    def clear_short_term_memory(self):
        self.short_term_memory = []
        self.save_short_term_memory()