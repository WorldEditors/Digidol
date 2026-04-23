import streamlit as st
import sys
import os
import json
from pathlib import Path
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.config_manager import ConfigManager


def get_roles_dir():
    base_dir = Path(__file__).parent.parent
    roles_dir = base_dir / "roles"
    return roles_dir


def get_static_dir():
    return Path(__file__).parent.parent / "static"


@st.cache_data(ttl=0)
def load_options():
    options_path = Path(__file__).parent / "options.json"
    if options_path.exists():
        with open(options_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data(ttl=0)
def load_role_profile(role_name: str) -> dict:
    path = get_roles_dir() / role_name / "profile.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_role_profile(role_name: str, profile: dict):
    role_dir = get_roles_dir() / role_name
    role_dir.mkdir(parents=True, exist_ok=True)
    with open(role_dir / "profile.json", "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


@st.cache_data(ttl=0)
def get_all_roles() -> list:
    roles_dir = get_roles_dir()
    if not roles_dir.exists():
        return []
    return [d.name for d in roles_dir.iterdir() if d.is_dir()]


def delete_role(role_name: str):
    import shutil
    role_dir = get_roles_dir() / role_name
    if role_dir.exists():
        shutil.rmtree(role_dir)


def get_role_avatar(role_name: str) -> str:
    avatar_path = get_roles_dir() / role_name / "avatar.png"
    if avatar_path.exists():
        return f"/roles/{role_name}/avatar.png"
    return None


def init_chat_state(role_name: str, config_mgr: ConfigManager):
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if st.session_state.get("chat_role") != role_name:
        st.session_state.messages = []
        st.session_state.chat_role = role_name
    if "config_mgr" not in st.session_state:
        st.session_state.config_mgr = config_mgr
        st.session_state.model_config = config_mgr.get_active_model()


def render_character_display(role_name: str):
    import streamlit.components.v1 as components

    profile = load_role_profile(role_name)
    display_name = profile.get("display_name", role_name)
    personality = profile.get("personality", "")

    avatar_path = get_roles_dir() / role_name / "avatar.png"

    if avatar_path.exists():
        st.image(str(avatar_path), width=200)
    else:
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; padding: 20px;">
            <div style="width: 200px; height: 200px; border-radius: 50%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; font-size: 80px; margin-bottom: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); animation: float 3s ease-in-out infinite;">
                👤
            </div>
            <div style="font-size: 24px; font-weight: bold; color: #333; margin-bottom: 5px;">{display_name}</div>
            <div style="font-size: 14px; color: #666; padding: 5px 15px; background: #f0f0f0; border-radius: 20px;">在线</div>
        </div>
        <style>
        @keyframes float {{
            0%, 100% {{ transform: translateY(0px); }}
            50% {{ transform: translateY(-10px); }}
        }}
        </style>
        """, unsafe_allow_html=True)

    with st.expander("📊 角色属性"):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**性格**: {personality}")
            st.write(f"**年龄**: {profile.get('age', 18)}")
        with col2:
            st.write(f"**性别**: {profile.get('gender', 'unknown')}")
            st.write(f"**说话风格**: {profile.get('speaking_style', '')}")

    st.markdown("### 🎭 3D 角色")

    model_viewer_path = Path(__file__).parent.parent / "static" / "model_viewer.html"
    if model_viewer_path.exists():
        with open(model_viewer_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        components.html(html_content, height=500, scrolling=False)


def render_chat_message(role: str, content: str):
    if role == "user":
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
            <div style="background: #4CAF50; color: white; padding: 12px 18px; border-radius: 18px 18px 4px 18px; max-width: 70%;">
                {content}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-start; margin-bottom: 10px;">
            <div style="background: #2196F3; color: white; padding: 12px 18px; border-radius: 18px 18px 18px 4px; max-width: 70%;">
                {content}
            </div>
        </div>
        """, unsafe_allow_html=True)


def call_llm(messages: list, config: dict, system_prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["api_base"]
    )
    all_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model=config["model_name"],
        messages=all_messages,
        temperature=0.8,
        max_tokens=600,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def parse_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except:
        return {"text": raw, "emotion": "neutral", "action": None, "memory_to_save": None}


def get_system_prompt(role_name: str) -> str:
    profile = load_role_profile(role_name)
    name = profile.get("display_name", role_name)
    personality = profile.get("personality", "")
    gender = profile.get("gender", "未知")
    age = profile.get("age", 18)
    education = profile.get("education", "")
    speaking_style = profile.get("speaking_style", "")
    likes = profile.get("likes", {})
    dislikes = profile.get("dislikes", [])
    habits = profile.get("habits", [])

    return f"""你是{name}，一个虚拟角色。
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


def get_emotion_emoji(emotion: str) -> str:
    emoji_map = {
        "happy": "😊", "sad": "😢", "angry": "😠", "shy": "😳",
        "excited": "🤩", "bored": "😴", "cute": "🥰", "thinking": "🤔",
        "sleepy": "😪", "neutral": "😐"
    }
    return emoji_map.get(emotion, "😐")


def main():
    st.title("⚙️ Digidol 智能角色系统")

    config_mgr = ConfigManager()
    options = load_options()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💬 聊天",
        "🧠 角色管理",
        "🤖 模型配置",
        "🔑 API Key 管理",
        "🔌 测试连接"
    ])

    with tab1:
        roles = get_all_roles()
        if not roles:
            st.warning("⚠️ 没有可用的角色，请在【角色管理】中创建角色")
            st.stop()

        selected_role = st.selectbox("选择角色", options=roles, key="chat_role_select")

        col_left, col_right = st.columns([1, 3])

        with col_left:
            render_character_display(selected_role)

            if st.button("🎤 开始聊天", type="primary", use_container_width=True):
                st.session_state.start_chat = True

        with col_right:
            if st.session_state.get("start_chat"):
                init_chat_state(selected_role, config_mgr)

                model_config = st.session_state.get("model_config")
                if not model_config or not model_config.get("api_key"):
                    st.error("❌ 请先在【API Key 管理】中配置 API Key")
                    st.stop()

                profile = load_role_profile(selected_role)
                st.subheader(f"与 {profile.get('display_name', selected_role)} 聊天")

                chat_container = st.container()
                with chat_container:
                    for msg in st.session_state.messages:
                        render_chat_message(msg["role"], msg["content"])

                with st.form("chat_form", clear_on_submit=True):
                    user_input = st.text_input("输入消息...", placeholder="输入你的问题...", label_visibility="collapsed")
                    submitted = st.form_submit_button("发送 ✈️", use_container_width=True)

                    if submitted and user_input:
                        st.session_state.messages.append({"role": "user", "content": user_input})
                        render_chat_message("user", user_input)

                        with st.spinner("思考中..."):
                            try:
                                system_prompt = get_system_prompt(selected_role)
                                messages_for_api = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                                raw = call_llm(messages_for_api, model_config, system_prompt)
                                parsed = parse_response(raw)
                                response_text = parsed.get("text", "抱歉，我没有理解你的意思...")
                                emotion = parsed.get("emotion", "neutral")
                                action = parsed.get("action")

                                st.session_state.messages.append({"role": "assistant", "content": response_text})
                                render_chat_message("assistant", response_text)

                                emotion_emoji = get_emotion_emoji(emotion)
                                st.markdown(f"**情绪**: {emotion_emoji} {emotion}")
                                if action and action != "null":
                                    st.markdown(f"**动作**: {action}")

                                st.markdown("---")
                                st.markdown("💡 **提示**: 如果角色有动作，可以在右侧3D角色上看到动画效果")

                            except Exception as e:
                                st.error(f"❌ 发生错误: {str(e)}")

                col_clear, col_back = st.columns(2)
                with col_clear:
                    if st.button("🗑️ 清除对话", use_container_width=True):
                        st.session_state.messages = []
                        st.rerun()
                with col_back:
                    if st.button("⬅️ 返回角色选择", use_container_width=True):
                        st.session_state.start_chat = False
                        st.rerun()
            else:
                st.info("👈 选择角色后点击【开始聊天】")

    with tab2:
        st.header("角色管理")

        roles_dir = get_roles_dir()
        st.caption(f"📁 角色目录: {roles_dir}")
        st.caption(f"📁 目录是否存在: {roles_dir.exists()}")

        roles = get_all_roles()
        st.info(f"共 {len(roles)} 个角色: {', '.join(roles) if roles else '无'}")

        if not roles:
            st.warning("⚠️ 没有找到角色！请检查角色目录是否存在并包含 profile.json 文件。")
            st.stop()

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("角色列表")
            selected_role = st.selectbox("选择角色", options=roles, key="role_select_tab2")
            st.caption(f"当前选中: {selected_role}")
            action = st.radio("操作", ["查看/编辑", "新建", "删除"])

        with col2:
            if action == "查看/编辑" and selected_role:
                profile = load_role_profile(selected_role)

                st.subheader(f"编辑角色: {selected_role}")
                col_a, col_b = st.columns(2)
                with col_a:
                    profile["display_name"] = st.text_input("显示名称", value=profile.get("display_name", ""))
                    profile["personality"] = st.text_area("性格", value=profile.get("personality", ""), height=100)
                    gender_idx = 2
                    if profile.get("gender", "unknown") in options["gender_options"]:
                        gender_idx = options["gender_options"].index(profile["gender"])
                    profile["gender"] = st.selectbox("性别", options["gender_options"], index=gender_idx)
                    profile["age"] = st.number_input("年龄", min_value=0, max_value=150, value=profile.get("age", 18))
                with col_b:
                    profile["speaking_style"] = st.text_area("说话风格", value=profile.get("speaking_style", ""), height=100)
                    profile["education"] = st.text_input("教育背景", value=profile.get("education", ""))
                    profile["hometown"] = st.text_input("家乡", value=profile.get("hometown", ""))

                st.subheader("爱好")
                likes = profile.get("likes", {})
                col_c, col_d = st.columns(2)
                with col_c:
                    profile["likes"] = profile.get("likes", {})
                    profile["likes"]["food"] = st.multiselect("喜欢的食物", options["food_options"],
                                                               default=[f for f in likes.get("food", []) if f in options["food_options"]])
                    profile["likes"]["games"] = st.multiselect("喜欢的游戏", options["game_options"],
                                                               default=[g for g in likes.get("games", []) if g in options["game_options"]])
                with col_d:
                    profile["likes"]["music"] = st.multiselect("喜欢的音乐", options["music_options"],
                                                               default=[m for m in likes.get("music", []) if m in options["music_options"]])
                    profile["likes"]["movies"] = st.multiselect("喜欢的电影", options["movie_options"],
                                                               default=[m for m in likes.get("movies", []) if m in options["movie_options"]])

                profile["dislikes"] = st.multiselect("讨厌的事物", options["dislike_options"],
                                                     default=[d for d in profile.get("dislikes", []) if d in options["dislike_options"]])
                profile["habits"] = st.text_area("习惯 (每行一个)", value="\n".join(profile.get("habits", [])), height=80)

                st.subheader("TTS 设置")
                custom_settings = profile.get("custom_settings", {})
                tts_col1, tts_col2, tts_col3 = st.columns(3)
                with tts_col1:
                    voice_options = [v["value"] for v in options["tts_voice_options"]]
                    voice_labels = [v["name"] for v in options["tts_voice_options"]]
                    current_voice = custom_settings.get("tts_voice", "zh-CN-XiaoxiaoNeural")
                    voice_index = voice_options.index(current_voice) if current_voice in voice_options else 0
                    profile.setdefault("custom_settings", {})["tts_voice"] = st.selectbox("语音", voice_labels, index=voice_index)
                with tts_col2:
                    rate = custom_settings.get("tts_rate", "+0%")
                    rate_index = options["tts_rate_options"].index(rate) if rate in options["tts_rate_options"] else 3
                    profile["custom_settings"]["tts_rate"] = st.selectbox("语速", options["tts_rate_options"], index=rate_index)
                with tts_col3:
                    pitch = custom_settings.get("tts_pitch", "+0Hz")
                    pitch_index = options["tts_pitch_options"].index(pitch) if pitch in options["tts_pitch_options"] else 3
                    profile["custom_settings"]["tts_pitch"] = st.selectbox("音调", options["tts_pitch_options"], index=pitch_index)

                if st.button("💾 保存角色"):
                    profile["name"] = selected_role
                    if isinstance(profile.get("habits"), str):
                        profile["habits"] = [h.strip() for h in profile["habits"].split("\n") if h.strip()]
                    save_role_profile(selected_role, profile)
                    st.success(f"✅ 角色 {selected_role} 已保存")

            elif action == "新建":
                st.subheader("创建新角色")
                new_role_name = st.text_input("角色ID (英文)", placeholder="my_character").strip()
                new_display_name = st.text_input("显示名称", placeholder="小明")
                new_personality = st.text_area("性格", placeholder="活泼开朗...")

                if st.button("➕ 创建角色"):
                    if new_role_name and new_display_name:
                        if new_role_name in roles:
                            st.error("❌ 角色ID已存在")
                        else:
                            new_profile = {
                                "name": new_role_name,
                                "display_name": new_display_name,
                                "personality": new_personality,
                                "gender": "unknown",
                                "age": 18,
                                "speaking_style": "",
                                "education": "",
                                "hometown": "",
                                "likes": {"food": [], "games": [], "music": [], "movies": []},
                                "dislikes": [],
                                "habits": [],
                                "custom_settings": {
                                    "tts_voice": "zh-CN-XiaoxiaoNeural",
                                    "tts_rate": "+0%",
                                    "tts_pitch": "+0Hz"
                                }
                            }
                            save_role_profile(new_role_name, new_profile)
                            st.success(f"✅ 角色 {new_role_name} 创建成功")
                            st.rerun()
                    else:
                        st.warning("⚠️ 请填写角色ID和显示名称")

            elif action == "删除" and selected_role:
                st.subheader(f"删除角色: {selected_role}")
                st.warning(f"⚠️ 确定要删除角色 **{selected_role}** 吗？此操作不可恢复！")
                if st.button("🗑️ 确认删除", type="primary"):
                    delete_role(selected_role)
                    st.success(f"✅ 角色 {selected_role} 已删除")
                    st.rerun()

    with tab3:
        st.header("模型配置")

        config_path = Path.home() / ".digidol" / "config.json"
        st.caption(f"📁 配置文件: {config_path}")
        st.caption(f"📁 文件是否存在: {config_path.exists()}")

        models = config_mgr.get_all_models()
        st.info(f"共 {len(models)} 个模型配置")

        if not models:
            st.warning("⚠️ 没有找到模型配置！请检查配置文件。")
            st.stop()

        st.markdown("---")

        for model_id, model_info in models.items():
            with st.expander(f"🔹 {model_info['name']} ({model_id})"):
                col1, col2 = st.columns(2)
                with col1:
                    enabled = st.checkbox("启用", value=model_info.get("enabled", True), key=f"enabled_{model_id}")
                    model_name = st.text_input("模型名", value=model_info.get("model_name", ""), key=f"name_{model_id}")
                with col2:
                    api_base = st.text_input("API Base URL", value=model_info.get("api_base", ""), key=f"base_{model_id}")

                if st.button(f"💾 保存 {model_info['name']}", key=f"save_{model_id}"):
                    config_mgr.update_model_config(model_id, model_name=model_name, api_base=api_base, enabled=enabled)
                    st.success(f"✅ {model_info['name']} 配置已保存")
                    st.rerun()

        st.markdown("---")
        st.subheader("切换默认模型")
        enabled_models = config_mgr.get_enabled_models()
        model_options = {k: v["name"] for k, v in enabled_models.items()}
        current_active = config_mgr.config.get("active_model", "kimi")
        active_index = list(model_options.keys()).index(current_active) if current_active in model_options else 0
        selected = st.selectbox("选择默认模型", options=list(model_options.keys()),
                                format_func=lambda x: model_options[x], index=active_index)
        if st.button("🔄 设置为默认模型"):
            config_mgr.set_active_model(selected)
            st.success(f"✅ 已设置 {enabled_models[selected]['name']} 为默认模型")
            st.rerun()

    with tab4:
        st.header("API Key 管理")
        active = config_mgr.get_active_model()
        if active:
            st.info(f"📌 当前使用: **{active['name']}** | 模型: {active.get('model_name', 'N/A')}")
        else:
            st.warning("⚠️ 当前没有配置默认模型")
        st.markdown("---")

        models = config_mgr.get_all_models()
        selected = st.selectbox("选择要配置的模型", options=list(models.keys()),
                                format_func=lambda x: f"{models[x]['name']} ({x})")

        st.markdown(f"### 配置 {models[selected]['name']}")
        current_key = models[selected].get("api_key", "")
        display_key = "****" + current_key[-4:] if len(current_key) > 4 else ("未设置" if not current_key else current_key)

        st.text(f"当前 API Key: {display_key}")
        api_key = st.text_input("输入新的 API Key", type="password", placeholder="sk-xxx...", key="api_key_input")

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("💾 保存 API Key"):
                if api_key:
                    config_mgr.update_model_config(selected, api_key=api_key)
                    st.success(f"✅ {models[selected]['name']} 的 API Key 已保存")
                    st.rerun()
                else:
                    st.warning("⚠️ 请输入 API Key")

    with tab5:
        st.header("测试���接")
        st.markdown("---")

        test_model = st.selectbox("选择要测试的模型",
                                  options=list(config_mgr.get_all_models().keys()),
                                  format_func=lambda x: config_mgr.get_all_models()[x]["name"],
                                  key="test_model_select")

        test_config = config_mgr.get_all_models()[test_model]

        if st.button("🔌 测试连接"):
            if not test_config.get("api_key"):
                st.error("❌ 请先配置 API Key")
            else:
                with st.spinner("测试中..."):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=test_config["api_key"], base_url=test_config["api_base"])
                        response = client.chat.completions.create(
                            model=test_config["model_name"],
                            messages=[{"role": "user", "content": "你好"}],
                            max_tokens=50
                        )
                        st.success(f"✅ {test_config['name']} 连接成功！")
                        st.code(f"响应: {response.choices[0].message.content}")
                    except Exception as e:
                        st.error(f"❌ 连接失败: {str(e)}")


if __name__ == "__main__":
    main()