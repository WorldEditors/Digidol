import os
import json
import re
from typing import Dict, Any, List, Optional
from .character import Character

class VLMAgent:
    def __init__(self, character: Character, api_key: str = None, model: str = "openai"):
        self.character = character
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None
        self._init_client()
    
    def _init_client(self):
        if self.model == "openai":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                print("请安装openai库: pip install openai")
        elif self.model == "anthropic":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                print("请安装anthropic库: pip install anthropic")
        elif self.model == "google":
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
            except ImportError:
                print("请安装google-generativeai库")
    
    def generate_response(self, user_input: str, context: Dict = None) -> Dict[str, Any]:
        system_prompt = self.character.get_system_prompt()
        
        conversation = self.character.get_conversation_context()
        conversation.append({"role": "user", "content": user_input})
        
        relevant_memories = self.character.get_relevant_memories(user_input)
        if relevant_memories:
            memory_context = "\n".join([f"- {m['content']} ({m.get('timestamp', '')})" for m in relevant_memories])
            system_prompt += f"\n\n相关记忆：\n{memory_context}"
        
        if context and context.get("emotion"):
            system_prompt += f"\n\n当前情绪状态：{context['emotion']}"
        
        try:
            if self.model == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "system", "content": system_prompt}] + conversation,
                    temperature=0.8,
                    max_tokens=500
                )
                response_text = response.choices[0].message.content
            
            elif self.model == "anthropic":
                response = self.client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=500,
                    system=system_prompt,
                    messages=conversation
                )
                response_text = response.content[0].text
            
            elif self.model == "google":
                model = self.client.GenerativeModel('gemini-pro')
                full_prompt = f"{system_prompt}\n\n对话历史：{json.dumps(conversation, ensure_ascii=False)}\n\n用户：{user_input}"
                response = model.generate_content(full_prompt)
                response_text = response.text
            
            else:
                response_text = "暂不支持该模型"
            
            return {
                "text": response_text,
                "action": self._extract_action(response_text),
                "emotion": self._detect_emotion(response_text)
            }
        
        except Exception as e:
            return {
                "text": f"抱歉，我现在有点累，让我休息一下...",
                "action": None,
                "emotion": "tired",
                "error": str(e)
            }
    
    def _extract_action(self, text: str) -> Optional[str]:
        action_pattern = r'\[动作\](.*?)\[/动作\]'
        match = re.search(action_pattern, text)
        return match.group(1).strip() if match else None
    
    def _detect_emotion(self, text: str) -> str:
        emotion_keywords = {
            "happy": ["开心", "高兴", "太棒了", "喜欢", "棒"],
            "sad": ["难过", "伤心", "委屈", "哭了"],
            "angry": ["生气", "讨厌", "过分"],
            "shy": ["害羞", "不好意思", "脸红"],
            "excited": ["兴奋", "激动", "期待", "超棒"],
            "bored": ["无聊", "没意思", "好闲"],
            "cute": ["可爱", "萌", "么么哒"]
        }
        
        for emotion, keywords in emotion_keywords.items():
            if any(kw in text for kw in keywords):
                return emotion
        return "neutral"


class MemoryRetrieval:
    def __init__(self, character: Character):
        self.character = character
    
    def retrieve(self, query: str, memory_type: str = "all") -> List[Dict]:
        results = []
        
        if memory_type in ["all", "short"]:
            short_memories = self.character.get_conversation_context()
            for mem in short_memories:
                if any(keyword in mem.get("content", "") for keyword in self._extract_keywords(query)):
                    results.append({
                        "type": "short",
                        "content": mem.get("content", ""),
                        "timestamp": mem.get("timestamp", "")
                    })
        
        if memory_type in ["all", "long"]:
            long_memories = self.character.get_relevant_memories(query)
            results.extend(long_memories)
        
        return results[:10]
    
    def _extract_keywords(self, text: str) -> List[str]:
        keywords = []
        important_words = ["喜欢", "讨厌", "名字", "生日", "爱好", "工作", "学习", "城市"]
        for word in important_words:
            if word in text:
                keywords.append(word)
        if not keywords:
            keywords = list(set(text.split()))[:5]
        return keywords


class ActionSelector:
    def __init__(self, character: Character):
        self.character = character
        self.skills = character.skills.get("skills", {})
    
    def select_action(self, user_input: str, emotion: str = None, auto_trigger: bool = True) -> Optional[Dict]:
        if not auto_trigger:
            return None
        
        user_input_lower = user_input.lower()
        
        for category in ["emotions", "actions"]:
            if category in self.skills:
                for skill_name, skill_data in self.skills[category].items():
                    keywords = skill_data.get("trigger_keywords", [])
                    if any(kw in user_input_lower for kw in keywords):
                        return {
                            "skill": skill_name,
                            "category": category,
                            "name": skill_data.get("name", ""),
                            "animations": skill_data.get("animations", []),
                            "expression": skill_data.get("expression", "")
                        }
        
        if emotion and "emotions" in self.skills:
            if emotion in self.skills["emotions"]:
                return {
                    "skill": emotion,
                    "category": "emotions",
                    "name": self.skills["emotions"][emotion].get("name", ""),
                    "animations": self.skills["emotions"][emotion].get("animations", []),
                    "expression": self.skills["emotions"][emotion].get("expression", "")
                }
        
        return None
    
    def get_all_skills(self) -> Dict:
        return self.skills
    
    def add_skill(self, category: str, skill_name: str, skill_data: Dict):
        if "skills" not in self.skills:
            self.skills["skills"] = {}
        if category not in self.skills["skills"]:
            self.skills["skills"][category] = {}
        self.skills["skills"][category][skill_name] = skill_data
        self._save_skills()
    
    def remove_skill(self, category: str, skill_name: str):
        if category in self.skills.get("skills", {}) and skill_name in self.skills["skills"][category]:
            del self.skills["skills"][category][skill_name]
            self._save_skills()
    
    def _save_skills(self):
        import os
        skills_path = os.path.join(os.path.dirname(__file__), "..", "roles", self.character.role_name, "skills.json")
        with open(skills_path, "w", encoding="utf-8") as f:
            json.dump({"skills": self.skills}, f, ensure_ascii=False, indent=2)