# DigiDol - 智能虚拟角色系统

一个具有记忆、情感和动作表情的 AI 虚拟角色陪伴系统，支持多种大语言模型、语义记忆检索、语音交互和智能家居控制。

## 功能特性

### 1. 多模型 LLM 集成
- 支持 OpenAI GPT-4o、Anthropic Claude、Google Gemini 三种后端
- 结构化 JSON 输出：每次响应自动携带情绪、动作、待存记忆字段
- 图像理解（Vision）：上传图片由 GPT-4o 描述后自动进入对话

### 2. 角色系统
- **角色特性**：性格、性别、年龄、教育程度、说话风格
- **喜好**：食物、游戏、音乐、电影等多维度设定
- **TTS 配置**：可定制语音音色、语速、音调
- 支持在 Web 界面创建、编辑和删除自定义角色

### 3. 记忆管理系统
- **短期记忆**：滚动保存最近 50 条对话，上下文窗口取最近 10 条
- **长期记忆**：重要信息持久化；LLM 可在响应中标注需要永久记住的内容，系统自动存储
- **语义检索**：使用 OpenAI `text-embedding-3-small` 做向量嵌入，余弦相似度排序；无 API Key 时降级为关键词匹配
- 数据持久化到 `roles/<name>/memory/` 目录下的 JSON 文件

### 4. 情绪与动作系统
- **情绪表达**：happy / sad / angry / shy / excited / bored / cute / thinking / sleepy / neutral
- **动作表演**：dance / wave / bow / pat / hug / cheer
- **智能家居**（预留）：开灯、关灯、调节温度、播放音乐、调节音量
- 支持关键词自动触发和手动指定触发两种模式

### 5. 语音交互
- **ASR 语音识别**：支持 Google Web Speech API、CMU Sphinx、OpenAI Whisper
- **TTS 语音合成**：支持 Edge TTS（Microsoft Neural 声）、gTTS、pyttsx3
- 角色 TTS 音色与 `profile.json` 绑定，切换角色自动切换声音

### 6. Web 管理界面
- 角色卡片浏览、创建、编辑、删除
- 实时对话（REST API + Socket.IO 双通道）
- 记忆面板：查看、新增、清除短期/长期记忆
- 技能面板：查看当前角色全部技能并手动触发
- 语音输入（MediaRecorder）、图片上传、TTS 播放

## 快速开始

### 环境要求

- Python 3.10+
- FFmpeg（用于音频处理，Edge TTS 生成 MP3 时需要）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 API Key

**方式一（推荐）**：在项目根目录创建 `.env` 文件：

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
SECRET_KEY=your-random-secret
```

**方式二**：直接在 Web 界面顶部的 API Key 配置区域输入，运行时生效。

### 启动 Web 界面

```bash
python web/app.py
```

浏览器访问 [http://localhost:5000](http://localhost:5000)

### 命令行模式

```bash
python run.py
```

## 项目结构

```
DigiDol/
├── agents/
│   ├── character.py         # 角色类：加载配置、记忆读写、构建 LLM Prompt
│   ├── agent.py             # VLMAgent（LLM 调用）、MemoryRetrieval、ActionSelector
│   └── memory_store.py      # 向量语义记忆存储与检索
├── asr/
│   └── asr_engine.py        # ASR 引擎：Google / Sphinx / Whisper
├── tts/
│   └── tts_engine.py        # TTS 引擎：Edge TTS / gTTS / pyttsx3
├── avatar/
│   ├── avatar_manager.py    # Avatar CRUD 管理
│   └── yui/
│       └── config.json      # Live2D 模型路径与动作/表情映射
├── roles/
│   ├── yui/                 # 内置角色：Yui（18 岁女大学生）
│   │   ├── profile.json     # 性格、TTS 配置
│   │   ├── skills.json      # 情绪/动作/智能家居技能
│   │   ├── avatar.json      # Live2D 模型路径
│   │   └── memory/
│   │       ├── short_term.json       # 短期对话历史
│   │       ├── long_term.json        # 长期重要记忆
│   │       └── long_term_vectors.json  # 语义向量（自动生成）
│   └── kazuha/              # 内置角色：Kazuha（22 岁男研究生）
├── web/
│   ├── app.py               # Flask + Socket.IO 后端
│   └── templates/
│       └── index.html       # 单页前端（原生 JS）
├── run.py                   # 命令行入口
└── requirements.txt
```

## 配置文件说明

### `roles/<name>/profile.json`

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
        "games": ["塞尔达传说", "动物森友会"]
    },
    "dislikes": ["恐怖片", "苦瓜"],
    "custom_settings": {
        "tts_voice": "zh-CN-XiaoxiaoNeural",
        "tts_rate": "+0%",
        "tts_pitch": "+0Hz"
    }
}
```

### `roles/<name>/skills.json`

```json
{
    "skills": {
        "emotions": {
            "happy": {
                "name": "高兴",
                "animations": ["jump", "smile"],
                "trigger_keywords": ["开心", "高兴", "棒"]
            }
        },
        "actions": {
            "dance": {
                "name": "跳舞",
                "animations": ["dance_1", "dance_2"],
                "trigger_keywords": ["跳舞"]
            }
        }
    }
}
```

## 添加新角色

**方式一**：Web 界面点击「创建新角色」，填写基本信息后自动生成。

**方式二**：手动创建目录：

```bash
mkdir -p roles/mychar/memory
cp roles/yui/skills.json roles/mychar/skills.json
# 编辑 roles/mychar/profile.json
```

## TTS 音色列表

| 音色 ID | 名称 | 性别 |
|---|---|---|
| zh-CN-XiaoxiaoNeural | 晓晓 | 女声 |
| zh-CN-YunxiNeural | 云希 | 男声 |
| zh-CN-YunyangNeural | 云扬 | 男声 |
| zh-CN-XiaoyouNeural | 晓悠 | 童声 |

## Avatar 格式支持

系统预留 Live2D 集成接口，配置文件路径位于 `avatar/<name>/config.json`：

- 模型文件：`.moc3`
- 动作文件：`.motion3.json`
- 表情文件：`.exp.json`

## License

MIT
