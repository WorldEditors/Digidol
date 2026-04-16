import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.character import Character
from agents.agent import VLMAgent
from tts.tts_engine import TTSManager
from asr.asr_engine import ASRManager
import json

async def main():
    print("=== Digidol 智能角色系统 ===\n")
    
    role_name = input("请输入角色名称 (yui/kazuha): ").strip() or "yui"
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = input("请输入API Key: ").strip()
    
    print(f"\n正在加载角色: {role_name}...")
    character = Character(role_name)
    print(f"角色: {character.profile.get('display_name', role_name)}")
    print(f"性格: {character.profile.get('personality', '')}\n")
    
    agent = VLMAgent(character, api_key=api_key, model="openai")
    
    tts_manager = TTSManager()
    tts_manager.set_active_engine("edge")
    tts_config = character.get_tts_config()
    tts_manager.current_engine.set_voice_config(tts_config)
    
    print("输入 'quit' 退出，输入 'voice' 测试语音，输入 'memories' 查看记忆\n")
    
    while True:
        user_input = input("你: ").strip()
        
        if user_input.lower() == "quit":
            break
        
        if user_input.lower() == "voice":
            test_text = "你好呀！我是Yui，很高兴认识你！"
            print(f"测试语音: {test_text}")
            audio_path = await tts_manager.speak(test_text)
            print(f"已生成音频: {audio_path}")
            continue
        
        if user_input.lower() == "memories":
            print("\n=== 短期记忆 ===")
            for m in character.get_conversation_context():
                print(f"{m['role']}: {m['content']}")
            print("\n=== 长期记忆 ===")
            for m in character.long_term_memory.get("important_memories", []):
                print(f"- {m['content']} ({m.get('timestamp', '')})")
            print()
            continue
        
        if not user_input:
            continue
        
        print("思考中...")
        response = agent.generate_response(user_input)
        
        print(f"{character.profile.get('display_name', 'Yui')}: {response['text']}")
        if response.get('action'):
            print(f"[动作: {response['action']}]")
        
        character.add_conversation("user", user_input)
        character.add_conversation("assistant", response['text'])
        
        use_voice = input("使用语音播放? (y/n): ").strip().lower() == "y"
        if use_voice:
            audio_path = await tts_manager.speak(response['text'])
            print(f"已生成音频: {audio_path}")

if __name__ == "__main__":
    asyncio.run(main())