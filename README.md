# Digidol - 智能虚拟角色系统

一个具有记忆、情感和动作表情的智能虚拟角色系统，支持VLM大模型、智能家居控制、语音交互。

## 功能特性

### 1. VLM大模型集成
- 支持多种VLM模型API（OpenAI GPT-4o、Google Gemini、Anthropic Claude等）
- API Key安全输入和管理
- 可处理图像输入（Vision能力）

### 2. 角色系统
- **角色特性**：性格、性别、年龄、教育程度、说话风格
- **喜好**：喜欢的食物、游戏、音乐、电影等
- **TTS配置**：可定制语音音色、语速、音调
- 角色可配置、可扩展

### 3. 记忆管理系统
- **短期记忆**：对话历史记录，自动保存最近的50条对话
- **长期记忆**：重要信息持久化存储
- 通过JSON文档维护，自动更新和检索

### 4. SKILLS动作表情系统
- **情绪表达**：高兴、悲伤、生气、惊讶、害羞、困倦、无聊、兴奋、卖萌
- **动作表演**：跳舞、挥手、鞠躬、拍拍、拥抱、加油
- **智能家居**：开灯、关灯、调节温度、播放音乐、调节音量
- 可扩展的技能系统

### 5. 语音交互
- **ASR语音识别**：支持Google语音识别、WebRTC、Whisper
- **TTS语音合成**：支持Edge TTS、gTTS、pyttsx3
- 可根据角色特性定制TTS音色和说话风格

### 6. Web管理界面
- 角色创建、编辑、删除
- 会话管理和重新启动
- 记忆查看和管理
- 技能和配置JSON编辑
- 语音输入、图片发送、语音播放

## 快速开始

### 环境要求
- Python 3.10+
- FFmpeg（用于音频处理）

### 安装依赖

```bash
cd Digidol
pip install -r requirements.txt
```

### 运行Web界面

```bash
python web/app.py
```

然后在浏览器访问 http://localhost:5000

### 配置API Key

在Web界面顶部输入对应的API Key：
- OpenAI API Key（用于GPT-4/GPT-4o）
- Anthropic API Key（用于Claude）
- Google API Key（用于Gemini）

### 创建和使用角色

1. 选择已有角色或创建新角色
2. 点击角色卡片启动对话
3. 输入文字、语音或图片进行交互

## 项目结构

```
Digidol/
├── agents/                  # 智能体实现
│   ├── character.py         # 角色类定义
│   └── agent.py             # VLM代理、记忆检索、动作选择
├── asr/                     # ASR语音识别
│   └── asr_engine.py        # 语音识别引擎
├── tts/                     # TTS语音合成
│   └── tts_engine.py       # 语音合成引擎
├── avatar/                  # 角色模型库
│   ├── avatar_manager.py   # 角色管理器
│   └── yui/                # 示例角色配置
│       ├── config.json     # 角色模型配置
│       ├── motions/        # 动作文件
│       └── expressions/   # 表情文件
├── roles/                   # 角色定义
│   ├── yui/                # Yui角色
│   │   ├── profile.json    # 角色特性配置
│   │   ├── skills.json     # 技能配置
│   │   ├── avatar.json     # 角色模型配置
│   │   └── memory/         # 记忆存储
│   │       ├── short_term.json  # 短期记忆
│   │       └── long_term.json   # 长期记忆
│   └── kazuha/             # Kazuha角色
├── web/                     # Web界面
│   ├── app.py              # Flask后端API
│   └── templates/
│       └── index.html      # 前端页面
├── run.py                   # 命令行运行脚本
└── requirements.txt         # 依赖列表
```

## 角色配置文件说明

### profile.json - 角色特性

```json
{
    "name": "yui",
    "display_name": "Yui",
    "personality": "活泼可爱、温柔体贴",
    "gender": "female",
    "age": 18,
    "education": "大学一年级",
    "speaking_style": "温柔可爱，声音甜美",
    "likes": {
        "food": ["草莓蛋糕", "奶茶"],
        "games": ["塞尔达传说"]
    },
    "custom_settings": {
        "tts": {
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+0%",
            "pitch": "+0Hz"
        }
    }
}
```

### skills.json - 技能配置

每个技能包含：
- `name`: 技能名称
- `description`: 技能描述
- `animations`: 动画列表
- `expression`: 表情描述
- `trigger_keywords`: 触发关键词

## 添加新角色

1. 在 `roles/` 目录下创建新文件夹
2. 复制 `roles/yui/` 的配置文件作为模板
3. 修改 `profile.json` 中的角色特性
4. 修改 `skills.json` 中的技能配置

## TTS音色列表

| 音色ID | 名称 | 性别 |
|--------|------|------|
| zh-CN-XiaoxiaoNeural | 晓晓 | 女声 |
| zh-CN-YunxiNeural | 云希 | 男声 |
| zh-CN-YunyangNeural | 云扬 | 男声 |
| zh-CN-XiaoyouNeural | 晓悠 | 童声 |

## 3D/2D角色库

系统支持集成Live2D格式的2D角色模型：
- 模型文件：.moc3
- 纹理文件：.png
- 动作文件：.motion3.json
- 表情文件：.exp.json

配置见 `avatar/yui/config.json`

## License

MIT