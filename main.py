# main.py
import asyncio
import io
import json
import os
import shutil
import subprocess
from typing import Optional
from pathlib import Path  # 添加这个导入
from vosk import Model, KaldiRecognizer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from matcher import QuestionMatcher

app = FastAPI(title="面试辅助工具 API", description="实时语音识别和问题匹配服务")

# 全局变量
vosk_model: Optional[Model] = None # 用于加载Vosk模型
matcher: Optional[QuestionMatcher] = None
interviewee_ws: Optional[WebSocket] = None

# --- 修改点：使用更可靠的路径定位方式 ---
def init_vosk_model():
    """在服务启动时加载Vosk离线模型"""
    global vosk_model
    
    # 构建相对于当前文件位置的绝对路径，这比相对路径更可靠
    # Path(__file__) 获取当前脚本(main.py)的路径
    # .parent 获取该路径的父目录
    # / "model" / "..." 是跨平台拼接路径的方式
    model_path = Path(__file__).parent / "model" / "vosk-model-small-cn-0.22"
    
    print(f"正在检查Vosk模型路径: {model_path}")
    
    if not model_path.exists():
        print(f"错误：Vosk模型文件夹未找到，检查路径: '{model_path}'")
        print("请确认 'model/vosk-model-small-cn-0.22' 文件夹已正确放置在项目根目录。")
        return False
    
    try:
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
        matcher = QuestionMatcher(knowledge_base_path)
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


@app.on_event("startup")
async def startup_event():
    """服务启动时初始化"""
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

@app.get("/", response_class=HTMLResponse)
async def get_interviewer_page():
    """提供面试官手机端页面"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>面试官录音端</title>
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
            max-width: 400px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        h1 { margin-bottom: 30px; font-size: 24px; }
        #status { 
            margin-bottom: 30px; 
            font-size: 16px; 
            padding: 15px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            min-height: 20px;
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
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 面试官录音端</h1>
        <div id="status" class="info">正在连接服务器...</div>
        <button id="startBtn" disabled>开始录音</button>
        <button id="stopBtn" disabled>停止录音</button>
        <div style="margin-top: 20px; font-size: 12px; opacity: 0.8;">
            支持连续录音，自动语音识别
        </div>
    </div>

    <script>
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const statusDiv = document.getElementById('status');
        let mediaRecorder;
        let ws;
        let audioChunks = [];
        let isRecording = false;

        function updateStatus(message, type = 'info') {
            statusDiv.textContent = message;
            statusDiv.className = type;
        }

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/interviewer`;
            
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                updateStatus('已连接服务器，可以开始录音', 'success');
                startBtn.disabled = false;
            };

            ws.onclose = () => {
                updateStatus('连接断开，请刷新页面重试', 'error');
                startBtn.disabled = true;
                stopBtn.disabled = true;
                // 尝试重连
                setTimeout(connectWebSocket, 3000);
            };

            ws.onerror = (error) => {
                console.error('WebSocket Error:', error);
                updateStatus('连接错误，请检查网络', 'error');
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'recognition_result') {
                    updateStatus(`识别结果: ${data.text}`, 'info');
                } else if (data.type === 'match_result') {
                    updateStatus(`匹配成功: ${data.question}`, 'success');
                }
            };
        }

        async function startRecording() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                alert('您的浏览器不支持录音功能');
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        sampleRate: 16000,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true
                    }
                });

                audioChunks = [];
                mediaRecorder = new MediaRecorder(stream);

                mediaRecorder.ondataavailable = event => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks);
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(audioBlob);
                        updateStatus('音频已发送，正在识别...', 'warning');
                    }
                };

                // 每3秒钟自动停止并发送一次
                mediaRecorder.start();
                isRecording = true;
                
                startBtn.disabled = true;
                stopBtn.disabled = false;
                updateStatus('正在录音中...', 'warning');

                // 设置定时发送
                setTimeout(() => {
                    if (isRecording && mediaRecorder && mediaRecorder.state === 'recording') {
                        mediaRecorder.stop();
                        setTimeout(() => {
                            if (isRecording) {
                                startRecording(); // 重新开始录音
                            }
                        }, 500);
                    }
                }, 3000);

            } catch (error) {
                console.error('录音失败:', error);
                updateStatus('录音失败，请检查麦克风权限', 'error');
            }
        }

        function stopRecording() {
            isRecording = false;
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
            startBtn.disabled = false;
            stopBtn.disabled = true;
            updateStatus('已停止录音', 'info');
        }

        startBtn.onclick = startRecording;
        stopBtn.onclick = stopRecording;

        // 页面加载时连接WebSocket
        window.onload = connectWebSocket;
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

# --- 修改点：核心处理逻辑完全重写以使用Vosk ---
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
        # 创建一个识别器实例
        # 第二个参数是采样率，必须与ffmpeg转换时设置的16000一致
        rec = KaldiRecognizer(vosk_model, 16000)
        
        # 将整个WAV文件的字节喂给识别器
        rec.AcceptWaveform(audio_data)
        
        # 获取最终识别结果
        result = json.loads(rec.FinalResult())
        text = result.get('text', '').replace(' ', '') # 获取文本并移除空格
        
        if text:
            print(f"✓ 离线识别结果: {text}")
            
            # 发送识别结果给面试官
            await websocket.send_text(json.dumps({
                'type': 'recognition_result',
                'text': text
            }))

            # 匹配答案 (这部分逻辑不变)
            if matcher:
                match_result = matcher.match(text)
                
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