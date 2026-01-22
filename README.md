[**🇨🇳 中文说明**](README_CN.md)

# UltraStream Sender

**UltraStream** is a high-performance, low-latency desktop screen streaming application developed in Python. It utilizes **DXCam** for hardware-accelerated screen capture and **UDP** for non-blocking data transmission, designed specifically for Local Area Network (LAN) environments.

The application features a modern GUI built with `ttkbootstrap`, offering real-time performance monitoring (FPS/Bitrate) and dynamic configuration of the Region of Interest (ROI).

## 🚀 Key Features

* **High-Speed Capture**: Leverages the Windows Desktop Duplication API via `dxcam` for ultra-low latency frame grabbing (>60 FPS).
* **UDP Transmission**: Implements a custom fragmentation protocol to handle high-throughput video data over UDP without head-of-line blocking.
* **Modern GUI**: User-friendly interface with a clean "Cosmo" theme.
* **Real-time Telemetry**: Live monitoring of transmission frame rates and network throughput.
* **Configurable**: Dynamic adjustment of Target IP, Port, Frame Rate, Monitor Index, and ROI size.

## 🛠️ Technical Architecture

### Dependencies
* **Python 3.8+** (Required)
* **DXCam**: For hardware-accelerated screen capture (Windows only).
* **OpenCV**: For efficient JPEG compression and frame processing.
* **Tkinter / ttkbootstrap**: For the graphical user interface.

### Network Protocol
The application transmits JPEG-encoded frames over UDP. To adhere to standard MTU limits and avoid IP fragmentation, frames are split into application-layer packets (max payload 60KB).

**Packet Header Structure (6 Bytes):**
Each UDP packet is prefixed with a binary header packed using `struct.pack("!IBB", ...)`:

| Offset | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| 0x00 | `Frame ID` | `uint32` | Unique identifier for the video frame (Monotonically increasing). |
| 0x04 | `Total Packets`| `uint8` | Total number of fragments for this frame. |
| 0x05 | `Packet Index` | `uint8` | The sequence index of the current fragment (0-based). |

## 📦 Installation

**Note:** This application requires a **Windows** operating system due to the dependency on the Desktop Duplication API.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/UltraStream-Sender.git](https://github.com/YOUR_USERNAME/UltraStream-Sender.git)
    cd UltraStream-Sender
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ▶️ Usage

1.  **Run the application:**
    ```bash
    python gui_sender.py
    ```

2.  **Configuration:**
    * **Target IP**: Enter the IP address of the receiving machine (Linux/Windows).
    * **Port**: Specify the UDP port (Default: 5005).
    * **ROI Size**: Select the size of the capture region (e.g., 640x640).
    * **Monitor Index**: 0 for Primary, 1 for Secondary.

3.  **Operation:**
    * Click **START** to begin the transmission thread.
    * Click **STOP** to safely terminate the capture engine and socket connection.

## ⚠️ Limitations

* **Windows Only**: The `dxcam` library does not support Linux or macOS.
* **Network Stability**: As this uses UDP without retransmission logic (fire-and-forget), packet loss may occur on congested networks, leading to visual artifacts on the receiver side.

## 📄 License

Distributed under the MIT License.