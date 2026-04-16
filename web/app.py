from flask import Flask, render_template, request, jsonify, session, send_file, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename
import json
import os
import uuid
import asyncio
import tempfile

app = Flask(__name__)
app.config['SECRET_KEY'] = 'digidol-secret-key'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

active_agents = {}
api_keys = {}
avatar_sessions = {}

def get_roles():
    roles_dir = os.path.join(os.path.dirname(__file__), "..", "roles")
    if not os.path.exists(roles_dir):
        return []
    return [d for d in os.listdir(roles_dir) if os.path.isdir(os.path.join(roles_dir, d))]

def get_role_profile(role_name):
    profile_path = os.path.join(os.path.dirname(__file__), "..", "roles", role_name, "profile.json")
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

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
            "active": role in active_agents
        })
    return jsonify(role_list)

@app.route('/api/keys', methods=['GET', 'POST'])
def manage_keys():
    global api_keys
    if request.method == 'POST':
        data = request.json
        api_keys[data.get('provider')] = data.get('key')
        return jsonify({"status": "success", "keys": list(api_keys.keys())})
    return jsonify({"providers": list(api_keys.keys())})

@app.route('/api/agent/start', methods=['POST'])
def start_agent():
    data = request.json
    role_name = data.get('role')
    model = data.get('model', 'openai')
    provider = data.get('provider', 'openai')
    
    if role_name not in api_keys:
        return jsonify({"error": "请先设置API Key"}), 400
    
    try:
        from agents.character import Character
        from agents.agent import VLMAgent
        
        character = Character(role_name)
        agent = VLMAgent(character, api_key=api_keys[provider], model=model)
        
        session_id = str(uuid.uuid4())
        active_agents[session_id] = {
            "character": character,
            "agent": agent,
            "role": role_name
        }
        
        return jsonify({"session_id": session_id, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/agent/<session_id>/chat', methods=['POST'])
def chat(session_id):
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404
    
    data = request.json
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
        "emotion": response.get("emotion")
    })

@app.route('/api/agent/<session_id>/memory', methods=['GET', 'POST', 'DELETE'])
def manage_memory(session_id):
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404
    
    character = active_agents[session_id]["character"]
    
    if request.method == 'GET':
        return jsonify({
            "short_term": character.short_term_memory,
            "long_term": character.long_term_memory
        })
    
    if request.method == 'POST':
        data = request.json
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
    
    data = request.json
    action = selector.select_action(
        data.get('input', ''),
        data.get('emotion'),
        auto_trigger=False
    )
    
    return jsonify(action or {"message": "没有匹配的动作"})

@app.route('/api/agent/<session_id>/stop', methods=['POST'])
def stop_agent(session_id):
    if session_id in active_agents:
        del active_agents[session_id]
    return jsonify({"status": "success"})

@app.route('/api/roles', methods=['POST'])
def create_role():
    data = request.json
    role_name = data.get('name')
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
            os.path.join(role_dir, "memory", file)
        )
    
    shutil.copy(
        os.path.join(os.path.dirname(__file__), "..", "roles", "yui", "skills.json"),
        os.path.join(role_dir, "skills.json")
    )
    
    return jsonify({"status": "success", "role": role_name})

@app.route('/api/roles/<role_name>', methods=['DELETE'])
def delete_role(role_name):
    if role_name in ["yui", "kazuha"]:
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
async def synthesize_speech():
    data = request.json
    text = data.get('text', '')
    session_id = data.get('session_id')
    voice = data.get('voice', 'zh-CN-XiaoxiaoNeural')
    rate = data.get('rate', '+0%')
    pitch = data.get('pitch', '+0Hz')
    
    from tts.tts_engine import TTSManager
    tts_manager = TTSManager()
    tts_manager.set_active_engine("edge")
    tts_manager.current_engine.set_voice_config({
        "voice": voice,
        "rate": rate,
        "pitch": pitch
    })
    
    output_filename = f"tts_{uuid.uuid4()}.mp3"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    audio_path = await tts_manager.speak(text, output_path=output_path)
    
    return jsonify({"audio_url": f"/audio/{os.path.basename(audio_path)}", "filename": output_filename})

@app.route('/api/avatars')
def list_avatars():
    from avatar.avatar_manager import AvatarManager
    manager = AvatarManager()
    return jsonify(manager.get_avatar_list())

@app.route('/api/avatars/<avatar_name>')
def get_avatar(avatar_name):
    from avatar.avatar_manager import AvatarManager
    manager = AvatarManager()
    config = manager.get_avatar_config(avatar_name)
    if config:
        return jsonify(config)
    return jsonify({"error": "Avatar不存在"}), 404

@app.route('/api/avatars', methods=['POST'])
def create_avatar():
    data = request.json
    from avatar.avatar_manager import AvatarManager
    manager = AvatarManager()
    if manager.add_avatar(data.get('name'), data.get('config', {})):
        return jsonify({"status": "success"})
    return jsonify({"error": "创建失败"}), 500

@app.route('/api/avatars/<avatar_name>', methods=['PUT'])
def update_avatar(avatar_name):
    data = request.json
    from avatar.avatar_manager import AvatarManager
    manager = AvatarManager()
    if manager.update_avatar_config(avatar_name, data.get('config', {})):
        return jsonify({"status": "success"})
    return jsonify({"error": "更新失败"}), 404

@app.route('/api/avatars/<avatar_name>', methods=['DELETE'])
def delete_avatar(avatar_name):
    from avatar.avatar_manager import AvatarManager
    manager = AvatarManager()
    if manager.delete_avatar(avatar_name):
        return jsonify({"status": "success"})
    return jsonify({"error": "删除失败"}), 404

@app.route('/api/roles/<role_name>/profile', methods=['GET', 'PUT'])
def manage_role_profile(role_name):
    profile_path = os.path.join(os.path.dirname(__file__), "..", "roles", role_name, "profile.json")
    
    if request.method == 'GET':
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify({"error": "角色不存在"}), 404
    
    if request.method == 'PUT':
        data = request.json
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success"})

@app.route('/api/roles/<role_name>/skills', methods=['GET', 'PUT'])
def manage_role_skills(role_name):
    skills_path = os.path.join(os.path.dirname(__file__), "..", "roles", role_name, "skills.json")
    
    if request.method == 'GET':
        if os.path.exists(skills_path):
            with open(skills_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify({"error": "技能文件不存在"}), 404
    
    if request.method == 'PUT':
        data = request.json
        with open(skills_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success"})

@app.route('/api/roles/<role_name>/avatar', methods=['GET', 'PUT'])
def manage_role_avatar(role_name):
    avatar_path = os.path.join(os.path.dirname(__file__), "..", "roles", role_name, "avatar.json")
    
    if request.method == 'GET':
        if os.path.exists(avatar_path):
            with open(avatar_path, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify({"error": "Avatar配置不存在"}), 404
    
    if request.method == 'PUT':
        data = request.json
        with open(avatar_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success"})

@app.route('/api/agent/<session_id>/tts', methods=['POST'])
async def synthesize_speech(session_id):
    if session_id not in active_agents:
        return jsonify({"error": "会话不存在"}), 404
    
    data = request.json
    text = data.get('text', '')
    
    agent_data = active_agents[session_id]
    character = agent_data["character"]
    
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
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
        character = agent_data["character"]
        agent = agent_data["agent"]
        
        if hasattr(agent, 'client') and hasattr(agent.client, 'chat'):
            response = agent.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "描述这张图片的内容"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ]
                }],
                max_tokens=300
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

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

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
        "emotion": response.get("emotion")
    }, room=session_id)

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)