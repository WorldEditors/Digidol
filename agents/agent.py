import os
import json
from typing import Dict, Any, List, Optional
from .character import Character

VALID_EMOTIONS = {"happy", "sad", "angry", "shy", "excited", "bored", "cute", "thinking", "sleepy", "neutral"}
VALID_ACTIONS = {"dance", "wave", "bow", "pat", "hug", "cheer"}


def _parse_structured_response(raw: str) -> Dict[str, Any]:
    """从 LLM 响应中解析 JSON，容错处理 markdown 代码块包裹。"""
    text = raw.strip()
    # 去除 ```json ... ``` 包裹
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 最后降级：把原始文本当做 text 字段
        return {"text": raw, "emotion": "neutral", "action": None, "memory_to_save": None}


class VLMAgent:
    def __init__(self, character: Character, api_key: str = None, model: str = "openai"):
        self.character = character
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None
        self._init_client()

        # 让 MemoryStore 也能使用 API key 做 embedding
        if self.api_key and model == "openai":
            character.set_memory_store_api_key(self.api_key)

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
            memory_context = "\n".join(
                [f"- {m['content']} ({m.get('timestamp', '')})" for m in relevant_memories]
            )
            system_prompt += f"\n\n相关记忆：\n{memory_context}"

        if context and context.get("emotion"):
            system_prompt += f"\n\n当前情绪状态：{context['emotion']}"

        try:
            raw = self._call_llm(system_prompt, conversation)
            parsed = _parse_structured_response(raw)

            text = parsed.get("text", "")
            emotion = parsed.get("emotion", "neutral")
            action = parsed.get("action")
            memory_to_save = parsed.get("memory_to_save")

            # 规范化：不在白名单内的值重置为默认
            if emotion not in VALID_EMOTIONS:
                emotion = "neutral"
            if action not in VALID_ACTIONS:
                action = None

            # 自动存入长期记忆
            if memory_to_save and isinstance(memory_to_save, str) and memory_to_save.strip():
                self.character.add_long_term_memory(memory_to_save.strip(), emotion)

            return {"text": text, "action": action, "emotion": emotion}

        except Exception as e:
            return {
                "text": "抱歉，我现在有点累，让我休息一下...",
                "action": None,
                "emotion": "tired",
                "error": str(e),
            }

    def _call_llm(self, system_prompt: str, conversation: List[Dict]) -> str:
        if self.model == "openai":
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": system_prompt}] + conversation,
                temperature=0.8,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content

        elif self.model == "anthropic":
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=600,
                system=system_prompt,
                messages=conversation,
            )
            return response.content[0].text

        elif self.model == "google":
            model = self.client.GenerativeModel("gemini-1.5-flash")
            full_prompt = (
                f"{system_prompt}\n\n"
                f"对话历史：{json.dumps(conversation, ensure_ascii=False)}\n\n"
                f"用户：{conversation[-1]['content']}"
            )
            response = model.generate_content(full_prompt)
            return response.text

        return json.dumps({"text": "暂不支持该模型", "emotion": "neutral", "action": None, "memory_to_save": None})


class MemoryRetrieval:
    def __init__(self, character: Character):
        self.character = character

    def retrieve(self, query: str, memory_type: str = "all") -> List[Dict]:
        results = []

        if memory_type in ["all", "short"]:
            for mem in self.character.get_conversation_context():
                if any(kw in mem.get("content", "") for kw in self._extract_keywords(query)):
                    results.append({
                        "type": "short",
                        "content": mem.get("content", ""),
                        "timestamp": mem.get("timestamp", ""),
                    })

        if memory_type in ["all", "long"]:
            results.extend(self.character.get_relevant_memories(query))

        return results[:10]

    def _extract_keywords(self, text: str) -> List[str]:
        important_words = ["喜欢", "讨厌", "名字", "生日", "爱好", "工作", "学习", "城市"]
        keywords = [w for w in important_words if w in text]
        if not keywords:
            keywords = list(set(text.split()))[:5]
        return keywords


class ActionSelector:
    def __init__(self, character: Character):
        self.character = character
        # skills.json 顶层有 "skills" key，其下才是 emotions/actions/smart_home
        self.skills = character.skills.get("skills", {})

    def select_action(
        self,
        user_input: str,
        emotion: str = None,
        auto_trigger: bool = True,
        skill_name: str = None,
        category: str = None,
    ) -> Optional[Dict]:
        # 手动触发：按 skill_name + category 精确查找
        if not auto_trigger:
            if skill_name and category and category in self.skills:
                skill_data = self.skills[category].get(skill_name)
                if skill_data:
                    return {
                        "skill": skill_name,
                        "category": category,
                        "name": skill_data.get("name", ""),
                        "animations": skill_data.get("animations", []),
                        "expression": skill_data.get("expression", ""),
                    }
            return None

        # 自动触发：关键词匹配
        user_input_lower = user_input.lower()
        for cat in ["emotions", "actions"]:
            if cat in self.skills:
                for sname, skill_data in self.skills[cat].items():
                    if any(kw in user_input_lower for kw in skill_data.get("trigger_keywords", [])):
                        return {
                            "skill": sname,
                            "category": cat,
                            "name": skill_data.get("name", ""),
                            "animations": skill_data.get("animations", []),
                            "expression": skill_data.get("expression", ""),
                        }

        # 情绪回退
        if emotion and "emotions" in self.skills and emotion in self.skills["emotions"]:
            skill_data = self.skills["emotions"][emotion]
            return {
                "skill": emotion,
                "category": "emotions",
                "name": skill_data.get("name", ""),
                "animations": skill_data.get("animations", []),
                "expression": skill_data.get("expression", ""),
            }

        return None

    def get_all_skills(self) -> Dict:
        return self.skills

    def add_skill(self, category: str, skill_name: str, skill_data: Dict):
        if category not in self.skills:
            self.skills[category] = {}
        self.skills[category][skill_name] = skill_data
        self._save_skills()

    def remove_skill(self, category: str, skill_name: str):
        if category in self.skills and skill_name in self.skills[category]:
            del self.skills[category][skill_name]
            self._save_skills()

    def _save_skills(self):
        skills_path = os.path.join(
            os.path.dirname(__file__), "..", "roles", self.character.role_name, "skills.json"
        )
        with open(skills_path, "w", encoding="utf-8") as f:
            json.dump({"skills": self.skills}, f, ensure_ascii=False, indent=2)
