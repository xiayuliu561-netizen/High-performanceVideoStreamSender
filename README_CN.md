[**🇺🇸 English Readme**](README.md)

# UltraStream Sender

**UltraStream** 是一款基于 Python 开发的高性能、低延迟桌面屏幕推流应用。它利用 **DXCam** 实现硬件加速屏幕捕获，并使用 **UDP** 协议进行非阻塞数据传输，专为局域网（LAN）环境设计。

该应用采用基于 `ttkbootstrap` 构建的现代化 GUI，支持实时性能监控（FPS/比特率）以及感兴趣区域（ROI）的动态配置。

## 🚀 核心功能

* **高速捕获**：利用 Windows 桌面复制 API（通过 `dxcam`），实现超低延迟的帧抓取（>60 FPS）。
* **UDP 传输**：实现自定义的分片协议，通过 UDP 处理高吞吐量视频数据，有效避免队头阻塞（Head-of-line blocking）。
* **现代化 GUI**：基于 "Cosmo" 主题构建的用户友好界面。
* **实时遥测**：实时监控传输帧率和网络吞吐量。
* **高度可配**：支持动态调整目标 IP、端口、帧率、显示器索引和 ROI 尺寸。

## 🛠️ 技术架构

### 依赖项
* **Python 3.8+** (必需)
* **DXCam**：用于硬件加速屏幕捕获（仅限 Windows）。
* **OpenCV**：用于高效的 JPEG 压缩和帧处理。
* **Tkinter / ttkbootstrap**：用于图形用户界面。

### 网络协议
应用程序通过 UDP 传输 JPEG 编码的帧。为了遵守标准的 MTU 限制并避免 IP 层分片，帧被拆分为应用层数据包（最大负载 60KB）。

**数据包头部结构 (6 字节):**
每个 UDP 数据包都带有一个使用 `struct.pack("!IBB", ...)` 打包的二进制头部：

| 偏移量 | 字段 | 类型 | 描述 |
| :--- | :--- | :--- | :--- |
| 0x00 | `Frame ID` | `uint32` | 视频帧的唯一标识符（单调递增）。 |
| 0x04 | `Total Packets`| `uint8` | 当前帧被切分的总分片数。 |
| 0x05 | `Packet Index` | `uint8` | 当前分片的序列索引（从 0 开始）。 |

## 📦 安装指南

**注意：** 由于依赖桌面复制 API，此应用程序仅支持 **Windows** 操作系统。

1.  **克隆仓库：**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/UltraStream-Sender.git](https://github.com/YOUR_USERNAME/UltraStream-Sender.git)
    cd UltraStream-Sender
    ```

2.  **安装依赖：**
    ```bash
    pip install -r requirements.txt
    ```

## ▶️ 使用说明

1.  **运行应用程序：**
    ```bash
    python gui_sender.py
    ```

2.  **配置参数：**
    * **Target IP**：输入接收端机器的 IP 地址（Linux/Windows）。
    * **Port**：指定 UDP 端口（默认：5005）。
    * **ROI Size**：选择捕获区域的大小（例如：640x640）。
    * **Monitor Index**：0 代表主显示器，1 代表副显示器。

3.  **操作：**
    * 点击 **START** 开始传输线程。
    * 点击 **STOP** 安全终止捕获引擎和套接字连接。

## ⚠️ 局限性

* **仅限 Windows**：`dxcam` 库不支持 Linux 或 macOS。
* **网络稳定性**：由于使用无重传逻辑的 UDP（即发即弃），在网络拥塞时可能会发生丢包，导致接收端出现画面伪影或花屏。

## 📄 许可证

本项目基于 MIT 许可证分发。