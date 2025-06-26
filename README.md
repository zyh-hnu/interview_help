
# 🎤 AI面试助手 (Interview Assistant)

一个基于语音识别和自然语言处理的智能面试辅助工具，能够实时识别面试官的问题并为面试者提供相应的答案提示。

## ✨ 功能特点

- 🎯 **实时语音识别**：使用Vosk离线语音识别，支持中文，无需联网
- 📱 **手机端录音**：面试者可通过手机浏览器进行录音
- 💻 **桌面端显示**：面试者电脑端实时显示匹配的答案
- 🧠 **智能匹配**：基于TF-IDF和余弦相似度的问题匹配算法
- 📝 **自定义知识库**：支持Excel格式的问答知识库，可自由编辑
- 🔄 **实时同步**：WebSocket实现手机APP端和面试者电脑端的实时通信
- 🎨 **友好界面**：PyQt5/tkinter双重UI支持，现代化界面设计

## 🏗️ 系统架构

```
面试者手机端 (Web) ──录音──> 后端服务 (FastAPI) ──匹配答案──> 面试者电脑端 (GUI)
                                     ↑
                              Vosk语音识别 + 知识库匹配
```

## 📋 环境要求

- Python 3.7+（推荐使用Python3.11.9）
- FFmpeg (用于音频格式转换)
- vosk本地语音识别
- Windows/macOS/Linux

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/zyh-hnu/interview-assistant.git
cd interview-assistant
```

### 2. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 3. 安装FFmpeg

#### Windows:
1. 从 [FFmpeg官网](https://ffmpeg.org/download.html) 下载Windows版本
2. 解压到任意目录（如 `C:\ffmpeg`）
3. 将 `C:\ffmpeg\bin` 添加到系统PATH环境变量
4. 或者修改 `main.py` 中的 `FFMPEG_CMD` 变量为完整路径

#### macOS:
```bash
brew install ffmpeg
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install ffmpeg
```

### 4. 下载语音识别模型

下载Vosk中文语音识别模型：

```bash
# 创建模型目录
mkdir model
cd model

# 下载模型 (约44MB)
wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip

# 解压模型
unzip vosk-model-small-cn-0.22.zip

# 确保目录结构为: model/vosk-model-small-cn-0.22/
```

最终目录结构应该是：
```
项目根目录/
├── model/
│   └── vosk-model-small-cn-0.22/
│       ├── am/
│       ├── graph/
│       ├── ivector/
│       └── conf/
├── main.py
├── run.py
└── ...
```

### 5. 创建知识库

```bash
python create_knowledge_base.py
```

选择选项1创建示例知识库，或者手动创建 `knowledge_base.xlsx` 文件，包含以下列：
- `question`: 面试问题
- `answer`: 对应答案

### 6. 启动服务

#### 方法一：一键启动（推荐）
```bash
python run.py
```

#### 方法二：手动启动
```bash
# 终端1：启动后端服务
python main.py

# 终端2：启动面试者客户端
python interviewee_client.py
```

### 7. 使用工具

1. **获取访问地址**：启动后会显示本机IP地址（如 `192.168.1.100:8000`）
2. **面试官操作**：在手机浏览器访问显示的地址
3. **面试者准备**：确保桌面端客户端窗口已开启
4. **开始面试**：点击手机页面"开始录音"，对着手机说出面试问题
5. **查看答案**：面试者电脑端会实时显示匹配的答案

## 🌐 使用HTTPS (ngrok)

如果需要在外网使用或需要HTTPS，可以使用ngrok：

### 安装ngrok
1. 访问 [ngrok官网](https://ngrok.com/) 注册账号
2. 下载并安装ngrok
3. 配置authtoken

### 使用ngrok
```bash
# 启动本地服务后，新开终端运行：
ngrok http 8000

# ngrok会提供一个公网HTTPS地址，如：
# https://abc123.ngrok.io
```

然后面试官可以通过ngrok提供的HTTPS地址访问。

## 📁 项目结构

```
interview-assistant/
├── main.py                 # FastAPI后端服务
├── run.py                  # 一键启动脚本
├── interviewee_client.py   # 面试者GUI客户端
├── matcher.py              # 问题匹配算法
├── create_knowledge_base.py # 知识库管理工具
├── requirements.txt        # Python依赖列表
├── knowledge_base.xlsx     # 问答知识库（运行后生成）
├── model/                  # Vosk语音识别模型目录
│   └── vosk-model-small-cn-0.22/
├── README.md
└── LICENSE
```

## ⚙️ 配置说明

### FFmpeg路径配置
如果系统PATH中没有FFmpeg，请修改 `main.py` 中的配置：

```python
# 在main.py中找到这行，修改为你的FFmpeg路径
FFMPEG_CMD = "C:\\ffmpeg\\bin\\ffmpeg.exe"  # Windows示例
# FFMPEG_CMD = "/usr/local/bin/ffmpeg"      # macOS/Linux示例
```

### 知识库自定义
编辑 `knowledge_base.xlsx` 文件：
- `question` 列：添加可能遇到的面试问题
- `answer` 列：添加对应的回答模板

### 匹配参数调整
在 `matcher.py` 中可以调整匹配阈值：

```python
def match(self, text, threshold=0.15):  # 降低阈值提高匹配率
```

## 🔧 故障排除

### 常见问题

1. **"FFmpeg not found"**
   - 确保FFmpeg已正确安装并在PATH中
   - 或在main.py中设置正确的FFmpeg路径

2. **"Vosk模型未找到"**
   - 确保模型目录结构正确
   - 重新下载并解压模型文件

3. **手机无法连接**
   - 确保手机和电脑在同一局域网
   - 检查防火墙设置
   - 尝试使用ngrok提供外网访问

4. **语音识别不准确**
   - 在安静环境中录音
   - 说话清晰，语速适中
   - 可以尝试下载更大的Vosk模型

5. **答案匹配不准确**
   - 完善知识库中的问题表述
   - 调整匹配阈值
   - 增加更多相似问题的变体

### 日志查看

启动时会显示详细的状态信息：
- ✓ 表示成功
- ✗ 表示失败
- ⚠️ 表示警告

## 🤝 贡献指南

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## ⭐ 支持项目

如果这个项目对您有帮助，请给个Star！

## 📞 联系方式

- 项目地址：[https://github.com/zyh-hnu/interview-assistant](https://github.com/zyh-hnu/interview-assistant)
- 问题反馈：[Issues](https://github.com/zyh-hnu/interview-assistant/issues)

## 🎯 未来计划

- [ ] 支持更多语言的语音识别
- [ ] 需要优化question和answer的匹配算法，进行迅速匹配定位并输出
- [ ] 支持云端知识库同步
- [ ] 移动端原生应用
- [ ] AI生成面试问题和答案
- [ ] 面试表现分析和建议

---

**免责声明**: 本工具仅供学习和研究使用，请合理使用，遵守相关法律法规和道德规范。
