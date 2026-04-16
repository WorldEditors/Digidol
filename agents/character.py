import json
import os
from typing import Dict, Any, List, Optional


class Character:
    def __init__(self, role_name: str):
        self.role_name = role_name
        self.role_dir = os.path.join(os.path.dirname(__file__), "..", "roles", role_name)
        self.profile: Dict = {}
        self.short_term_memory: List[Dict] = []
        self.long_term_memory: Dict = {}
        self.skills: Dict = {}
        self._memory_store = None
        self.load_character()

    # ------------------------------------------------------------------ #
    # Loading                                                              #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def save_short_term_memory(self):
        short_term_path = os.path.join(self.role_dir, "memory", "short_term.json")
        with open(short_term_path, "w", encoding="utf-8") as f:
            json.dump({"conversation_history": self.short_term_memory}, f, ensure_ascii=False, indent=2)

    def save_long_term_memory(self):
        long_term_path = os.path.join(self.role_dir, "memory", "long_term.json")
        with open(long_term_path, "w", encoding="utf-8") as f:
            json.dump(self.long_term_memory, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    # Memory operations                                                    #
    # ------------------------------------------------------------------ #

    def add_conversation(self, role: str, content: str):
        self.short_term_memory.append({
            "role": role,
            "content": content,
            "timestamp": self._get_timestamp(),
        })
        if len(self.short_term_memory) > 50:
            self.short_term_memory = self.short_term_memory[-50:]
        self.save_short_term_memory()

    def add_long_term_memory(self, content: str, emotion: str = "中性"):
        # 写入 long_term.json（供向后兼容展示）
        memory = {
            "content": content,
            "timestamp": self._get_timestamp(),
            "emotion": emotion,
        }
        if "important_memories" not in self.long_term_memory:
            self.long_term_memory["important_memories"] = []
        self.long_term_memory["important_memories"].append(memory)
        self.save_long_term_memory()

        # 同时写入向量存储
        store = self._get_memory_store()
        if store:
            store.add(content, emotion, {"timestamp": memory["timestamp"]})

    def update_user_info(self, key: str, value: Any):
        if "user_info" not in self.long_term_memory:
            self.long_term_memory["user_info"] = {}
        self.long_term_memory["user_info"][key] = value
        self.save_long_term_memory()

    def clear_short_term_memory(self):
        self.short_term_memory = []
        self.save_short_term_memory()

    # ------------------------------------------------------------------ #
    # Retrieval                                                            #
    # ------------------------------------------------------------------ #

    def get_conversation_context(self) -> List[Dict]:
        """返回最近 10 条对话供 LLM 使用（不含 timestamp）。"""
        recent = self.short_term_memory[-10:]
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def get_relevant_memories(self, query: str) -> List[Dict]:
        store = self._get_memory_store()
        if store:
            return store.search(query, top_k=5)

        # 降级：关键词匹配
        hints = ["喜欢", "讨厌", "名字", "生日", "爱好", "工作", "学习", "城市"]
        memories = self.long_term_memory.get("important_memories", [])
        relevant = [
            m for m in memories
            if any(kw in query or kw in m.get("content", "") for kw in hints)
        ]
        return relevant[-5:]

    # ------------------------------------------------------------------ #
    # LLM prompt helpers                                                   #
    # ------------------------------------------------------------------ #

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

你必须以如下 JSON 格式回复，不要输出任何 JSON 以外的内容：
{{
  "text": "角色的回复内容",
  "emotion": "情绪标签（从 happy/sad/angry/shy/excited/bored/cute/thinking/sleepy/neutral 中选一个）",
  "action": "动作标签（从 dance/wave/bow/pat/hug/cheer/null 中选一个，无动作时填 null）",
  "memory_to_save": "如果本次对话有需要永久记住的重要信息，在此填写；否则填 null"
}}"""
        return prompt

    def get_tts_config(self) -> Dict[str, str]:
        settings = self.profile.get("custom_settings", {})
        return {
            "voice": settings.get("tts_voice", "zh-CN-XiaoxiaoNeural"),
            "rate": settings.get("tts_rate", "+0%"),
            "pitch": settings.get("tts_pitch", "+0Hz"),
        }

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _get_memory_store(self):
        """懒加载 MemoryStore，只有在 role_dir 存在时才初始化。"""
        if self._memory_store is None and os.path.exists(self.role_dir):
            from .memory_store import MemoryStore
            api_key = os.environ.get("OPENAI_API_KEY")
            self._memory_store = MemoryStore(self.role_dir, api_key=api_key)
        return self._memory_store

    def set_memory_store_api_key(self, api_key: str):
        store = self._get_memory_store()
        if store:
            store.set_api_key(api_key)
