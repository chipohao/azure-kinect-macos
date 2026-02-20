# Azure Kinect DK — macOS 使用指南

Azure Kinect DK 在 macOS 上無法使用深度攝影機（閉源驅動，無 macOS 版），但 RGB 攝影機和 7 聲道麥克風陣列透過標準 UVC/UAC 協議可正常運作。本專案透過 MediaPipe 從 RGB 影像做姿態/手部/臉部追蹤，並以 OSC 送出資料供 Max/MSP、TouchDesigner 等軟體使用。

## 功能總覽

| 功能 | 方式 | OSC 前綴 |
|------|------|----------|
| 骨架追蹤 (17 關節) | MediaPipe Pose | `/pose/` |
| 靜態手勢 (7 種) | MediaPipe Gesture | `/gesture/` |
| DTW 動態手勢 (自訂) | 錄製範本 + DTW 比對 | `/dtw/` |
| 規則姿態偵測 | 關節位置規則 | `/rule/` |
| 臉部追蹤 (6 關鍵點) | MediaPipe Face | `/face/` |
| RGB 攝影機 | UVC 直接擷取 | — |
| 麥克風陣列 (7ch) | UAC 直接擷取 | — |

## 安裝

```bash
# Python 虛擬環境（已建立在 ~/azure-kinect-osc/）
/opt/homebrew/bin/python3.12 -m venv ~/azure-kinect-osc
source ~/azure-kinect-osc/bin/activate
pip install mediapipe opencv-contrib-python python-osc
```

MediaPipe 模型檔下載到 `models/`（已包含）。

## 使用

```bash
source ~/azure-kinect-osc/bin/activate
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/AntigravityProjects/azure-kinect-dk

# ── 即時追蹤 ──
python kinect-osc.py                        # 預設：姿態 + 靜態手勢
python kinect-osc.py --pose --dtw           # 骨架 + DTW 動態手勢
python kinect-osc.py --pose --rules         # 骨架 + 規則姿態偵測
python kinect-osc.py --pose --dtw --rules   # 骨架 + DTW + 規則
python kinect-osc.py --all                  # 全部功能
python kinect-osc.py --gesture              # 只有靜態手勢
python kinect-osc.py --face                 # 只有臉部

# ── DTW 手勢錄製 ──
python kinect-osc.py --record wave          # 錄製 "wave"（3 秒）
python kinect-osc.py --record circle --duration 4
python kinect-osc.py --list-gestures        # 列出所有已錄製的手勢

# ── 選項 ──
--camera 0              # 指定攝影機索引
--osc-port 7000         # 指定 OSC port（預設 9000）
--osc-ip 192.168.1.100  # 送到其他電腦
--no-preview            # 不顯示視窗（headless）
--dtw-threshold 1.2     # DTW 觸發閾值（越小越嚴格）
--dtw-window 2.5        # DTW 滑動視窗秒數
```

## OSC 訊息格式

預設送往 `127.0.0.1:9000`。座標 x, y 為 `0.0`~`1.0`（正規化），z 為相對深度。

### 姿態 `--pose`

```
/pose/detected              int     0 或 1
/pose/nose                  x y z
/pose/left_shoulder         x y z
/pose/right_shoulder        x y z
/pose/left_elbow            x y z
/pose/right_elbow           x y z
/pose/left_wrist            x y z
/pose/right_wrist           x y z
/pose/left_hip              x y z
/pose/right_hip             x y z
/pose/left_knee             x y z
/pose/right_knee            x y z
/pose/left_ankle            x y z
/pose/right_ankle           x y z
```

### 靜態手勢 `--gesture`

MediaPipe 內建 7 種靜態手勢：`Open_Palm`, `Closed_Fist`, `Pointing_Up`, `Thumb_Up`, `Thumb_Down`, `Victory`, `ILoveYou`

```
/gesture/left               string  手勢名稱 或 "None"
/gesture/right              string  手勢名稱 或 "None"
/gesture/left/score         float   辨識信心度 0.0~1.0
/gesture/right/score        float   辨識信心度 0.0~1.0
```

### DTW 動態手勢 `--dtw`

自訂動態手勢（需先用 `--record` 錄製範本）。追蹤手腕軌跡，用 DTW 比對。

```
/dtw/gesture                string  手勢名稱 或 "none"
/dtw/score                  float   DTW 距離（越小越像）
/dtw/trigger                int     1 = 觸發瞬間，0 = 未觸發
```

**錄製流程**：
1. `python kinect-osc.py --record wave` → 倒數 3 秒後開始錄製
2. 做出手勢動作（預設錄 3 秒，追蹤右手腕）
3. 範本存為 `gestures/wave.json`
4. 若要追蹤左手腕或鼻子，編輯 JSON 的 `"track"` 欄位

### 規則姿態 `--rules`

即時偵測，不需訓練。

```
/rule/arms_up               int     雙手高舉過頭
/rule/left_arm_up           int     左手舉起
/rule/right_arm_up          int     右手舉起
/rule/squat                 int     蹲下
/rule/lean_left             int     身體左傾
/rule/lean_right            int     身體右傾
/rule/hands_together        int     雙手靠近
/rule/jump                  int     跳躍（瞬間觸發）
```

### 臉部 `--face`

```
/face/detected              int     0 或 1
/face/nose_tip              x y z
/face/left_eye              x y z
/face/right_eye             x y z
/face/mouth_center          x y z
/face/forehead              x y z
/face/chin                  x y z
```

### 通用

```
/fps                        float   目前 FPS
```

## Max/MSP 接收範例

```
[udpreceive 9000]
  |
[route /pose /gesture /dtw /rule /face /fps]
```

DTW 觸發用法：
```
[route /dtw]
  |
[route trigger gesture]
  |        |
[sel 1]  [print]     ← trigger=1 時觸發事件
```

## TouchDesigner 接收

1. **OSC In** CHOP → Port `9000`
2. 用 **Select** CHOP 過濾需要的地址
3. 用 **CHOP Execute** DAT 接收 `/dtw/trigger` 觸發事件

## 檔案結構

```
azure-kinect-dk/
├── kinect-osc.py               ← 主程式
├── README.md
├── models/                     ← MediaPipe 模型（.gitignore）
│   ├── pose_landmarker_full.task
│   ├── hand_landmarker.task
│   ├── face_landmarker.task
│   └── gesture_recognizer.task
├── gestures/                   ← DTW 手勢範本（自動建立）
│   ├── wave.json
│   └── circle.json
├── max-patches/
│   ├── azure-kinect-rgb.maxpat ← RGB 攝影機直接擷取
│   └── azure-kinect-mic.maxpat ← 7ch 麥克風陣列
└── td-projects/
```

Python 虛擬環境: `~/azure-kinect-osc/` (Python 3.12)

## macOS 硬體限制

Azure Kinect SDK (libk4a) 不支援 macOS，repo 已於 2024/08 封存。深度引擎 (depth engine) 是閉源二進位檔，僅提供 Windows/Linux x86_64。因此深度攝影機 (ToF)、IMU、原生 Body Tracking 在 macOS 上無法使用。本專案透過 MediaPipe 從 RGB 影像做替代追蹤。
