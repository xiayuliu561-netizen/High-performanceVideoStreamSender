
**[🇨🇳 中文说明](https://www.google.com/search?q=README_CN.md)**

# UltraStream Pro

A low-latency desktop screen streaming tool designed for Local Area Network (LAN) environments. Developed in Python, it utilizes a multiprocessing architecture to handle UDP video streaming while maintaining UI responsiveness.

## Key Features

* **Multiprocessing Architecture**: Separates the streaming engine from the GUI. This prevents the Global Interpreter Lock (GIL) from causing UI unresponsiveness during high-load captures.
* **Efficient Pipeline**: Combines **DXCam** (utilizing the Windows Desktop Duplication API) for screen capture with **TurboJPEG** for C-level image encoding.
* **Memory Optimization**: Uses `memoryview` to stream data directly from buffers, reducing the overhead associated with memory allocation during fragmentation.
* **Framerate Control**: Integrates Windows high-precision OS timers (`WinMM`) to provide a stable framerate output (e.g., 60 FPS).

## Protocol Structure

To adhere to network MTU limits, video frames are fragmented at the application layer. Each UDP packet includes a 6-byte header (`!IBB`):

| Offset | Field | Type | Description |
| --- | --- | --- | --- |
| 0x00 | `Frame ID` | `uint32` | Monotonically increasing frame sequence. |
| 0x04 | `Total Pkts` | `uint8` | Total number of fragments for the current frame. |
| 0x05 | `Pkt Index` | `uint8` | Current fragment index (0-based). |

## Quick Start

**Requirements:** Windows OS, Python 3.8+

1. **Install Dependencies:**
```bash
pip install ttkbootstrap dxcam PyTurboJPEG opencv-python

```


2. **Run the Application:**
```bash
python gui_sender.py

```


3. **Configure & Stream**: Enter the receiver's IP/Port, select the target framerate, and click **START STREAM**.

## Notes & Limitations

* **Platform Compatibility**: Currently relies on Windows-specific APIs (`dxcam` and `ctypes.windll.winmm`). Linux and macOS are not supported.
* **TurboJPEG Fallback**: Installing `libjpeg-turbo64` is recommended for optimal performance. The system will automatically fall back to OpenCV encoding if the library is not found.

## License

MIT License.
