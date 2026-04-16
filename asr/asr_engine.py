import speech_recognition as sr
import asyncio
from typing import Optional

class ASREngine:
    def __init__(self, provider: str = "google"):
        self.provider = provider
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
    
    def listen(self, timeout: int = 5, phrase_time_limit: int = 10) -> Optional[str]:
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            
            if self.provider == "google":
                return self.recognizer.recognize_google(audio, language='zh-CN')
            elif self.provider == "sphinx":
                return self.recognizer.recognize_sphinx(audio, language='zh-CN')
            elif self.provider == "whisper":
                try:
                    import whisper
                    if not hasattr(self, 'whisper_model'):
                        self.whisper_model = whisper.load_model("base")
                    result = self.whisper_model.transcribe(audio.get_wav_data(), language='zh')
                    return result["text"]
                except ImportError:
                    raise ImportError("请安装openai-whisper: pip install openai-whisper")
            else:
                return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            raise Exception(f"ASR请求错误: {str(e)}")
        except Exception as e:
            raise Exception(f"ASR错误: {str(e)}")
    
    async def listen_async(self, timeout: int = 5, phrase_time_limit: int = 10) -> Optional[str]:
        return await asyncio.to_thread(self.listen, timeout, phrase_time_limit)
    
    def listen_from_file(self, audio_path: str) -> Optional[str]:
        try:
            with sr.AudioFile(audio_path) as source:
                audio = self.recognizer.record(source)
            
            if self.provider == "google":
                return self.recognizer.recognize_google(audio, language='zh-CN')
            elif self.provider == "whisper":
                import whisper
                if not hasattr(self, 'whisper_model'):
                    self.whisper_model = whisper.load_model("base")
                result = self.whisper_model.transcribe(audio_path, language='zh')
                return result["text"]
            return None
        except Exception as e:
            raise Exception(f"音频文件识别错误: {str(e)}")


class ASRManager:
    def __init__(self):
        self.engines = {}
        self.current_engine = None
    
    def register_engine(self, name: str, engine: ASREngine):
        self.engines[name] = engine
    
    def set_active_engine(self, name: str):
        if name in self.engines:
            self.current_engine = self.engines[name]
    
    def recognize(self, timeout: int = 5) -> Optional[str]:
        if self.current_engine is None:
            self.current_engine = ASREngine()
        return self.current_engine.listen(timeout=timeout)
    
    async def recognize_async(self, timeout: int = 5) -> Optional[str]:
        if self.current_engine is None:
            self.current_engine = ASREngine()
        return await self.current_engine.listen_async(timeout=timeout)
    
    def recognize_from_file(self, audio_path: str) -> Optional[str]:
        if self.current_engine is None:
            self.current_engine = ASREngine()
        return self.current_engine.listen_from_file(audio_path)