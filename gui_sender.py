import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
from ttkbootstrap.scrolled import ScrolledText

import threading
import socket
import struct
import time
import cv2
import dxcam
import json
import os
import sys


# === 配置管理类 ===
class ConfigManager:
    CONFIG_FILE = "streamer_config.json"
    DEFAULT_CONFIG = {
        "ip": "192.168.1.100",
        "port": 5005,
        "roi_size": 640,
        "target_fps": 60,
        "monitor_idx": 0
    }

    @staticmethod
    def load():
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        elif __file__:
            application_path = os.path.dirname(__file__)

        config_path = os.path.join(application_path, ConfigManager.CONFIG_FILE)

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return {**ConfigManager.DEFAULT_CONFIG, **json.load(f)}
            except:
                pass
        return ConfigManager.DEFAULT_CONFIG

    @staticmethod
    def save(data):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        elif __file__:
            application_path = os.path.dirname(__file__)

        config_path = os.path.join(application_path, ConfigManager.CONFIG_FILE)

        try:
            with open(config_path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"保存配置失败: {e}")


# === 主应用程序 ===
class StreamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UltraStream 推流端")
        self.root.geometry("500x700")

        # 绑定关闭事件，确保完全退出
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = ConfigManager.load()

        self.is_running = False
        self.camera = None
        self.sock = None
        self.thread = None

        self.stats = {
            "fps": 0,
            "bitrate": 0.0,
            "frames_sent": 0
        }

        self.setup_ui()
        self.log("系统初始化完成，亮色主题已加载。")

    def setup_ui(self):
        header_frame = ttk.Frame(self.root, padding=20, bootstyle="primary")
        header_frame.pack(fill=X)

        ttk.Label(header_frame, text="VIDEO STREAMER", font=("Microsoft YaHei UI", 20, "bold"),
                  bootstyle="inverse-primary").pack(side=LEFT)
        self.status_badge = ttk.Label(header_frame, text="就绪", bootstyle="light", font=("Microsoft YaHei UI", 10),
                                      padding=5)
        self.status_badge.pack(side=RIGHT, pady=5)

        main_content = ttk.Frame(self.root, padding=15)
        main_content.pack(fill=BOTH, expand=True)

        settings_frame = ttk.Labelframe(main_content, text="核心参数配置", padding=15)
        settings_frame.pack(fill=X, pady=10)

        def create_entry(parent, label_text, row, variable, widget_type="entry", values=None):
            ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=W, pady=8)
            if widget_type == "combo":
                widget = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=18)
            else:
                widget = ttk.Entry(parent, textvariable=variable, width=20)
            widget.grid(row=row, column=1, sticky=E, padx=5, pady=8)
            return widget

        self.ip_var = tk.StringVar(value=self.config["ip"])
        self.port_var = tk.IntVar(value=self.config["port"])
        self.roi_var = tk.IntVar(value=self.config["roi_size"])
        self.fps_var = tk.IntVar(value=self.config["target_fps"])
        self.monitor_var = tk.IntVar(value=self.config["monitor_idx"])

        create_entry(settings_frame, "目标 IP 地址:", 0, self.ip_var)
        create_entry(settings_frame, "目标端口 (UDP):", 1, self.port_var)

        ttk.Separator(settings_frame, orient=HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)

        create_entry(settings_frame, "ROI 尺寸 (像素):", 3, self.roi_var, "combo",
                     values=[320, 416, 512, 640, 800, 1024])
        create_entry(settings_frame, "目标帧率 (FPS):", 4, self.fps_var)

        monitor_frame = ttk.Frame(settings_frame)
        monitor_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Label(monitor_frame, text="显示器索引:").pack(side=LEFT)
        ttk.Spinbox(monitor_frame, from_=0, to=5, textvariable=self.monitor_var, width=5).pack(side=LEFT, padx=25)
        ttk.Label(monitor_frame, text="(0=主屏, 1=副屏)", font=("Arial", 8), bootstyle="secondary").pack(side=LEFT)

        # 3. 监控区域
        stats_frame = ttk.Frame(main_content, padding=(5, 15))
        stats_frame.pack(fill=X)

        self.lbl_fps = ttk.Label(stats_frame, text="FPS: 0", font=("Consolas", 11, "bold"), bootstyle="info")
        self.lbl_fps.pack(side=LEFT, padx=10)

        self.lbl_bitrate = ttk.Label(stats_frame, text="Bitrate: 0.0 Mbps", font=("Consolas", 11, "bold"),
                                     bootstyle="warning")
        self.lbl_bitrate.pack(side=RIGHT, padx=10)

        # 4. 按钮区域
        btn_frame = ttk.Frame(main_content, padding=(0, 10))
        btn_frame.pack(fill=X)

        self.start_btn = ttk.Button(btn_frame, text="启动推流 (START)", command=self.start_stream, bootstyle="success",
                                    width=18)
        self.start_btn.pack(side=LEFT, fill=X, expand=True, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="停止推流 (STOP)", command=self.stop_stream, state="disabled",
                                   bootstyle="danger", width=18)
        self.stop_btn.pack(side=RIGHT, fill=X, expand=True, padx=5)

        # 5. 日志区域
        ttk.Label(main_content, text="运行日志", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor=W, pady=(15, 5))

        self.log_area = ScrolledText(main_content, height=8, font=("Consolas", 9), bootstyle="default")
        self.log_area.pack(fill=BOTH, expand=True)
        self.log_area.text.configure(state='disabled')

    def log(self, message, level="info"):
        """线程安全的日志记录"""

        def _log():
            timestamp = time.strftime('%H:%M:%S')
            self.log_area.text.configure(state='normal')

            tag = "INFO"
            if "错误" in message or "失败" in message:
                tag = "ERROR"
            elif "警告" in message:
                tag = "WARNING"
            elif "启动" in message:
                tag = "SUCCESS"

            full_msg = f"[{timestamp}] {message}\n"
            self.log_area.text.insert(tk.END, full_msg, tag)

            self.log_area.text.tag_config("ERROR", foreground="#d9534f")
            self.log_area.text.tag_config("WARNING", foreground="#f0ad4e")
            self.log_area.text.tag_config("SUCCESS", foreground="#5cb85c")
            self.log_area.text.tag_config("INFO", foreground="#333333")

            self.log_area.text.see(tk.END)
            self.log_area.text.configure(state='disabled')

        self.root.after(0, _log)

    def update_stats_ui(self, fps, bitrate_mbps):
        try:
            self.lbl_fps.config(text=f"FPS: {fps:.1f}")
            self.lbl_bitrate.config(text=f"Bitrate: {bitrate_mbps:.2f} Mbps")
        except:
            pass

    def start_stream(self):
        if self.is_running: return

        # 保存配置
        current_config = {
            "ip": self.ip_var.get(),
            "port": self.port_var.get(),
            "roi_size": self.roi_var.get(),
            "target_fps": self.fps_var.get(),
            "monitor_idx": self.monitor_var.get()
        }
        ConfigManager.save(current_config)

        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_badge.config(text="正在推流 (LIVE)", bootstyle="danger")
        self.log("正在启动推流引擎...", "SUCCESS")

        self.thread = threading.Thread(target=self.stream_logic, daemon=True)
        self.thread.start()

    def stop_stream(self):
        if not self.is_running: return
        self.log("正在停止推流...", "warning")
        self.is_running = False
        self.status_badge.config(text="正在停止...", bootstyle="warning")

    def stream_logic(self):
        udp_ip = self.ip_var.get()
        udp_port = self.port_var.get()
        roi_size = self.roi_var.get()
        target_fps = self.fps_var.get()
        monitor_idx = self.monitor_var.get()
        max_payload = 60000

        frame_counter = 0
        byte_counter = 0
        last_stat_time = time.time()

        try:
            self.log(f"正在初始化 DXCam (显示器 {monitor_idx})...")
            self.camera = dxcam.create(output_idx=monitor_idx, output_color="BGR")

            temp_frame = self.camera.grab()
            if temp_frame is None:
                raise Exception("无法抓取屏幕，请检查显示器索引。")

            screen_h, screen_w, _ = temp_frame.shape
            left = (screen_w - roi_size) // 2
            top = (screen_h - roi_size) // 2
            right = left + roi_size
            bottom = top + roi_size

            if left < 0 or top < 0:
                raise Exception(f"ROI ({roi_size}x{roi_size}) 超出屏幕范围")

            region = (left, top, right, bottom)
            self.log(f"推流准备就绪 -> {udp_ip}:{udp_port}", "SUCCESS")

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)

            self.camera.start(target_fps=target_fps, video_mode=True, region=region)

            while self.is_running:
                frame = self.camera.get_latest_frame()
                if frame is None: continue

                retval, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if not retval: continue

                data = buffer.tobytes()
                size = len(data)

                num_packets = (size + max_payload - 1) // max_payload
                frame_id = frame_counter % 4294967295
                frame_counter += 1

                for i in range(num_packets):
                    start = i * max_payload
                    end = min((i + 1) * max_payload, size)
                    segment = data[start:end]
                    header = struct.pack("!IBB", frame_id, num_packets, i)
                    packet = header + segment
                    self.sock.sendto(packet, (udp_ip, udp_port))
                    byte_counter += len(packet)

                now = time.time()
                if now - last_stat_time >= 0.5:
                    duration = now - last_stat_time
                    fps = (frame_counter - self.stats['frames_sent']) / duration
                    bitrate = (byte_counter * 8) / (1024 * 1024) / duration

                    self.root.after(0, lambda f=fps, b=bitrate: self.update_stats_ui(f, b))

                    self.stats['frames_sent'] = frame_counter
                    byte_counter = 0
                    last_stat_time = now

        except Exception as e:
            self.log(f"运行时错误: {str(e)}", "ERROR")
            self.is_running = False
        finally:
            self.cleanup()

    def cleanup(self):
        """=== 修复 3: 安全的资源清理 ==="""
        try:
            if self.camera and self.camera.is_capturing:
                self.camera.stop()
        except:
            pass  # 忽略所有 DXCam 关闭错误

        try:
            if self.sock:
                self.sock.close()
        except:
            pass

        try:
            if self.camera:
                del self.camera
                self.camera = None
        except:
            pass

        self.log("推流服务已停止。")
        self.root.after(0, self.reset_ui_state)

    def reset_ui_state(self):
        try:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.status_badge.config(text="就绪 (IDLE)", bootstyle="light")
            self.update_stats_ui(0, 0)
        except:
            pass

    def on_close(self):
        """窗口关闭事件处理"""
        self.is_running = False
        self.cleanup()
        # 强制销毁窗口并退出 Python，防止后台线程残留
        self.root.destroy()
        os._exit(0)


if __name__ == "__main__":
    # 可选主题: "cosmo", "flatly", "yeti", "pulse"
    root = ttk.Window(themename="cosmo")

    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    app = StreamerApp(root)
    root.mainloop()
