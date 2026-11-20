import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "../services/api.js";
import PasswordInput from "./PasswordInput.jsx";

function dateInputValue(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

export function ChangePasswordView({ apiFetch, onComplete, onLogout }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await apiRequest(apiFetch, "/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: password }),
      });
      onComplete(result);
    } catch (changeError) {
      setError(changeError.message || "Could not update your password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-wrap">
      <section className="panel" style={{ maxWidth: "480px", margin: "3rem auto" }}>
        <p className="eyebrow">Account security</p>
        <h1>Choose a new password</h1>
        <p>Your temporary password must be replaced before continuing.</p>
        <form className="form-stack" onSubmit={submit}>
          <label>
            New password
            <PasswordInput
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <label>
            Confirm password
            <PasswordInput
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          {error && <p className="error-banner" role="alert">{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? "Saving…" : "Update password"}
          </button>
        </form>
        <button className="button-quiet" onClick={onLogout}>Log out</button>
      </section>
    </main>
  );
}

export function AnalyticsView({ apiFetch }) {
  const today = new Date();
  const initialStart = new Date(today);
  initialStart.setDate(today.getDate() - 6);
  const [startDate, setStartDate] = useState(dateInputValue(initialStart));
  const [endDate, setEndDate] = useState(dateInputValue(today));
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    const query = `?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
    try {
      const [weekly, heatmap, streaks, domains] = await Promise.all([
        apiRequest(apiFetch, `/analytics/weekly${query}`),
        apiRequest(apiFetch, `/analytics/heatmap${query}`),
        apiRequest(apiFetch, `/analytics/streaks${query}&minimum_minutes=1`),
        apiRequest(apiFetch, `/analytics/domains${query}`),
      ]);
      setData({ weekly, heatmap, streaks, domains });
    } catch (loadError) {
      setError(loadError.message || "Could not load analytics.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const current = data?.weekly?.comparison?.current;
  return (
    <main className="feature-page">
      <header>
        <p className="eyebrow">Patterns, not pressure</p>
        <h1>Analytics</h1>
      </header>
      <section className="panel">
        <div className="date-controls">
          <label>Start date<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
          <label>End date<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
          <button onClick={load} disabled={loading}>{loading ? "Loading…" : "Apply"}</button>
        </div>
      </section>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {current && (
        <section className="kpi-grid" style={{ marginTop: "1rem" }}>
          {[
            ["Focused time", `${Math.round(current.total_focus_seconds / 60)} min`],
            ["Average focus score", current.average_focus_score == null ? "—" : `${Math.round(current.average_focus_score)}%`],
            ["Distraction transitions", current.distraction_count],
            ["Longest streak", `${Math.round((data.streaks?.longest_streak_seconds || 0) / 60)} min`],
          ].map(([label, value]) => (
            <article className="kpi-card" key={label}>
              <span className="kpi-label">{label}</span>
              <strong className="kpi-value tabular">{value}</strong>
            </article>
          ))}
        </section>
      )}
      {data && (
        <div className="dashboard-grid" style={{ marginTop: "1rem" }}>
          <section className="panel">
            <p className="eyebrow">Daily activity</p>
            <h2>Focus trend</h2>
            {data.weekly.daily.length ? (
              <div className="daily-table">
                {data.weekly.daily.map((day) => (
                  <div className="daily-row" key={day.date}>
                    <strong>{day.date}</strong>
                    <span>{Math.round(day.total_focus_seconds / 60)} focused min</span>
                    <span>{day.average_score == null ? "No score" : `${Math.round(day.average_score)}% average`}</span>
                  </div>
                ))}
              </div>
            ) : <p className="empty">No analytics data in this date range.</p>}
          </section>
          <section className="panel">
            <p className="eyebrow">Context</p>
            <h2>Most reported domains</h2>
            {data.domains.length ? data.domains.slice(0, 8).map((domain) => (
              <div className="daily-row" key={`${domain.domain}-${domain.category}`}>
                <strong>{domain.domain}</strong>
                <span className="badge">{domain.category}</span>
                <span>{domain.sample_count} reports</span>
              </div>
            )) : <p className="empty">No browser domain context in this range.</p>}
          </section>
          <section className="panel">
            <p className="eyebrow">Weekly rhythm</p>
            <h2>Day and hour heatmap</h2>
            <div className="heatmap" role="img" aria-label="Weekly focus heatmap">
              {data.heatmap.cells.map((cell) => {
                // Muted tones use the same focused/drifting/distracted palette as session views.
                const tone = !cell.sample_count
                  ? "empty"
                  : cell.average_score >= 75
                    ? "high"
                    : cell.average_score >= 50
                      ? "medium"
                      : "low";
                return (
                  <div
                    className={`heatmap-cell heatmap-${tone}`}
                    key={`${cell.day_of_week}-${cell.hour}`}
                    title={`${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][cell.day_of_week]} ${cell.hour}:00 · ${cell.average_score == null ? "No data" : `${Math.round(cell.average_score)}%`}`}
                  />
                );
              })}
            </div>
            <div className="heatmap-legend">
              <span>Low</span><span>Moderate</span><span>High</span>
            </div>
          </section>
          <section className="panel">
            <p className="eyebrow">Deep work</p>
            <h2>Focus streaks</h2>
            {data.streaks.streaks.length ? data.streaks.streaks.slice(0, 8).map((streak) => (
              <div className="daily-row" key={`${streak.session_id}-${streak.started_at}`}>
                <strong>Session #{streak.session_id}</strong>
                <span>{Math.round(streak.duration_seconds / 60)} min</span>
                <span>{new Date(streak.started_at * 1000).toLocaleString()}</span>
              </div>
            )) : <p className="empty">No focus streaks recorded in this range.</p>}
          </section>
        </div>
      )}
    </main>
  );
}

export function CoachingView({ apiFetch }) {
  const [insights, setInsights] = useState([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setInsights(await apiRequest(apiFetch, "/insights") || []);
      setError("");
    } catch (loadError) {
      setError(loadError.message || "Could not load coaching insights.");
    }
  }

  useEffect(() => {
    load();
  }, [apiFetch]);

  async function act(insightId, action, feedback) {
    try {
      await apiRequest(apiFetch, `/insights/${insightId}/${action}`, {
        method: "POST",
        ...(feedback
          ? {
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ feedback }),
            }
          : {}),
      });
      await load();
    } catch (actionError) {
      setError(actionError.message || "Could not update this insight.");
    }
  }

  return (
    <main className="feature-page">
      <p className="eyebrow">Small, actionable guidance</p>
      <h1>Coaching</h1>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {!error && insights.length === 0 ? (
        <p className="empty">No coaching insights yet. Complete a focus session to generate them.</p>
      ) : (
        <div className="insight-list">
          {insights.map((insight) => (
            <article className="insight-card" key={insight.id}>
              <div className="controls-row">
                <span className="badge">{insight.source === "ai" ? "AI-written" : "Rule-based"}</span>
                <small>Session #{insight.session_id}</small>
              </div>
              <p style={{ marginTop: "1rem", lineHeight: 1.65 }}>{insight.message}</p>
              <div className="insight-actions">
                <button className="button-secondary" onClick={() => act(insight.id, "feedback", "helpful")}>Helpful</button>
                <button className="button-secondary" onClick={() => act(insight.id, "feedback", "not_helpful")}>Not helpful</button>
                {!insight.dismissed && (
                  <button className="button-quiet" onClick={() => act(insight.id, "dismiss")}>Dismiss</button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}

export function CollectionView({ apiFetch, onBack }) {
  const [session, setSession] = useState(null);
  const [labels, setLabels] = useState([]);
  const [consented, setConsented] = useState(false);
  const [message, setMessage] = useState("");
  const [labelBusy, setLabelBusy] = useState(false);

  async function load() {
    try {
      const current = await apiRequest(apiFetch, "/sessions/current");
      setSession(current);
      if (current?.id) {
        const [consent, recorded] = await Promise.all([
          apiRequest(apiFetch, `/sessions/${current.id}/collection`),
          apiRequest(apiFetch, `/sessions/${current.id}/labels`),
        ]);
        setConsented(Boolean(consent?.consent));
        setLabels(recorded || []);
      }
    } catch (loadError) {
      setMessage(loadError.message || "Could not load collection status.");
    }
  }

  useEffect(() => {
    load();
  }, [apiFetch]);

  async function updateConsent(nextConsent) {
    if (!session?.id) return;
    try {
      await apiRequest(apiFetch, `/sessions/${session.id}/collection/consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consent: nextConsent }),
      });
      setConsented(nextConsent);
      setMessage(nextConsent
        ? "Consent saved. Only derived numerical features are stored."
        : "Collection disabled for this session.");
    } catch (consentError) {
      setMessage(consentError.message || "Could not save consent.");
    }
  }

  async function addLabel(label) {
    if (!session?.id || session.elapsed_seconds < 30) {
      setMessage("Run a session for at least 30 seconds before labeling it.");
      return;
    }
    setLabelBusy(true);
    try {
      await apiRequest(apiFetch, `/sessions/${session.id}/labels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_elapsed_seconds: Math.max(0, session.elapsed_seconds - 30),
          end_elapsed_seconds: session.elapsed_seconds,
          label,
        }),
      });
      setMessage(`Recorded ${label} for the latest 30 seconds.`);
      await load();
    } catch (labelError) {
      setMessage(labelError.message || "Could not save label.");
    } finally {
      setLabelBusy(false);
    }
  }

  async function exportDataset() {
    if (!session?.id) {
      setMessage("Start a session before exporting.");
      return;
    }
    const response = await apiFetch(`/sessions/${session.id}/dataset.csv`);
    if (!response.ok) {
      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      setMessage(payload?.detail || "Could not export dataset.");
      return;
    }
    downloadBlob(await response.blob(), `focus-guard-session-${session.id}.csv`);
  }

  const labelledMinutes = labels.reduce(
    (total, label) => total + Math.max(
      0,
      (label.end_elapsed_seconds || 0) - (label.start_elapsed_seconds || 0),
    ),
    0,
  ) / 60;

  return (
    <main className="feature-page">
      <button className="button-quiet" onClick={onBack}>← Dashboard</button>
      <p className="eyebrow">Optional, explicit consent</p>
      <h1>Data collection</h1>
      <section className="panel">
        <h2>Privacy consent</h2>
        <p>Collection stores numerical vision and context features only. Raw frames, recordings, full URLs, and page titles are never stored.</p>
        <button
          className={consented ? "button-secondary" : ""}
          onClick={() => updateConsent(!consented)}
          disabled={!session?.id}
        >
          {consented ? "Disable collection" : "I consent to collection"}
        </button>
        <span className="badge" style={{ marginLeft: "0.5rem" }}>
          {consented ? "Enabled for this session" : "Disabled"}
        </span>
      </section>
      {message && <p className="status-message" role="status">{message}</p>}
      <div className="kpi-grid" style={{ marginTop: "1rem" }}>
        <article className="kpi-card"><span className="kpi-label">Labelled minutes</span><strong className="kpi-value tabular">{labelledMinutes.toFixed(1)}</strong></article>
        <article className="kpi-card"><span className="kpi-label">Recorded labels</span><strong className="kpi-value tabular">{labels.length}</strong></article>
      </div>
      <section className="panel" style={{ marginTop: "1rem" }}>
        <h2>Label the last 30 seconds</h2>
        <p>Labels are only saved when collection consent is enabled for the running session.</p>
        <div className="session-controls">
          {["focused", "drifting", "distracted", "fatigued"].map((label) => (
            <button
              className="button-secondary"
              key={label}
              onClick={() => addLabel(label)}
              disabled={!consented || session?.state !== "running" || labelBusy}
            >
              {label}
            </button>
          ))}
          <button onClick={exportDataset} disabled={!consented}>Export session CSV</button>
        </div>
      </section>
    </main>
  );
}

export function SettingsView({ apiFetch }) {
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [sessions, setSessions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [sessionError, setSessionError] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const loadSessions = useCallback(async (signal) => {
    setLoadingSessions(true);
    setSessionError("");
    try {
      const result = await apiRequest(
        apiFetch,
        "/history",
        signal ? { signal } : undefined,
      );
      if (!Array.isArray(result)) throw new Error("Session data returned an unexpected format.");
      if (!signal?.aborted) setSessions(result);
    } catch (loadError) {
      if (!signal?.aborted) {
        setSessionError(loadError.message || "Could not load session data.");
      }
    } finally {
      if (!signal?.aborted) setLoadingSessions(false);
    }
  }, [apiFetch]);

  useEffect(() => {
    const controller = new AbortController();
    loadSessions(controller.signal);
    return () => controller.abort();
  }, [loadSessions]);

  async function exportData() {
    setBusy("export");
    setMessage("");
    try {
      const response = await apiFetch("/data/export.json");
      if (!response.ok) throw new Error("Could not export account data.");
      downloadBlob(await response.blob(), "focus-guard-export.json");
      setMessage("Your data export has been downloaded.");
    } catch (exportError) {
      setMessage(exportError.message || "Could not export data.");
    } finally {
      setBusy("");
    }
  }

  async function deleteAllData() {
    setBusy("delete");
    setMessage("");
    try {
      const result = await apiRequest(apiFetch, "/data", { method: "DELETE" });
      const count = result.deleted_sessions || 0;
      setSessions([]);
      setSessionError("");
      setConfirmingDelete(false);
      setMessage(`Deleted session and derived data. ${count} session${count === 1 ? "" : "s"} removed.`);
    } catch (deleteError) {
      setMessage(deleteError.message || "Could not delete account data.");
      setConfirmingDelete(false);
    } finally {
      setBusy("");
    }
  }

  function handleDeleteDialogKeyDown(event) {
    if (event.key === "Escape" && !busy) {
      setConfirmingDelete(false);
      return;
    }
    if (event.key !== "Tab") return;
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

  return (
    <main className="feature-page settings-page">
      <header className="settings-header">
        <p className="eyebrow">Your data, your choice</p>
        <h1>Settings</h1>
        <p className="muted">Export a copy of your data or permanently delete your session data.</p>
      </header>
      {message && <p className="status-message" role="status">{message}</p>}
      {/* Keep account settings focused on the two data actions requested. */}
      {/* Show session averages only; detailed telemetry remains available through export. */}
      <section className="panel settings-session-data">
        <div className="settings-session-header">
          <div>
            <p className="eyebrow">Your stored data</p>
            <h2>Recent sessions</h2>
          </div>
          {!loadingSessions && <span className="badge">{sessions.length} shown</span>}
        </div>
        {loadingSessions ? (
          <p className="loading">Loading session data…</p>
        ) : sessionError ? (
          <div className="settings-load-error" role="alert">
            <p>{sessionError}</p>
            <button className="button-secondary" onClick={() => loadSessions()} disabled={loadingSessions}>
              Try again
            </button>
          </div>
        ) : sessions.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Duration</th>
                  <th>Avg score</th>
                  <th>Focused</th>
                  <th>Distracted</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => {
                  const summary = session.summary;
                  const hasObservedData = Number(summary?.observed_seconds) > 0;
                  const duration = Math.max(0, Math.floor(Number(session.elapsed_seconds) || 0));
                  return (
                    <tr key={session.id}>
                      <td>
                        {session.started_at
                          ? new Date(Number(session.started_at) * 1000).toLocaleString()
                          : "—"}
                      </td>
                      <td className="tabular">{Math.floor(duration / 60)}m {String(duration % 60).padStart(2, "0")}s</td>
                      <td className="tabular">
                        {summary?.average_focus_score == null
                          ? "—"
                          : `${Math.round(summary.average_focus_score)}%`}
                      </td>
                      <td className="tabular">
                        {hasObservedData ? `${Math.round(summary.focus_percentage)}%` : "—"}
                      </td>
                      <td className="tabular">
                        {hasObservedData ? `${Math.round(summary.distraction_percentage)}%` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty">No sessions have been recorded yet.</p>
        )}
      </section>
      <div className="settings-data-grid">
        <section className="panel settings-data-card">
          <div className="settings-action-icon export-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3v12m0 0 4-4m-4 4-4-4" />
              <path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" />
            </svg>
          </div>
          <p className="eyebrow">Take your data with you</p>
          <h2>Export data</h2>
          <p className="muted">Download your sessions, summaries, and related account data as a JSON file.</p>
          <button className="button-secondary" onClick={exportData} disabled={Boolean(busy)}>
            {busy === "export" ? "Preparing export…" : "Export all data"}
          </button>
        </section>
        <section className="panel settings-data-card settings-delete-card">
          <div className="settings-action-icon delete-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 7h16m-10 4v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3" />
            </svg>
          </div>
          <p className="eyebrow">Permanent action</p>
          <h2>Delete data</h2>
          <p className="muted">Permanently remove your sessions and derived data. Your account will remain active.</p>
          <button
            className="button-danger"
            onClick={() => setConfirmingDelete(true)}
            disabled={Boolean(busy)}
          >
            {busy === "delete" ? "Deleting data…" : "Delete all data"}
          </button>
        </section>
      </div>
      {confirmingDelete && (
        <div
          className="settings-delete-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !busy) {
              setConfirmingDelete(false);
            }
          }}
        >
          <section
            className="settings-delete-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-delete-title"
            aria-describedby="settings-delete-description"
            onKeyDown={handleDeleteDialogKeyDown}
          >
            <div className="settings-delete-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 7h16m-10 4v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3" />
              </svg>
            </div>
            <p className="eyebrow">Permanent action</p>
            <h2 id="settings-delete-title">Delete your session data?</h2>
            <p id="settings-delete-description">
              This removes your sessions, summaries, and derived data. Your account and sign-in will remain active.
            </p>
            {busy === "delete" && (
              <p className="settings-delete-progress" role="status">Deleting your data…</p>
            )}
            <div className="settings-delete-actions">
              <button
                className="button-secondary"
                autoFocus
                onClick={() => setConfirmingDelete(false)}
                disabled={Boolean(busy)}
              >
                Keep my data
              </button>
              <button className="button-danger" onClick={deleteAllData} disabled={Boolean(busy)}>
                {busy === "delete" ? "Deleting…" : "Delete data"}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

export function SummaryView({ session, onDashboard, onStart }) {
  // The backend's time-weighted summary is authoritative for the displayed averages.
  const summary = session?.summary;
  const observed = summary?.observed_seconds || 0;
  const otherSeconds = Math.max(
    0,
    observed -
      (summary?.focused_seconds || 0) -
      (summary?.distracted_seconds || 0),
  );
  const formatDuration = (seconds = 0) => {
    const total = Math.max(0, Math.round(seconds));
    const minutes = Math.floor(total / 60);
    return `${minutes}m ${String(total % 60).padStart(2, "0")}s`;
  };

  return (
    <main className="page-wrap">
      <header className="summary-header">
        <p className="eyebrow">Session complete</p>
        <h1>Session summary</h1>
        <p className="muted">
          Your attention mix, averaged across the time we observed this session.
        </p>
      </header>
      <section className="panel summary-panel">
        {session && (
          <>
            <div className="summary-meta">
              <span>{formatDuration(session.elapsed_seconds || 0)} session</span>
              <span>Session #{session.id || "—"}</span>
              {summary?.average_focus_score != null && (
                <span>Average score {Math.round(summary.average_focus_score)}%</span>
              )}
            </div>
            {observed > 0 ? (
              <>
                <div className="summary-stats">
                  <article className="summary-stat">
                    <span className="summary-stat-label">Focused</span>
                    <strong>{Math.round(summary.focus_percentage)}%</strong>
                    <span>{formatDuration(summary.focused_seconds)}</span>
                  </article>
                  <article className="summary-stat distracted">
                    <span className="summary-stat-label">Distracted</span>
                    <strong>{Math.round(summary.distraction_percentage)}%</strong>
                    <span>{formatDuration(summary.distracted_seconds)}</span>
                  </article>
                  <article className="summary-stat other">
                    <span className="summary-stat-label">Drifting / fatigued</span>
                    <strong>{Math.round((otherSeconds / observed) * 100)}%</strong>
                    <span>
                      {formatDuration(summary.drifting_seconds + summary.fatigued_seconds)}
                    </span>
                  </article>
                </div>
                <div
                  className="summary-bar"
                  role="img"
                  aria-label={`Observed time: ${Math.round(summary.focus_percentage)} percent focused, ${Math.round(summary.distraction_percentage)} percent distracted`}
                >
                  <span
                    className="summary-bar-focused"
                    style={{ width: `${summary.focus_percentage}%` }}
                  />
                  <span
                    className="summary-bar-distracted"
                    style={{ width: `${summary.distraction_percentage}%` }}
                  />
                  <span
                    className="summary-bar-other"
                    style={{ width: `${(otherSeconds / observed) * 100}%` }}
                  />
                </div>
                <p className="summary-footnote">
                  Based on {formatDuration(observed)} of observed session time.
                  Percentages are time-weighted estimates, not a count of camera frames.
                </p>
              </>
            ) : (
              <p className="empty">
                No attention samples were available for this session, so a focus
                estimate could not be calculated.
              </p>
            )}
          </>
        )}
        <div className="summary-actions">
          <button onClick={onDashboard}>View Dashboard</button>
          <button className="button-secondary" onClick={onStart}>Start Another Session</button>
        </div>
      </section>
    </main>
  );
}
