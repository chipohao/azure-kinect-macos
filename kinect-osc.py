#!/usr/bin/env python3
"""
Azure Kinect DK → MediaPipe → OSC (雙向)

用法:
    source ~/azure-kinect-osc/bin/activate
    python kinect-osc.py                        # 預設：姿態 + 手勢
    python kinect-osc.py --pose --dtw --rules   # 骨架 + DTW + 規則
    python kinect-osc.py --all                  # 全部功能
    python kinect-osc.py --list-gestures        # 列出已錄製的手勢

OSC 送出 (→ Max/TD，預設 port 9000):
    /pose/{joint}           x y z       17 個關節
    /gesture/left           string      靜態手勢名
    /gesture/right          string
    /dtw/gesture            string      動態手勢名
    /dtw/trigger            0 或 1      觸發瞬間
    /rule/{name}            0 或 1      規則姿態
    /face/{point}           x y z       6 個臉部點
    /rec/status             string      錄製狀態 (idle/countdown/recording/saved)
    /rec/progress           float       錄製進度 0.0~1.0
    /fps                    float

OSC 接收 (← Max/TD，預設 port 9001):
    /cmd/record <name>                  開始錄製手勢（預設 3 秒）
    /cmd/record <name> <duration>       指定秒數
    /cmd/record/stop                    提前停止錄製
    /cmd/reload                         重新載入手勢範本
    /cmd/threshold <float>              調整 DTW 閾值

鍵盤快捷鍵（預覽視窗 focus 時）:
    R       開始/停止錄製（名稱自動編號 gesture_001, 002...）
    1-5     快速錄製 gesture_1 ~ gesture_5
    Q       結束
"""

import argparse
import json
import math
import threading
import time
import sys
import os
from collections import deque

import cv2
import numpy as np
import mediapipe as mp
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

BaseOptions = mp.tasks.BaseOptions
VisionRunningMode = mp.tasks.vision.RunningMode

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")
GESTURES_DIR = os.path.join(SCRIPT_DIR, "gestures")

# ── Landmark 名稱 ──

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
#  DTW
# ════════════════════════════════════════════════════

def dtw_distance(seq_a, seq_b):
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return float("inf")
    dtw = [[float("inf")] * (m + 1) for _ in range(n + 1)]
    dtw[0][0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = math.sqrt(sum(
                (seq_a[i-1][k] - seq_b[j-1][k]) ** 2
                for k in range(len(seq_a[i-1]))
            ))
            dtw[i][j] = cost + min(dtw[i-1][j], dtw[i][j-1], dtw[i-1][j-1])
    return dtw[n][m] / max(n, m)


def normalize_trajectory(traj):
    if len(traj) < 2:
        return traj
    arr = np.array(traj, dtype=np.float32)
    arr -= arr.mean(axis=0)
    scale = np.abs(arr).max()
    if scale > 1e-6:
        arr /= scale
    return arr.tolist()


class DTWMatcher:
    def __init__(self, gestures_dir, window_sec=2.0, threshold=1.5, cooldown=1.0):
        self.gestures_dir = gestures_dir
        self.templates = {}
        self.window_sec = window_sec
        self.threshold = threshold
        self.cooldown = cooldown
        self.last_trigger_time = 0.0
        self.buffer = deque()
        self.reload()

    def reload(self):
        self.templates.clear()
        if not os.path.isdir(self.gestures_dir):
            return
        for fname in os.listdir(self.gestures_dir):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(self.gestures_dir, fname)) as f:
                data = json.load(f)
            name = data.get("name", fname.replace(".json", ""))
            track = data.get("track", "right_wrist")
            raw = [[fr[track][0], fr[track][1]]
                   for fr in data["frames"] if track in fr]
            self.templates[name] = {
                "trajectory": normalize_trajectory(raw),
                "track": track,
            }
        if self.templates:
            print(f"DTW: 載入 {len(self.templates)} 個範本 ({', '.join(self.templates.keys())})")
        else:
            print("DTW: 尚無手勢範本（用 /cmd/record 或按 R 錄製）")

    def push_frame(self, timestamp, lm_dict):
        self.buffer.append((timestamp, lm_dict))
        cutoff = timestamp - self.window_sec
        while self.buffer and self.buffer[0][0] < cutoff:
            self.buffer.popleft()

    def match(self):
        now = time.time()
        if len(self.buffer) < 10 or not self.templates:
            return "none", float("inf"), False
        best_name, best_score = "none", float("inf")
        for name, tmpl in self.templates.items():
            track = tmpl["track"]
            live_raw = [[d[track][0], d[track][1]]
                        for _, d in self.buffer if track in d]
            if len(live_raw) < 10:
                continue
            score = dtw_distance(normalize_trajectory(live_raw), tmpl["trajectory"])
            if score < best_score:
                best_score = score
                best_name = name
        is_trigger = (best_score < self.threshold
                      and (now - self.last_trigger_time) > self.cooldown)
        if is_trigger:
            self.last_trigger_time = now
        return best_name, best_score, is_trigger


# ════════════════════════════════════════════════════
#  即時錄製器（在主迴圈中運作，不需重啟）
# ════════════════════════════════════════════════════

class LiveRecorder:
    """在即時追蹤中錄製手勢範本"""

    def __init__(self, gestures_dir, default_duration=3.0):
        self.gestures_dir = gestures_dir
        self.default_duration = default_duration
        self.auto_counter = 0

        # 狀態
        self.state = "idle"  # idle / countdown / recording
        self.name = ""
        self.duration = 0.0
        self.countdown_start = 0.0
        self.record_start = 0.0
        self.frames = []

    def start(self, name=None, duration=None):
        """開始錄製（先進入 3 秒倒數）"""
        if self.state != "idle":
            return
        if name is None:
            self.auto_counter += 1
            name = f"gesture_{self.auto_counter:03d}"
        self.name = name
        self.duration = duration or self.default_duration
        self.state = "countdown"
        self.countdown_start = time.time()
        self.frames = []
        print(f"錄製準備: {self.name} ({self.duration}s)")

    def stop(self):
        """提前停止錄製並儲存"""
        if self.state == "recording":
            self._save()
        self.state = "idle"

    def push_frame(self, lm_dict):
        """每幀呼叫，回傳 (state, progress)"""
        now = time.time()

        if self.state == "countdown":
            elapsed = now - self.countdown_start
            if elapsed >= 3.0:
                self.state = "recording"
                self.record_start = now
                self.frames = []
                print(f">>> 開始錄製 {self.name}！")
            return self.state, max(0, 3.0 - elapsed)

        if self.state == "recording":
            self.frames.append(lm_dict)
            elapsed = now - self.record_start
            progress = elapsed / self.duration
            if elapsed >= self.duration:
                self._save()
                self.state = "idle"
                return "saved", 1.0
            return self.state, progress

        return "idle", 0.0

    def _save(self):
        os.makedirs(self.gestures_dir, exist_ok=True)
        if len(self.frames) < 10:
            print(f"錄製失敗: 只有 {len(self.frames)} 幀")
            return
        data = {
            "name": self.name,
            "track": "right_wrist",
            "duration": self.duration,
            "num_frames": len(self.frames),
            "frames": self.frames,
        }
        path = os.path.join(self.gestures_dir, f"{self.name}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"儲存: {path} ({len(self.frames)} 幀)")


# ════════════════════════════════════════════════════
#  規則姿態
# ════════════════════════════════════════════════════

class RuleDetector:
    def __init__(self):
        self.prev_hip_y = None
        self.jump_cooldown = 0.0

    def detect(self, landmarks):
        lm = landmarks
        r = {}
        nose = lm[0]
        l_sh, r_sh = lm[11], lm[12]
        l_wr, r_wr = lm[15], lm[16]
        l_hp, r_hp = lm[23], lm[24]
        l_kn, r_kn = lm[25], lm[26]

        mid_hp_y = (l_hp.y + r_hp.y) / 2
        mid_hp_x = (l_hp.x + r_hp.x) / 2
        mid_sh_x = (l_sh.x + r_sh.x) / 2

        r["arms_up"] = int(l_wr.y < nose.y and r_wr.y < nose.y)
        r["left_arm_up"] = int(l_wr.y < l_sh.y - 0.1)
        r["right_arm_up"] = int(r_wr.y < r_sh.y - 0.1)
        r["squat"] = int(((l_kn.y + r_kn.y) / 2) - mid_hp_y < 0.08)

        lean = mid_sh_x - mid_hp_x
        r["lean_left"] = int(lean < -0.06)
        r["lean_right"] = int(lean > 0.06)

        hand_dist = math.sqrt((l_wr.x - r_wr.x)**2 + (l_wr.y - r_wr.y)**2)
        r["hands_together"] = int(hand_dist < 0.08)

        now = time.time()
        r["jump"] = 0
        if self.prev_hip_y is not None and now > self.jump_cooldown:
            if self.prev_hip_y - mid_hp_y > 0.04:
                r["jump"] = 1
                self.jump_cooldown = now + 0.8
        self.prev_hip_y = mid_hp_y
        return r


# ════════════════════════════════════════════════════
#  MediaPipe 建立器
# ════════════════════════════════════════════════════

def create_pose_landmarker():
    return mp.tasks.vision.PoseLandmarker.create_from_options(
        mp.tasks.vision.PoseLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=os.path.join(MODELS_DIR, "pose_landmarker_full.task")
            ),
            running_mode=VisionRunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    )

def create_gesture_recognizer():
    return mp.tasks.vision.GestureRecognizer.create_from_options(
        mp.tasks.vision.GestureRecognizerOptions(
            base_options=BaseOptions(
                model_asset_path=os.path.join(MODELS_DIR, "gesture_recognizer.task")
            ),
            running_mode=VisionRunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    )

def create_face_landmarker():
    return mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=os.path.join(MODELS_DIR, "face_landmarker.task")
            ),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    )


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
    left_g, right_g = "None", "None"
    left_s, right_s = 0.0, 0.0
    if result.gestures:
        for gl, hl in zip(result.gestures, result.handedness):
            gn = gl[0].category_name if gl else "None"
            gs = gl[0].score if gl else 0.0
            hand = hl[0].category_name if hl else ""
            if hand == "Left":
                right_g, right_s = gn, gs
            elif hand == "Right":
                left_g, left_s = gn, gs
    client.send_message("/gesture/left", left_g)
    client.send_message("/gesture/right", right_g)
    client.send_message("/gesture/left/score", left_s)
    client.send_message("/gesture/right/score", right_s)

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
    lms = result.pose_landmarks[0]
    for a, b in [(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),
                 (23,24),(23,25),(25,27),(24,26),(26,28),(15,17),(15,19),(16,18),(16,20)]:
        cv2.line(frame,
                 (int(lms[a].x*w), int(lms[a].y*h)),
                 (int(lms[b].x*w), int(lms[b].y*h)), (0,255,0), 2)
    for idx, name in POSE_LANDMARK_NAMES.items():
        lm = lms[idx]
        cx, cy = int(lm.x*w), int(lm.y*h)
        cv2.circle(frame, (cx, cy), 5, (0,0,255), -1)
        cv2.putText(frame, name.split("_")[-1], (cx+8, cy-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255,255,255), 1)

def draw_gesture(frame, result):
    if not result.gestures:
        return
    h, w = frame.shape[:2]
    for hand_lms in (result.hand_landmarks or []):
        for a, b in [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
                     (0,9),(9,10),(10,11),(11,12),(0,13),(13,14),(14,15),(15,16),
                     (0,17),(17,18),(18,19),(19,20),(5,9),(9,13),(13,17)]:
            cv2.line(frame,
                     (int(hand_lms[a].x*w), int(hand_lms[a].y*h)),
                     (int(hand_lms[b].x*w), int(hand_lms[b].y*h)), (255,100,0), 2)
    for i, (gl, hl) in enumerate(zip(result.gestures, result.handedness)):
        gn = gl[0].category_name if gl else "?"
        gs = gl[0].score if gl else 0
        hand = hl[0].category_name if hl else "?"
        if result.hand_landmarks and i < len(result.hand_landmarks):
            wr = result.hand_landmarks[i][0]
            tx, ty = int(wr.x*w), int(wr.y*h) - 20
        else:
            tx, ty = 10, 80 + i*40
        cv2.putText(frame, f"{hand}: {gn} ({gs:.0%})", (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

def draw_face(frame, result):
    if not result.face_landmarks:
        return
    h, w = frame.shape[:2]
    for idx, name in FACE_LANDMARK_NAMES.items():
        lm = result.face_landmarks[0][idx]
        cx, cy = int(lm.x*w), int(lm.y*h)
        cv2.circle(frame, (cx, cy), 4, (255,200,0), -1)
        cv2.putText(frame, name, (cx+6, cy-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255,200,0), 1)

def draw_rules(frame, rules, y_start=60):
    y = y_start
    for name, active in rules.items():
        color = (0,255,0) if active else (80,80,80)
        cv2.putText(frame, f"{'>>>' if active else '   '} {name}",
                    (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y += 22

def draw_dtw(frame, name, score, trigger):
    h, w = frame.shape[:2]
    if trigger:
        cv2.putText(frame, f"DTW: {name}", (w-300, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,255), 3)
    elif name != "none":
        cv2.putText(frame, f"dtw: {name} ({score:.2f})", (w-300, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150,150,150), 1)

def draw_recording(frame, rec_state, rec_value, rec_name):
    h, w = frame.shape[:2]
    if rec_state == "countdown":
        sec = int(rec_value) + 1
        cv2.putText(frame, f"REC {rec_name} in {sec}",
                    (w//2-150, h//2), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 3)
    elif rec_state == "recording":
        # 紅色閃爍圓點
        if int(time.time() * 3) % 2:
            cv2.circle(frame, (w-30, 30), 12, (0,0,255), -1)
        cv2.putText(frame, f"REC: {rec_name}", (w-250, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        # 進度條
        bar_w = int(w * 0.3)
        bar_x = w - bar_w - 20
        cv2.rectangle(frame, (bar_x, 70), (bar_x + bar_w, 85), (100,100,100), -1)
        cv2.rectangle(frame, (bar_x, 70),
                      (bar_x + int(bar_w * rec_value), 85), (0,0,255), -1)
    elif rec_state == "saved":
        cv2.putText(frame, f"Saved: {rec_name}", (w-300, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)


# ════════════════════════════════════════════════════
#  主程式
# ════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Azure Kinect → MediaPipe → OSC")
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--osc-ip", default="127.0.0.1")
    parser.add_argument("--osc-port", type=int, default=9000,
                        help="OSC 送出 port（預設 9000）")
    parser.add_argument("--listen-port", type=int, default=9001,
                        help="OSC 接收 port（預設 9001）")
    parser.add_argument("--pose", action="store_true")
    parser.add_argument("--gesture", action="store_true")
    parser.add_argument("--face", action="store_true")
    parser.add_argument("--dtw", action="store_true")
    parser.add_argument("--rules", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dtw-threshold", type=float, default=1.5)
    parser.add_argument("--dtw-window", type=float, default=2.0)
    parser.add_argument("--record-duration", type=float, default=3.0,
                        help="預設錄製秒數（預設 3.0）")
    parser.add_argument("--list-gestures", action="store_true")
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()

    # 列出手勢
    if args.list_gestures:
        if not os.path.isdir(GESTURES_DIR):
            print("尚無錄製的手勢")
            return
        for fn in sorted(os.listdir(GESTURES_DIR)):
            if fn.endswith(".json"):
                with open(os.path.join(GESTURES_DIR, fn)) as f:
                    d = json.load(f)
                print(f"  {d['name']:15s}  {d['num_frames']:3d} 幀  "
                      f"{d['duration']:.1f}s  追蹤: {d['track']}")
        return

    # 模式設定
    if args.all:
        args.pose = args.gesture = args.face = args.dtw = args.rules = True
    if args.dtw or args.rules:
        args.pose = True
    if not args.pose and not args.gesture and not args.face:
        args.pose = True
        args.gesture = True

    # 攝影機
    cam_index = args.camera
    if cam_index is None:
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

    # OSC 送出
    osc = udp_client.SimpleUDPClient(args.osc_ip, args.osc_port)

    # 偵測器
    pose_det = create_pose_landmarker() if args.pose else None
    gesture_det = create_gesture_recognizer() if args.gesture else None
    face_det = create_face_landmarker() if args.face else None
    dtw_matcher = DTWMatcher(
        GESTURES_DIR, args.dtw_window, args.dtw_threshold
    ) if args.dtw else None
    rule_det = RuleDetector() if args.rules else None
    recorder = LiveRecorder(GESTURES_DIR, args.record_duration)

    # ── OSC 接收（背景執行緒）──
    def on_cmd_record(addr, *osc_args):
        name = str(osc_args[0]) if osc_args else None
        dur = float(osc_args[1]) if len(osc_args) > 1 else None
        recorder.start(name, dur)

    def on_cmd_record_stop(addr, *osc_args):
        recorder.stop()

    def on_cmd_reload(addr, *osc_args):
        if dtw_matcher:
            dtw_matcher.reload()
            osc.send_message("/rec/status", "reloaded")

    def on_cmd_threshold(addr, *osc_args):
        if dtw_matcher and osc_args:
            dtw_matcher.threshold = float(osc_args[0])
            print(f"DTW threshold → {dtw_matcher.threshold}")

    disp = Dispatcher()
    disp.map("/cmd/record/stop", on_cmd_record_stop)
    disp.map("/cmd/record", on_cmd_record)
    disp.map("/cmd/reload", on_cmd_reload)
    disp.map("/cmd/threshold", on_cmd_threshold)

    osc_server = ThreadingOSCUDPServer(("0.0.0.0", args.listen_port), disp)
    server_thread = threading.Thread(target=osc_server.serve_forever, daemon=True)
    server_thread.start()

    # ── 輸出資訊 ──
    features = []
    if pose_det:    features.append("姿態")
    if gesture_det: features.append("靜態手勢")
    if dtw_matcher: features.append("DTW")
    if rule_det:    features.append("規則")
    if face_det:    features.append("臉部")

    print(f"攝影機 [{cam_index}] {actual_w}×{actual_h}")
    print(f"OSC 送出 → {args.osc_ip}:{args.osc_port}")
    print(f"OSC 接收 ← 0.0.0.0:{args.listen_port}")
    print(f"模式: {' + '.join(features)}")
    print(f"鍵盤: R=錄製  1-5=快速錄製  Q=結束\n")

    fps_count = 0
    fps = 0.0
    fps_time = time.time()
    saved_flash_until = 0.0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        fps_count += 1
        timestamp_ms = int(time.time() * 1000)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # ── 姿態 ──
        pose_result = None
        if pose_det:
            pose_result = pose_det.detect_for_video(mp_image, timestamp_ms)
            send_pose_osc(osc, pose_result)
            if not args.no_preview:
                draw_pose(frame, pose_result)

        # ── 錄製（需要 pose 資料）──
        rec_state, rec_value = "idle", 0.0
        if pose_result and pose_result.pose_landmarks and recorder.state != "idle":
            lm_dict = {}
            for idx, lm_name in DTW_TRACK_LANDMARKS.items():
                lm = pose_result.pose_landmarks[0][idx]
                lm_dict[lm_name] = [lm.x, lm.y, lm.z]
            rec_state, rec_value = recorder.push_frame(lm_dict)
            osc.send_message("/rec/status", rec_state)
            osc.send_message("/rec/progress", rec_value if isinstance(rec_value, float) else 0.0)
            if rec_state == "saved":
                saved_flash_until = time.time() + 2.0
                # 自動重新載入 DTW 範本
                if dtw_matcher:
                    dtw_matcher.reload()
        elif recorder.state == "countdown":
            rec_state, rec_value = recorder.push_frame({})
            osc.send_message("/rec/status", rec_state)

        # ── DTW ──
        if dtw_matcher and pose_result and pose_result.pose_landmarks and recorder.state == "idle":
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

        # ── 規則 ──
        if rule_det and pose_result and pose_result.pose_landmarks:
            rules = rule_det.detect(pose_result.pose_landmarks[0])
            for name, val in rules.items():
                osc.send_message(f"/rule/{name}", val)
            if not args.no_preview:
                draw_rules(frame, rules)

        # ── 靜態手勢 ──
        if gesture_det:
            gesture_result = gesture_det.recognize_for_video(mp_image, timestamp_ms)
            send_gesture_osc(osc, gesture_result)
            if not args.no_preview:
                draw_gesture(frame, gesture_result)

        # ── 臉部 ──
        if face_det:
            face_result = face_det.detect_for_video(mp_image, timestamp_ms)
            send_face_osc(osc, face_result)
            if not args.no_preview:
                draw_face(frame, face_result)

        # ── FPS ──
        now = time.time()
        if now - fps_time >= 1.0:
            fps = fps_count / (now - fps_time)
            fps_count = 0
            fps_time = now
            osc.send_message("/fps", fps)

        # ── 預覽 ──
        if not args.no_preview:
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

            # 錄製 UI
            if recorder.state != "idle":
                draw_recording(frame, rec_state, rec_value, recorder.name)
            elif now < saved_flash_until:
                draw_recording(frame, "saved", 1.0, recorder.name)

            cv2.imshow("Azure Kinect - MediaPipe", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            elif key == ord("r"):
                if recorder.state == "idle":
                    recorder.start()
                else:
                    recorder.stop()
            elif key in [ord("1"), ord("2"), ord("3"), ord("4"), ord("5")]:
                n = chr(key)
                recorder.start(f"gesture_{n}")

    # 清理
    cap.release()
    osc_server.shutdown()
    if not args.no_preview:
        cv2.destroyAllWindows()
    for d in [pose_det, gesture_det, face_det]:
        if d:
            d.close()
    print("\n結束")


if __name__ == "__main__":
    main()
