import { useState } from "react";

const STATES = [
  { name: "focused", score: 88 },
  { name: "drifting", score: 56 },
  { name: "distracted", score: 24 },
];

export default function HomeView({ onOpenAuth, onStart }) {
  const [previewState, setPreviewState] = useState(STATES[0]);
  const focused = previewState.name === "focused" ? 62 : previewState.name === "drifting" ? 38 : 20;
  const distracted = previewState.name === "distracted" ? 52 : previewState.name === "drifting" ? 30 : 14;
  const other = 100 - focused - distracted;

  return (
    <main className="page-wrap hero">
      <section>
        <p className="eyebrow">Calm telemetry for deep work</p>
        <h1>Stay locked in without the clutter.</h1>
        <p className="hero-copy">
          Webcam landmarks estimate focus without saving camera frames. Optional
          browser context reports only the active domain, keeping your session
          data useful and private.
        </p>
        <div className="hero-actions">
          <button onClick={onStart}>Start Focus Session</button>
          <button className="button-secondary" onClick={() => onOpenAuth("signin")}>
            Sign In
          </button>
        </div>
        <p className="muted" style={{ marginTop: "1.25rem", fontSize: "0.78rem" }}>
          Camera access is optional and can be stopped at any time.
        </p>
      </section>

      {/* Keep the preview focused on session outcomes instead of an animated gauge. */}
      <section className={`preview-card state-${previewState.name}`} aria-label="Session summary preview">
        <div className="state-pills" role="group" aria-label="Preview focus states">
          {STATES.map((state) => (
            <button
              className={`state-pill${state.name === previewState.name ? " active" : ""}`}
              key={state.name}
              onClick={() => setPreviewState(state)}
              aria-pressed={state.name === previewState.name}
            >
              {state.name}
            </button>
          ))}
        </div>
        <div className="preview-summary" aria-live="polite">
          <div className="preview-summary-header">
            <div>
              <span className="preview-overline">SESSION SNAPSHOT</span>
              <h2>Attention, at a glance.</h2>
            </div>
            <span className={`badge ${previewState.name}`}>{previewState.name}</span>
          </div>
          <div className="preview-score">
            <span className="score-value">{previewState.score}</span>
            <span>%</span>
            <small>sample focus score</small>
          </div>
          <div className="preview-distribution" role="img" aria-label={`${focused}% focused, ${distracted}% distracted, ${other}% other states`}>
            <span className="summary-bar-focused" style={{ width: `${focused}%` }} />
            <span className="summary-bar-distracted" style={{ width: `${distracted}%` }} />
            <span className="summary-bar-other" style={{ width: `${other}%` }} />
          </div>
          <div className="preview-legend">
            <span><i className="legend-dot" style={{ "--legend-color": "var(--focus-focused)" }} /> Focused {focused}%</span>
            <span><i className="legend-dot" style={{ "--legend-color": "var(--focus-distracted)" }} /> Distracted {distracted}%</span>
          </div>
          <p className="hero-footnote">Illustrative values · your session results are time-weighted</p>
        </div>
      </section>
    </main>
  );
}
