from __future__ import annotations

from dataclasses import dataclass
from math import dist


@dataclass
class VisionSnapshot:
    face_present: bool = False
    blink_count: int = 0
    blink_rate: float = 0.0
    head_pose: str = "unknown"
    gaze: str = "looking_away"
    posture: str = "unknown"


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

    def close(self) -> None:
        if self._mesh is not None:
            self._mesh.close()
            self._mesh = None

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
                return self.snapshot

            landmarks = result.multi_face_landmarks[0].landmark
            self.snapshot.face_present = True
            left_eye = [landmarks[i] for i in (33, 133, 159, 145, 153, 155)]
            right_eye = [landmarks[i] for i in (362, 263, 386, 374, 381, 380)]
            left_ear = eye_aspect_ratio([(lm.x, lm.y) for lm in left_eye])
            right_ear = eye_aspect_ratio([(lm.x, lm.y) for lm in right_eye])
            blink_detected = detect_blink((left_ear + right_ear) / 2.0, threshold=self.ear_threshold)
            self.snapshot.blink_count = 1 if blink_detected else 0
            self.snapshot.blink_rate = 1.0 if blink_detected else 0.0

            nose = landmarks[1]
            forehead = landmarks[10]
            chin = landmarks[152]
            left_eye_center = [(landmarks[33].x + landmarks[133].x) / 2.0, (landmarks[33].y + landmarks[133].y) / 2.0]
            right_eye_center = [(landmarks[263].x + landmarks[362].x) / 2.0, (landmarks[263].y + landmarks[362].y) / 2.0]
            face_center_x = (left_eye_center[0] + right_eye_center[0]) / 2.0
            face_center_y = (forehead.y + chin.y) / 2.0
            yaw = (nose.x - face_center_x) * 100.0
            pitch = (nose.y - face_center_y) * 100.0
            self.snapshot.head_pose = head_pose(yaw, pitch)

            eye_center_x = (left_eye_center[0] + right_eye_center[0]) / 2.0
            eye_center_y = (left_eye_center[1] + right_eye_center[1]) / 2.0
            horizontal_ratio = 1.0 - min(abs(nose.x - eye_center_x) / max(abs(right_eye_center[0] - left_eye_center[0]), 1e-6), 1.0)
            vertical_ratio = 1.0 - min(abs(nose.y - eye_center_y) / max(abs(chin.y - forehead.y), 1e-6), 1.0)
            self.snapshot.gaze = gaze_state(horizontal_ratio, vertical_ratio)

            left_shoulder = landmarks[11]
            right_shoulder = landmarks[123]
            shoulder_distance = abs(left_shoulder.x - right_shoulder.x)
            face_height = abs(forehead.y - chin.y)
            self.snapshot.posture = posture_state(face_height, shoulder_distance)
        except (ImportError, AttributeError, TypeError, ValueError):
            self.snapshot.face_present = False
            self.snapshot.gaze = "looking_away"
            self.snapshot.head_pose = "unknown"
            self.snapshot.posture = "unknown"
        return self.snapshot