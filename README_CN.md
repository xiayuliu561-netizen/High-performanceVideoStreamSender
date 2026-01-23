**[🇬🇧 English README](README.md)**

# StreamSender

一款适用于局域网环境的低延迟桌面推流工具。本项目基于 Python 开发，采用多进程架构，在保证图形界面正常响应的前提下，提供稳定的 UDP 视频流传输功能。

## 核心特性

* **多进程架构**：将高负载的推流逻辑与 UI 界面进程隔离，避免了 Python 全局解释器锁 (GIL) 在高负载下导致的界面阻塞。
* **高效流水线**：结合 **DXCam** (Windows 桌面复制 API) 获取屏幕帧，并使用 **TurboJPEG** 进行高效图像编码。
* **内存优化**：传输层采用 `memoryview` 进行数据分片，减少了传统拷贝方式带来的内存分配开销。
* **帧率控制**：调用 Windows 系统的高精度定时器 (`WinMM`)，提供相对稳定的帧率输出（如 60 FPS）。

## 协议结构

为适应网络 MTU 限制，视频帧在应用层进行分片。每个 UDP 数据包包含一个 6 字节的二进制包头 (`!IBB`)：

| 字节偏移 | 字段名 | 数据类型 | 描述 |
| --- | --- | --- | --- |
| 0x00 | `Frame ID` | `uint32` | 帧序列号（单调递增，用于接收端重组）。 |
| 0x04 | `Total Pkts` | `uint8` | 当前视频帧被分割的总包数。 |
| 0x05 | `Pkt Index` | `uint8` | 当前分片包的索引（从 0 开始）。 |

## 快速开始

**系统要求:** Windows 操作系统, Python 3.8+

1. **安装依赖:**
```bash
pip install ttkbootstrap dxcam PyTurboJPEG opencv-python

```


2. **运行程序:**
```bash
python gui_sender.py

```


3. **配置与推流**: 填写接收端的 IP 与端口，设置目标帧率与截取区域，点击 **START STREAM** 开始推流。

## 注意事项与限制

* **平台限制**：由于依赖操作系统底层 API（`dxcam` 及 `ctypes.windll.winmm`），目前仅支持 Windows 系统。
* **TurboJPEG 模式**：建议安装 `libjpeg-turbo64` 库以获得更好的性能。若未检测到该库，系统将自动回退至 OpenCV 进行编码。

## 许可证

采用 MIT 许可证开源。
