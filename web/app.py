import os
import re
import json
import uuid
import asyncio
import tempfile

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename

# 支持从 .env 文件加载环境变量（可选）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'digidol-dev-secret')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

active_agents: dict = {}
avatar_sessions: dict = {}

# 从环境变量预加载 API keys
api_keys: dict = {
    k: v for k, v in {
        "openai": os.environ.get("OPENAI_API_KEY", ""),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
        "google": os.environ.get("GOOGLE_API_KEY", ""),
    }.items() if v
}

_ROLE_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]{1,32}$')


def validate_role_name(name: str) -> bool:
    return bool(name and _ROLE_NAME_RE.match(name))


def get_roles():
    roles_dir = os.path.join(os.path.dirname(__file__), "..", "roles")
    if not os.path.exists(roles_dir):
        return []
    return [d for d in os.listdir(roles_dir) if os.path.isdir(os.path.join(roles_dir, d))]


def get_role_profile(role_name: str):
    if not validate_role_name(role_name):
        return {}
    profile_path = os.path.join(os.path.dirname(__file__), "..", "roles", role_name, "profile.json")
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route('/')
def index():
    roles = get_roles()
    return render_template('index.html', roles=roles)


@app.route('/api/roles')
def list_roles():
    roles = get_roles()
    role_list = []
    for role in roles:
        profile = get_role_profile(role)
        role_list.append({
            "name": role,
            "display_name": profile.get("display_name", role),
            "gender": profile.get("gender", "未知"),
            "age": profile.get("age", 0),
            "personality": profile.get("personality", ""),
            "active": role in active_agents,
        })
    return jsonify(role_list)


@app.route('/api/keys', methods=['GET', 'POST'])
def manage_keys():
    global api_keys
    if request.method == 'POST':
        data = request.json or {}
        provider = data.get('provider', '')
        key = data.get('key', '')
        if provider and key:
            api_keys[provider] = key
        return jsonify({"status": "success", "providers": list(api_keys.keys())})
    # 返回已配置的 provider 列表（不返回 key 值）
    return jsonify({"providers": list(api_keys.keys())})


@app.route('/api/agent/start', methods=['POST'])
def start_agent():
    data = request.json or {}
    role_name = data.get('role', '')
    model = data.get('model', 'openai')
    provider = data.get('provider', 'openai')

    if not validate_role_name(role_name):
        return jsonify({"error": "无效的角色名称"}), 400

    if not api_keys.get(provider):
        return jsonify({"error": f"请先配置 {provider} 的 API Key"}), 400

    try:
        from agents.character import Character
        from agents.agent import VLMAgent

        character = Character(role_name)
        agent = VLMAgent(character, api_key=api_keys[provider], model=model)

        session_id = str(uuid.uuid4())
        active_agents[session_id] = {
            "character": character,
            "agent": agent,
            "role": role_name,
        }

        return jsonify({"session_id": session_id, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/agent/<session_id>/chat', methods=['POST'])
def chat(session_id):
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404

    data = request.json or {}
    user_input = data.get('message', '')

    agent_data = active_agents[session_id]
    character = agent_data["character"]
    agent = agent_data["agent"]

    response = agent.generate_response(user_input)

    character.add_conversation("user", user_input)
    character.add_conversation("assistant", response.get("text", ""))

    return jsonify({
        "response": response.get("text", ""),
        "action": response.get("action"),
        "emotion": response.get("emotion"),
    })


@app.route('/api/agent/<session_id>/memory', methods=['GET', 'POST', 'DELETE'])
def manage_memory(session_id):
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404

    character = active_agents[session_id]["character"]

    if request.method == 'GET':
        return jsonify({
            "short_term": character.short_term_memory,
            "long_term": character.long_term_memory,
        })

    if request.method == 'POST':
        data = request.json or {}
        memory_type = data.get('type', 'long')
        content = data.get('content', '')
        emotion = data.get('emotion', '中性')
        if memory_type == 'long':
            character.add_long_term_memory(content, emotion)
        else:
            character.add_conversation("system", content)
        return jsonify({"status": "success"})

    if request.method == 'DELETE':
        memory_type = request.args.get('type', 'all')
        if memory_type == 'short':
            character.clear_short_term_memory()
        elif memory_type == 'long':
            character.long_term_memory = {"important_memories": [], "user_info": {}, "preferences": {}}
            character.save_long_term_memory()
        return jsonify({"status": "success"})


@app.route('/api/agent/<session_id>/skills', methods=['GET'])
def get_skills(session_id):
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404

    from agents.agent import ActionSelector
    character = active_agents[session_id]["character"]
    selector = ActionSelector(character)
    return jsonify(selector.get_all_skills())


@app.route('/api/agent/<session_id>/action', methods=['POST'])
def trigger_action(session_id):
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404

    from agents.agent import ActionSelector
    character = active_agents[session_id]["character"]
    selector = ActionSelector(character)

    data = request.json or {}
    action = selector.select_action(
        user_input=data.get('input', ''),
        emotion=data.get('emotion'),
        auto_trigger=False,
        skill_name=data.get('skill_name'),
        category=data.get('category'),
    )

    return jsonify(action or {"message": "没有匹配的动作"})


@app.route('/api/agent/<session_id>/stop', methods=['POST'])
def stop_agent(session_id):
    if session_id in active_agents:
        del active_agents[session_id]
    return jsonify({"status": "success"})


@app.route('/api/roles', methods=['POST'])
def create_role():
    data = request.json or {}
    role_name = data.get('name', '')

    if not validate_role_name(role_name):
        return jsonify({"error": "角色名称只能包含字母、数字、下划线和连字符，长度 1-32"}), 400

    profile = data.get('profile', {})

    role_dir = os.path.join(os.path.dirname(__file__), "..", "roles", role_name)
    os.makedirs(os.path.join(role_dir, "memory"), exist_ok=True)

    with open(os.path.join(role_dir, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    import shutil
    default_memory_dir = os.path.join(os.path.dirname(__file__), "..", "roles", "yui", "memory")
    for file in os.listdir(default_memory_dir):
        shutil.copy(
            os.path.join(default_memory_dir, file),
            os.path.join(role_dir, "memory", file),
        )

    shutil.copy(
        os.path.join(os.path.dirname(__file__), "..", "roles", "yui", "skills.json"),
        os.path.join(role_dir, "skills.json"),
    )

    return jsonify({"status": "success", "role": role_name})


@app.route('/api/roles/<role_name>', methods=['DELETE'])
def delete_role(role_name):
    if not validate_role_name(role_name):
        return jsonify({"error": "无效的角色名称"}), 400
    if role_name in ("yui", "kazuha"):
        return jsonify({"error": "不能删除默认角色"}), 400

    role_dir = os.path.join(os.path.dirname(__file__), "..", "roles", role_name)
    if os.path.exists(role_dir):
        import shutil
        shutil.rmtree(role_dir)
        return jsonify({"status": "success"})
    return jsonify({"error": "角色不存在"}), 404


@app.route('/api/tts/voices')
def list_voices():
    from tts.tts_engine import TTSManager
    manager = TTSManager()
    return jsonify(manager.get_available_voices())


@app.route('/api/tts/synthesize', methods=['POST'])
async def synthesize_speech_standalone():
    """独立 TTS 合成接口（不依赖会话）。"""
    data = request.json or {}
    text = data.get('text', '')
    voice = data.get('voice', 'zh-CN-XiaoxiaoNeural')
    rate = data.get('rate', '+0%')
    pitch = data.get('pitch', '+0Hz')

    from tts.tts_engine import TTSManager
    tts_manager = TTSManager()
    tts_manager.set_active_engine("edge")
    tts_manager.current_engine.set_voice_config({"voice": voice, "rate": rate, "pitch": pitch})

    output_filename = f"tts_{uuid.uuid4()}.mp3"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    audio_path = await tts_manager.speak(text, output_path=output_path)

    return jsonify({"audio_url": f"/audio/{os.path.basename(audio_path)}", "filename": output_filename})


@app.route('/api/agent/<session_id>/tts', methods=['POST'])
async def synthesize_speech_session(session_id):
    """会话 TTS 合成接口（使用角色声音配置）。"""
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404

    data = request.json or {}
    text = data.get('text', '')

    character = active_agents[session_id]["character"]

    from tts.tts_engine import TTSManager
    tts_manager = TTSManager()
    tts_manager.set_active_engine("edge")

    tts_config = character.get_tts_config()
    tts_manager.current_engine.set_voice_config(tts_config)

    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"tts_{session_id}_{uuid.uuid4()}.mp3")
    audio_path = await tts_manager.speak(text, output_path=output_path)

    return jsonify({"audio_url": f"/audio/{os.path.basename(audio_path)}"})


@app.route('/audio/<filename>')
def serve_audio(filename):
    safe_name = secure_filename(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_name)


@app.route('/api/agent/<session_id>/asr', methods=['POST'])
def recognize_speech(session_id):
    if 'audio' not in request.files:
        return jsonify({"error": "没有音频文件"}), 400

    audio_file = request.files['audio']
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"asr_{uuid.uuid4()}.wav")
    audio_file.save(temp_path)

    try:
        from asr.asr_engine import ASRManager
        asr_manager = ASRManager()
        asr_manager.set_active_engine("google")
        text = asr_manager.recognize_from_file(temp_path)
        os.remove(temp_path)
        return jsonify({"text": text or ""})
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": str(e)}), 500


@app.route('/api/agent/<session_id>/vision', methods=['POST'])
def process_vision(session_id):
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404

    if 'image' not in request.files:
        return jsonify({"error": "没有图片文件"}), 400

    image_file = request.files['image']
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"vision_{uuid.uuid4()}.jpg")
    image_file.save(temp_path)

    try:
        import base64
        with open(temp_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        agent_data = active_agents[session_id]
        agent = agent_data["agent"]

        if hasattr(agent, 'client') and hasattr(agent.client, 'chat'):
            response = agent.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "描述这张图片的内容"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                    ],
                }],
                max_tokens=300,
            )
            description = response.choices[0].message.content
        else:
            description = "暂不支持视觉识别"

        os.remove(temp_path)
        return jsonify({"description": description})
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------ #
# Avatar CRUD                                                          #
# ------------------------------------------------------------------ #

@app.route('/api/avatars')
def list_avatars():
    from avatar.avatar_manager import AvatarManager
    return jsonify(AvatarManager().get_avatar_list())


@app.route('/api/avatars/<avatar_name>')
def get_avatar(avatar_name):
    from avatar.avatar_manager import AvatarManager
    config = AvatarManager().get_avatar_config(avatar_name)
    if config:
        return jsonify(config)
    return jsonify({"error": "Avatar不存在"}), 404


@app.route('/api/avatars', methods=['POST'])
def create_avatar():
    data = request.json or {}
    from avatar.avatar_manager import AvatarManager
    if AvatarManager().add_avatar(data.get('name'), data.get('config', {})):
        return jsonify({"status": "success"})
    return jsonify({"error": "创建失败"}), 500


@app.route('/api/avatars/<avatar_name>', methods=['PUT'])
def update_avatar(avatar_name):
    data = request.json or {}
    from avatar.avatar_manager import AvatarManager
    if AvatarManager().update_avatar_config(avatar_name, data.get('config', {})):
        return jsonify({"status": "success"})
    return jsonify({"error": "更新失败"}), 404


@app.route('/api/avatars/<avatar_name>', methods=['DELETE'])
def delete_avatar(avatar_name):
    from avatar.avatar_manager import AvatarManager
    if AvatarManager().delete_avatar(avatar_name):
        return jsonify({"status": "success"})
    return jsonify({"error": "删除失败"}), 404


# ------------------------------------------------------------------ #
# Role file management                                                 #
# ------------------------------------------------------------------ #

@app.route('/api/roles/<role_name>/profile', methods=['GET', 'PUT'])
def manage_role_profile(role_name):
    if not validate_role_name(role_name):
        return jsonify({"error": "无效的角色名称"}), 400

    profile_path = os.path.join(os.path.dirname(__file__), "..", "roles", role_name, "profile.json")

    if request.method == 'GET':
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify({"error": "角色不存在"}), 404

    data = request.json or {}
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "success"})


@app.route('/api/roles/<role_name>/skills', methods=['GET', 'PUT'])
def manage_role_skills(role_name):
    if not validate_role_name(role_name):
        return jsonify({"error": "无效的角色名称"}), 400

    skills_path = os.path.join(os.path.dirname(__file__), "..", "roles", role_name, "skills.json")

    if request.method == 'GET':
        if os.path.exists(skills_path):
            with open(skills_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify({"error": "技能文件不存在"}), 404

    data = request.json or {}
    with open(skills_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "success"})


@app.route('/api/roles/<role_name>/avatar', methods=['GET', 'PUT'])
def manage_role_avatar(role_name):
    if not validate_role_name(role_name):
        return jsonify({"error": "无效的角色名称"}), 400

    avatar_path = os.path.join(os.path.dirname(__file__), "..", "roles", role_name, "avatar.json")

    if request.method == 'GET':
        if os.path.exists(avatar_path):
            with open(avatar_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify({"error": "Avatar配置不存在"}), 404

    data = request.json or {}
    with open(avatar_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "success"})


# ------------------------------------------------------------------ #
# Socket.IO                                                            #
# ------------------------------------------------------------------ #

@socketio.on('connect')
def handle_connect():
    pass


@socketio.on('disconnect')
def handle_disconnect():
    pass


@socketio.on('join')
def handle_join(data):
    session_id = data.get('session_id')
    if session_id in active_agents:
        join_room(session_id)


@socketio.on('chat_message')
def handle_chat_message(data):
    session_id = data.get('session_id')
    message = data.get('message')

    if session_id not in active_agents:
        emit('response', {"error": "会话不存在"}, room=session_id)
        return

    agent_data = active_agents[session_id]
    character = agent_data["character"]
    agent = agent_data["agent"]

    response = agent.generate_response(message)
    character.add_conversation("user", message)
    character.add_conversation("assistant", response.get("text", ""))

    emit('response', {
        "text": response.get("text", ""),
        "action": response.get("action"),
        "emotion": response.get("emotion"),
    }, room=session_id)


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
