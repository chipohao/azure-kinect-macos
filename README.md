# Azure Kinect DK on macOS — 使用指南

Azure Kinect DK 的深度攝影機在 macOS 上無法使用（Microsoft 閉源驅動，無 macOS 版）。本專案改用 RGB 攝影機搭配 MediaPipe 做即時追蹤，透過 OSC 雙向通訊整合 Max/MSP 和 TouchDesigner。

---

## 目錄

1. [硬體相容性](#硬體相容性)
2. [安裝](#安裝)
3. [快速開始](#快速開始)
4. [功能模式](#功能模式)
5. [OSC 輸出參考](#osc-輸出參考)
6. [從 Max/MSP 控制](#從-maxmsp-控制)
7. [DTW 手勢錄製與辨識](#dtw-手勢錄製與辨識)
8. [TouchDesigner 整合](#touchdesigner-整合)
9. [Max/MSP 直接擷取（不經 Python）](#maxmsp-直接擷取不經-python)
10. [命令列參數](#命令列參數)
11. [檔案結構](#檔案結構)

---

## 硬體相容性

| 元件 | macOS 狀態 | 本專案解決方式 |
|------|-----------|---------------|
| RGB 攝影機 (4K) | ✅ UVC 原生支援 | 直接使用 |
| 麥克風陣列 (7ch, 48kHz) | ✅ UAC 原生支援 | 直接使用 |
| 骨架追蹤 | ❌ 需要 K4A SDK | ✅ MediaPipe Pose（17 關節）→ OSC |
| 手勢辨識 | ❌ 需要 K4A SDK | ✅ MediaPipe Gesture（7 種）+ DTW（自訂）→ OSC |
| 臉部追蹤 | ❌ 需要 K4A SDK | ✅ MediaPipe Face（6 關鍵點）→ OSC |
| 深度攝影機 (ToF) | ❌ 閉源驅動 | 無法替代 |
| IMU | ❌ 需要 K4A SDK | 無法替代 |

---

## 安裝與啟動

```bash
git clone https://github.com/chipohao/azure-kinect-macos.git
cd azure-kinect-macos
./run.sh
```

`run.sh` 會自動：
1. 下載 MediaPipe 模型到 `models/`
2. 透過 `uv` 建立 `.venv/` 並安裝依賴（定義在 `pyproject.toml`）
3. 啟動程式（預設 `--pose --dtw --rules`）

前提：需要安裝 [uv](https://docs.astral.sh/uv/)（`curl -LsSf https://astral.sh/uv/install.sh | sh`）。
每台電腦第一次跑會花約 1 分鐘安裝依賴，之後直接啟動。

**指定其他模式：**
```bash
./run.sh --all                  # 全功能
./run.sh --gesture              # 只有靜態手勢
./run.sh --no-preview           # 不開預覽視窗
```

啟動後：
- 預覽視窗顯示即時畫面 + 骨架疊加
- OSC 資料送到 `127.0.0.1:9000`（Max/TD 在這邊收）
- Python 在 `port 9001` 聽指令（Max/TD 送到這邊控制）

---

## 功能模式

用 `--` 旗標組合開啟不同功能，可任意搭配：

```bash
python kinect-osc.py --pose                 # 骨架追蹤
python kinect-osc.py --pose --rules         # 骨架 + 規則姿態
python kinect-osc.py --pose --dtw           # 骨架 + DTW 動態手勢
python kinect-osc.py --pose --dtw --rules   # 骨架 + DTW + 規則（推薦）
python kinect-osc.py --gesture              # 靜態手勢（手型辨識）
python kinect-osc.py --face                 # 臉部追蹤
python kinect-osc.py --all                  # 全部開啟
```

### 功能說明

| 旗標 | 功能 | 需要訓練？ | 適合場景 |
|------|------|-----------|---------|
| `--pose` | 17 個骨架關節 xyz 座標 | 不用 | 動作追蹤、互動控制 |
| `--rules` | 舉手/蹲下/跳躍/傾斜/雙手靠近 | 不用 | 簡單觸發事件 |
| `--gesture` | 7 種靜態手型（握拳/張開/比讚...） | 不用 | 手型切換控制 |
| `--dtw` | 自訂動態手勢（揮手/畫圈/任意動作） | 錄 3 秒範本 | 特定動作觸發 |
| `--face` | 6 個臉部關鍵點 | 不用 | 臉部追蹤 |

---

## OSC 輸出參考

所有座標 x, y 為 `0.0`~`1.0`（正規化畫面座標），z 為相對深度。

### 骨架 `--pose`

| OSC 地址 | 值 | 說明 |
|----------|-----|------|
| `/pose/detected` | 0 / 1 | 是否偵測到人 |
| `/pose/nose` | x y z | 鼻子 |
| `/pose/left_shoulder` | x y z | 左肩 |
| `/pose/right_shoulder` | x y z | 右肩 |
| `/pose/left_elbow` | x y z | 左肘 |
| `/pose/right_elbow` | x y z | 右肘 |
| `/pose/left_wrist` | x y z | 左手腕 |
| `/pose/right_wrist` | x y z | 右手腕 |
| `/pose/left_pinky` | x y z | 左小指 |
| `/pose/right_pinky` | x y z | 右小指 |
| `/pose/left_index` | x y z | 左食指 |
| `/pose/right_index` | x y z | 右食指 |
| `/pose/left_hip` | x y z | 左髖 |
| `/pose/right_hip` | x y z | 右髖 |
| `/pose/left_knee` | x y z | 左膝 |
| `/pose/right_knee` | x y z | 右膝 |
| `/pose/left_ankle` | x y z | 左腳踝 |
| `/pose/right_ankle` | x y z | 右腳踝 |

### 規則姿態 `--rules`

即時偵測，不需訓練。值為 0（未觸發）或 1（觸發）。

| OSC 地址 | 說明 |
|----------|------|
| `/rule/arms_up` | 雙手高舉過頭 |
| `/rule/left_arm_up` | 左手舉起（高於肩膀） |
| `/rule/right_arm_up` | 右手舉起 |
| `/rule/squat` | 蹲下 |
| `/rule/lean_left` | 身體左傾 |
| `/rule/lean_right` | 身體右傾 |
| `/rule/hands_together` | 雙手靠近 |
| `/rule/jump` | 跳躍（瞬間觸發一次） |

### 靜態手勢 `--gesture`

MediaPipe 內建 7 種手型辨識：`Open_Palm`, `Closed_Fist`, `Pointing_Up`, `Thumb_Up`, `Thumb_Down`, `Victory`, `ILoveYou`

| OSC 地址 | 值 | 說明 |
|----------|-----|------|
| `/gesture/left` | string | 左手手勢名 或 "None" |
| `/gesture/right` | string | 右手手勢名 或 "None" |
| `/gesture/left/score` | float | 左手辨識信心度 0.0~1.0 |
| `/gesture/right/score` | float | 右手辨識信心度 0.0~1.0 |

### DTW 動態手勢 `--dtw`

自訂動態手勢，需先錄製範本（見下方說明）。

| OSC 地址 | 值 | 說明 |
|----------|-----|------|
| `/dtw/{name}` | 0 / 1 | 該手勢是否觸發（每個錄製的手勢都有獨立 path） |
| `/dtw/{name}/progress` | 0.0~1.0 | 手勢進行百分比（類似 GVF） |
| `/dtw/{name}/following` | 0 / 1 | 是否正在跟蹤此手勢 |
| `/dtw/gesture` | string | 目前最接近的手勢名 或 "none" |
| `/dtw/score` | float | DTW 距離（越小越像） |
| `/dtw/list` | string... | `/cmd/list` 的回應 |

**每個你錄製的手勢都會自動產生 `/dtw/{名稱}` 的 OSC 路徑。** 例如錄了 `wave` 和 `circle`，就會有 `/dtw/wave`、`/dtw/wave/progress`、`/dtw/circle`、`/dtw/circle/progress` 等。

### 臉部 `--face`

| OSC 地址 | 值 | 說明 |
|----------|-----|------|
| `/face/detected` | 0 / 1 | 是否偵測到臉 |
| `/face/nose_tip` | x y z | 鼻尖 |
| `/face/left_eye` | x y z | 左眼 |
| `/face/right_eye` | x y z | 右眼 |
| `/face/mouth_center` | x y z | 嘴巴中心 |
| `/face/forehead` | x y z | 額頭 |
| `/face/chin` | x y z | 下巴 |

### 錄製狀態

| OSC 地址 | 值 | 說明 |
|----------|-----|------|
| `/rec/status` | string | idle / countdown / recording / saved |
| `/rec/progress` | float | 錄製進度 0.0~1.0 |

### 通用

| OSC 地址 | 值 |
|----------|-----|
| `/fps` | float |

---

## 從 Max/MSP 控制

Python 在 **port 9001** 接收來自 Max 的控制指令。

### Max → Python（送到 port 9001）

用 `[udpsend 127.0.0.1 9001]` 送出：

| 指令 | 說明 |
|------|------|
| `/cmd/record wave` | 開始錄製名為 "wave" 的手勢（倒數 3 秒後錄 3 秒） |
| `/cmd/record circle 5` | 錄製 "circle"，指定 5 秒 |
| `/cmd/record/stop` | 提前停止錄製 |
| `/cmd/reload` | 重新載入所有 DTW 範本 |
| `/cmd/threshold 1.2` | 調整 DTW 觸發閾值（越小越嚴格，預設 1.5） |
| `/cmd/mode/pose 1` | 即時開啟/關閉骨架追蹤（0=關, 1=開） |
| `/cmd/mode/gesture 1` | 即時開啟/關閉靜態手勢 |
| `/cmd/mode/face 1` | 即時開啟/關閉臉部追蹤 |
| `/cmd/mode/dtw 1` | 即時開啟/關閉 DTW 手勢辨識 |
| `/cmd/mode/rules 1` | 即時開啟/關閉規則姿態 |
| `/cmd/delete wave` | 刪除手勢範本 "wave" |
| `/cmd/list` | 回傳已載入的手勢列表（收 `/dtw/list`） |
| `/cmd/stop` | 優雅關閉程式 |

### Python → Max（收 port 9000）

用 `[udpreceive 9000]` 接收。

**接收骨架座標：**
```
[udpreceive 9000]
    |
[route /pose/left_wrist]
    |
[unpack f f f]              ← x y z
```

**接收規則觸發：**
```
[udpreceive 9000]
    |
[route /rule/arms_up]       ← 舉手 = 1, 放下 = 0
    |
[sel 1]
    |
[bang]                      ← 舉手時觸發
```

**接收 DTW 手勢觸發：**
```
[udpreceive 9000]
    |
[route /dtw/wave]           ← wave 手勢觸發 = 1
    |
[sel 1]
    |
[bang]                      ← 做出 wave 動作時觸發
```

**從 Max 錄製手勢：**
```
[message /cmd/record swipe]
    |
[udpsend 127.0.0.1 9001]   ← 送出後 Python 會倒數 3 秒開始錄
```

---

## DTW 手勢錄製與辨識

### 什麼是 DTW？

DTW（Dynamic Time Warping）是一種比對兩段時間序列相似度的演算法。你先做一次動作錄下來當範本，之後即時追蹤時，程式會持續比對你的動作軌跡和範本是否相似。

### 三種錄製方式

**方式一：鍵盤（預覽視窗要在 focus）**

| 按鍵 | 動作 |
|------|------|
| R | 錄製（自動命名 gesture_001, 002...） |
| 1~5 | 快速錄製到 gesture_1 ~ gesture_5 |
| 錄製中按 R | 提前停止並儲存 |

**方式二：從 Max/MSP 送 OSC**

```
[udpsend 127.0.0.1 9001]

/cmd/record wave        ← 錄製 "wave"
/cmd/record circle 5    ← 錄製 "circle"，5 秒
/cmd/record/stop        ← 提前停止
```

**方式三：命令列（需重啟程式）**

```bash
python kinect-osc.py --record wave
python kinect-osc.py --record circle --record-duration 5
python kinect-osc.py --list-gestures    # 列出已錄的
```

### 錄製流程

1. 送出錄製指令
2. **倒數 3 秒**（預覽視窗顯示倒數）— 準備動作
3. **錄製開始**（紅點閃爍 + 進度條）— 做出手勢
4. 時間到自動停止 → 儲存到 `gestures/{name}.json`
5. DTW 範本自動重新載入，立即可辨識

### 注意事項

- 預設追蹤**右手腕**軌跡。若要改追蹤左手腕或鼻子，編輯 JSON 的 `"track"` 欄位（可選 `right_wrist`、`left_wrist`、`nose`）
- `--dtw-threshold`（預設 1.5）：越小越嚴格，需要更精確的動作才觸發
- `--dtw-window`（預設 2.0 秒）：比對用的滑動視窗長度
- 建議動作幅度大一點，辨識效果更好

---

## TouchDesigner 整合

### 接收追蹤資料

1. 新增 **OSC In** CHOP → Port `9000`
2. 用 **Select** CHOP 篩選需要的頻道（如 `/pose/left_wrist`）
3. 用 **Math** CHOP 做座標轉換（0~1 → 像素座標）

### 接收 DTW 觸發

1. **OSC In** CHOP → Port `9000`
2. **Select** CHOP → `/dtw/wave`
3. **CHOP Execute** DAT → 在 `onValueChange` 中處理觸發

### 送出控制指令

1. 新增 **OSC Out** CHOP → Address `127.0.0.1` Port `9001`
2. 送出 `/cmd/record wave` 等指令

### RGB 和麥克風直接擷取

- **Video Device In** TOP → 選擇 "Azure Kinect 4K Camera"
- **Audio Device In** CHOP → 選擇 "Azure Kinect Microphone Array"（48kHz, 7ch）
- 注意：Kinect Azure TOP/CHOP 節點**僅限 Windows**

---

## Max/MSP 直接擷取（不經 Python）

### RGB 攝影機

開啟 `max-patches/azure-kinect-rgb.maxpat`，或手動：
- `[jit.grab]` → `[getdevlist]` → 選擇 "Azure Kinect 4K Camera"
- 支援 720p / 1080p / 4K

### 麥克風陣列

開啟 `max-patches/azure-kinect-mic.maxpat`，或手動：
- Audio Status → Input Device → "Azure Kinect Microphone Array"
- Sample Rate 設為 48000 Hz
- `[adc~ 1 2 3 4 5 6 7]` 取得 7 聲道

---

## 命令列參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `--camera N` | 自動偵測 | 攝影機索引 |
| `--width N` | 1280 | 擷取寬度 |
| `--height N` | 720 | 擷取高度 |
| `--osc-ip` | 127.0.0.1 | OSC 送出目標 IP |
| `--osc-port` | 9000 | OSC 送出 port |
| `--listen-port` | 9001 | OSC 接收 port（聽指令） |
| `--pose` | — | 開啟骨架追蹤 |
| `--gesture` | — | 開啟靜態手勢辨識 |
| `--face` | — | 開啟臉部追蹤 |
| `--dtw` | — | 開啟 DTW 動態手勢辨識 |
| `--rules` | — | 開啟規則姿態偵測 |
| `--all` | — | 開啟全部功能 |
| `--dtw-threshold` | 1.5 | DTW 觸發閾值（越小越嚴格） |
| `--dtw-window` | 2.0 | DTW 滑動視窗秒數 |
| `--record-duration` | 3.0 | 預設錄製秒數 |
| `--no-preview` | — | 不顯示預覽視窗 |
| `--list-gestures` | — | 列出已錄製的手勢 |

---

## 檔案結構

```
azure-kinect-macos/
├── run.sh                      ← 一鍵啟動（下載模型 + uv run）
├── kinect-osc.py               ← 主程式
├── pyproject.toml              ← Python 依賴定義
├── README.md                   ← 本文件
├── MANUAL.md                   ← 使用者手冊
├── .venv/                      ← Python 虛擬環境（uv 自動建立，gitignored）
├── models/                     ← MediaPipe 模型（自動下載，gitignored）
├── gestures/                   ← DTW 手勢範本（錄製後自動建立）
│   └── *.json
└── max-patches/
    ├── azure-kinect-rgb.maxpat ← RGB 直接擷取
    └── azure-kinect-mic.maxpat ← 7ch 麥克風
```
