const STATE_NAMES = new Set(["focused", "drifting", "distracted"]);

export default function FocusCockpit({ attention, focusStreak = 0 }) {
  const score = Math.max(0, Math.min(100, Math.round(attention?.score || 0)));
  const focusState = STATE_NAMES.has(attention?.state) ? attention.state : "drifting";
  const streakMinutes = Math.floor(focusStreak / 60);
  const streakSeconds = Math.floor(focusStreak % 60);

  return (
    <section className={`session-hero state-${focusState}`} aria-label="Live focus">
      {/* The live score stays prominent while a quiet meter replaces the animated ring. */}
      <div className="focus-readout" aria-live="polite">
        <p className="eyebrow">Current estimate</p>
        <div className="focus-readout-line">
          <strong className="score-value">{attention ? score : "—"}</strong>
          <span className="focus-readout-percent">/ 100</span>
        </div>
        <span className="gauge-state">{attention ? focusState : "Waiting for camera"}</span>
        <div
          className="focus-score-track"
          role="progressbar"
          aria-label="Current focus estimate"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={attention ? score : 0}
        >
          <span style={{ width: `${attention ? score : 0}%` }} />
        </div>
        <small className="muted">
          Current run{" "}
          <span className="tabular">{streakMinutes}:{String(streakSeconds).padStart(2, "0")}</span>
        </small>
      </div>
    </section>
  );
}
