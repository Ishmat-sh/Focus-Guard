from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import atan2, degrees, dist
from time import monotonic


@dataclass
class VisionSnapshot:
    face_present: bool = False
    blink_count: int = 0
    blink_rate: float = 0.0
    ear: float | None = None
    head_pose: str = "unknown"
    head_yaw_degrees: float | None = None
    head_pitch_degrees: float | None = None
    head_roll_degrees: float | None = None
    gaze: str = "looking_away"
    gaze_offset_x: float | None = None
    gaze_offset_y: float | None = None
    posture: str = "unknown"
    posture_score: float | None = None


def eye_aspect_ratio(eye: list[tuple[float, float]]) -> float:
    if len(eye) != 6:
        raise ValueError("An eye requires six landmarks")
    return (dist(eye[1], eye[5]) + dist(eye[2], eye[4])) / max(2 * dist(eye[0], eye[3]), 1e-9)


def detect_blink(ear: float, threshold: float = 0.21) -> bool:
    return ear < threshold


def head_pose(yaw: float, pitch: float, threshold: float = 15.0) -> str:
    if yaw > threshold:
        return "right"
    if yaw < -threshold:
        return "left"
    if pitch > threshold:
        return "down"
    if pitch < -threshold:
        return "up"
    return "forward"


def gaze_state(horizontal_ratio: float, vertical_ratio: float) -> str:
    return "looking_at_screen" if 0.25 <= horizontal_ratio <= 1.0 and 0.25 <= vertical_ratio <= 1.0 else "looking_away"


def posture_state(face_height: float, shoulder_distance: float) -> str:
    if shoulder_distance <= 0:
        return "unknown"
    return "upright" if face_height / shoulder_distance >= 0.55 else "slouched"


class FaceAnalyzer:
    def __init__(self, ear_threshold: float = 0.21) -> None:
        self.ear_threshold = ear_threshold
        self.snapshot = VisionSnapshot()
        self._mesh = None
        self._eyes_were_closed = False
        self._blink_times: deque[float] = deque()

    def close(self) -> None:
        if self._mesh is not None:
            self._mesh.close()
            self._mesh = None

    def _record_blink_state(self, eyes_closed: bool, now: float | None = None) -> int:
        timestamp = monotonic() if now is None else now
        if self._eyes_were_closed and not eyes_closed:
            self._blink_times.append(timestamp)
        self._eyes_were_closed = eyes_closed
        while self._blink_times and timestamp - self._blink_times[0] > 60:
            self._blink_times.popleft()
        return len(self._blink_times)

    def process(self, frame) -> VisionSnapshot:
        self.snapshot = VisionSnapshot()
        try:
            import mediapipe as mp
            rgb = frame[:, :, ::-1]
            if self._mesh is None:
                self._mesh = mp.solutions.face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True)
            result = self._mesh.process(rgb)
            if not result or not getattr(result, "multi_face_landmarks", None):
                self.snapshot.face_present = False
                self.snapshot.gaze = "looking_away"
                self.snapshot.head_pose = "unknown"
                self.snapshot.posture = "unknown"
                self._eyes_were_closed = False
                return self.snapshot

            landmarks = result.multi_face_landmarks[0].landmark
            self.snapshot.face_present = True
            left_eye = [landmarks[i] for i in (33, 133, 159, 145, 153, 155)]
            right_eye = [landmarks[i] for i in (362, 263, 386, 374, 381, 380)]
            left_ear = eye_aspect_ratio([(lm.x, lm.y) for lm in left_eye])
            right_ear = eye_aspect_ratio([(lm.x, lm.y) for lm in right_eye])
            self.snapshot.ear = (left_ear + right_ear) / 2.0
            eyes_closed = detect_blink(self.snapshot.ear, threshold=self.ear_threshold)
            self.snapshot.blink_count = self._record_blink_state(eyes_closed)
            self.snapshot.blink_rate = float(self.snapshot.blink_count)

            nose = landmarks[1]
            forehead = landmarks[10]
            chin = landmarks[152]
            left_eye_center = [(landmarks[33].x + landmarks[133].x) / 2.0, (landmarks[33].y + landmarks[133].y) / 2.0]
            right_eye_center = [(landmarks[263].x + landmarks[362].x) / 2.0, (landmarks[263].y + landmarks[362].y) / 2.0]
            face_center_x = (left_eye_center[0] + right_eye_center[0]) / 2.0
            face_center_y = (forehead.y + chin.y) / 2.0
            eye_distance = max(abs(right_eye_center[0] - left_eye_center[0]), 1e-6)
            face_height = max(abs(chin.y - forehead.y), 1e-6)
            yaw = degrees(atan2(nose.x - face_center_x, eye_distance))
            pitch = degrees(atan2(nose.y - face_center_y, face_height))
            roll = degrees(
                atan2(
                    right_eye_center[1] - left_eye_center[1],
                    right_eye_center[0] - left_eye_center[0],
                )
            )
            self.snapshot.head_yaw_degrees = yaw
            self.snapshot.head_pitch_degrees = pitch
            self.snapshot.head_roll_degrees = roll
            self.snapshot.head_pose = head_pose(yaw, pitch)

            eye_center_x = (left_eye_center[0] + right_eye_center[0]) / 2.0
            eye_center_y = (left_eye_center[1] + right_eye_center[1]) / 2.0
            self.snapshot.gaze_offset_x = (nose.x - eye_center_x) / eye_distance
            self.snapshot.gaze_offset_y = (nose.y - eye_center_y) / face_height
            horizontal_ratio = 1.0 - min(abs(self.snapshot.gaze_offset_x), 1.0)
            vertical_ratio = 1.0 - min(abs(self.snapshot.gaze_offset_y), 1.0)
            self.snapshot.gaze = gaze_state(horizontal_ratio, vertical_ratio)

            self.snapshot.posture = "unknown"
        except (ImportError, AttributeError, TypeError, ValueError):
            self.snapshot.face_present = False
            self.snapshot.gaze = "looking_away"
            self.snapshot.head_pose = "unknown"
            self.snapshot.posture = "unknown"
            self._eyes_were_closed = False
        return self.snapshot