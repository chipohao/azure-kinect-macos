#!/usr/bin/env bash
# Azure Kinect DK — 一鍵啟動
# 用法: ./run.sh [任何 kinect-osc.py 的參數]
#   ./run.sh --pose --dtw --rules
#   ./run.sh --all
#   ./run.sh --list-gestures

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="$SCRIPT_DIR/models"

# 下載 MediaPipe 模型（如果不存在）
mkdir -p "$MODELS_DIR"
BASE_URL="https://storage.googleapis.com/mediapipe-models"
models=(
    "pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
    "gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"
)
for model_path in "${models[@]}"; do
    filename=$(basename "$model_path")
    if [ ! -f "$MODELS_DIR/$filename" ]; then
        echo "下載模型: $filename"
        curl -sL "$BASE_URL/$model_path" -o "$MODELS_DIR/$filename"
    fi
done

# 用 uv 自動管理 venv + 依賴 + 執行
if [ $# -eq 0 ]; then
    exec uv run "$SCRIPT_DIR/kinect-osc.py" --pose --dtw --rules
else
    exec uv run "$SCRIPT_DIR/kinect-osc.py" "$@"
fi
