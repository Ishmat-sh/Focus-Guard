from backend.context.categories import AppCategory, categorize_application
from backend.core.alerts import AlertManager
from backend.core.scoring import AttentionScorer, AttentionState, VisionSignals
from backend.core.session import SessionManager, SessionState
from backend.vision.analyzer import detect_blink, eye_aspect_ratio, gaze_state, head_pose, posture_state


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