import asyncio
import os
import aiohttp
from typing import Optional, Dict

class TTSEngine:
    def __init__(self, provider: str = "edge"):
        self.provider = provider
        self.voice_config = {}
    
    def set_voice_config(self, config: Dict):
        self.voice_config = config
    
    async def synthesize(self, text: str, output_path: str = None) -> str:
        if self.provider == "edge":
            return await self._edge_tts(text, output_path)
        elif self.provider == "gtts":
            return self._gtts(text, output_path)
        elif self.provider == "pyttsx3":
            return self._pyttsx3_synthesize(text, output_path)
        else:
            raise ValueError(f"不支持的TTS提供商: {self.provider}")
    
    async def _edge_tts(self, text: str, output_path: str = None) -> str:
        try:
            import edge_tts
            voice = self.voice_config.get("voice", "zh-CN-XiaoxiaoNeural")
            rate = self.voice_config.get("rate", "+0%")
            pitch = self.voice_config.get("pitch", "+0Hz")
            
            if output_path is None:
                output_path = "temp_audio.mp3"
            
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(output_path)
            return output_path
        
        except ImportError:
            raise ImportError("请安装edge-tts: pip install edge-tts")
        except Exception as e:
            raise Exception(f"Edge TTS错误: {str(e)}")
    
    def _gtts(self, text: str, output_path: str = None) -> str:
        try:
            from gtts import gTTS
            if output_path is None:
                output_path = "temp_audio.mp3"
            tts = gTTS(text=text, lang='zh-cn')
            tts.save(output_path)
            return output_path
        except ImportError:
            raise ImportError("请安装gTTS: pip install gTTS")
    
    def _pyttsx3_synthesize(self, text: str, output_path: str = None) -> str:
        import pyttsx3
        engine = pyttsx3.init()
        
        voices = engine.getProperty('voices')
        if self.voice_config.get("voice_name"):
            for voice in voices:
                if self.voice_config["voice_name"] in voice.name:
                    engine.setProperty('voice', voice.id)
                    break
        
        rate = self.voice_config.get("rate", 200)
        engine.setProperty('rate', rate)
        
        if output_path is None:
            output_path = "temp_audio.wav"
        
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        return output_path


class TTSManager:
    def __init__(self):
        self.engines = {}
        self.current_engine = TTSEngine("edge")
    
    def register_engine(self, name: str, engine: TTSEngine):
        self.engines[name] = engine
    
    def set_active_engine(self, name: str):
        if name in self.engines:
            self.current_engine = self.engines[name]
        elif name == "edge":
            self.current_engine = TTSEngine("edge")
        elif name == "gtts":
            self.current_engine = TTSEngine("gtts")
        elif name == "pyttsx3":
            self.current_engine = TTSEngine("pyttsx3")
    
    async def speak(self, text: str, voice_config: Dict = None, output_path: str = None) -> str:
        if voice_config:
            self.current_engine.set_voice_config(voice_config)
        
        return await self.current_engine.synthesize(text, output_path)
    
    def get_available_voices(self, provider: str = "edge") -> list:
        if provider == "edge":
            return [
                {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓 (女声)", "gender": "Female"},
                {"id": "zh-CN-YunxiNeural", "name": "云希 (男声)", "gender": "Male"},
                {"id": "zh-CN-YunyangNeural", "name": "云扬 (男声)", "gender": "Male"},
                {"id": "zh-CN-XiaoyouNeural", "name": "晓悠 (童声)", "gender": "Female"},
            ]
        return []