# interviewee_client.py
import sys
import asyncio
import websockets
import json
from datetime import datetime
try:
    from PyQt5.QtWidgets import (QApplication, QLabel, QVBoxLayout, QWidget,
                                QPushButton, QHBoxLayout, QScrollArea, QFrame)
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont, QPalette, QColor
    PYQT_AVAILABLE = True
except ImportError:
    print("PyQt5 未安装，尝试使用 tkinter...")
    import tkinter as tk
    from tkinter import scrolledtext, messagebox
    import threading
    PYQT_AVAILABLE = False

class AnswerDisplayWindow:
    def __init__(self):
        if PYQT_AVAILABLE:
            self._init_pyqt()
        else:
            self._init_tkinter()

    def _init_pyqt(self):
        """使用PyQt5初始化窗口"""
        self.app = QApplication(sys.argv)
        self.window = QWidget()
        self.setup_pyqt_ui()

    def _init_tkinter(self):
        """使用tkinter初始化窗口"""
        self.window = tk.Tk()
        self.setup_tkinter_ui()

    def setup_pyqt_ui(self):
        """设置PyQt5界面"""
        self.window.setWindowTitle("面试助手 - 答案显示")
        self.window.setWindowFlags(Qt.WindowStaysOnTopHint)

        # 设置窗口样式
        self.window.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 0.95);
                color: #00FF00;
                font-family: 'Microsoft YaHei', 'Consolas', monospace;
            }
        """)

        # 创建布局
        layout = QVBoxLayout()

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("🤖 面试助手")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setStyleSheet("color: #00BFFF; margin-bottom: 10px;")

        # 控制按钮
        self.clear_btn = QPushButton("清除")
        self.hide_btn = QPushButton("隐藏")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                border: 1px solid #555;
                padding: 5px 15px;
                border-radius: 3px;
                color: white;
            }
            QPushButton:hover { background-color: #555; }
        """)
        self.hide_btn.setStyleSheet(self.clear_btn.styleSheet())

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.clear_btn)
        title_layout.addWidget(self.hide_btn)

        # 状态标签
        self.status_label = QLabel("等待连接服务器...")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        self.status_label.setStyleSheet("color: #FFD700; padding: 5px;")

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #555;
                border-radius: 5px;
            }
            QScrollBar:vertical {
                background: #333;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #666;
                border-radius: 6px;
                min-height: 20px;
            }
        """)

        # 内容显示
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop)

        scroll_area.setWidget(self.content_widget)

        # 添加到主布局
        layout.addLayout(title_layout)
        layout.addWidget(self.status_label)
        layout.addWidget(scroll_area)

        self.window.setLayout(layout)
        self.window.resize(500, 400)

        # 连接信号
        self.clear_btn.clicked.connect(self.clear_content)
        self.hide_btn.clicked.connect(self.toggle_visibility)

        self.window.show()

    def setup_tkinter_ui(self):
        """设置tkinter界面"""
        self.window.title("面试助手 - 答案显示")
        self.window.geometry("500x400")
        self.window.configure(bg='#1E1E1E')

        # 设置窗口置顶
        self.window.attributes('-topmost', True)

        # 标题框架
        title_frame = tk.Frame(self.window, bg='#1E1E1E')
        title_frame.pack(fill='x', padx=10, pady=5)

        title_label = tk.Label(title_frame, text="🤖 面试助手",
                              bg='#1E1E1E', fg='#00BFFF',
                              font=('Microsoft YaHei', 14, 'bold'))
        title_label.pack(side='left')

        # 控制按钮
        btn_frame = tk.Frame(title_frame, bg='#1E1E1E')
        btn_frame.pack(side='right')

        self.clear_btn = tk.Button(btn_frame, text="清除",
                                  bg='#333', fg='white',
                                  command=self.clear_content)
        self.clear_btn.pack(side='right', padx=2)

        self.hide_btn = tk.Button(btn_frame, text="隐藏",
                                 bg='#333', fg='white',
                                 command=self.toggle_visibility)
        self.hide_btn.pack(side='right', padx=2)

        # 状态标签
        self.status_label = tk.Label(self.window, text="等待连接服务器...",
                                    bg='#1E1E1E', fg='#FFD700',
                                    font=('Microsoft YaHei', 10))
        self.status_label.pack(fill='x', padx=10, pady=2)

        # 内容显示区域
        self.text_area = scrolledtext.ScrolledText(
            self.window,
            bg='#1E1E1E', fg='#00FF00',
            font=('Consolas', 11),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.text_area.pack(fill='both', expand=True, padx=10, pady=5)

    def update_status(self, status_text, color=None):
        """更新状态"""
        if PYQT_AVAILABLE:
            self.status_label.setText(status_text)
            if color:
                self.status_label.setStyleSheet(f"color: {color}; padding: 5px;")
        else:
            self.status_label.config(text=status_text)
            if color:
                self.status_label.config(fg=color)

    def add_message(self, message):
        """添加新消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}]\n{message}\n{'-'*50}\n"

        if PYQT_AVAILABLE:
            message_label = QLabel(formatted_message)
            message_label.setWordWrap(True)
            message_label.setFont(QFont("Consolas", 11))
            message_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 50, 0, 0.3);
                    padding: 10px;
                    margin: 5px;
                    border-radius: 5px;
                    border-left: 3px solid #00FF00;
                }
            """)
            self.content_layout.addWidget(message_label)

            # 滚动到底部
            QTimer.singleShot(100, lambda: self.window.findChild(QScrollArea).verticalScrollBar().setValue(
                self.window.findChild(QScrollArea).verticalScrollBar().maximum()
            ))
        else:
            self.text_area.config(state=tk.NORMAL)
            self.text_area.insert(tk.END, formatted_message)
            self.text_area.config(state=tk.DISABLED)
            self.text_area.see(tk.END)

    def clear_content(self):
        """清除内容"""
        if PYQT_AVAILABLE:
            for i in reversed(range(self.content_layout.count())):
                self.content_layout.itemAt(i).widget().setParent(None)
        else:
            self.text_area.config(state=tk.NORMAL)
            self.text_area.delete(1.0, tk.END)
            self.text_area.config(state=tk.DISABLED)

    def toggle_visibility(self):
        """切换窗口可见性"""
        if PYQT_AVAILABLE:
            if self.window.isVisible():
                self.window.hide()
                # 可以添加系统托盘功能
            else:
                self.window.show()
        else:
            if self.window.winfo_viewable():
                self.window.withdraw()
            else:
                self.window.deiconify()

    def run(self):
        """运行应用"""
        if PYQT_AVAILABLE:
            return self.app.exec_()
        else:
            self.window.mainloop()

class WebSocketClientThread:
    def __init__(self, window):
        self.window = window
        self.uri = "ws://localhost:8000/ws/interviewee"
        self.running = False

    def start(self):
        """启动WebSocket客户端"""
        self.running = True
        if PYQT_AVAILABLE:
            self.thread = WebSocketQtThread(self.window, self.uri)
            self.thread.start()
        else:
            self.thread = threading.Thread(target=self._run_asyncio, daemon=True)
            self.thread.start()

    def _run_asyncio(self):
        """运行asyncio事件循环 (For a tkinter app)"""
        # 定义一个嵌套的异步函数来处理websocket逻辑
        async def listen():
            """监听WebSocket消息"""
            while self.running:
                try:
                    async with websockets.connect(self.uri) as websocket:
                        print("成功连接到服务器")
                        self.window.update_status("✓ 连接成功！等待面试官提问...", "#4CAF50")

                        # 发送心跳
                        await websocket.send("ping")

                        async for message in websocket:
                            if message == "pong":
                                continue

                            print(f"收到消息: {message}")
                            self.window.add_message(message)

                except websockets.exceptions.ConnectionClosed:
                    print("连接已关闭")
                    self.window.update_status("连接断开，正在重试...", "#FF9800")
                except Exception as e:
                    print(f"连接失败: {e}")
                    self.window.update_status(f"连接失败: {e}", "#F44336")

                if self.running:
                    await asyncio.sleep(5)  # 5秒后重试

        # 在由线程启动的事件循环中运行上面的异步函数
        asyncio.run(listen())

class WebSocketQtThread(QThread):
    """PyQt5线程类"""
    message_received = pyqtSignal(str)
    status_updated = pyqtSignal(str, str)

    def __init__(self, window, uri):
        super().__init__()
        self.window = window
        self.uri = uri
        self.running = True

        # 连接信号
        self.message_received.connect(self.window.add_message)
        self.status_updated.connect(self.window.update_status)

    def run(self):
        """在新线程中运行asyncio事件循环"""
        asyncio.run(self.listen())

    async def listen(self):
        """监听WebSocket消息"""
        while self.running:
            try:
                async with websockets.connect(self.uri) as websocket:
                    print("成功连接到服务器")
                    self.status_updated.emit("✓ 连接成功！等待面试官提问...", "#4CAF50")

                    # 发送心跳
                    await websocket.send("ping")

                    async for message in websocket:
                        if message == "pong":
                            continue

                        print(f"收到消息: {message}")
                        self.message_received.emit(message)

            except websockets.exceptions.ConnectionClosed:
                print("连接已关闭")
                self.status_updated.emit("连接断开，正在重试...", "#FF9800")
            except Exception as e:
                print(f"连接失败: {e}")
                self.status_updated.emit(f"连接失败: {e}", "#F44336")

            if self.running:
                await asyncio.sleep(5)  # 5秒后重试

def main():
    """主函数"""
    print("=== 面试助手客户端启动 ===")

    # 检查依赖
    if not PYQT_AVAILABLE:
        print("注意: PyQt5 未安装，使用 tkinter 界面")
        print("建议安装 PyQt5 以获得更好的体验: pip install PyQt5")

    try:
        # 创建窗口
        window = AnswerDisplayWindow()

        # 创建并启动WebSocket客户端
        ws_client = WebSocketClientThread(window)
        ws_client.start()

        print("✓ 客户端启动成功")
        print("✓ WebSocket客户端已启动")
        print("请确保后端服务正在运行 (python main.py)")

        # 运行应用
        return window.run()

    except KeyboardInterrupt:
        print("用户中断，正在退出...")
        return 0
    except Exception as e:
        print(f"启动失败: {e}")
        if not PYQT_AVAILABLE:
            messagebox.showerror("错误", f"启动失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())