function formatElapsed(seconds = 0) {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = total % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

export default function TopSessionBar({ session, attention, backendConnected }) {
  const state = attention?.state || "waiting";
  return (
    <div className="session-statusbar">
      <div className="status-indicator">
        <span className="muted">Session</span>
        <strong className="timer">{formatElapsed(session.elapsed_seconds)}</strong>
        {session.id && <span className="badge">ID {session.id}</span>}
      </div>
      <span className={`badge ${state}`}>
        {state === "waiting" ? "Camera ready" : state}
      </span>
      <span className={`status-indicator${backendConnected ? " online" : ""}`}>
        <span className="status-dot" />
        {backendConnected ? "Backend connected" : "Backend offline"}
      </span>
    </div>
  );
}
