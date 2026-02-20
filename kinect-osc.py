#!/usr/bin/env python3
"""
Azure Kinect DK → MediaPipe → OSC

用法:
    source ~/azure-kinect-osc/bin/activate
    python kinect-osc.py                    # 預設：姿態 + 手勢
    python kinect-osc.py --pose             # 只有骨架關節
    python kinect-osc.py --gesture          # 只有手勢辨識
    python kinect-osc.py --face             # 臉部追蹤
    python kinect-osc.py --all              # 全部開啟

OSC 輸出（具名關節，不再是 float 海）:

  姿態 --pose:
    /pose/nose              x y z
    /pose/left_shoulder     x y z
    /pose/right_wrist       x y z
    ...（共 17 個主要關節）
    /pose/detected          0 或 1

  手勢 --gesture:
    /gesture/left           手勢名稱 (Closed_Fist, Open_Palm, Pointing_Up, Thumb_Up, Victory, ILoveYou, None)
    /gesture/right          手勢名稱
    /gesture/left/score     辨識信心度 0.0~1.0
    /gesture/right/score    辨識信心度 0.0~1.0

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
import time
import sys
import os

import cv2
import mediapipe as mp
from pythonosc import udp_client

BaseOptions = mp.tasks.BaseOptions
VisionRunningMode = mp.tasks.vision.RunningMode

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")

# ── MediaPipe Pose: 33 landmarks，但只送重要的 17 個 ──

POSE_LANDMARK_NAMES = {
    0:  "nose",
    11: "left_shoulder",
    12: "right_shoulder",
    13: "left_elbow",
    14: "right_elbow",
    15: "left_wrist",
    16: "right_wrist",
    17: "left_pinky",
    18: "right_pinky",
    19: "left_index",
    20: "right_index",
    23: "left_hip",
    24: "right_hip",
    25: "left_knee",
    26: "right_knee",
    27: "left_ankle",
    28: "right_ankle",
}

# ── MediaPipe Face: 478 landmarks，只送 6 個關鍵點 ──

FACE_LANDMARK_NAMES = {
    1:   "nose_tip",
    159: "left_eye",
    386: "right_eye",
    13:  "mouth_center",
    10:  "forehead",
    152: "chin",
}


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


# ── OSC 送出 ──

def send_pose_osc(client, result):
    if result.pose_landmarks:
        client.send_message("/pose/detected", 1)
        for idx, name in POSE_LANDMARK_NAMES.items():
            lm = result.pose_landmarks[0][idx]
            client.send_message(f"/pose/{name}", [lm.x, lm.y, lm.z])
    else:
        client.send_message("/pose/detected", 0)


def send_gesture_osc(client, result):
    # 整理左右手結果
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

            # MediaPipe 的 handedness 是鏡像的（攝影機視角）
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


# ── 畫面繪製 ──

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

    # 畫手部 landmark
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

    # 顯示手勢名稱
    for i, (gesture_list, handedness_list) in enumerate(
        zip(result.gestures, result.handedness)
    ):
        gesture_name = gesture_list[0].category_name if gesture_list else "?"
        score = gesture_list[0].score if gesture_list else 0
        hand_label = handedness_list[0].category_name if handedness_list else "?"

        # 找手腕位置來放文字
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


# ── 主程式 ──

def main():
    parser = argparse.ArgumentParser(description="Azure Kinect → MediaPipe → OSC")
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--osc-ip", default="127.0.0.1")
    parser.add_argument("--osc-port", type=int, default=9000)
    parser.add_argument("--pose", action="store_true", help="骨架關節追蹤")
    parser.add_argument("--gesture", action="store_true", help="手勢辨識")
    parser.add_argument("--face", action="store_true", help="臉部追蹤")
    parser.add_argument("--all", action="store_true", help="全部開啟")
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()

    if args.all:
        args.pose = args.gesture = args.face = True
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

    osc = udp_client.SimpleUDPClient(args.osc_ip, args.osc_port)

    pose_det = create_pose_landmarker() if args.pose else None
    gesture_det = create_gesture_recognizer() if args.gesture else None
    face_det = create_face_landmarker() if args.face else None

    features = []
    if pose_det:
        features.append("姿態")
    if gesture_det:
        features.append("手勢")
    if face_det:
        features.append("臉部")

    print(f"攝影機 [{cam_index}] {actual_w}×{actual_h}")
    print(f"OSC → {args.osc_ip}:{args.osc_port}")
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

        if pose_det:
            pose_result = pose_det.detect_for_video(mp_image, timestamp_ms)
            send_pose_osc(osc, pose_result)
            if not args.no_preview:
                draw_pose(frame, pose_result)

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
