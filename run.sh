#!/usr/bin/env bash
# Azure Kinect DK — 自動建立環境並啟動
# 用法: ./run.sh [任何 kinect-osc.py 的參數]
#   ./run.sh --pose --dtw --rules
#   ./run.sh --all
#   ./run.sh --list-gestures

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# 下載 MediaPipe 模型
download_models() {
    local MODELS_DIR="$SCRIPT_DIR/models"
    mkdir -p "$MODELS_DIR"
    local BASE_URL="https://storage.googleapis.com/mediapipe-models"
    local models=(
        "pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
        "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
        "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
        "gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"
    )
    for model_path in "${models[@]}"; do
        local filename=$(basename "$model_path")
        if [ ! -f "$MODELS_DIR/$filename" ]; then
            echo "下載模型: $filename"
            curl -sL "$BASE_URL/$model_path" -o "$MODELS_DIR/$filename"
        fi
    done
}

# 建立 venv（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    echo "建立 Python 虛擬環境..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    echo "安裝依賴..."
    pip install -q -r "$SCRIPT_DIR/requirements.txt"
    download_models
    echo ""
else
    source "$VENV_DIR/bin/activate"
fi

# 確認模型存在
download_models

# 啟動（預設 --pose --dtw --rules）
if [ $# -eq 0 ]; then
    exec python "$SCRIPT_DIR/kinect-osc.py" --pose --dtw --rules
else
    exec python "$SCRIPT_DIR/kinect-osc.py" "$@"
fi
