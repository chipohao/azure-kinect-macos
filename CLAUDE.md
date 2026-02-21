# CLAUDE.md — Azure Kinect DK on macOS

## Overview

Azure Kinect DK 透過 RGB 攝影機 + MediaPipe 做即時人體/手勢/臉部追蹤，以 OSC 送出資料供 Max/MSP 或 TouchDesigner 使用。支援雙向 OSC 控制。

## Architecture

```
Azure Kinect RGB (UVC) → OpenCV → MediaPipe → OSC (port 9000) → Max/MSP / TD
                                                 ← OSC (port 9001) ← Max/MSP / TD
```

- **kinect-osc.py** — 唯一的主程式，包含所有追蹤、DTW、規則偵測、錄製、OSC 收發
- **models/** — MediaPipe 預訓練模型 (.task)，已在 .gitignore
- **gestures/** — DTW 手勢範本 (JSON)，執行時自動建立
- **max-patches/** — Max/MSP 範例 patch

## Dependencies

依賴定義在 `pyproject.toml`，由 `uv` 管理（自動建 `.venv/`）。

```
opencv-contrib-python   # 攝影機擷取（不要同時裝 opencv-python，會衝突）
mediapipe               # 骨架/手勢/臉部追蹤
python-osc              # OSC 收發
numpy                   # 數值計算
```

## Key Conventions

- OSC 地址用 `/模組/名稱` 格式（如 `/pose/left_wrist`, `/rule/jump`, `/dtw/wave`）
- MediaPipe 33 個 landmarks 精簡為 17 個具名關節（只送有意義的）
- DTW 使用 pure Python + numpy 實作（無外部 DTW 套件依賴）
- 座標正規化為 0.0~1.0（MediaPipe 預設輸出）
- 所有控制指令走 `/cmd/*` namespace

## Running

```bash
./run.sh                        # 自動建環境 + 啟動（預設 --pose --dtw --rules）
./run.sh --all                  # 全功能
./run.sh --no-preview           # headless 模式
```

## Hardware Limitations

- **深度攝影機不可用** — Microsoft depth engine 是閉源二進位檔，無 macOS 版
- **IMU 不可用** — 需要 K4A SDK
- **可用**：RGB 攝影機 (UVC, 最高 4K) + 7 聲道麥克風陣列 (UAC, 48kHz)

## Files

| File | Purpose |
|------|---------|
| `kinect-osc.py` | 主程式 |
| `README.md` | 開發者文件（安裝、架構、完整 API） |
| `MANUAL.md` | 使用者手冊（純操作參考） |
| `models/*.task` | MediaPipe 模型（gitignored） |
| `gestures/*.json` | DTW 手勢範本（執行時建立） |
| `max-patches/` | Max/MSP 範例 |
