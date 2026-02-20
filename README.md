# Azure Kinect DK — macOS 使用指南

## 裝置資訊

- **型號**: Azure Kinect DK (Microsoft)
- **連接**: USB 3.0 Type-C（需外接電源）
- **主機**: M4 Mac Studio (macOS)

## macOS 相容性

| 元件 | macOS 支援 | 替代方案 |
|------|-----------|---------|
| RGB 攝影機 (4K) | ✅ 原生 UVC | 直接使用 |
| 麥克風陣列 (7ch) | ✅ 原生 UAC | 直接使用，48kHz |
| 姿態追蹤 (33 點) | ✅ MediaPipe | `kinect-osc.py --pose` |
| 手部追蹤 (21 點×2) | ✅ MediaPipe | `kinect-osc.py --hands` |
| 臉部追蹤 (478 點) | ✅ MediaPipe | `kinect-osc.py --face` |
| 深度攝影機 (ToF) | ❌ | 硬體閉源驅動，無 macOS 版 |
| IMU | ❌ | 需 K4A SDK（僅 Windows/Linux） |

---

## MediaPipe → OSC 追蹤工具

### 安裝

Python venv 已建立在 `~/azure-kinect-osc/`：

```bash
# 環境已就緒，如需重建：
/opt/homebrew/bin/python3.12 -m venv ~/azure-kinect-osc
source ~/azure-kinect-osc/bin/activate
pip install mediapipe opencv-contrib-python python-osc
```

### 執行

```bash
source ~/azure-kinect-osc/bin/activate
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/AntigravityProjects/azure-kinect-dk

# 全部追蹤（姿態 + 手部 + 臉部）
python kinect-osc.py

# 只開姿態追蹤
python kinect-osc.py --pose

# 手部 + 臉部
python kinect-osc.py --hands --face

# 指定攝影機索引和 OSC port
python kinect-osc.py --camera 0 --osc-port 7000

# 不顯示預覽視窗（headless 模式）
python kinect-osc.py --no-preview
```

### OSC 訊息格式

預設送往 `127.0.0.1:9000`。

| 地址 | 格式 | 說明 |
|------|------|------|
| `/pose/detected` | int (0/1) | 是否偵測到人體 |
| `/pose/landmarks` | float × 132 | 33 個 landmark × (x, y, z, visibility) |
| `/hand/count` | int | 偵測到的手數量 (0-2) |
| `/hand/0/landmarks` | float × 63 | 第一隻手 21 landmark × (x, y, z) |
| `/hand/1/landmarks` | float × 63 | 第二隻手 21 landmark × (x, y, z) |
| `/face/detected` | int (0/1) | 是否偵測到臉部 |
| `/face/landmarks` | float × 1434 | 478 landmark × (x, y, z) |
| `/fps` | float | 目前處理 FPS |

座標系統：x, y 為 0.0~1.0（正規化畫面座標），z 為相對深度。

### 在 Max/MSP 接收 OSC

用 `udpreceive 9000` 接收，搭配 `route` 拆分：

```
[udpreceive 9000]
  |
[route /pose /hand /face /fps]
  |        |       |      |
[route detected landmarks]
```

### 在 TouchDesigner 接收 OSC

1. 新增 **OSC In** CHOP
2. Port 設為 `9000`
3. 使用 Select CHOP 過濾 `/pose/landmarks` 等地址

---

## ffmpeg 測試指令

```bash
# 列出可用裝置
ffmpeg -f avfoundation -list_devices true -i ""

# 擷取一張 RGB 靜態圖（確認攝影機可用）
ffmpeg -f avfoundation -framerate 30 -video_size 1920x1080 \
  -i "Azure Kinect 4K Camera" -frames:v 1 -update 1 test.jpg

# 錄製 7 聲道音訊（10 秒）
ffmpeg -f avfoundation -i ":Azure Kinect Microphone Array" \
  -ac 7 -ar 48000 -t 10 test_mic.wav
```

---

## 檔案結構

```
azure-kinect-dk/
├── README.md               ← 本文件
├── kinect-osc.py           ← MediaPipe → OSC 主程式
├── models/
│   ├── pose_landmarker_full.task
│   ├── hand_landmarker.task
│   └── face_landmarker.task
├── max-patches/
│   ├── azure-kinect-rgb.maxpat
│   └── azure-kinect-mic.maxpat
└── td-projects/
```

Python 虛擬環境: `~/azure-kinect-osc/` (Python 3.12)
