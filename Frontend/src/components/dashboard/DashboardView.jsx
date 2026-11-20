import { useEffect, useMemo, useState } from "react";
import KpiStrip from "./KpiStrip.jsx";
import SessionHistoryTable from "./SessionHistoryTable.jsx";
import { apiRequest } from "../../services/api.js";

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

export default function DashboardView({ apiFetch, onStart, onCollection }) {
  const [analytics, setAnalytics] = useState(null);
  const [streaks, setStreaks] = useState(null);
  const [domains, setDomains] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [error, setError] = useState("");

  const dateRange = useMemo(() => {
    const end = new Date();
    const start = new Date(end);
    start.setDate(end.getDate() - 29);
    return `?start_date=${isoDate(start)}&end_date=${isoDate(end)}`;
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest(apiFetch, `/analytics/weekly${dateRange}`),
      apiRequest(apiFetch, `/analytics/streaks${dateRange}&minimum_minutes=1`),
      apiRequest(apiFetch, `/analytics/domains${dateRange}`),
      apiRequest(apiFetch, "/history"),
    ])
      .then(([weekly, focusStreaks, domainUsage, history]) => {
        if (!active) return;
        setAnalytics(weekly);
        setStreaks(focusStreaks);
        setDomains(domainUsage || []);
        setSessions(history || []);
      })
      .catch((loadError) => {
        if (active) setError(loadError.message || "Could not load dashboard analytics");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiFetch, dateRange]);

  async function toggleDetails(session) {
    setSelectedSession(session);
    if (!session) {
      setSamples([]);
      return;
    }
    setLoadingTimeline(true);
    setError("");
    try {
      const timeline = await apiRequest(apiFetch, `/sessions/${session.id}/timeline`);
      setSamples(timeline || []);
    } catch (loadError) {
      setSamples([]);
      setError(loadError.message || "Could not load session timeline");
    } finally {
      setLoadingTimeline(false);
    }
  }

  return (
    <main className="page-wrap">
      <header style={{ marginBottom: "1.5rem" }}>
        <p className="eyebrow">Your focus history</p>
        <h1>Dashboard</h1>
        <p className="muted">A clear view of your sessions and the attention data they recorded.</p>
      </header>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {loading ? (
        <p className="loading">Loading your analytics…</p>
      ) : (
        <>
          <KpiStrip analytics={analytics} streaks={streaks} domains={domains} />
          <section className="panel" style={{ marginTop: "1rem" }}>
            <div className="controls-row">
              <div>
                <p className="eyebrow">Sessions</p>
                <h2>Recent activity</h2>
              </div>
              {sessions.length > 0 && <button onClick={onStart}>Start Session</button>}
              <button className="button-quiet" onClick={onCollection}>
                Optional data collection
              </button>
            </div>
            <SessionHistoryTable
              sessions={sessions}
              selectedSession={selectedSession}
              samples={samples}
              loadingTimeline={loadingTimeline}
              onSelect={toggleDetails}
              onStart={onStart}
            />
          </section>
        </>
      )}
    </main>
  );
}
