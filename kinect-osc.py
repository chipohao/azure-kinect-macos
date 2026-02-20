#!/usr/bin/env python3
"""
Azure Kinect DK → MediaPipe → OSC

用法:
    source ~/azure-kinect-osc/bin/activate

    # 即時追蹤
    python kinect-osc.py                        # 預設：姿態 + 手勢
    python kinect-osc.py --pose --dtw           # 骨架 + DTW 動態手勢辨識
    python kinect-osc.py --pose --rules         # 骨架 + 規則姿態偵測
    python kinect-osc.py --all                  # 全部功能

    # 錄製 DTW 手勢範本
    python kinect-osc.py --record wave          # 錄製 "wave" 手勢（3 秒）
    python kinect-osc.py --record circle --duration 4
    python kinect-osc.py --list-gestures        # 列出已錄製的手勢

OSC 輸出:

  姿態 --pose:
    /pose/detected          0 或 1
    /pose/nose              x y z
    /pose/left_wrist        x y z
    ...（共 17 個主要關節）

  靜態手勢 --gesture:
    /gesture/left           手勢名 (Open_Palm, Closed_Fist, Victory, ...)
    /gesture/right          手勢名
    /gesture/left/score     0.0~1.0
    /gesture/right/score    0.0~1.0

  DTW 動態手勢 --dtw (需搭配 --pose):
    /dtw/gesture            辨識到的手勢名稱 (wave, circle, ... 或 none)
    /dtw/score              DTW 距離（越小越像，< threshold 才觸發）
    /dtw/trigger            1（觸發瞬間）或 0

  規則姿態 --rules (需搭配 --pose):
    /rule/arms_up           0 或 1（雙手高舉過頭）
    /rule/left_arm_up       0 或 1
    /rule/right_arm_up      0 或 1
    /rule/squat             0 或 1（蹲下）
    /rule/lean_left         0 或 1（身體左傾）
    /rule/lean_right        0 或 1（身體右傾）
    /rule/hands_together    0 或 1（雙手靠近）
    /rule/jump              1（跳躍瞬間觸發）

  臉部 --face:
    /face/detected          0 或 1
    /face/nose_tip          x y z
    /face/left_eye          x y z
    /face/right_eye         x y z
    /face/mouth_center      x y z
    /face/forehead          x y z
    /face/chin              x y z

  通用:
    /fps                    float
"""

import argparse
import json
import math
import time
import sys
import os
from collections import deque

import cv2
import numpy as np
import mediapipe as mp
from pythonosc import udp_client

BaseOptions = mp.tasks.BaseOptions
VisionRunningMode = mp.tasks.vision.RunningMode

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")
GESTURES_DIR = os.path.join(SCRIPT_DIR, "gestures")

# ── Pose landmark 名稱對照 ──

POSE_LANDMARK_NAMES = {
    0:  "nose",
    11: "left_shoulder",  12: "right_shoulder",
    13: "left_elbow",     14: "right_elbow",
    15: "left_wrist",     16: "right_wrist",
    17: "left_pinky",     18: "right_pinky",
    19: "left_index",     20: "right_index",
    23: "left_hip",       24: "right_hip",
    25: "left_knee",      26: "right_knee",
    27: "left_ankle",     28: "right_ankle",
}

# DTW 追蹤用的關鍵 landmark（用於手勢辨識的軌跡）
DTW_TRACK_LANDMARKS = {
    15: "left_wrist",
    16: "right_wrist",
    0:  "nose",
}

FACE_LANDMARK_NAMES = {
    1:   "nose_tip",
    159: "left_eye",
    386: "right_eye",
    13:  "mouth_center",
    10:  "forehead",
    152: "chin",
}


# ════════════════════════════════════════════════════
#  DTW 動態手勢辨識
# ════════════════════════════════════════════════════

def dtw_distance(seq_a, seq_b):
    """計算兩條軌跡的 DTW 距離（純 Python，無需額外套件）"""
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return float("inf")

    dtw = [[float("inf")] * (m + 1) for _ in range(n + 1)]
    dtw[0][0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0.0
            for k in range(len(seq_a[i - 1])):
                cost += (seq_a[i - 1][k] - seq_b[j - 1][k]) ** 2
            cost = math.sqrt(cost)
            dtw[i][j] = cost + min(dtw[i - 1][j], dtw[i][j - 1], dtw[i - 1][j - 1])

    return dtw[n][m] / max(n, m)  # 正規化


def normalize_trajectory(traj):
    """將軌跡正規化：置中 + 縮放到單位大小"""
    if len(traj) < 2:
        return traj
    arr = np.array(traj, dtype=np.float32)
    center = arr.mean(axis=0)
    arr -= center
    scale = np.abs(arr).max()
    if scale > 1e-6:
        arr /= scale
    return arr.tolist()


class DTWMatcher:
    """DTW 動態手勢比對器"""

    def __init__(self, gestures_dir, window_sec=2.0, threshold=1.5, cooldown=1.0):
        self.templates = {}
        self.window_sec = window_sec
        self.threshold = threshold
        self.cooldown = cooldown
        self.last_trigger_time = 0.0
        # 滑動視窗：存放 (timestamp, {landmark_name: [x, y]})
        self.buffer = deque()
        self.load_templates(gestures_dir)

    def load_templates(self, gestures_dir):
        if not os.path.isdir(gestures_dir):
            return
        for fname in os.listdir(gestures_dir):
            if fname.endswith(".json"):
                path = os.path.join(gestures_dir, fname)
                with open(path, "r") as f:
                    data = json.load(f)
                name = data.get("name", fname.replace(".json", ""))
                # 取主要追蹤 landmark 的軌跡
                landmark_key = data.get("track", "right_wrist")
                raw = [[frame[landmark_key][0], frame[landmark_key][1]]
                       for frame in data["frames"]
                       if landmark_key in frame]
                self.templates[name] = {
                    "trajectory": normalize_trajectory(raw),
                    "track": landmark_key,
                }
        if self.templates:
            print(f"DTW: 載入 {len(self.templates)} 個手勢範本 ({', '.join(self.templates.keys())})")

    def push_frame(self, timestamp, landmarks_dict):
        """推入一幀 landmark 資料"""
        self.buffer.append((timestamp, landmarks_dict))
        # 移除超出視窗的舊資料
        cutoff = timestamp - self.window_sec
        while self.buffer and self.buffer[0][0] < cutoff:
            self.buffer.popleft()

    def match(self):
        """比對目前 buffer 中的軌跡，回傳 (gesture_name, score, is_trigger)"""
        now = time.time()
        if len(self.buffer) < 10:
            return "none", float("inf"), False

        best_name = "none"
        best_score = float("inf")

        for name, tmpl in self.templates.items():
            landmark_key = tmpl["track"]
            # 從 buffer 抽取該 landmark 的軌跡
            live_raw = []
            for _, lm_dict in self.buffer:
                if landmark_key in lm_dict:
                    live_raw.append([lm_dict[landmark_key][0],
                                     lm_dict[landmark_key][1]])
            if len(live_raw) < 10:
                continue

            live_norm = normalize_trajectory(live_raw)
            score = dtw_distance(live_norm, tmpl["trajectory"])
            if score < best_score:
                best_score = score
                best_name = name

        is_trigger = (best_score < self.threshold
                      and (now - self.last_trigger_time) > self.cooldown)
        if is_trigger:
            self.last_trigger_time = now

        return best_name, best_score, is_trigger


def record_gesture(cap, pose_det, name, duration, gestures_dir):
    """錄製手勢範本"""
    os.makedirs(gestures_dir, exist_ok=True)

    print(f"\n錄製手勢: {name}")
    print(f"時間: {duration} 秒")
    print("請準備好動作...")
    print()

    # 倒數
    for i in range(3, 0, -1):
        print(f"  {i}...")
        # 持續擷取畫面避免 buffer 堆積
        start_wait = time.time()
        while time.time() - start_wait < 1.0:
            ret, frame = cap.read()
            if not ret:
                break
            h, w = frame.shape[:2]
            cv2.putText(frame, f"Recording: {name}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(frame, str(i), (w // 2 - 30, h // 2 + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 4)
            cv2.imshow("Azure Kinect - Record", frame)
            cv2.waitKey(1)

    print("  >>> 開始錄製！<<<")
    frames = []
    start_time = time.time()
    ts_base = int(time.time() * 1000)

    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp_ms = int(time.time() * 1000)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = pose_det.detect_for_video(mp_image, timestamp_ms)

        if result.pose_landmarks:
            lm_dict = {}
            for idx, lm_name in DTW_TRACK_LANDMARKS.items():
                lm = result.pose_landmarks[0][idx]
                lm_dict[lm_name] = [lm.x, lm.y, lm.z]
            frames.append(lm_dict)

            # 畫出追蹤點
            h, w = frame.shape[:2]
            for idx in DTW_TRACK_LANDMARKS:
                lm = result.pose_landmarks[0][idx]
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)

        elapsed = time.time() - start_time
        progress = elapsed / duration
        h, w = frame.shape[:2]
        cv2.putText(frame, f"REC: {name} ({elapsed:.1f}s / {duration}s)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        # 進度條
        bar_w = int(w * 0.8)
        bar_x = int(w * 0.1)
        cv2.rectangle(frame, (bar_x, h - 40), (bar_x + bar_w, h - 20),
                      (100, 100, 100), -1)
        cv2.rectangle(frame, (bar_x, h - 40),
                      (bar_x + int(bar_w * progress), h - 20),
                      (0, 0, 255), -1)

        cv2.imshow("Azure Kinect - Record", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("取消錄製")
            return

    cv2.destroyAllWindows()

    if len(frames) < 10:
        print(f"錯誤: 只錄到 {len(frames)} 幀，太少了")
        return

    # 儲存
    data = {
        "name": name,
        "track": "right_wrist",  # 預設追蹤右手腕
        "duration": duration,
        "num_frames": len(frames),
        "frames": frames,
    }
    path = os.path.join(gestures_dir, f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n儲存完成: {path} ({len(frames)} 幀)")
    print(f"追蹤關節: right_wrist")
    print(f"提示: 若要改追蹤 left_wrist 或 nose，編輯 JSON 的 'track' 欄位")


# ════════════════════════════════════════════════════
#  規則姿態偵測
# ════════════════════════════════════════════════════

class RuleDetector:
    """基於規則的姿態偵測"""

    def __init__(self):
        self.prev_hip_y = None
        self.jump_cooldown = 0.0

    def detect(self, landmarks):
        """回傳各規則的觸發狀態 dict"""
        lm = landmarks
        results = {}

        nose = lm[0]
        l_shoulder, r_shoulder = lm[11], lm[12]
        l_wrist, r_wrist = lm[15], lm[16]
        l_hip, r_hip = lm[23], lm[24]
        l_knee, r_knee = lm[25], lm[26]

        mid_shoulder_y = (l_shoulder.y + r_shoulder.y) / 2
        mid_hip_y = (l_hip.y + r_hip.y) / 2
        mid_hip_x = (l_hip.x + r_hip.x) / 2
        mid_shoulder_x = (l_shoulder.x + r_shoulder.x) / 2

        # 雙手舉過頭
        results["arms_up"] = int(
            l_wrist.y < nose.y and r_wrist.y < nose.y
        )
        # 單手
        results["left_arm_up"] = int(l_wrist.y < l_shoulder.y - 0.1)
        results["right_arm_up"] = int(r_wrist.y < r_shoulder.y - 0.1)

        # 蹲下：膝蓋 y 接近臀部 y
        knee_hip_dist = ((l_knee.y + r_knee.y) / 2) - mid_hip_y
        results["squat"] = int(knee_hip_dist < 0.08)

        # 身體傾斜：肩膀中心相對臀部中心的水平偏移
        lean = mid_shoulder_x - mid_hip_x
        results["lean_left"] = int(lean < -0.06)
        results["lean_right"] = int(lean > 0.06)

        # 雙手靠近
        hand_dist = math.sqrt(
            (l_wrist.x - r_wrist.x) ** 2 + (l_wrist.y - r_wrist.y) ** 2
        )
        results["hands_together"] = int(hand_dist < 0.08)

        # 跳躍偵測：臀部 y 突然下降（畫面座標 y 向下，跳起來 y 變小）
        now = time.time()
        results["jump"] = 0
        if self.prev_hip_y is not None and now > self.jump_cooldown:
            dy = self.prev_hip_y - mid_hip_y
            if dy > 0.04:  # 臀部快速上升
                results["jump"] = 1
                self.jump_cooldown = now + 0.8
        self.prev_hip_y = mid_hip_y

        return results


# ════════════════════════════════════════════════════
#  MediaPipe 建立器
# ════════════════════════════════════════════════════

def create_pose_landmarker():
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=os.path.join(MODELS_DIR, "pose_landmarker_full.task")
        ),
        running_mode=VisionRunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp.tasks.vision.PoseLandmarker.create_from_options(options)


def create_gesture_recognizer():
    options = mp.tasks.vision.GestureRecognizerOptions(
        base_options=BaseOptions(
            model_asset_path=os.path.join(MODELS_DIR, "gesture_recognizer.task")
        ),
        running_mode=VisionRunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp.tasks.vision.GestureRecognizer.create_from_options(options)


def create_face_landmarker():
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=os.path.join(MODELS_DIR, "face_landmarker.task")
        ),
        running_mode=VisionRunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp.tasks.vision.FaceLandmarker.create_from_options(options)


# ════════════════════════════════════════════════════
#  OSC 送出
# ════════════════════════════════════════════════════

def send_pose_osc(client, result):
    if result.pose_landmarks:
        client.send_message("/pose/detected", 1)
        for idx, name in POSE_LANDMARK_NAMES.items():
            lm = result.pose_landmarks[0][idx]
            client.send_message(f"/pose/{name}", [lm.x, lm.y, lm.z])
    else:
        client.send_message("/pose/detected", 0)


def send_gesture_osc(client, result):
    left_gesture = "None"
    right_gesture = "None"
    left_score = 0.0
    right_score = 0.0

    if result.gestures:
        for i, (gesture_list, handedness_list) in enumerate(
            zip(result.gestures, result.handedness)
        ):
            gesture_name = gesture_list[0].category_name if gesture_list else "None"
            score = gesture_list[0].score if gesture_list else 0.0
            hand_label = handedness_list[0].category_name if handedness_list else ""
            if hand_label == "Left":
                right_gesture = gesture_name
                right_score = score
            elif hand_label == "Right":
                left_gesture = gesture_name
                left_score = score

    client.send_message("/gesture/left", left_gesture)
    client.send_message("/gesture/right", right_gesture)
    client.send_message("/gesture/left/score", left_score)
    client.send_message("/gesture/right/score", right_score)


def send_face_osc(client, result):
    if result.face_landmarks:
        client.send_message("/face/detected", 1)
        for idx, name in FACE_LANDMARK_NAMES.items():
            lm = result.face_landmarks[0][idx]
            client.send_message(f"/face/{name}", [lm.x, lm.y, lm.z])
    else:
        client.send_message("/face/detected", 0)


# ════════════════════════════════════════════════════
#  畫面繪製
# ════════════════════════════════════════════════════

def draw_pose(frame, result):
    if not result.pose_landmarks:
        return
    h, w = frame.shape[:2]
    landmarks = result.pose_landmarks[0]
    connections = [
        (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
        (11, 23), (12, 24), (23, 24),
        (23, 25), (25, 27), (24, 26), (26, 28),
        (15, 17), (15, 19), (16, 18), (16, 20),
    ]
    for a, b in connections:
        x1, y1 = int(landmarks[a].x * w), int(landmarks[a].y * h)
        x2, y2 = int(landmarks[b].x * w), int(landmarks[b].y * h)
        cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    for idx, name in POSE_LANDMARK_NAMES.items():
        lm = landmarks[idx]
        cx, cy = int(lm.x * w), int(lm.y * h)
        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
        cv2.putText(frame, name.split("_")[-1], (cx + 8, cy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)


def draw_gesture(frame, result):
    if not result.gestures:
        return
    h, w = frame.shape[:2]
    for hand_lms in (result.hand_landmarks or []):
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17),
        ]
        for a, b in connections:
            x1, y1 = int(hand_lms[a].x * w), int(hand_lms[a].y * h)
            x2, y2 = int(hand_lms[b].x * w), int(hand_lms[b].y * h)
            cv2.line(frame, (x1, y1), (x2, y2), (255, 100, 0), 2)
        for lm in hand_lms:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 3, (255, 100, 0), -1)
    for i, (gesture_list, handedness_list) in enumerate(
        zip(result.gestures, result.handedness)
    ):
        gesture_name = gesture_list[0].category_name if gesture_list else "?"
        score = gesture_list[0].score if gesture_list else 0
        hand_label = handedness_list[0].category_name if handedness_list else "?"
        if result.hand_landmarks and i < len(result.hand_landmarks):
            wrist = result.hand_landmarks[i][0]
            tx, ty = int(wrist.x * w), int(wrist.y * h) - 20
        else:
            tx, ty = 10, 80 + i * 40
        text = f"{hand_label}: {gesture_name} ({score:.0%})"
        cv2.putText(frame, text, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)


def draw_face(frame, result):
    if not result.face_landmarks:
        return
    h, w = frame.shape[:2]
    for idx, name in FACE_LANDMARK_NAMES.items():
        lm = result.face_landmarks[0][idx]
        cx, cy = int(lm.x * w), int(lm.y * h)
        cv2.circle(frame, (cx, cy), 4, (255, 200, 0), -1)
        cv2.putText(frame, name, (cx + 6, cy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 200, 0), 1)


def draw_rules(frame, rules_state, y_offset=60):
    """在畫面上顯示規則偵測狀態"""
    y = y_offset
    for name, active in rules_state.items():
        color = (0, 255, 0) if active else (80, 80, 80)
        label = f"{'>>>' if active else '   '} {name}"
        cv2.putText(frame, label, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y += 22


def draw_dtw(frame, dtw_name, dtw_score, is_trigger, y_offset=60):
    """在畫面右上角顯示 DTW 結果"""
    h, w = frame.shape[:2]
    if is_trigger:
        color = (0, 255, 255)
        cv2.putText(frame, f"DTW: {dtw_name}", (w - 300, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)
    elif dtw_name != "none":
        color = (150, 150, 150)
        cv2.putText(frame, f"dtw: {dtw_name} ({dtw_score:.2f})",
                    (w - 300, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


# ════════════════════════════════════════════════════
#  主程式
# ════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Azure Kinect → MediaPipe → OSC")
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--osc-ip", default="127.0.0.1")
    parser.add_argument("--osc-port", type=int, default=9000)

    # 追蹤模式
    parser.add_argument("--pose", action="store_true", help="骨架關節追蹤")
    parser.add_argument("--gesture", action="store_true", help="靜態手勢辨識")
    parser.add_argument("--face", action="store_true", help="臉部追蹤")
    parser.add_argument("--dtw", action="store_true", help="DTW 動態手勢辨識")
    parser.add_argument("--rules", action="store_true", help="規則姿態偵測")
    parser.add_argument("--all", action="store_true", help="全部開啟")

    # DTW 參數
    parser.add_argument("--dtw-threshold", type=float, default=1.5,
                        help="DTW 觸發閾值（越小越嚴格，預設 1.5）")
    parser.add_argument("--dtw-window", type=float, default=2.0,
                        help="DTW 滑動視窗秒數（預設 2.0）")

    # 錄製模式
    parser.add_argument("--record", metavar="NAME", help="錄製手勢範本")
    parser.add_argument("--duration", type=float, default=3.0,
                        help="錄製秒數（預設 3.0）")
    parser.add_argument("--list-gestures", action="store_true",
                        help="列出已錄製的手勢")

    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()

    # 列出手勢
    if args.list_gestures:
        if not os.path.isdir(GESTURES_DIR):
            print("尚無錄製的手勢")
            return
        for fname in sorted(os.listdir(GESTURES_DIR)):
            if fname.endswith(".json"):
                path = os.path.join(GESTURES_DIR, fname)
                with open(path) as f:
                    data = json.load(f)
                print(f"  {data['name']:15s}  {data['num_frames']:3d} 幀  "
                      f"{data['duration']:.1f}s  追蹤: {data['track']}")
        return

    # 預設模式
    if args.all:
        args.pose = args.gesture = args.face = args.dtw = args.rules = True
    if args.record:
        args.pose = True
    if args.dtw or args.rules:
        args.pose = True
    if not args.pose and not args.gesture and not args.face:
        args.pose = True
        args.gesture = True

    # 尋找攝影機
    cam_index = args.camera
    if cam_index is None:
        print("正在尋找攝影機...")
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cam_index = i
                cap.release()
                if cam_index is not None:
                    break
        if cam_index is None:
            print("錯誤: 找不到攝影機")
            sys.exit(1)

    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"攝影機 [{cam_index}] {actual_w}×{actual_h}")

    # 錄製模式
    if args.record:
        pose_det = create_pose_landmarker()
        record_gesture(cap, pose_det, args.record, args.duration, GESTURES_DIR)
        pose_det.close()
        cap.release()
        return

    # OSC
    osc = udp_client.SimpleUDPClient(args.osc_ip, args.osc_port)
    print(f"OSC → {args.osc_ip}:{args.osc_port}")

    # 建立偵測器
    pose_det = create_pose_landmarker() if args.pose else None
    gesture_det = create_gesture_recognizer() if args.gesture else None
    face_det = create_face_landmarker() if args.face else None
    dtw_matcher = DTWMatcher(
        GESTURES_DIR, args.dtw_window, args.dtw_threshold
    ) if args.dtw else None
    rule_det = RuleDetector() if args.rules else None

    features = []
    if pose_det:
        features.append("姿態")
    if gesture_det:
        features.append("靜態手勢")
    if dtw_matcher:
        features.append("DTW動態手勢")
    if rule_det:
        features.append("規則偵測")
    if face_det:
        features.append("臉部")

    print(f"模式: {' + '.join(features)}")
    print("按 Q 結束\n")

    fps_count = 0
    fps = 0.0
    fps_time = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        fps_count += 1
        timestamp_ms = int(time.time() * 1000)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        pose_result = None
        if pose_det:
            pose_result = pose_det.detect_for_video(mp_image, timestamp_ms)
            send_pose_osc(osc, pose_result)
            if not args.no_preview:
                draw_pose(frame, pose_result)

        # DTW
        if dtw_matcher and pose_result and pose_result.pose_landmarks:
            lm_dict = {}
            for idx, lm_name in DTW_TRACK_LANDMARKS.items():
                lm = pose_result.pose_landmarks[0][idx]
                lm_dict[lm_name] = [lm.x, lm.y]
            dtw_matcher.push_frame(time.time(), lm_dict)
            dtw_name, dtw_score, is_trigger = dtw_matcher.match()
            osc.send_message("/dtw/gesture", dtw_name)
            osc.send_message("/dtw/score", dtw_score)
            osc.send_message("/dtw/trigger", int(is_trigger))
            if not args.no_preview:
                draw_dtw(frame, dtw_name, dtw_score, is_trigger)

        # Rules
        if rule_det and pose_result and pose_result.pose_landmarks:
            rules_state = rule_det.detect(pose_result.pose_landmarks[0])
            for name, val in rules_state.items():
                osc.send_message(f"/rule/{name}", val)
            if not args.no_preview:
                draw_rules(frame, rules_state)

        if gesture_det:
            gesture_result = gesture_det.recognize_for_video(mp_image, timestamp_ms)
            send_gesture_osc(osc, gesture_result)
            if not args.no_preview:
                draw_gesture(frame, gesture_result)

        if face_det:
            face_result = face_det.detect_for_video(mp_image, timestamp_ms)
            send_face_osc(osc, face_result)
            if not args.no_preview:
                draw_face(frame, face_result)

        now = time.time()
        if now - fps_time >= 1.0:
            fps = fps_count / (now - fps_time)
            fps_count = 0
            fps_time = now
            osc.send_message("/fps", fps)

        if not args.no_preview:
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Azure Kinect - MediaPipe", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if not args.no_preview:
        cv2.destroyAllWindows()
    for d in [pose_det, gesture_det, face_det]:
        if d:
            d.close()
    print("\n結束")


if __name__ == "__main__":
    main()
