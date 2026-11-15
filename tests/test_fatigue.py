import pytest

from backend.core.fatigue import FatigueEstimator


def test_fatigue_estimator_uses_timed_perclos_and_blink_durations() -> None:
    estimator = FatigueEstimator(window_seconds=60)

    estimator.update(0.1, now=0)
    sample = estimator.update(0.3, now=0.4)
    sample = estimator.update(0.1, now=1)
    sample = estimator.update(0.3, now=1.7)

    assert sample.perclos == pytest.approx(1.1 / 1.7)
    assert sample.slow_blink_count == 1
    assert sample.average_blink_duration_seconds == pytest.approx(0.55)


def test_break_suggestion_requires_sustained_high_fatigue_risk() -> None:
    estimator = FatigueEstimator(
        window_seconds=60,
        break_threshold=70,
        sustained_seconds=15,
    )

    assert estimator.update(0.1, now=0).break_suggestion is False
    assert estimator.update(0.1, now=5).break_suggestion is False
    assert estimator.update(0.1, now=10).break_suggestion is False
    assert estimator.update(0.1, now=15).break_suggestion is False
    assert estimator.update(0.1, now=20).break_suggestion is True


def test_fatigue_state_resets_when_session_is_inactive() -> None:
    estimator = FatigueEstimator()
    estimator.update(0.1, now=0)
    estimator.update(0.1, now=1)

    snapshot = estimator.update(None, now=2, active=False)

    assert snapshot.risk == 0
    assert snapshot.perclos is None
    assert snapshot.break_suggestion is False


def test_fatigue_estimator_rejects_non_monotonic_timestamps() -> None:
    estimator = FatigueEstimator()
    estimator.update(0.3, now=2)

    with pytest.raises(ValueError, match="non-decreasing"):
        estimator.update(0.3, now=1)


def test_yawn_detection_requires_a_sustained_open_mouth_and_counts_once() -> None:
    estimator = FatigueEstimator(yawn_duration_seconds=1.0)

    assert estimator.update(0.3, mouth_aspect_ratio=0.7, now=0).yawn_count == 0
    assert estimator.update(0.3, mouth_aspect_ratio=0.7, now=1.1).yawn_count == 1
    assert estimator.update(0.3, mouth_aspect_ratio=0.7, now=2.2).yawn_count == 1
    assert estimator.update(0.3, mouth_aspect_ratio=0.2, now=2.3).yawn_count == 1
