export default function SessionControls({
  state,
  cameraEnabled,
  soundEnabled,
  pending,
  onStart,
  onPauseResume,
  onEnd,
  onToggleSound,
}) {
  const active = state === "running" || state === "paused";

  async function confirmEnd() {
    if (!window.confirm("End this focus session?")) return;
    await onEnd();
  }

  return (
    <div className="panel">
      <p className="eyebrow">Session controls</p>
      <div className="session-controls">
        {!active ? (
          <button onClick={onStart} disabled={pending}>
            {pending ? "Starting…" : cameraEnabled ? "Start Session" : "Enable Camera & Start"}
          </button>
        ) : (
          <>
            <button className="button-secondary" onClick={onPauseResume} disabled={pending}>
              {state === "paused" ? "Resume" : "Pause"}
            </button>
            <button className="button-danger" onClick={confirmEnd} disabled={pending}>
              End Session
            </button>
          </>
        )}
        <button
          className={soundEnabled ? "button-secondary" : "button-quiet"}
          onClick={onToggleSound}
          aria-pressed={soundEnabled}
        >
          Gentle alert {soundEnabled ? "on" : "off"}
        </button>
      </div>
      <p className="muted" style={{ margin: "0.8rem 0 0", fontSize: "0.78rem" }}>
        Alerts are local and optional. Camera frames are analyzed live and are not stored.
      </p>
    </div>
  );
}
