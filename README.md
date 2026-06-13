# 🎬 BiliSum — B站视频转文字 + AI 笔记

将 B 站视频一键转为文字稿，并生成 AI 摘要笔记的本地 Web 服务。

## 工作流程

```
粘贴 B站链接 → 下载音频 → 语音转文字(Whisper) → AI整理+笔记(DeepSeek) → 展示结果
```

- **下载**：yt-dlp 仅下载音频流（MP3）
- **转码**：FFmpeg 转为 16kHz 单声道 WAV
- **ASR**：faster-whisper base 模型（CPU 本地运行，完全免费）
- **LLM**：DeepSeek API 做文本整理和结构化笔记

## 环境要求

- **Linux / macOS / WSL2**（Windows 推荐使用 WSL2）
- **Python 3.10+**（推荐 3.12+）
- **FFmpeg**（系统已安装）
- **8GB+ RAM**（推荐）
- **网络**：需要访问 api.deepseek.com

## 快速安装

### 1. 克隆项目

```bash
git clone https://github.com/jiecow/BiliSum.git
cd bilisum
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 下载 Whisper 模型

```bash
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
```

> 这会下载约 140MB 的模型文件（仅首次需要）。如果网络慢，可改用 `tiny` 模型（约 75MB，更快但准确率略低）。

### 4. 配置 API Key

编辑 `config.py`，确认以下内容：

```python
DEEPSEEK_API_KEY = "你的DeepSeek API密钥"     # 必填
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"          # 或 deepseek-v4-pro
```

> 可以改用 `deepseek-v4-pro` 获得更强效果，但响应速度会慢一些。

## 启动服务

```bash
source .venv/bin/activate
python3 run.py
```

打开浏览器访问 **http://localhost:3015**

## 使用说明

1. **首页**：在输入框粘贴 B 站视频链接（支持 `bilibili.com` 和 `b23.tv` 短链）
2. **等待处理**：页面实时显示进度（下载 → 转码 → 语音识别 → AI 整理）
3. **选择笔记风格**：提交前可选择 10 种笔记风格（默认/详细/精简/教程/学术/小红书/生活向导/任务导向/商业/会议纪要/中英文对照）
4. **查看结果**：自动跳转结果页，包含：
   - 📝 **AI 笔记** — 按所选风格生成的结构化 Markdown
   - 📄 **整理后文本** — 润色后的全文
   - ⏱️ **带时间戳转写** — 逐段原文，可定位到视频时间点

### 示例链接

```
https://www.bilibili.com/video/BV1xx411c7mD
https://b23.tv/xxxxxx
```

## 📝 笔记风格

提交视频前可选择以下 10 种笔记风格：

| 风格 | 说明 |
|---|---|
| 📝 **默认** | 标准结构化笔记（摘要 + 要点 + 时间线） |
| 📖 **详细** | 保留完整信息量的深度分析笔记 |
| ✂️ **精简** | 极简提炼，只保留 3 个核心要点 |
| 🎓 **教程** | 教学风格，步骤化讲解 |
| 🎓 **学术** | 论文风格，含摘要/方法论/结论 |
| 📕 **小红书** | 爆款种草文风格，多 emoji |
| 🏠 **生活向导** | 生活百科风格，亲切友好 |
| ✅ **任务导向** | 清单体，可执行的任务列表 |
| 💼 **商业风格** | 商业分析报告风格 |
| 📋 **会议纪要** | 正式会议记录格式 |
| 🌐 **中英文对照** | 中英双语逐段对照 |

## API 接口

| 端点 | 说明 |
|---|---|
| `GET /` | 首页 |
| `POST /submit` | 提交视频链接 |
| `GET /status/<task_id>` | 查询任务进度（JSON） |
| `GET /result/<task_id>` | 查看结果页面 |
| `GET /api/text/<task_id>` | 获取纯文本结果（JSON） |

## 配置说明

编辑 `config.py` 可调整：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `PORT` | 3015 | Web 服务端口 |
| `WHISPER_MODEL_SIZE` | `base` | Whisper 模型：`tiny`/`base`/`small` |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | `deepseek-v4-flash` 或 `deepseek-v4-pro` |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_API_KEY` | — | 你的 API 密钥 |

## 性能说明

- **CPU 转写速度**：1 分钟音频约需 1-3 分钟转写（base 模型）
- **长视频建议**：10 分钟以上的视频建议使用 `tiny` 模型
- **内存占用**：`base` 模型约占用 500MB-1GB 内存

## 技术栈

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频/音频下载
- [FFmpeg](https://ffmpeg.org/) — 音频转码
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — 本地 ASR 引擎
- [DeepSeek API](https://platform.deepseek.com/) — LLM 文本整理和摘要生成
- [Flask](https://flask.palletsprojects.com/) — Web 框架

## License

MIT
