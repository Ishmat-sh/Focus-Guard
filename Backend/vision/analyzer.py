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
    return "looking_at_screen" if 0.3 <= horizontal_ratio <= 0.7 and 0.3 <= vertical_ratio <= 0.7 else "looking_away"


def posture_state(face_height: float, shoulder_distance: float) -> str:
    if shoulder_distance <= 0:
        return "unknown"
    return "upright" if face_height / shoulder_distance >= 0.55 else "slouched"


class FaceAnalyzer:
    def __init__(self, ear_threshold: float = 0.21) -> None:
        self.ear_threshold = ear_threshold
        self.snapshot = VisionSnapshot()

    def process(self, frame) -> VisionSnapshot:
        try:
            import mediapipe as mp
            rgb = frame[:, :, ::-1]
            with mp.solutions.face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True) as mesh:
                result = mesh.process(rgb)
            self.snapshot.face_present = bool(result.multi_face_landmarks)
            if not self.snapshot.face_present:
                self.snapshot.gaze = "looking_away"
        except (ImportError, AttributeError, TypeError, ValueError):
            self.snapshot.face_present = False
        return self.snapshot