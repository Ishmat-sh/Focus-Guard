export default function TelemetryInspector({
  user,
  onClose,
  onResetPassword,
  onDeleteUser,
  onEndSession,
}) {
  if (!user) return null;

  return (
    <div
      className="auth-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="inspector-title">
        <div className="auth-header">
          <div>
            <p className="eyebrow">Telemetry inspector</p>
            <h2 id="inspector-title">{user.name}</h2>
            <p>{user.email} · User #{user.id}</p>
          </div>
          <button className="button-quiet" onClick={onClose}>Close</button>
        </div>
        <div className="panel" style={{ margin: "1rem 0" }}>
          <p>Current session</p>
          <strong>
            {user.current_session
              ? `#${user.current_session.id} · ${user.current_session.state}`
              : "No active session"}
          </strong>
          <p style={{ margin: "0.5rem 0 0" }}>
            Domain: <strong>{user.current_domain?.domain || "No recent domain"}</strong>
          </p>
        </div>
        <p className="eyebrow">Recent state changes</p>
        {user.recent_transitions?.length ? (
          <div className="history-list">
            {[...user.recent_transitions].reverse().map((entry, index) => (
              <div className="history-row" key={`${entry.recorded_at}-${index}`}>
                <span className={`badge ${entry.state}`}>{entry.state}</span>
                <span className="tabular">{Math.round(entry.score)}%</span>
                <span>
                  {entry.app_name || "Unknown context"}
                  <small style={{ display: "block" }}>
                    {new Date(entry.recorded_at * 1000).toLocaleTimeString()}
                  </small>
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty">No attention transitions have been recorded.</p>
        )}
        <p className="eyebrow" style={{ marginTop: "1.25rem" }}>Reported domains</p>
        {user.recent_domains?.length ? (
          <div className="history-list">
            {user.recent_domains.map((entry, index) => (
              <div className="history-row" key={`${entry.session_id}-${entry.recorded_at}-${index}`}>
                <strong>{entry.domain}</strong>
                <span className="badge">{entry.category}</span>
                <small>{new Date(entry.recorded_at * 1000).toLocaleString()}</small>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">No browser domains have been reported.</p>
        )}
        <p className="eyebrow" style={{ marginTop: "1.25rem" }}>Recent sessions</p>
        {user.recent_sessions?.length ? (
          user.recent_sessions.map((session) => (
            <div className="daily-row" key={session.id}>
              <strong>Session #{session.id}</strong>
              <span>{Math.round(session.elapsed_seconds || 0)} seconds · {session.state}</span>
              <span>{session.started_at
                ? new Date(session.started_at * 1000).toLocaleDateString()
                : "—"}</span>
            </div>
          ))
        ) : (
          <p className="muted">No sessions recorded.</p>
        )}
        <div className="session-controls" style={{ marginTop: "1rem" }}>
          {user.current_session && (
            <button className="button-danger" onClick={() => onEndSession(user)}>
              Force-end session
            </button>
          )}
          <button className="button-secondary" onClick={() => onResetPassword(user)}>
            Reset password
          </button>
          <button className="button-danger" onClick={() => onDeleteUser(user)}>
            Delete user
          </button>
        </div>
      </aside>
    </div>
  );
}
