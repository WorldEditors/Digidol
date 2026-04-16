# AGENT.md — DigiDol 开发指南

本文档面向在此代码库中工作的 AI Agent 或开发者，描述项目约定、关键设计决策和常见操作。

## 项目概况

DigiDol 是一个 Python 3.10+ 的 AI 虚拟角色后端，核心依赖：

| 组件 | 技术 |
|---|---|
| Web 框架 | Flask 2.3+ + Flask-SocketIO 5.3+ |
| LLM | OpenAI / Anthropic / Google（三选一） |
| TTS | edge-tts（默认）/ gTTS / pyttsx3 |
| ASR | SpeechRecognition（Google / Sphinx / Whisper） |
| 存储 | JSON 文件（无数据库） |

## 目录职责

```
agents/          核心逻辑层，不依赖 Flask
  character.py   角色状态与记忆（Character 类）
  agent.py       LLM 调用与动作选择（VLMAgent, ActionSelector）
  memory_store.py 向量语义记忆存储（MemoryStore 类）

web/app.py       HTTP 路由层，只做参数解析和响应格式化
roles/<name>/    角色数据目录（JSON 文件，运行时读写）
```

## 重要约定

### LLM 响应格式

所有 LLM 调用均要求返回严格 JSON，字段如下：

```json
{
  "text": "角色的回复内容",
  "emotion": "happy|sad|angry|shy|excited|bored|cute|thinking|sleepy|neutral",
  "action": "dance|wave|bow|pat|hug|cheer|null",
  "memory_to_save": "需要永久记住的内容，或 null"
}
```

- OpenAI：通过 `response_format={"type":"json_object"}` 强制约束
- Anthropic / Google：通过 system prompt 中的 JSON 模板约束，`_parse_structured_response()` 做容错解析

**不要**在 system prompt 里使用 `[动作]...[/动作]` 标签，该格式已废弃。

### 角色名校验

所有接受 `role_name` 的路由都必须先调用 `validate_role_name(name)` 校验（白名单正则 `^[a-zA-Z0-9_-]{1,32}$`），防止路径穿越。

### TTS 配置字段

`profile.json` 中 TTS 配置使用**扁平 key**：

```json
"custom_settings": {
    "tts_voice": "zh-CN-XiaoxiaoNeural",
    "tts_rate": "+0%",
    "tts_pitch": "+0Hz"
}
```

`Character.get_tts_config()` 将其转换为 `{"voice": ..., "rate": ..., "pitch": ...}` 供 TTSEngine 使用。不要在 `custom_settings` 下嵌套 `tts` 子对象。

### ActionSelector 调用规范

```python
# 自动触发（关键词匹配）
selector.select_action(user_input="我好开心", auto_trigger=True)

# 手动触发（精确指定）
selector.select_action(
    user_input="",
    auto_trigger=False,
    skill_name="dance",
    category="actions"
)
```

`auto_trigger=False` 时必须同时传 `skill_name` 和 `category`，否则返回 `None`。

### `skills.json` 数据结构

顶层有 `"skills"` key，`ActionSelector.__init__` 中 `self.skills = character.skills.get("skills", {})` 已剥离该层，内部直接操作 `emotions / actions / smart_home`：

```
skills.json                ActionSelector.skills
{"skills": {"emotions": …}} → {"emotions": …, "actions": …}
```

`add_skill` / `remove_skill` 操作 `self.skills`，保存时重新包裹 `{"skills": self.skills}`。

## API 路由速查

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/keys` | 设置 API Key（`provider`, `key`） |
| POST | `/api/agent/start` | 启动会话（`role`, `model`, `provider`）→ `session_id` |
| POST | `/api/agent/<id>/chat` | 发送消息 → `{response, action, emotion}` |
| GET/POST/DELETE | `/api/agent/<id>/memory` | 记忆管理 |
| POST | `/api/agent/<id>/action` | 手动触发动作（`skill_name`, `category`） |
| POST | `/api/agent/<id>/tts` | 角色声音 TTS → `audio_url` |
| POST | `/api/tts/synthesize` | 独立 TTS（`text`, `voice`, `rate`, `pitch`） |
| POST | `/api/agent/<id>/asr` | 音频文件 → 识别文字 |
| POST | `/api/agent/<id>/vision` | 图片 → GPT-4o 描述 |
| GET/POST | `/api/roles` | 列出 / 创建角色 |
| DELETE | `/api/roles/<name>` | 删除角色（yui/kazuha 受保护） |
| GET/PUT | `/api/roles/<name>/profile` | 读写 `profile.json` |
| GET/PUT | `/api/roles/<name>/skills` | 读写 `skills.json` |

Socket.IO 事件：`join`（加入房间）、`chat_message`（发消息）、`response`（接收回复）。

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API Key，启动时自动加载 | — |
| `ANTHROPIC_API_KEY` | Anthropic API Key | — |
| `GOOGLE_API_KEY` | Google API Key | — |
| `SECRET_KEY` | Flask session 密钥 | `digidol-dev-secret` |

支持在项目根目录放置 `.env` 文件，需要安装 `python-dotenv`（已在 requirements.txt 中）。

## 记忆系统

### 短期记忆
- 存储路径：`roles/<name>/memory/short_term.json`
- 上限 50 条，LLM 上下文取最近 10 条（`get_conversation_context()`）
- 每次 `add_conversation()` 调用后**同步写磁盘**

### 长期记忆
- JSON 存储：`roles/<name>/memory/long_term.json`
- 向量存储：`roles/<name>/memory/long_term_vectors.json`（`MemoryStore` 自动维护）
- `Character.add_long_term_memory()` 同时写入两处
- `VLMAgent.generate_response()` 在 LLM 返回 `memory_to_save` 非空时自动调用

### 语义检索
`MemoryStore.search(query)` 优先使用 OpenAI `text-embedding-3-small` 做余弦相似度排序；若无 API Key 则降级为 `KEYWORD_HINTS` 关键词匹配。

## 常见操作

### 新增角色
```bash
mkdir -p roles/mychar/memory
cp roles/yui/skills.json roles/mychar/skills.json
# 手动编写 roles/mychar/profile.json
```

### 修改 LLM 使用的模型
在 `agents/agent.py` 的 `_call_llm()` 中修改对应 provider 的 `model=` 参数。

### 添加新技能
直接编辑 `roles/<name>/skills.json`，在 `emotions` 或 `actions` 下添加新条目，或通过 `PUT /api/roles/<name>/skills` 接口更新。

### 调试 LLM 输出
`_parse_structured_response()` 在 JSON 解析失败时降级返回原始文本作为 `text`，可在此函数中加日志排查结构化输出问题。

## 已知限制

- **Live2D 渲染未实现**：前端无 Live2D SDK，动作命令目前仅通过 Socket.IO 发出，不产生实际动画
- **智能家居为占位**：`skills.json` 中 `smart_home` 条目的 `api` 字段未接入实际控制逻辑
- **无用户认证**：当前无登录机制，所有 API 均可匿名访问，生产部署需自行添加认证层
- **并发写冲突**：多个标签页操作同一角色时，JSON 文件写入存在竞争风险
