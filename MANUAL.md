# Azure Kinect DK — OSC 使用手冊

本工具透過 Azure Kinect 的 RGB 攝影機做即時人體追蹤，將骨架、手勢、姿態等資料以 OSC 送出。

---

## 啟動

```bash
source ~/azure-kinect-osc/bin/activate
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/AntigravityProjects/azure-kinect-dk
python kinect-osc.py --pose --dtw --rules
```

啟動後會出現預覽視窗，按 **Q** 關閉。

---

## OSC 通訊

| 方向 | Port | 用途 |
|------|------|------|
| **送出** → Max/TD | 9000 | 追蹤資料 |
| **接收** ← Max/TD | 9001 | 控制指令 |

---

## 骨架追蹤 (`--pose`)

17 個關節，每個送出 x y z 三個 float（0.0~1.0 正規化座標）。

| OSC 地址 | 部位 |
|----------|------|
| `/pose/detected` | 0 / 1 |
| `/pose/nose` | 鼻子 |
| `/pose/left_shoulder` | 左肩 |
| `/pose/right_shoulder` | 右肩 |
| `/pose/left_elbow` | 左肘 |
| `/pose/right_elbow` | 右肘 |
| `/pose/left_wrist` | 左手腕 |
| `/pose/right_wrist` | 右手腕 |
| `/pose/left_pinky` | 左小指 |
| `/pose/right_pinky` | 右小指 |
| `/pose/left_index` | 左食指 |
| `/pose/right_index` | 右食指 |
| `/pose/left_hip` | 左髖 |
| `/pose/right_hip` | 右髖 |
| `/pose/left_knee` | 左膝 |
| `/pose/right_knee` | 右膝 |
| `/pose/left_ankle` | 左腳踝 |
| `/pose/right_ankle` | 右腳踝 |

**Max 接收範例：**
```
[udpreceive 9000]
    |
[route /pose/left_wrist]
    |
[unpack f f f]
 |   |   |
 x   y   z
```

---

## 規則姿態 (`--rules`)

不需訓練，即時偵測。值為 0 或 1。

| OSC 地址 | 動作 |
|----------|------|
| `/rule/arms_up` | 雙手高舉過頭 |
| `/rule/left_arm_up` | 左手舉起 |
| `/rule/right_arm_up` | 右手舉起 |
| `/rule/squat` | 蹲下 |
| `/rule/lean_left` | 身體左傾 |
| `/rule/lean_right` | 身體右傾 |
| `/rule/hands_together` | 雙手靠近 |
| `/rule/jump` | 跳躍（瞬間 1，之後回 0） |

**Max 接收範例：**
```
[udpreceive 9000]
    |
[route /rule/jump]
    |
[sel 1]
    |
[bang]
```

---

## 靜態手勢 (`--gesture`)

辨識手型，左右手各自送出。

可辨識的手勢：`Open_Palm` `Closed_Fist` `Pointing_Up` `Thumb_Up` `Thumb_Down` `Victory` `ILoveYou`

| OSC 地址 | 值 |
|----------|-----|
| `/gesture/left` | 手勢名 或 "None" |
| `/gesture/right` | 手勢名 或 "None" |
| `/gesture/left/score` | 信心度 0.0~1.0 |
| `/gesture/right/score` | 信心度 0.0~1.0 |

---

## DTW 動態手勢 (`--dtw`)

自訂動態手勢（揮手、畫圈等），需先錄製範本。

每個錄製的手勢都有獨立的 OSC 路徑：

| OSC 地址 | 值 | 說明 |
|----------|-----|------|
| `/dtw/{手勢名}` | 0 / 1 | 該手勢是否觸發 |
| `/dtw/{手勢名}/progress` | 0.0~1.0 | 手勢進行百分比 |
| `/dtw/{手勢名}/following` | 0 / 1 | 是否正在跟蹤此手勢 |
| `/dtw/gesture` | string | 目前最接近的手勢名 |
| `/dtw/score` | float | DTW 距離（越小越像） |

例如錄了 `wave` 和 `circle`：
```
/dtw/wave               0 或 1
/dtw/wave/progress      0.0 ~ 1.0
/dtw/wave/following     0 或 1
/dtw/circle             0 或 1
/dtw/circle/progress    0.0 ~ 1.0
/dtw/circle/following   0 或 1
```

**Max 接收範例：**
```
[udpreceive 9000]
    |
[route /dtw/wave]
    |
[sel 1]
    |
[bang]                  ← wave 完成時觸發
```

用 progress 做漸變效果：
```
[route /dtw/wave/progress]
    |
[slide 5 5]             ← 平滑化
    |
(控制參數)
```

### 錄製手勢

**從鍵盤（預覽視窗）：**

| 按鍵 | 動作 |
|------|------|
| R | 錄製（自動命名） |
| 1~5 | 快速錄製到 gesture_1 ~ gesture_5 |

**從 Max 送 OSC 指令：**

```
[udpsend 127.0.0.1 9001]

/cmd/record wave        ← 錄製 "wave"（倒數 3 秒 → 錄 3 秒）
/cmd/record circle 5    ← 錄製 "circle"，5 秒
/cmd/record/stop        ← 提前停止
/cmd/reload             ← 重新載入範本
/cmd/threshold 1.2      ← 調整觸發敏感度（預設 1.5，越小越嚴格）
```

錄製完成後自動儲存並載入，不需重啟。

---

## 遠端控制指令（從 Max/TD 送到 port 9001）

| OSC 指令 | 說明 |
|----------|------|
| `/cmd/record <name>` | 錄製手勢（倒數 3 秒 → 錄 3 秒） |
| `/cmd/record <name> <sec>` | 指定錄製秒數 |
| `/cmd/record/stop` | 提前停止錄製 |
| `/cmd/reload` | 重新載入 DTW 範本 |
| `/cmd/threshold <float>` | 調整 DTW 閾值（預設 1.5，越小越嚴格） |
| `/cmd/mode/pose <0\|1>` | 即時開關骨架追蹤 |
| `/cmd/mode/gesture <0\|1>` | 即時開關靜態手勢 |
| `/cmd/mode/face <0\|1>` | 即時開關臉部追蹤 |
| `/cmd/mode/dtw <0\|1>` | 即時開關 DTW 手勢辨識 |
| `/cmd/mode/rules <0\|1>` | 即時開關規則姿態 |
| `/cmd/delete <name>` | 刪除手勢範本 |
| `/cmd/list` | 查詢已載入的手勢（回覆送到 `/dtw/list`） |
| `/cmd/stop` | 優雅關閉程式 |

**Max 切換模式範例：**
```
[message /cmd/mode/dtw 0]       ← 關閉 DTW
    |
[udpsend 127.0.0.1 9001]

[message /cmd/mode/face 1]      ← 開啟臉部追蹤
    |
[udpsend 127.0.0.1 9001]
```

**Max 關閉程式範例：**
```
[message /cmd/stop]
    |
[udpsend 127.0.0.1 9001]
```

---

## 臉部追蹤 (`--face`)

| OSC 地址 | 部位 |
|----------|------|
| `/face/detected` | 0 / 1 |
| `/face/nose_tip` | 鼻尖 |
| `/face/left_eye` | 左眼 |
| `/face/right_eye` | 右眼 |
| `/face/mouth_center` | 嘴巴中心 |
| `/face/forehead` | 額頭 |
| `/face/chin` | 下巴 |

---

## 啟動模式速查

| 指令 | 功能 |
|------|------|
| `python kinect-osc.py --pose --dtw --rules` | 骨架 + 動態手勢 + 規則姿態 |
| `python kinect-osc.py --all` | 全部開啟 |
| `python kinect-osc.py --gesture` | 只有靜態手勢 |
| `python kinect-osc.py --face` | 只有臉部 |
| `python kinect-osc.py --osc-port 7000` | 改 OSC 送出 port |
| `python kinect-osc.py --no-preview` | 不開預覽（headless） |
| `python kinect-osc.py --list-gestures` | 列出已錄的手勢 |
