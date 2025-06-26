# run.py - 一键启动脚本
import os
import sys
import subprocess
import time
import threading
import webbrowser
from pathlib import Path

def check_dependencies():
    """检查依赖包是否安装"""
    print("1. 正在检查依赖...")
    # 严格按照原有风格，使用动态导入进行检查
    try:
        import fastapi
        import uvicorn
        import websockets
        import speech_recognition
        import pandas
        import openpyxl
        import sklearn
        import jieba
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e.name}")
        print("\n请运行以下命令安装所有依赖:")
        print("pip install -r requirements.txt")
        return False
    
    print("✓ 所有依赖包已安装")
    return True

def check_knowledge_base():
    """检查知识库文件"""
    print("\n2. 正在检查知识库文件...")
    kb_file = Path("knowledge_base.xlsx")
    
    if not kb_file.exists():
        print("   - 未找到知识库文件 knowledge_base.xlsx")
        print("   - 请先运行: python create_knowledge_base.py (选择选项1)")
        return False
    
    print("✓ 知识库文件存在")
    return True

def get_local_ip():
    """获取本机IP地址"""
    import socket
    try:
        # 连接到一个外部地址来获取本机IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        # 如果无法获取，回退到localhost
        return "127.0.0.1"

def start_backend():
    """启动后端服务"""
    print("\n3. 正在启动后端服务...")
    # 使用 Popen 启动 FastAPI 服务，以便不阻塞主进程
    cmd = [sys.executable, "main.py"]
    try:
        # 在后台启动服务，并让其日志正常输出
        process = subprocess.Popen(cmd)
        return process
    except Exception as e:
        print(f"❌ 启动后端服务失败: {e}")
        return None

def start_client():
    """启动客户端"""
    print("\n4. 正在启动面试者客户端...")
    cmd = [sys.executable, "interviewee_client.py"]
    try:
        process = subprocess.Popen(cmd)
        return process
    except Exception as e:
        print(f"❌ 启动客户端失败: {e}")
        return None

def show_usage_info(ip_address):
    """显示使用说明"""
    server_url = f"http://{ip_address}:8000"
    print(f"""
{'='*60}
🎉 面试辅助工具启动成功！

📱 面试官手机端:
   在手机浏览器访问: {server_url}
   (请确保手机和电脑在同一个局域网下)
   
💻 面试者电脑端:
   一个GUI窗口应该已经自动打开。
   
📋 使用步骤:
   1. 手机打开上述网址。
   2. 点击“开始录音”。
   3. 对手机说话，电脑端的窗口将显示匹配的答案。
   
🛑 停止服务:
   请关闭此窗口 (或按 Ctrl+C) 来停止所有服务。
{'='*60}
    """)

def main():
    """主函数"""
    print("🎯 面试辅助工具启动器")
    print("-" * 50)
    
    if not check_dependencies() or not check_knowledge_base():
        input("\n环境检查未通过，请根据提示操作后重试。按回车键退出...")
        sys.exit(1)
    
    ip_address = get_local_ip()
    print(f"✓ 本机IP地址: {ip_address}")
    
    backend_process = None
    client_process = None
    
    try:
        # 启动后端服务
        backend_process = start_backend()
        if not backend_process:
            raise RuntimeError("后端服务启动失败")
        
        # 给予后端一些时间来完成初始化
        print("   - 等待后端服务加载...")
        time.sleep(4)
        
        # 启动客户端
        client_process = start_client()
        if not client_process:
            raise RuntimeError("客户端启动失败")
            
        # 给予客户端一些时间来加载UI
        time.sleep(2)
        
        # 所有服务启动后，显示使用说明
        show_usage_info(ip_address)
        
        # 保持主进程运行，以便捕获Ctrl+C，并监控子进程
        # 这里用一个循环来等待，直到后端进程结束
        backend_process.wait()

    except KeyboardInterrupt:
        print("\n\n收到用户中断信号 (Ctrl+C)...")
    
    except Exception as e:
        print(f"\n运行时发生错误: {e}")

    finally:
        print("正在关闭所有相关服务，请稍候...")
        # 终止客户端进程
        if client_process and client_process.poll() is None:
            client_process.terminate()
        
        # 终止后端进程
        if backend_process and backend_process.poll() is None:
            backend_process.terminate()
        
        # 等待进程完全关闭
        if client_process:
            client_process.wait(timeout=3)
        if backend_process:
            backend_process.wait(timeout=3)
            
        print("所有服务已停止。")
        input("按回车键退出。")

if __name__ == "__main__":
    main()