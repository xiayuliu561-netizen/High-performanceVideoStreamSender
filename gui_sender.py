import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import warnings
from ttkbootstrap.widgets.scrolled import ScrolledText

import multiprocessing as mp
import socket
import struct
import time
import json
import os
import sys

warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    from turbojpeg import TurboJPEG, TJPF_BGR

    HAS_TURBOJPEG = True
except ImportError:
    HAS_TURBOJPEG = False
    import cv2


class ConfigManager:
    CONFIG_FILE = "streamer_config.json"
    DEFAULT_CONFIG = {"ip": "192.168.1.100", "port": 5005, "roi_size": 640, "target_fps": 60, "monitor_idx": 0}

    @staticmethod
    def load():
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ConfigManager.CONFIG_FILE)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return {**ConfigManager.DEFAULT_CONFIG, **json.load(f)}
            except Exception:
                pass
        return ConfigManager.DEFAULT_CONFIG

    @staticmethod
    def save(data):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ConfigManager.CONFIG_FILE)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass


def stream_worker(cmd_queue, stats_queue, config):
    import dxcam
    import ctypes

    if os.name == 'nt':
        ctypes.windll.winmm.timeBeginPeriod(1)

    camera = None
    sock = None
    jpeg = None

    try:
        if HAS_TURBOJPEG:
            dll_path = r"C:\libjpeg-turbo64\bin\turbojpeg.dll"
            try:
                jpeg = TurboJPEG()
            except Exception:
                if os.path.exists(dll_path):
                    jpeg = TurboJPEG(dll_path)
                else:
                    raise RuntimeError("TurboJPEG DLL not found.")

        monitor_idx = config['monitor_idx']
        roi_size = config['roi_size']
        target_fps = config['target_fps']
        udp_ip = config['ip']
        udp_port = config['port']

        camera = dxcam.create(output_idx=monitor_idx, output_color="BGR")
        temp_frame = camera.grab()
        if temp_frame is None:
            stats_queue.put({"type": "error", "msg": "Failed to grab screen. Check monitor index."})
            return

        screen_h, screen_w, _ = temp_frame.shape
        left = max(0, (screen_w - roi_size) // 2)
        top = max(0, (screen_h - roi_size) // 2)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16 * 1024 * 1024)

        camera.start(target_fps=target_fps, video_mode=True, region=(left, top, left + roi_size, top + roi_size))

        encoder_type = 'TurboJPEG' if HAS_TURBOJPEG else 'OpenCV'
        stats_queue.put(
            {"type": "log", "msg": f"Stream started on {udp_ip}:{udp_port} [{encoder_type}]", "level": "SUCCESS"})

        MAX_PAYLOAD = 60000
        header_struct = struct.Struct("!IBB")

        network_frame_id = 0
        stats_frame_counter = 0
        byte_counter = 0
        last_stat_time = time.time()
        target_interval = 1.0 / target_fps

        is_running = True

        while is_running:
            if not cmd_queue.empty():
                cmd = cmd_queue.get_nowait()
                if cmd == 'STOP':
                    break

            start_time = time.perf_counter()

            frame = camera.get_latest_frame()
            if frame is None:
                time.sleep(0.001)
                continue

            if HAS_TURBOJPEG:
                buffer = jpeg.encode(frame, quality=85, pixel_format=TJPF_BGR)
            else:
                _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                buffer = buf.tobytes()

            data_view = memoryview(buffer)
            size = len(data_view)
            num_packets = (size + MAX_PAYLOAD - 1) // MAX_PAYLOAD

            frame_id = network_frame_id % 4294967295
            network_frame_id += 1
            stats_frame_counter += 1

            for i in range(num_packets):
                start = i * MAX_PAYLOAD
                end = min((i + 1) * MAX_PAYLOAD, size)
                packet = header_struct.pack(frame_id, num_packets, i) + data_view[start:end].tobytes()
                sock.sendto(packet, (udp_ip, udp_port))
                byte_counter += len(packet)

            now = time.time()
            if now - last_stat_time >= 0.5:
                duration = now - last_stat_time
                stats_queue.put({
                    "type": "stats",
                    "fps": stats_frame_counter / duration,
                    "bitrate": (byte_counter * 8) / (1024 * 1024) / duration
                })
                stats_frame_counter = 0
                byte_counter = 0
                last_stat_time = now

            process_time = time.perf_counter() - start_time
            if process_time < target_interval:
                time.sleep(target_interval - process_time)

    except Exception as e:
        stats_queue.put({"type": "error", "msg": f"Worker Exception: {str(e)}"})
    finally:
        if os.name == 'nt':
            ctypes.windll.winmm.timeEndPeriod(1)

        if camera and camera.is_capturing:
            camera.stop()
            time.sleep(0.1)

        if sock: sock.close()

        stats_queue.put({"type": "stopped"})
        time.sleep(0.2)
        os._exit(0)


class StreamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UltraStream")
        self.root.geometry("520x720")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = ConfigManager.load()
        self.is_running = False

        self.cmd_queue = mp.Queue()
        self.stats_queue = mp.Queue()
        self.stream_process = None

        self.setup_ui()

        if HAS_TURBOJPEG:
            self.log("Service initialized.", "info")
        else:
            self.log("Service initialized (OpenCV fallback mode).", "warning")

        self.root.after(100, self.poll_stats)

    def setup_ui(self):
        header_frame = ttk.Frame(self.root, padding=20, bootstyle="primary")
        header_frame.pack(fill=X)

        ttk.Label(header_frame, text="VIDEO STREAMER", font=("Microsoft YaHei UI", 18, "bold"),
                  bootstyle="inverse-primary").pack(side=LEFT)
        self.status_badge = ttk.Label(header_frame, text="IDLE", bootstyle="light", font=("Microsoft YaHei UI", 10),
                                      padding=5)
        self.status_badge.pack(side=RIGHT, pady=5)

        main_content = ttk.Frame(self.root, padding=15)
        main_content.pack(fill=BOTH, expand=True)

        settings_frame = ttk.Labelframe(main_content, text="Configuration", padding=15)
        settings_frame.pack(fill=X, pady=10)

        def create_entry(parent, label_text, row, variable, widget_type="entry", values=None):
            ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=W, pady=8)
            if widget_type == "combo":
                w = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=18)
            else:
                w = ttk.Entry(parent, textvariable=variable, width=20)
            w.grid(row=row, column=1, sticky=E, padx=5, pady=8)
            return w

        self.ip_var = tk.StringVar(value=self.config["ip"])
        self.port_var = tk.IntVar(value=self.config["port"])
        self.roi_var = tk.IntVar(value=self.config["roi_size"])
        self.fps_var = tk.IntVar(value=self.config["target_fps"])
        self.monitor_var = tk.IntVar(value=self.config["monitor_idx"])

        create_entry(settings_frame, "Target IP:", 0, self.ip_var)
        create_entry(settings_frame, "Target Port:", 1, self.port_var)
        ttk.Separator(settings_frame, orient=HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)
        create_entry(settings_frame, "ROI Size:", 3, self.roi_var, "combo",
                     values=[320, 416, 512, 640, 800, 1024])
        create_entry(settings_frame, "Target FPS:", 4, self.fps_var)

        monitor_frame = ttk.Frame(settings_frame)
        monitor_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Label(monitor_frame, text="Monitor Index:").pack(side=LEFT)
        ttk.Spinbox(monitor_frame, from_=0, to=5, textvariable=self.monitor_var, width=5).pack(side=LEFT, padx=25)

        stats_frame = ttk.Frame(main_content, padding=(5, 15))
        stats_frame.pack(fill=X)

        self.lbl_fps = ttk.Label(stats_frame, text="FPS: 0", font=("Consolas", 11, "bold"), bootstyle="info")
        self.lbl_fps.pack(side=LEFT, padx=10)
        self.lbl_bitrate = ttk.Label(stats_frame, text="Bitrate: 0.00 Mbps", font=("Consolas", 11, "bold"),
                                     bootstyle="warning")
        self.lbl_bitrate.pack(side=RIGHT, padx=10)

        btn_frame = ttk.Frame(main_content, padding=(0, 10))
        btn_frame.pack(fill=X)

        self.start_btn = ttk.Button(btn_frame, text="START STREAM", command=self.start_stream, bootstyle="success",
                                    width=18)
        self.start_btn.pack(side=LEFT, fill=X, expand=True, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="STOP STREAM", command=self.stop_stream, state="disabled",
                                   bootstyle="danger", width=18)
        self.stop_btn.pack(side=RIGHT, fill=X, expand=True, padx=5)

        ttk.Label(main_content, text="Runtime Log", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor=W, pady=(15, 5))
        self.log_area = ScrolledText(main_content, height=8, font=("Consolas", 9), bootstyle="default")
        self.log_area.pack(fill=BOTH, expand=True)
        self.log_area.text.configure(state='disabled')

    def log(self, message, level="info"):
        timestamp = time.strftime('%H:%M:%S')
        self.log_area.text.configure(state='normal')

        tag = "INFO"
        if level.upper() == "ERROR":
            tag = "ERROR"
        elif level.upper() == "WARNING":
            tag = "WARNING"
        elif level.upper() == "SUCCESS":
            tag = "SUCCESS"

        self.log_area.text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_area.text.tag_config("ERROR", foreground="#d9534f")
        self.log_area.text.tag_config("WARNING", foreground="#f0ad4e")
        self.log_area.text.tag_config("SUCCESS", foreground="#5cb85c")
        self.log_area.text.tag_config("INFO", foreground="#333333")
        self.log_area.text.see(tk.END)
        self.log_area.text.configure(state='disabled')

    def start_stream(self):
        if self.is_running: return

        config_data = {
            "ip": self.ip_var.get(), "port": self.port_var.get(),
            "roi_size": self.roi_var.get(), "target_fps": self.fps_var.get(),
            "monitor_idx": self.monitor_var.get()
        }
        ConfigManager.save(config_data)

        while not self.cmd_queue.empty(): self.cmd_queue.get()
        while not self.stats_queue.empty(): self.stats_queue.get()

        self.stream_process = mp.Process(target=stream_worker, args=(self.cmd_queue, self.stats_queue, config_data),
                                         daemon=True)
        self.stream_process.start()

        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_badge.config(text="LIVE", bootstyle="danger")
        self.log("Initializing worker process...", "SUCCESS")

    def stop_stream(self):
        if not self.is_running: return
        self.log("Stopping stream...", "warning")
        self.status_badge.config(text="STOPPING", bootstyle="warning")
        self.cmd_queue.put('STOP')

    def poll_stats(self):
        if self.is_running and self.stream_process and not self.stream_process.is_alive():
            if self.stats_queue.empty():
                self.log("Worker process terminated unexpectedly.", "ERROR")
                self.reset_ui_state()

        while not self.stats_queue.empty():
            msg = self.stats_queue.get()
            msg_type = msg.get("type")

            if msg_type == "stats":
                self.lbl_fps.config(text=f"FPS: {msg['fps']:.1f}")
                self.lbl_bitrate.config(text=f"Bitrate: {msg['bitrate']:.2f} Mbps")
            elif msg_type == "log":
                self.log(msg["msg"], msg.get("level", "INFO"))
            elif msg_type == "error":
                self.log(msg["msg"], "ERROR")
                self.reset_ui_state()
            elif msg_type == "stopped":
                self.log("Stream stopped.")
                self.reset_ui_state()

        self.root.after(100, self.poll_stats)

    def reset_ui_state(self):
        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_badge.config(text="IDLE", bootstyle="light")
        self.lbl_fps.config(text="FPS: 0")
        self.lbl_bitrate.config(text="Bitrate: 0.00 Mbps")

    def on_close(self):
        if self.is_running:
            self.cmd_queue.put('STOP')
            if self.stream_process and self.stream_process.is_alive():
                self.stream_process.join(timeout=0.5)

        if self.stream_process and self.stream_process.is_alive():
            self.stream_process.terminate()

        self.root.destroy()


if __name__ == "__main__":
    mp.freeze_support()

    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = ttk.Window(themename="cosmo")
    app = StreamerApp(root)
    root.mainloop()