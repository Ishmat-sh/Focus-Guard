import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";


const API = "http://localhost:8000";

function App() {
  const [session, setSession] = useState({ state: "idle", elapsed_seconds: 0 });
  const [attention, setAttention] = useState({ score: 0, state: "drifting", app_name: "Unknown", app_category: "unknown" });
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");

  const request = async (path, options = {}) => {
    const response = await fetch(`${API}${path}`, options);
    if (!response.ok) throw new Error((await response.json()).detail || "Request failed");
    return response.json();
  };

  const refresh = async () => {
    try {
      const [current, live, past] = await Promise.all([
        request("/sessions/current"),
        request("/attention"),
        request("/history"),
      ]);
      setSession(current);
      setAttention(live);
      setHistory(past);
      setError("");
    } catch (requestError) {
      setError("Backend offline. Start FastAPI on port 8000.");
    }
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, []);

  const action = async (path) => {
    try {
      await request(path, { method: "POST" });
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const minutes = Math.floor((session.elapsed_seconds || 0) / 60);
  const seconds = String(Math.floor((session.elapsed_seconds || 0) % 60)).padStart(2, "0");
  const score = Math.round(attention.score || 0);

  return (
    <main className="page-shell">
      <header className="topbar"><div className="brand-mark">FG</div><div><p className="eyebrow">Focus Guard / workspace monitor</p><h1>Make attention visible.</h1></div><span className={`connection ${error ? "offline" : "online"}`}>{error ? "Offline" : "Live"}</span></header>
      {error && <p className="error-banner">{error}</p>}
      <section className="dashboard-grid">
        <article className="score-panel panel"><div className="panel-kicker">Attention score</div><div className="score-ring" style={{ "--score": `${score * 3.6}deg` }}><strong>{score}</strong><span>/ 100</span></div><p className="state-label">{attention.state}</p><p className="muted">{attention.app_name} · {attention.app_category}</p></article>
        <article className="session-panel panel"><div className="panel-kicker">Current session</div><div className="timer">{minutes}:{seconds}</div><div className="status-row"><span className={`status-dot ${session.state}`} />{session.state}</div><div className="controls"><button className="primary" onClick={() => action("/sessions/start")}>Start</button><button onClick={() => action(session.state === "paused" ? "/sessions/resume" : "/sessions/pause")}>{session.state === "paused" ? "Resume" : "Pause"}</button><button onClick={() => action("/sessions/end")}>End</button></div></article>
        <article className="signals-panel panel"><div className="panel-kicker">Signal window</div><div className="signal"><span>Face detection</span><b>Ready for camera</b></div><div className="signal"><span>Gaze</span><b>Awaiting vision input</b></div><div className="signal"><span>Active app</span><b>{attention.app_name}</b></div><div className="signal"><span>Database</span><b>{history.length} saved sessions</b></div></article>
      </section>
      <section className="history-section"><div className="section-heading"><div><p className="eyebrow">Archive</p><h2>Recent sessions</h2></div><span>{history.length} recorded</span></div><div className="history-list">{history.length ? history.map((item) => <div className="history-row" key={item.id}><span>Session {item.id}</span><b>{Math.round(item.elapsed_seconds)}s</b><span className="muted">{item.state}</span></div>) : <p className="empty">Your completed sessions will appear here.</p>}</div></section>
    </main>
  );
}


createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />

  </StrictMode>

);