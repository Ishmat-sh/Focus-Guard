import { Fragment } from "react";
import DriftTimeline from "./DriftTimeline.jsx";

function formatDate(timestamp) {
  if (!timestamp) return "—";
  return new Date(Number(timestamp) * 1000).toLocaleString();
}

function formatDuration(seconds = 0) {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  return `${minutes}m ${String(total % 60).padStart(2, "0")}s`;
}

export default function SessionHistoryTable({
  sessions,
  selectedSession,
  samples,
  loadingTimeline,
  onSelect,
  onStart,
}) {
  if (!sessions.length) {
    return (
      <div className="empty">
        <p>No focus sessions yet.</p>
        <button onClick={onStart}>Start Your First Session</button>
      </div>
    );
  }

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Duration</th>
            <th>Avg score</th>
            {/* Persisted per-session averages make the history scannable at a glance. */}
            <th>Focused</th>
            <th>Distracted</th>
            <th>Top domain</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => {
            const expanded = selectedSession?.id === session.id;
            return (
              <Fragment key={session.id}>
                <tr key={session.id}>
                  <td>{formatDate(session.started_at)}</td>
                  <td className="tabular">{formatDuration(session.elapsed_seconds)}</td>
                  <td className="tabular">
                    {session.average_focus_score == null
                      ? "—"
                      : `${Math.round(session.average_focus_score)}%`}
                  </td>
                  <td>
                    {session.summary
                      ? `${Math.round(session.summary.focus_percentage)}%`
                      : "—"}
                  </td>
                  <td>
                    {session.summary
                      ? `${Math.round(session.summary.distraction_percentage)}%`
                      : "—"}
                  </td>
                  <td>{session.top_domain || "—"}</td>
                  <td>
                    <button className="button-quiet" onClick={() => onSelect(expanded ? null : session)}>
                      {expanded ? "Hide" : "View Details"}
                    </button>
                  </td>
                </tr>
                {expanded && (
                  <tr key={`${session.id}-details`}>
                    <td colSpan="7">
                      <strong>Session {session.id} timeline</strong>
                      {loadingTimeline ? (
                        <p className="loading">Loading session details…</p>
                      ) : (
                        <DriftTimeline
                          samples={samples}
                          sessionDuration={session.elapsed_seconds}
                        />
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
