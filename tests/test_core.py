import sys
import types

import numpy as np

from backend.context.categories import AppCategory, categorize_application
from backend.core.alerts import AlertManager
from backend.core.scoring import AttentionScorer, AttentionState, VisionSignals
from backend.core.session import SessionManager, SessionState
from backend.vision.analyzer import FaceAnalyzer, detect_blink, eye_aspect_ratio, gaze_state, head_pose, posture_state


def test_session_manager_tracks_pause_and_resume() -> None:
    now = [0.0]
    manager = SessionManager(lambda: now[0])
    assert manager.start().state == SessionState.RUNNING
    now[0] = 5.0
    assert manager.pause().elapsed_seconds == 5.0
    now[0] = 20.0
    assert manager.resume().state == SessionState.RUNNING
    now[0] = 23.0
    completed = manager.end()
    assert completed.state == SessionState.COMPLETED
    assert completed.elapsed_seconds == 8.0


def test_attention_scoring_and_categories() -> None:
    scorer = AttentionScorer()
    focused = scorer.score(VisionSignals(True, True, True), AppCategory.PRODUCTIVE.value, "Code")
    distracted = scorer.score(VisionSignals(False, False, False), AppCategory.DISTRACTING.value, "YouTube")
    assert focused.state == AttentionState.FOCUSED
    assert distracted.score < focused.score
    assert categorize_application("Visual Studio Code") == AppCategory.PRODUCTIVE
    assert categorize_application("YouTube") == AppCategory.DISTRACTING


def test_alert_requires_sustained_distraction_and_resets() -> None:
    alerts = AlertManager(threshold_seconds=10, cooldown_seconds=60)
    assert alerts.update(True, True, 0) is None
    assert alerts.update(True, True, 9) is None
    assert alerts.update(True, True, 10) is not None
    assert alerts.update(True, True, 11) is None
    assert alerts.update(True, False, 12) is None


def test_vision_helpers() -> None:
    assert eye_aspect_ratio([(0, 0), (1, 1), (1, -1), (4, 0), (3, -1), (3, 1)]) > 0
    assert detect_blink(0.1)
    assert head_pose(-20, 0) == "left"
    assert gaze_state(0.5, 0.5) == "looking_at_screen"
    assert posture_state(1.0, 1.0) == "upright"


def test_blink_counter_counts_transitions_and_expires_after_one_minute() -> None:
    analyzer = FaceAnalyzer()

    assert analyzer._record_blink_state(True, 0.0) == 0
    assert analyzer._record_blink_state(False, 0.2) == 1
    assert analyzer._record_blink_state(True, 1.0) == 1
    assert analyzer._record_blink_state(False, 1.2) == 2
    assert analyzer._record_blink_state(False, 62.0) == 0


def test_face_analyzer_uses_landmarks_for_face_detection_and_gaze(monkeypatch) -> None:
    class FakeLandmark:
        def __init__(self, x: float, y: float) -> None:
            self.x = x
            self.y = y
            self.z = 0.0

    class FakeFace:
        def __init__(self, landmarks):
            self.landmark = landmarks

    class FakeResult:
        def __init__(self, landmarks):
            self.multi_face_landmarks = [FakeFace(landmarks)]

    class FakeFaceMesh:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def process(self, rgb):
            return FakeResult(landmarks)

    landmarks = [FakeLandmark(0.5, 0.5) for _ in range(468)]
    landmarks[33] = FakeLandmark(0.46, 0.48)
    landmarks[133] = FakeLandmark(0.5, 0.48)
    landmarks[159] = FakeLandmark(0.47, 0.52)
    landmarks[145] = FakeLandmark(0.43, 0.52)
    landmarks[153] = FakeLandmark(0.53, 0.52)
    landmarks[155] = FakeLandmark(0.5, 0.52)
    landmarks[263] = FakeLandmark(0.54, 0.48)
    landmarks[362] = FakeLandmark(0.46, 0.48)
    landmarks[10] = FakeLandmark(0.5, 0.35)
    landmarks[152] = FakeLandmark(0.5, 0.18)
    landmarks[168] = FakeLandmark(0.5, 0.7)
    landmarks[9] = FakeLandmark(0.5, 0.5)

    fake_mp = types.SimpleNamespace(
        solutions=types.SimpleNamespace(face_mesh=types.SimpleNamespace(FaceMesh=FakeFaceMesh))
    )
    monkeypatch.setitem(sys.modules, "mediapipe", fake_mp)

    snapshot = FaceAnalyzer().process(np.zeros((120, 160, 3), dtype=np.uint8))

    assert snapshot.face_present is True
    assert snapshot.head_pose in {"forward", "left", "right", "up", "down"}
    assert snapshot.gaze == "looking_at_screen"
    assert snapshot.posture == "unknown"


def test_unknown_posture_does_not_lower_attention_score() -> None:
    scorer = AttentionScorer()

    result = scorer.score(
        VisionSignals(face_present=True, looking_at_screen=True, upright=None),
        AppCategory.PRODUCTIVE.value,
        "Code",
    )

    assert result.score == 100.0