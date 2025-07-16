# main.py
import asyncio
import io
import json
import os
import shutil
import subprocess
from typing import Optional
from pathlib import Path  # 添加这个导入
from contextlib import asynccontextmanager  # 添加这个导入
from vosk import Model, KaldiRecognizer,SetLogLevel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio

from matcher import SemanticQuestionMatcher

import jieba.analyse
import jieba.posseg as pseg

#句子清洗功能
class RefinedProcessor:
    def __init__(self):
        self.stop_words=self._load_stop_words()
        jieba.lcut("预热",cut_all=False)
        print("✓ 文本处理器初始化完成")

    def _load_stop_words(self):
        # 实际项目中可以从文件加载更丰富的停用词表
        return {
            '的', '了', '呢', '啊', '哦', '嗯', '这个', '那个', '我想','问一下',
            '请问', '就是', '然后', '其实', '对于', '吧', '呀', '哈', '么','其实','之后','那么'
        }

    def clean_and_rebuild(self, text: str) -> str:
        """
        对文本进行分词，移除停用词，然后重组成一个干净的句子。
        Args:
            text: ASR识别出的原始文本
            
        Returns:
            由关键词组成的更干净的文本字符串
        """
        if not text:
            return ""
        
        
        # 1. 使用jieba进行精确模式分词
        words=jieba.lcut(text.strip(),cut_all=False)

        # 2. 过滤掉停用词 和 单个字符的词 (可以过滤掉很多无意义的词)
        filtered_words = [word for word in words if word not in self.stop_words and len(word.strip()) > 1]

        # 如果过滤后什么都不剩，可以尝试返回原始文本，或者一个稍微不那么严格的过滤结果
        if not filtered_words:
            # 策略：如果严格过滤后为空，放宽条件，只过滤停用词，保留单字符
            filtered_words = [word for word in words if word not in self.stop_words]
        
        # 3. 将过滤后的词重新拼接成句子
        cleaned_text = "".join(filtered_words)  # 使用""拼接，更像一个句子
        
        print(f"原始文本: '{text}' -> 清理后: '{cleaned_text}'")
        
        return cleaned_text


# --- 修改点：使用新的lifespan事件处理器 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global processor
    processor=RefinedProcessor()
    
    # 应用启动时执行
    print("=== 面试辅助工具后端服务启动 ===")

    # 首先初始化Vosk模型
    if init_vosk_model():
        print("✓ Vosk语音识别模型初始化成功")
    else:
        print("✗ Vosk语音识别模型初始化失败")
        print("注意：语音识别功能将不可用")
    
    # 然后初始化问题匹配器
    if init_matcher():
        print("✓ 问题匹配器初始化成功")
        if matcher:
            stats = matcher.get_stats()
            print(f"✓ 知识库加载完成，共 {stats['total_questions']} 个问题")
    else:
        print("✗ 问题匹配器初始化失败")
    
    print("服务器已启动，等待连接...")
    
    yield  # 服务在此处运行
    
    # 应用关闭时执行的代码可以放在这里
    print("=== 面试辅助工具后端服务关闭 ===")


app = FastAPI(
    title="面试辅助工具 API", 
    description="实时语音识别和问题匹配服务",
    lifespan=lifespan  # 将lifespan管理器注册到应用
)
# 全局变量
vosk_model: Optional[Model] = None # 用于加载Vosk模型
matcher: Optional[SemanticQuestionMatcher] = None
interviewee_ws: Optional[WebSocket] = None
processor: Optional[RefinedProcessor]=None 

def init_vosk_model():
    """在服务启动时加载Vosk离线模型"""
    global vosk_model
    
    # 构建相对于当前文件位置的绝对路径，这比相对路径更可靠
    # Path(__file__) 获取当前脚本(main.py)的路径
    # .parent 获取该路径的父目录
    # / "model" / "..." 是跨平台拼接路径的方式
    model_path = Path(__file__).parent / "model" / "vosk-model-cn-0.22"
    
    print(f"正在检查Vosk模型路径: {model_path}")
    
    if not model_path.exists():
        print(f"错误：Vosk模型文件夹未找到，检查路径: '{model_path}'")
        print("请确认 'model/vosk-model-cn-0.22' 文件夹已正确放置在项目根目录。")
        return False
    
    try:
        SetLogLevel(-1)
        print("正在加载Vosk模型，请稍候...")
        vosk_model = Model(str(model_path)) # vosk库需要字符串格式的路径
        print("✓ Vosk模型加载成功")
        return True
    except Exception as e:
        print(f"加载Vosk模型失败: {e}")
        return False

# 初始化问题匹配器
def init_matcher():
    global matcher
    knowledge_base_path = 'knowledge_base.xlsx'
    
    if not os.path.exists(knowledge_base_path):
        print(f"警告：未找到知识库文件 {knowledge_base_path}")
        print("请创建包含 'question' 和 'answer' 列的Excel文件")
        return False
    
    try:
        matcher= SemanticQuestionMatcher(knowledge_base_path)
        return True
    except Exception as e:
        print(f"初始化匹配器失败: {e}")
        return False

# --- 修改后的音频转换函数 ---
def convert_audio_to_wav(input_bytes: bytes) -> bytes:
    """使用FFmpeg将任意格式的音频字节流转换为WAV格式的字节流"""

    # --- 请在这里填入您ffmpeg.exe的完整路径 ---
    # 示例 (Windows): "C:\\ffmpeg\\bin\\ffmpeg.exe"  (注意是双反斜杠)
    # 示例 (macOS/Linux): "/usr/local/bin/ffmpeg"
    FFMPEG_CMD = "ffmpeg"  # 默认值，如果下面的路径检查失败，会尝试使用系统PATH

    # --- 将你的路径填在这里 ---
    # 例如：
    FFMPEG_CMD ="C:\\ffmpeg\\bin\\ffmpeg.exe"
    
    # 检查指定的路径是否存在，如果不存在或未设置，则尝试使用系统PATH
    if not os.path.exists(FFMPEG_CMD):
        # 如果指定路径不存在，尝试在系统PATH中查找
        ffmpeg_in_path = shutil.which("ffmpeg")
        if ffmpeg_in_path:
            FFMPEG_CMD = ffmpeg_in_path
            print(f"使用系统PATH中的ffmpeg: {FFMPEG_CMD}")
        else:
            print(f"错误：在指定路径和系统PATH中都未找到ffmpeg。")
            print(f"请检查 FFMPEG_CMD 变量的路径是否正确: '{FFMPEG_CMD}'")
            raise RuntimeError("FFmpeg not found")
    
    command = [
        FFMPEG_CMD,
        '-i', 'pipe:0',
        '-ac', '1',
        '-ar', '16000',
        '-f', 'wav',
        'pipe:1'
    ]
    
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        wav_bytes, err = process.communicate(input=input_bytes)
        
        if process.returncode != 0:
            print(f"FFmpeg错误: {err.decode(errors='ignore')}")
            return None
        
        return wav_bytes
    except FileNotFoundError:
        print(f"错误: 无法执行命令 '{FFMPEG_CMD}'。请确保路径正确且文件有执行权限。")
        return None
    except Exception as e:
        print(f"FFmpeg转换时发生异常: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def get_interviewer_page():
    """提供面试官手机端页面 - 集成VAD功能"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>面试官录音端 - 智能VAD</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta charset="utf-8">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            text-align: center; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            max-width: 450px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        h1 { margin-bottom: 20px; font-size: 24px; }
        .subtitle { margin-bottom: 30px; font-size: 14px; opacity: 0.8; }
        #status { 
            margin-bottom: 20px; 
            font-size: 16px; 
            padding: 15px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            min-height: 20px;
        }
        #vadStatus {
            margin-bottom: 20px;
            font-size: 14px;
            padding: 10px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .audio-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            background: #666;
            transition: background 0.3s ease;
        }
        .audio-indicator.speaking {
            background: #4CAF50;
            animation: pulse 1s infinite;
        }
        .audio-indicator.silence {
            background: #ff9800;
        }
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.2); opacity: 0.7; }
            100% { transform: scale(1); opacity: 1; }
        }
        button { 
            font-size: 18px; 
            padding: 15px 30px; 
            cursor: pointer; 
            border: none;
            border-radius: 25px;
            margin: 10px;
            transition: all 0.3s ease;
            font-weight: bold;
            min-width: 120px;
        }
        button:hover { transform: translateY(-2px); }
        button:disabled { 
            opacity: 0.5; 
            cursor: not-allowed; 
            transform: none;
        }
        #startBtn { background: #4CAF50; color: white; }
        #stopBtn { background: #f44336; color: white; }
        .success { color: #4CAF50; }
        .error { color: #ff6b6b; }
        .warning { color: #ffa726; }
        .info { color: #29b6f6; }
        .stats {
            margin-top: 20px;
            font-size: 12px;
            opacity: 0.7;
            background: rgba(255,255,255,0.05);
            padding: 10px;
            border-radius: 8px;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
            margin-right: 10px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 面试官录音端</h1>
        <div class="subtitle">基于VAD的智能语音检测</div>
        
        <div id="status" class="info">
            <span class="loading"></span>正在加载VAD模型...
        </div>
        
        <div id="vadStatus">
            <span class="audio-indicator" id="audioIndicator"></span>
            <span id="vadText">等待开始...</span>
        </div>
        
        <button id="startBtn" disabled>开始智能录音</button>
        <button id="stopBtn" disabled>停止录音</button>
        
        <div class="stats">
            <div>发送语音片段: <span id="sentCount">0</span></div>
            <div>识别成功: <span id="recognizedCount">0</span></div>
            <div>匹配成功: <span id="matchedCount">0</span></div>
        </div>
    </div>

    <!-- 按照最新API加载VAD库 -->
    <script src="https://cdn.jsdelivr.net/npm/onnxruntime-web@1.14.0/dist/ort.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.22/dist/bundle.min.js"></script>
    
    <script>
        // DOM元素
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const statusDiv = document.getElementById('status');
        const vadText = document.getElementById('vadText');
        const audioIndicator = document.getElementById('audioIndicator');
        const sentCount = document.getElementById('sentCount');
        const recognizedCount = document.getElementById('recognizedCount');
        const matchedCount = document.getElementById('matchedCount');

        // 全局变量
        let myvad = null;
        let ws = null;
        let isRecording = false;
        let stats = { sent: 0, recognized: 0, matched: 0 };

        function updateStatus(message, type = 'info') {
            statusDiv.innerHTML = message;
            statusDiv.className = type;
        }

        function updateVadStatus(text, isSpeaking = false) {
            vadText.textContent = text;
            audioIndicator.className = isSpeaking ? 'audio-indicator speaking' : 'audio-indicator silence';
        }

        function updateStats() {
            sentCount.textContent = stats.sent;
            recognizedCount.textContent = stats.recognized;
            matchedCount.textContent = stats.matched;
        }

        // 将Float32Array转换为WAV格式
        function encodeWAV(samples, sampleRate = 16000) {
            const buffer = new ArrayBuffer(44 + samples.length * 2);
            const view = new DataView(buffer);
            
            // WAV头部
            const writeString = (offset, string) => {
                for (let i = 0; i < string.length; i++) {
                    view.setUint8(offset + i, string.charCodeAt(i));
                }
            };
            
            writeString(0, 'RIFF');
            view.setUint32(4, 36 + samples.length * 2, true);
            writeString(8, 'WAVE');
            writeString(12, 'fmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, 1, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true);
            view.setUint16(32, 2, true);
            view.setUint16(34, 16, true);
            writeString(36, 'data');
            view.setUint32(40, samples.length * 2, true);
            
            // 写入音频数据
            const offset = 44;
            for (let i = 0; i < samples.length; i++) {
                const sample = Math.max(-1, Math.min(1, samples[i]));
                view.setInt16(offset + i * 2, sample * 0x7FFF, true);
            }
            
            return buffer;
        }

        // 初始化VAD
        async function initializeVAD() {
            try {
                updateStatus('<span class="loading"></span>正在初始化VAD模型...', 'warning');
                
                // 使用最新的API创建VAD实例
                myvad = await vad.MicVAD.new({
                    onSpeechStart: () => {
                        console.log("检测到语音开始");
                        updateVadStatus('正在说话...', true);
                    },
                    
                    onSpeechEnd: (audio) => {
                        console.log(`语音结束，音频长度: ${audio.length} 采样点`);
                        updateVadStatus('处理中...', false);
                        
                        try {
                            // 转换为WAV格式
                            const wavBuffer = encodeWAV(audio);
                            const audioBlob = new Blob([wavBuffer], { type: 'audio/wav' });
                            
                            // 发送给后端
                            if (ws && ws.readyState === WebSocket.OPEN && audioBlob.size > 1000) {
                                ws.send(audioBlob);
                                stats.sent++;
                                updateStats();
                                updateStatus(`发送音频片段 ${stats.sent}`, 'info');
                            }
                        } catch (error) {
                            console.error('音频处理失败:', error);
                            updateStatus('音频处理失败', 'error');
                        }
                        
                        // 重置状态
                        setTimeout(() => {
                            if (isRecording) {
                                updateVadStatus('等待语音...', false);
                            }
                        }, 1000);
                    },
                    
                    onVADMisfire: () => {
                        console.log("VAD误触发");
                        updateVadStatus('等待语音...', false);
                    }
                });
                
                updateStatus('VAD模型加载成功', 'success');
                return true;
                
            } catch (error) {
                console.error('VAD初始化失败:', error);
                updateStatus(`VAD初始化失败: ${error.message}`, 'error');
                return false;
            }
        }

        // 开始录音
        async function startRecording() {
            if (isRecording) return;
            
            startBtn.disabled = true;
            
            try {
                // 如果VAD未初始化，先初始化
                if (!myvad) {
                    const success = await initializeVAD();
                    if (!success) {
                        startBtn.disabled = false;
                        return;
                    }
                }
                
                // 启动VAD
                await myvad.start();
                
                isRecording = true;
                stopBtn.disabled = false;
                updateStatus('智能录音已启动', 'success');
                updateVadStatus('等待语音...', false);
                
            } catch (error) {
                console.error('启动录音失败:', error);
                updateStatus(`启动录音失败: ${error.message}`, 'error');
                startBtn.disabled = false;
            }
        }

        // 停止录音
        async function stopRecording() {
            if (!isRecording || !myvad) return;
            
            try {
                await myvad.pause();
                isRecording = false;
                
                startBtn.disabled = false;
                stopBtn.disabled = true;
                updateStatus('录音已停止', 'info');
                updateVadStatus('已停止', false);
                
            } catch (error) {
                console.error('停止录音失败:', error);
                updateStatus('停止录音失败', 'error');
            }
        }
        
        // WebSocket连接
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/interviewer`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                updateStatus('服务器连接成功，正在初始化VAD...', 'success');
                // 连接成功后初始化VAD
                initializeVAD().then(success => {
                    if (success) {
                        startBtn.disabled = false;
                        updateStatus('系统准备就绪', 'success');
                    }
                });
            };
            
            ws.onclose = () => {
                updateStatus('服务器连接断开，正在重连...', 'error');
                startBtn.disabled = true;
                stopBtn.disabled = true;
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
                updateStatus('连接错误，请检查网络', 'error');
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleServerMessage(data);
                } catch(e) { 
                    console.error("无法解析服务器消息:", event.data); 
                }
            };
        }

        function handleServerMessage(data) {
            switch (data.type) {
                case 'recognition_result':
                    stats.recognized++;
                    updateStats();
                    updateStatus(`识别: ${data.text}`, 'info');
                    break;
                case 'match_result':
                    stats.matched++;
                    updateStats();
                    updateStatus(`匹配成功: ${data.question}`, 'success');
                    break;
                case 'error':
                    updateStatus(`错误: ${data.message}`, 'error');
                    break;
            }
        }
        
        // 事件绑定
        startBtn.onclick = startRecording;
        stopBtn.onclick = stopRecording;

        // 页面加载时连接WebSocket
        window.onload = () => {
            updateStatus('正在连接服务器...', 'info');
            connectWebSocket();
        };

        // 页面关闭时清理资源
        window.onbeforeunload = async () => {
            if (myvad && isRecording) {
                try {
                    await myvad.pause();
                } catch (e) {
                    console.log('清理VAD时出错:', e);
                }
            }
            if (ws) ws.close();
        };
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)



@app.websocket("/ws/interviewee")
async def interviewee_websocket_endpoint(websocket: WebSocket):
    """面试者客户端连接点"""
    global interviewee_ws
    await websocket.accept()
    interviewee_ws = websocket
    print("✓ 面试者客户端已连接")
    
    try:
        while True:
            # 保持连接，可以接收心跳或命令
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        interviewee_ws = None
        print("✗ 面试者客户端已断开")

@app.websocket("/ws/interviewer")
async def interviewer_websocket_endpoint(websocket: WebSocket):
    """面试官手机连接点"""
    await websocket.accept()
    print("✓ 面试官手机端已连接")
    
    try:
        while True:
            # 接收音频数据
            audio_data = await websocket.receive_bytes()
            print(f"收到音频数据，大小: {len(audio_data)} 字节")
            
            # 在处理前先进行格式转换
            wav_audio_data = convert_audio_to_wav(audio_data)
            
            if wav_audio_data:
                # 使用转换后的数据进行处理
                await process_audio(websocket, wav_audio_data)
            else:
                print("✗ 音频转换失败，跳过处理")
            
    except WebSocketDisconnect:
        print("✗ 面试官手机端已断开")
    except Exception as e:
        print(f"处理音频时出错: {e}")

async def process_audio(websocket: WebSocket, audio_data: bytes):
    """使用Vosk处理音频识别和匹配"""
    # 检查Vosk模型是否已加载
    if not vosk_model:
        print("✗ Vosk模型未加载，无法进行识别")
        await websocket.send_text(json.dumps({
            'type': 'error', 
            'message': 'Vosk语音识别模型未加载'
        }))
        return

    try:
        #异步实现FFmpeg转换
        wav_audio_data=await asyncio.to_thread(convert_audio_to_wav,audio_data)
        if not wav_audio_data:
            print("✗ 音视频转换失败，跳过处理")
            return

        # 将同步的Vosk代码封装在一个函数内
        def run_recognition(data):
            rec = KaldiRecognizer(vosk_model, 16000)
            rec.AcceptWaveform(data)
            return json.loads(rec.FinalResult())

        result = await asyncio.to_thread(run_recognition, wav_audio_data)
        text = result.get('text', '').replace(' ', '') # 获取文本并移除空格
        
        if text:
            print(f"✓ 离线识别结果: {text}")
            
            # 发送识别结果给面试官
            await websocket.send_text(json.dumps({
                'type': 'recognition_result',
                'text': text
            }))

            # 匹配答案 (这部分逻辑不变)
            if matcher and processor :
                
                #提炼关键词
                cleaned_text = processor.clean_and_rebuild(text)
                if cleaned_text:

                    #异步运行语义匹配
                    match_result = await asyncio.to_thread(matcher.match, cleaned_text)

                    if match_result:
                        answer = match_result['answer']
                        question = match_result['question']
                        similarity = match_result['similarity']
                        
                        print(f"✓ 找到匹配答案，相似度: {similarity:.3f}")
                        
                        await websocket.send_text(json.dumps({
                            'type': 'match_result', 'question': question, 'similarity': similarity
                        }))
                        
                        if interviewee_ws:
                            formatted_answer = f"问题: {question}\n\n答案: {answer}\n\n(相似度: {similarity:.2f})"
                            await interviewee_ws.send_text(formatted_answer)
                            print(f"✓ 已发送答案给面试者: {answer[:30]}...")
                    else:
                        print("✗ 未找到匹配的答案")
                        if interviewee_ws:
                            await interviewee_ws.send_text(f"未找到匹配答案: {text}")
            else:
                print("✗ 问题匹配器未初始化")

        else:
            print("✗ 离线识别未能解析出文本")
            await websocket.send_text(json.dumps({
                'type': 'error', 'message': '无法理解音频内容'
            }))

    except Exception as e:
        print(f"✗ 离线识别处理时出错: {e}")
        await websocket.send_text(json.dumps({
            'type': 'error', 'message': f'处理音频时出错: {e}'
        }))

@app.get("/status")
async def get_status():
    """获取服务状态"""
    return {
        'status': 'running',
        'vosk_model_loaded': vosk_model is not None,
        'matcher_loaded': matcher is not None,
        'interviewee_connected': interviewee_ws is not None,
        'knowledge_base_stats': matcher.get_stats() if matcher else None
    }

if __name__ == "__main__":
    print("启动面试辅助工具后端服务...")
    uvicorn.run(app, host="0.0.0.0", port=8000)