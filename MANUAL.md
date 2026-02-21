# Azure Kinect DK — Quick Reference

> 完整文件見 [README.md](README.md)

---

## 1. 啟動

```
./run.sh                          ← 預設模式
./run.sh --all                    ← 全功能
./run.sh --no-preview             ← 無視窗
```

---

## 2. OSC 埠號

```
Python ──(9000)──→ Max / TD       追蹤資料
Python ←──(9001)── Max / TD       控制指令
```

---

## 3. 收資料（Max 端收 port 9000）

```
[udpreceive 9000]
       |
[route /pose/left_wrist]     ← 換成你要的地址
       |
[unpack f f f]               ← x  y  z
```

### 骨架 `/pose/*`  ← 17 點，每點 x y z

```
         nose
          |
  l_shoulder─r_shoulder
     |           |
  l_elbow     r_elbow
     |           |
  l_wrist     r_wrist
  ├ l_pinky   ├ r_pinky
  └ l_index   └ r_index
     |           |
   l_hip───────r_hip
     |           |
   l_knee     r_knee
     |           |
   l_ankle    r_ankle
```

### 規則 `/rule/*`  ← 值為 0 或 1

| 地址 | 觸發條件 |
|------|---------|
| `arms_up` | 雙手高舉 |
| `left_arm_up` | 左手舉起 |
| `right_arm_up` | 右手舉起 |
| `squat` | 蹲下 |
| `lean_left` | 左傾 |
| `lean_right` | 右傾 |
| `hands_together` | 雙手靠近 |
| `jump` | 跳躍（瞬發） |

### 手勢 `/gesture/*`

| 地址 | 值 |
|------|---|
| `left` / `right` | `Open_Palm` `Closed_Fist` `Pointing_Up` `Thumb_Up` `Thumb_Down` `Victory` `ILoveYou` 或 `None` |
| `left/score` / `right/score` | 0.0~1.0 |

### DTW `/dtw/*`  ← 自訂動態手勢

| 地址 | 值 | 用途 |
|------|---|------|
| `/dtw/{名稱}` | 0 / 1 | 觸發 |
| `/dtw/{名稱}/progress` | 0.0~1.0 | 進度 |
| `/dtw/{名稱}/following` | 0 / 1 | 跟蹤中 |
| `/dtw/gesture` | string | 最近手勢名 |
| `/dtw/score` | float | 距離 |

### 臉部 `/face/*`  ← 6 點，每點 x y z

`nose_tip` `left_eye` `right_eye` `mouth_center` `forehead` `chin`

### 其他

| 地址 | 值 |
|------|---|
| `/fps` | float |
| `/rec/status` | `idle` / `countdown` / `recording` / `saved` |
| `/rec/progress` | 0.0~1.0 |

---

## 4. 送指令（Max 端送 port 9001）

```
[message /cmd/record wave]
       |
[udpsend 127.0.0.1 9001]
```

| 指令 | 說明 |
|------|------|
| `/cmd/record <name>` | 錄手勢（3s 倒數 → 3s 錄） |
| `/cmd/record <name> <sec>` | 指定秒數 |
| `/cmd/record/stop` | 停止錄製 |
| `/cmd/reload` | 重載 DTW 範本 |
| `/cmd/threshold <f>` | DTW 閾值（預設 1.5，↓ = 更嚴格） |
| `/cmd/mode/pose <0\|1>` | 開關骨架 |
| `/cmd/mode/gesture <0\|1>` | 開關手勢 |
| `/cmd/mode/face <0\|1>` | 開關臉部 |
| `/cmd/mode/dtw <0\|1>` | 開關 DTW |
| `/cmd/mode/rules <0\|1>` | 開關規則 |
| `/cmd/delete <name>` | 刪除手勢 |
| `/cmd/list` | 查詢手勢（回覆在 `/dtw/list`） |
| `/cmd/stop` | 關閉程式 |

---

## 5. 錄製 DTW 手勢

```
 ① 送指令                    ② 倒數 3 秒         ③ 做動作 3 秒        ④ 自動儲存
 /cmd/record wave     →     3... 2... 1...   →    🔴 錄製中        →   ✓ 立即可用
```

**鍵盤**（視窗 focus 時）：`R` = 錄製　`1`~`5` = 快速錄到 gesture_1~5　`Q` = 離開

---

## 6. 常用 Max 接線

**觸發事件：**
```
[udpreceive 9000] → [route /rule/jump] → [sel 1] → [bang]
```

**連續值控制：**
```
[udpreceive 9000] → [route /pose/left_wrist] → [unpack f f f] → x y z
```

**DTW 進度漸變：**
```
[udpreceive 9000] → [route /dtw/wave/progress] → [slide 5 5] → (控制參數)
```

**從 Max 錄製：**
```
[message /cmd/record circle 5] → [udpsend 127.0.0.1 9001]
```
