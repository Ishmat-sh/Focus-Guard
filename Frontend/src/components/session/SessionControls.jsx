import { useState } from "react";

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
  const [confirmingEnd, setConfirmingEnd] = useState(false);
  const active = state === "running" || state === "paused";

  async function confirmEnd() {
    await onEnd();
    setConfirmingEnd(false);
  }

  function handleConfirmationKeyDown(event) {
    if (event.key === "Escape" && !pending) {
      setConfirmingEnd(false);
      return;
    }
    if (event.key === "Tab") {
      const buttons = event.currentTarget.querySelectorAll("button:not(:disabled)");
      const firstButton = buttons[0];
      const lastButton = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === firstButton) {
        event.preventDefault();
        lastButton?.focus();
      } else if (!event.shiftKey && document.activeElement === lastButton) {
        event.preventDefault();
        firstButton?.focus();
      }
    }
  }

  return (
    <>
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
              <button className="button-danger" onClick={() => setConfirmingEnd(true)} disabled={pending}>
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
      {/* A designed confirmation avoids accidental session ends and explains what gets saved. */}
      {confirmingEnd && (
        <div
          className="end-session-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !pending) setConfirmingEnd(false);
          }}
        >
          <section
            className="end-session-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="end-session-title"
            aria-describedby="end-session-description"
            onKeyDown={handleConfirmationKeyDown}
          >
            <div className="end-session-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 2" />
              </svg>
            </div>
            <p className="eyebrow">Session control</p>
            <h2 id="end-session-title">End this focus session?</h2>
            <p id="end-session-description">
              We’ll stop vision sampling and save your session summary so you can review your focus and distraction averages.
            </p>
            {pending && (
              <p className="end-session-saving" role="status">
                Saving your session and preparing the summary…
              </p>
            )}
            <div className="end-session-actions">
              <button
                className="button-secondary"
                autoFocus
                onClick={() => setConfirmingEnd(false)}
                disabled={pending}
              >
                Keep working
              </button>
              <button className="button-danger" onClick={confirmEnd} disabled={pending}>
                {pending ? "Ending session…" : "End session"}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
