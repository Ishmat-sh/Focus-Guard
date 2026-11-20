import { useState, useEffect } from "react";

const API = (
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`
).replace(/\/$/, "");

function App() {
  const [page, setPage] = useState("home");
  const [userAuth, setUserAuth] = useState(null);
  const [adminCredentials, setAdminCredentials] = useState(null);

  async function apiFetch(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (userAuth?.access_token) {
      headers.set("Authorization", `Bearer ${userAuth.access_token}`);
    }
    return fetch(`${API}${path}`, { ...options, headers });
  }

  async function logoutUser() {
    if (userAuth?.access_token) {
      await apiFetch("/sessions/end", { method: "POST" }).catch(() => {});
      await apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    }
    if (window.cameraStream) {
      window.cameraStream.getTracks().forEach((track) => track.stop());
      window.cameraStream = null;
    }
    setUserAuth(null);
    setPage("home");
  }
  // HOME PAGE
  function Home() {
    return (
      <div className="page">
        <h1>Focus Guard</h1>

        <p>
          Track your focus and performance.
        </p>

        <br />

        <button onClick={() => setPage("signup")}>
          Sign Up
        </button>

        <button onClick={() => setPage("login")}>
          Sign In
        </button>

        <br />
        <br />

        <button onClick={() => setPage("admin")}>
          Admin Login
        </button>
      </div>
    );
  }
  // SIGN UP

  function Signup() {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");

    async function signup(e) {
      e.preventDefault();
      try {
        const response = await fetch(`${API}/users`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, email, password }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Could not create account");
        setUserAuth(result);
        setPage("camera");
      } catch (error) {
        alert(error.message || "Could not connect to the server");
      }
    }

    return (
      <div className="page">
        <h2>Sign Up</h2>

        <p>Create a new account.</p>

        <form onSubmit={signup}>
          <input
            type="text"
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />

          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button type="submit">
            Create Account
          </button>
        </form>

        <br />

        <button onClick={() => setPage("login")}>
          Already have an account? Sign In
        </button>

        <br />

        <button onClick={() => setPage("home")}>
          Back
        </button>
      </div>
    );
  }
  // USER LOGIN

  function Login() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");

    async function login(e) {
      e.preventDefault();
      try {
        const response = await fetch(`${API}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Could not sign in");
        setUserAuth(result);
        setPage(result.user.must_change_password ? "changePassword" : "camera");
      } catch (error) {
        alert(error.message || "Could not connect to the server");
      }
    }

    return (
      <div className="page">
        <h2>Sign In</h2>

        <p>Sign in to your account.</p>

        <form onSubmit={login}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button type="submit">
            Sign In
          </button>
        </form>

        <br />

        <button onClick={() => setPage("signup")}>
          Create Account
        </button>

        <br />

        <button onClick={() => setPage("home")}>
          Back
        </button>
      </div>
    );
  }
  // ADMIN LOGIN

  function AdminLogin() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    async function adminLogin(e) {
      e.preventDefault();
      try {
        const response = await fetch(`${API}/admin/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Invalid admin credentials");
        setAdminCredentials({ username, password });
        setPage("adminDashboard");
      } catch (error) {
        alert(error.message || "Could not connect to the server");
      }
    }

    return (
      <div className="page">
        <h2>Admin Login</h2>

        <p>Login to the admin panel.</p>

        <form onSubmit={adminLogin}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) =>
              setUsername(e.target.value)
            }
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) =>
              setPassword(e.target.value)
            }
          />

          <button type="submit">
            Login
          </button>
        </form>

        <br />

        <button onClick={() => setPage("home")}>
          Back
        </button>
      </div>
    );
  }

  function ChangePassword() {
    const [password, setPassword] = useState("");
    const [confirmation, setConfirmation] = useState("");
    const [error, setError] = useState("");

    async function submit(e) {
      e.preventDefault();
      if (password.length < 8) {
        setError("Password must be at least 8 characters");
        return;
      }
      if (password !== confirmation) {
        setError("Passwords do not match");
        return;
      }
      try {
        const response = await apiFetch("/auth/change-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ new_password: password }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Could not change password");
        setUserAuth(result);
        setPage("camera");
      } catch (changeError) {
        setError(changeError.message || "Could not connect to the server");
      }
    }

    return (
      <div className="page">
        <h2>Choose a new password</h2>
        <p>Your temporary password has to be replaced before continuing.</p>
        {error && <p className="error-banner">{error}</p>}
        <form onSubmit={submit}>
          <input
            type="password"
            placeholder="New password (8+ characters)"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={8}
          />
          <input
            type="password"
            placeholder="Confirm new password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            required
            minLength={8}
          />
          <button type="submit">Update password</button>
        </form>
        <button onClick={logoutUser}>Log out</button>
      </div>
    );
  }
  // CAMERA ACCESs

  function Camera() {
    const [cameraEnabled, setCameraEnabled] =
      useState(false);

    async function enableCamera() {
      try {
        const stream =
          await navigator.mediaDevices.getUserMedia({
            video: true,
          });

        window.cameraStream = stream;

        setCameraEnabled(true);

        alert("Camera access allowed!");
      } catch (error) {
        console.log(error);

        alert("Camera access denied.");
      }
    }

    async function leaveCamera() {
      await logoutUser();
    }

    return (
      <div className="page">
        <h2>Camera Access</h2>

        <p>
          Focus Guard needs access to your camera
          to measure focus and vision.
        </p>

        <button onClick={enableCamera}>
          Enable Camera
        </button>

        {cameraEnabled && (
          <div>
            <p className="success">
              ✓ Camera is enabled
            </p>

            <button
              onClick={() => setPage("dashboard")}
            >
              Continue to Dashboard
            </button>
          </div>
        )}

        <br />

        <button onClick={leaveCamera}>
          Back
        </button>
      </div>
    );
  }
  // DASHBOARD

  function Dashboard() {
    const [session, setSession] = useState({
      state: "idle",
      elapsed_seconds: 0,
    });

    const [attention, setAttention] = useState({
      score: 0,
      state: "drifting",

      face_present: false,
      blink_count: 0,
      gaze: "Unknown",
      head_pose: "Unknown",
      vision_score: 0,
    });

    const [history, setHistory] = useState([]);
    const [hasAttention, setHasAttention] = useState(false);
    const [collectionEnabled, setCollectionEnabled] = useState(false);
    const [collectionPrompt, setCollectionPrompt] = useState(false);
    const [labels, setLabels] = useState([]);
    const [labelCount, setLabelCount] = useState(0);
    const [labelMessage, setLabelMessage] = useState("");
    const [scorerStatus, setScorerStatus] = useState(null);

    const [error, setError] = useState("");

    const [loading, setLoading] = useState(true);
    // STOP CAMERA

    function stopCamera() {
      if (window.cameraStream) {
        window.cameraStream
          .getTracks()
          .forEach((track) => {
            track.stop();
          });

        window.cameraStream = null;
      }
    }
    // GET DATA FROM BACKEND

    async function request(path, options = {}) {
      const response = await apiFetch(path, options);

      if (!response.ok) {
        let message = "Request failed";

        try {
          const data = await response.json();
          message =
            data.detail || message;
        } catch {
          // Keep default message
        }

        throw new Error(message);
      }

      return response.json();
    }

    async function requestAttention() {
      const video = document.getElementById("camera");
      if (!video || video.readyState < 2 || !video.videoWidth) {
        return null;
      }

      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0);
      const frame = await new Promise((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.7)
      );
      if (!frame) return null;
      return request("/attention/frame", {
        method: "POST",
        headers: { "Content-Type": "image/jpeg" },
        body: frame,
      });
    }
    // REFRESH DATA

    async function refresh() {
      try {
        const [current, past, scorerResponse] = await Promise.all([
          request("/sessions/current"),
          request("/history"),
          request("/scorer"),
        ]);
        setScorerStatus(scorerResponse);
        const live = current.state === "running" ? await requestAttention() : null;

        setSession(current);

        if (current.id) {
          try {
            const [collectionResponse, labelsResponse] = await Promise.all([
              apiFetch(`/sessions/${current.id}/collection`, { method: "GET" }),
              apiFetch(`/sessions/${current.id}/labels`, { method: "GET" }),
            ]);
            if (collectionResponse.ok) {
              const collectionStatus = await collectionResponse.json();
              setCollectionEnabled(Boolean(collectionStatus.consent));
            }
            if (labelsResponse.ok) {
              const recordedLabels = await labelsResponse.json();
              setLabels(recordedLabels);
              setLabelCount(
                recordedLabels.reduce(
                  (total, item) =>
                    total +
                    Math.max(
                      0,
                      (item.end_elapsed_seconds || 0) -
                        (item.start_elapsed_seconds || 0),
                    ),
                  0,
                ) / 60,
              );
            }
          } catch {
            // Collection controls remain available even if a label request fails.
          }
        }

        if (live) {
          setAttention((old) => ({ ...old, ...live }));
          setHasAttention(true);
        }

        setHistory(past);

        setError("");

        setLoading(false);
      } catch (requestError) {
        console.log(requestError);

        setError(requestError.message || "Could not load dashboard data");

        setLoading(false);
      }
    }
    // START API POLLING
    useEffect(() => {
      let cancelled = false;
      let timer;
      async function poll() {
        await refresh();
        if (!cancelled) timer = setTimeout(poll, 1000);
      }
      poll();
      return () => {
        cancelled = true;
        clearTimeout(timer);
      };
    }, []);
    // CAMERA DISPLAY
    useEffect(() => {
      const video =
        document.getElementById("camera");

      if (
        video &&
        window.cameraStream
      ) {
        video.srcObject =
          window.cameraStream;
      }

      return () => {
        if (video) {
          video.srcObject = null;
        }
      };
    }, []);

    useEffect(() => {
      if (!collectionEnabled || session.state !== "running") {
        setCollectionPrompt(false);
        return undefined;
      }
      const promptTimer = window.setInterval(() => {
        setCollectionPrompt(true);
      }, 10 * 60 * 1000);
      return () => window.clearInterval(promptTimer);
    }, [collectionEnabled, session.state]);

    async function setCollectionConsent(enabled) {
      if (!session.id) {
        setLabelMessage("Start a session before enabling collection.");
        return;
      }
      try {
        await request(`/sessions/${session.id}/collection/consent`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ consent: enabled }),
        });
        setCollectionEnabled(enabled);
        setCollectionPrompt(false);
        setLabelMessage(
          enabled
            ? "Consent saved. Only derived numerical features will be stored."
            : "Collection disabled for this session.",
        );
      } catch (requestError) {
        setLabelMessage(requestError.message || "Could not update collection consent");
      }
    }

    async function addLabel(label) {
      if (!session.id) return;
      const end = Number(session.elapsed_seconds || 0);
      const start = Math.max(0, end - 30);
      if (end <= start) {
        setLabelMessage("This label needs at least 30 seconds of session time.");
        return;
      }
      try {
        await request(`/sessions/${session.id}/labels`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            start_elapsed_seconds: start,
            end_elapsed_seconds: end,
            label,
          }),
        });
        setCollectionPrompt(false);
        setLabelMessage(`Recorded: ${label}`);
        await refresh();
      } catch (requestError) {
        setLabelMessage(requestError.message || "Could not record label");
      }
    }

    async function exportDataset() {
      if (!session.id) {
        setLabelMessage("Start and run a session before exporting.");
        return;
      }
      try {
        const response = await apiFetch(`/sessions/${session.id}/dataset.csv`);
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || "Could not export the dataset");
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `focus-guard-session-${session.id}.csv`;
        link.click();
        window.URL.revokeObjectURL(url);
      } catch (requestError) {
        setLabelMessage(requestError.message || "Could not export the dataset");
      }
    }
    // SESSION ACTION
    async function action(path) {
      try {
        await request(path, {
          method: "POST",
        });

        await refresh();

        // If session has ended, turn camera off
        if (path === "/sessions/end") {
          stopCamera();
        }
      } catch (requestError) {
        console.log(requestError);

        setError(
          requestError.message
        );
      }
    }

    async function setScorerMode(mode) {
      try {
        await request("/scorer", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode }),
        });
        await refresh();
      } catch (requestError) {
        setError(requestError.message || "Could not change scorer mode");
      }
    }
    // BACKEND SESSION TIME

    const elapsed =
      session.elapsed_seconds || 0;
    const minutes =
      Math.floor(elapsed / 60);
    const displaySeconds =
      String(
        Math.floor(elapsed % 60)
      ).padStart(2, "0");
    const score =
      Math.round(
        attention.score || 0
      );
    const visionScore =
      Math.round(
        attention.vision_score ||
          attention.vision ||
          0
      );
    // DASHBOARD
    return (
      <div>
        {/* NAVBAR */}
        <div className="navbar">
          <h2>
            Focus Guard
          </h2>
          <div className="navbar-actions">
            <button onClick={() => setPage("dashboard")}>Dashboard</button>
            <button onClick={() => setPage("collection")}>Collection</button>
            <button onClick={() => setPage("analytics")}>Analytics</button>
            <button onClick={() => setPage("coaching")}>Coaching</button>
            <button onClick={() => setPage("settings")}>Settings</button>
            <button onClick={logoutUser}>Logout</button>
          </div>
        </div>
        <div className="dashboard">
          <h1>
            Dashboard
          </h1>
          <p>
            Your focus session is being
            monitored.
          </p>
          {/* STATUS */}
          {loading && (
            <p className="loading">
              Loading dashboard...
            </p>
          )}
          {error && (
            <p className="error-banner">
              {error}
            </p>
          )}
          {!error && !loading && (
            <p className="connected">
              ● Backend connected
            </p>
          )}
          {/* CAMERA */}
          <div className="camera-container">
            <h2>
              Your Camera
            </h2>
            <video
              id="camera"
              autoPlay
              playsInline
              muted
            />
          </div>
          {/* METRICS */}
          <div className="metrics">
            <div className="box">
              <h3>
                Estimated score
              </h3>
              <p className="big-number">
                {hasAttention ? score : "—"}
              </p>
            </div>
            <div className="box">
              <h3>
                Estimated state
              </h3>
              <p>
                {hasAttention ? attention.state : "Not available"}
              </p>
            </div>
            <div className="box">
              <h3>
                Duration
              </h3>
              <p>
                {minutes}:
                {displaySeconds}
              </p>
            </div>
            <div className="box">
              <h3>
                Vision
              </h3>
              <p>
                {hasAttention ? `${visionScore}%` : "—"}
              </p>
            </div>
          </div>
          <div className="status-card">
            <h2>Attention Scorer</h2>
            <p>
              Active source: <strong>{attention.scorer || "rules"}</strong>
              {attention.confidence != null
                ? ` — confidence ${Math.round(attention.confidence * 100)}%`
                : ""}
            </p>
            {scorerStatus?.model_version && (
              <p>Model version: <strong>{scorerStatus.model_version}</strong></p>
            )}
            {attention.inference_ms != null && (
              <p>Inference time: {Number(attention.inference_ms).toFixed(2)} ms</p>
            )}
            {attention.scorer_fallback_reason && (
              <p className="error-banner">{attention.scorer_fallback_reason}</p>
            )}
            <button onClick={() => setScorerMode("ml")} disabled={attention.scorer === "ml"}>
              Use ML
            </button>
            <button onClick={() => setScorerMode("rules")} disabled={attention.scorer === "rules"}>
              Use Rules
            </button>
          </div>
          {/* SESSION CONTROLS */}
          <div className="session-controls">
            <button
              className="start-button"
              disabled={session.state === "running" || session.state === "paused"}
              onClick={() =>
                action(
                  "/sessions/start"
                )
              }
            >
              Start
            </button>
            <button
              disabled={!['running', 'paused'].includes(session.state)}
              onClick={() =>
                action(
                  session.state ===
                    "paused"
                    ? "/sessions/resume"
                    : "/sessions/pause"
                )
              }
            >
              {session.state ===
              "paused"
                ? "Resume"
                : "Pause"}
            </button>
            <button
              className="end-button"
              disabled={!['running', 'paused'].includes(session.state)}
              onClick={async () => {
                try {
                  await request(
                    "/sessions/end",
                    {
                      method: "POST",
                    }
                  );
                  // IMPORTANT:
                  // Stop camera immediately
                  stopCamera();
                  // Refresh backend data
                  await refresh();
                  // Then show summary
                  setPage("summary");
                } catch (requestError) {
                  console.log(
                    requestError
                  );
                  setError(
                    requestError.message
                  );
                }
              }}
            >
              End Session
            </button>
          </div>
          {/* VISION METRICS */}
          <div className="vision-section">
            <h2>
              Vision Metrics
            </h2>
            <div className="vision-grid">
              <div className="vision-box">
                <span>
                  Face Detection
                </span>
                <strong>
                  {attention.face_present
                    ? "Detected"
                    : "Not detected"}
                </strong>
              </div>
              <div className="vision-box">
                <span>Blinks in last minute</span>
                <strong>{attention.blink_count ?? 0}</strong>
              </div>
              <div className="vision-box">
                <span>
                  Estimated gaze
                </span>
                <strong>
                  {attention.gaze ||
                    "Unknown"}
                </strong>
              </div>
              <div className="vision-box">
                <span>
                  Estimated head pose
                </span>
                <strong>
                  {attention.head_pose ||
                    "Unknown"}
                </strong>
              </div>
              <div className="vision-box">
                <span>Posture</span>
                <strong>{attention.posture || "Unknown"}</strong>
              </div>
              <div className="vision-box">
                <span>Focused-only baseline</span>
                <strong>
                  {attention.focus_baseline_status === "matches_focused_baseline"
                    ? "Matches focused baseline"
                    : attention.focus_baseline_status === "deviates_from_focused_baseline"
                      ? "Outside focused baseline"
                      : attention.focus_baseline_status === "warming_up"
                        ? "Warming up"
                        : "Unavailable"}
                </strong>
              </div>
              <div className="vision-box">
                <span>DAiSEE engagement level (0-3)</span>
                <strong>
                  {attention.daisee_engagement_status === "available"
                    ? `Level ${attention.daisee_engagement_level}`
                    : attention.daisee_engagement_status === "warming_up"
                      ? "Warming up"
                      : "Unavailable"}
                </strong>
              </div>
            </div>
            <p className="empty">
              DAiSEE's 0-3 label estimate is experimental: it missed every held-out level 0
              and 1 example. Neither output diagnoses focus, distraction, drifting, or fatigue.
            </p>
          </div>
          {/* HISTORY */}
          <div className="history-section">
            <h2>
              Recent Sessions
            </h2>
            {history.length === 0 ? (
              <p className="empty">
                No completed sessions yet.
              </p>
            ) : (
              <div className="history-list">
                {history.map(
                  (item) => (
                    <div
                      className="history-row"
                      key={item.id}
                    >
                      <span>
                        Session {item.id}
                      </span>
                      <span>
                        {Math.round(
                          item.elapsed_seconds ||
                            0
                        )}{" "}
                        seconds
                      </span>
                      <span>
                        {item.state}
                      </span>
                    </div>
                  )
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
  function Analytics() {
    const today = new Date();
    const defaultStart = new Date(today);
    defaultStart.setDate(today.getDate() - 6);
    const [startDate, setStartDate] = useState(defaultStart.toISOString().slice(0, 10));
    const [endDate, setEndDate] = useState(today.toISOString().slice(0, 10));
    const [weekly, setWeekly] = useState(null);
    const [heatmap, setHeatmap] = useState(null);
    const [streaks, setStreaks] = useState(null);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState("");

    async function loadAnalytics() {
      setLoading(true);
      setMessage("");
      try {
        const parameters = `?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
        const [weeklyResponse, heatmapResponse, streaksResponse] = await Promise.all([
          apiFetch(`/analytics/weekly${parameters}`),
          apiFetch(`/analytics/heatmap${parameters}`),
          apiFetch(`/analytics/streaks${parameters}&minimum_minutes=5`),
        ]);
        if (!weeklyResponse.ok || !heatmapResponse.ok || !streaksResponse.ok) {
          throw new Error("Could not load analytics");
        }
        setWeekly(await weeklyResponse.json());
        setHeatmap(await heatmapResponse.json());
        setStreaks(await streaksResponse.json());
      } catch (loadError) {
        setMessage(loadError.message || "Could not load analytics");
      } finally {
        setLoading(false);
      }
    }

    useEffect(() => {
      loadAnalytics();
    }, []);

    const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    function heatColor(sampleCount, averageScore) {
      if (!sampleCount || averageScore == null) return "#eef0f3";
      if (averageScore >= 75) return "#3a9b57";
      if (averageScore >= 50) return "#d6a84b";
      return "#d9534f";
    }

    return (
      <div className="page app-page">
        <div className="navbar">
          <h2>Focus Guard</h2>
          <div className="navbar-actions">
            <button onClick={() => setPage("dashboard")}>Dashboard</button>
            <button onClick={() => setPage("collection")}>Collection</button>
            <button onClick={() => setPage("analytics")}>Analytics</button>
            <button onClick={() => setPage("coaching")}>Coaching</button>
            <button onClick={() => setPage("settings")}>Settings</button>
            <button onClick={logoutUser}>Logout</button>
          </div>
        </div>
        <div className="feature-page">
          <h1>Analytics</h1>
          <div className="date-controls">
            <label>
              Start
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </label>
            <label>
              End
              <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            </label>
            <button onClick={loadAnalytics} disabled={loading}>
              {loading ? "Loading..." : "Apply"}
            </button>
          </div>
          {message && <p className="error-banner">{message}</p>}
          {weekly && (
            <>
              <div className="metrics">
                <div className="box">
                  <h3>Focus time</h3>
                  <p>{Math.round(weekly.comparison.current.total_focus_seconds / 60)} min</p>
                </div>
                <div className="box">
                  <h3>Average score</h3>
                  <p>{weekly.comparison.current.average_focus_score == null
                    ? "—"
                    : `${Math.round(weekly.comparison.current.average_focus_score)}%`}</p>
                </div>
                <div className="box">
                  <h3>Distractions</h3>
                  <p>{weekly.comparison.current.distraction_count}</p>
                </div>
              </div>
              <div className="status-card">
                <h2>Daily trend</h2>
                {weekly.daily.length === 0 ? (
                  <p className="empty">No analytics data in this date range.</p>
                ) : (
                  <div className="daily-table">
                    {weekly.daily.map((day) => (
                      <div className="daily-row" key={day.date}>
                        <strong>{day.date}</strong>
                        <span>{Math.round(day.total_focus_seconds / 60)} focus min</span>
                        <span>{day.average_score == null ? "No score" : `${Math.round(day.average_score)} average`}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
          {heatmap && (
            <div className="status-card">
              <h2>Day and hour heatmap</h2>
              {heatmap.cells.every((cell) => !cell.sample_count) ? (
                <p className="empty">No activity samples in this date range.</p>
              ) : (
                <div className="heatmap" role="table" aria-label="Focus heatmap">
                  {heatmap.cells.map((cell) => (
                    <div
                      role="cell"
                      key={`${cell.day_of_week}-${cell.hour}`}
                      className="heatmap-cell"
                      style={{ backgroundColor: heatColor(cell.sample_count, cell.average_score) }}
                      title={`${dayNames[cell.day_of_week]} ${cell.hour}:00 — ${
                        cell.average_score == null ? "No data" : `${Math.round(cell.average_score)}`
                      }`}
                    >
                      {cell.sample_count ? "" : ""}
                    </div>
                  ))}
                </div>
              )}
              <div className="heatmap-legend">
                <span><i style={{ background: "#eef0f3" }} /> Empty</span>
                <span><i style={{ background: "#d9534f" }} /> Low</span>
                <span><i style={{ background: "#d6a84b" }} /> Moderate</span>
                <span><i style={{ background: "#3a9b57" }} /> High</span>
              </div>
            </div>
          )}
          {streaks && (
            <div className="status-card">
              <h2>Focus streaks</h2>
              <p>Longest: <strong>{Math.round(streaks.longest_streak_seconds / 60)} minutes</strong></p>
              <p>Latest: <strong>{Math.round(streaks.latest_streak_seconds / 60)} minutes</strong></p>
              {streaks.streaks.length === 0 ? (
                <p className="empty">No streaks of at least 5 minutes.</p>
              ) : (
                streaks.streaks.map((streak) => (
                  <div className="daily-row" key={`${streak.session_id}-${streak.started_at}`}>
                    <strong>Session {streak.session_id}</strong>
                    <span>{Math.round(streak.duration_seconds / 60)} minutes</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  function Coaching() {
    const [insights, setInsights] = useState([]);
    const [loading, setLoading] = useState(true);
    const [message, setMessage] = useState("");

    async function loadInsights() {
      setLoading(true);
      try {
        const response = await apiFetch("/insights");
        if (!response.ok) throw new Error("Could not load coaching insights");
        setInsights(await response.json());
      } catch (loadError) {
        setMessage(loadError.message || "Could not load coaching");
      } finally {
        setLoading(false);
      }
    }

    useEffect(() => {
      loadInsights();
    }, []);

    async function dismissInsight(insightId) {
      try {
        const response = await apiFetch(`/insights/${insightId}/dismiss`, { method: "POST" });
        if (!response.ok) throw new Error("Could not dismiss insight");
        await loadInsights();
      } catch (actionError) {
        setMessage(actionError.message || "Could not dismiss insight");
      }
    }

    async function feedback(insightId, value) {
      try {
        const response = await apiFetch(`/insights/${insightId}/feedback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ feedback: value }),
        });
        if (!response.ok) throw new Error("Could not save feedback");
        await loadInsights();
      } catch (actionError) {
        setMessage(actionError.message || "Could not save feedback");
      }
    }

    return (
      <div className="page app-page">
        <div className="navbar">
          <h2>Focus Guard</h2>
          <div className="navbar-actions">
            <button onClick={() => setPage("dashboard")}>Dashboard</button>
            <button onClick={() => setPage("collection")}>Collection</button>
            <button onClick={() => setPage("analytics")}>Analytics</button>
            <button onClick={() => setPage("coaching")}>Coaching</button>
            <button onClick={() => setPage("settings")}>Settings</button>
            <button onClick={logoutUser}>Logout</button>
          </div>
        </div>
        <div className="feature-page">
          <h1>Coaching</h1>
          {loading ? (
            <p className="loading">Loading insights...</p>
          ) : message ? (
            <p className="error-banner">{message}</p>
          ) : insights.length === 0 ? (
            <p className="empty">No coaching insights yet. Complete a focus session to generate them.</p>
          ) : (
            <div className="insight-list">
              {insights.map((insight) => (
                <div className={`insight-card${insight.dismissed ? " dismissed" : ""}`} key={insight.id}>
                  <div>
                    <strong>{insight.source === "ai" ? "AI-written" : "Rule-based"}</strong>
                    <span>Session {insight.session_id}</span>
                  </div>
                  <p>{insight.message}</p>
                  {insight.dismissed ? (
                    <span className="dismissed-label">Dismissed</span>
                  ) : (
                    <div className="insight-actions">
                      <button onClick={() => feedback(insight.id, "helpful")}>
                        Helpful
                      </button>
                      <button onClick={() => feedback(insight.id, "not_helpful")}>
                        Not helpful
                      </button>
                      <button className="secondary-button" onClick={() => dismissInsight(insight.id)}>
                        Dismiss
                      </button>
                    </div>
                  )}
                  {insight.feedback && (
                    <small>Feedback: {insight.feedback.replace("_", " ")}</small>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  function Settings() {
    const [retention, setRetention] = useState("");
    const [rules, setRules] = useState([]);
    const [history, setHistory] = useState([]);
    const [browserContext, setBrowserContext] = useState(null);
    const [biometrics, setBiometrics] = useState([]);
    const [syncState, setSyncState] = useState([]);
    const [lightingEndpoint, setLightingEndpoint] = useState("");
    const [ruleType, setRuleType] = useState("domain");
    const [ruleValue, setRuleValue] = useState("");
    const [ruleCategory, setRuleCategory] = useState("productive");
    const [message, setMessage] = useState("");

    async function loadSettings() {
      try {
        const [retentionResponse, rulesResponse, historyResponse, browserResponse, biometricResponse, syncResponse] =
          await Promise.all([
            apiFetch("/privacy/retention"),
            apiFetch("/context/category-rules"),
            apiFetch("/history"),
            apiFetch("/context/browser"),
            apiFetch("/biometrics"),
            apiFetch("/sync"),
          ]);
        if (!retentionResponse.ok || !rulesResponse.ok || !historyResponse.ok) {
          throw new Error("Could not load settings");
        }
        const retentionData = await retentionResponse.json();
        setRetention(
          retentionData.retention_days == null
            ? ""
            : String(retentionData.retention_days),
        );
        setRules(await rulesResponse.json());
        setHistory(await historyResponse.json());
        if (browserResponse.ok) setBrowserContext(await browserResponse.json());
        else setBrowserContext(null);
        if (biometricResponse.ok) setBiometrics(await biometricResponse.json());
        if (syncResponse.ok) setSyncState(await syncResponse.json());
      } catch (loadError) {
        setMessage(loadError.message || "Could not load settings");
      }
    }

    useEffect(() => {
      loadSettings();
    }, []);

    async function saveRetention() {
      try {
        const response = await apiFetch("/privacy/retention", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            retention_days: retention === "" ? null : Number(retention),
          }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not save retention");
        setMessage(
          data.retention_days == null
            ? "Retention disabled."
            : `Retention set to ${data.retention_days} days.`,
        );
      } catch (saveError) {
        setMessage(saveError.message || "Could not save retention");
      }
    }

    async function saveRule(event) {
      event.preventDefault();
      try {
        const response = await apiFetch("/context/category-rules", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            rule_type: ruleType,
            rule_value: ruleValue.trim(),
            category: ruleCategory,
          }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not save rule");
        setRuleValue("");
        setMessage(`Saved category rule for ${data.rule_value}.`);
        await loadSettings();
      } catch (ruleError) {
        setMessage(ruleError.message || "Could not save rule");
      }
    }

    async function deleteRule(ruleId) {
      const response = await apiFetch(`/context/category-rules/${ruleId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        setMessage("Could not delete category rule");
        return;
      }
      await loadSettings();
    }

    async function exportData() {
      try {
        const response = await apiFetch("/data/export.json");
        if (!response.ok) throw new Error("Could not export data");
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "focus-guard-export.json";
        link.click();
        window.URL.revokeObjectURL(url);
      } catch (exportError) {
        setMessage(exportError.message || "Could not export data");
      }
    }

    async function deleteSession(sessionId) {
      if (!window.confirm(`Delete session ${sessionId} and all of its data?`)) return;
      const response = await apiFetch(`/sessions/${sessionId}`, { method: "DELETE" });
      if (!response.ok) {
        setMessage("Could not delete session");
        return;
      }
      setMessage(`Deleted session ${sessionId}.`);
      await loadSettings();
    }

    async function configureSync(enabled) {
      let deviceId = window.localStorage.getItem("focus_guard_device_id");
      if (!deviceId) {
        deviceId = crypto.randomUUID();
        window.localStorage.setItem("focus_guard_device_id", deviceId);
      }
      try {
        const response = await apiFetch("/sync", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_id: deviceId,
            device_name: navigator.platform || "Browser device",
            enabled,
          }),
        });
        if (!response.ok) throw new Error("Could not update sync settings");
        setMessage(
          enabled
            ? "Derived-data sync is enabled. Raw frames and URLs are never included."
            : "Sync disabled. No data leaves this account.",
        );
        await loadSettings();
      } catch (syncError) {
        setMessage(syncError.message || "Could not update sync");
      }
    }

    async function setLightingState(state) {
      if (!lightingEndpoint.trim()) {
        setMessage("Enter a real smart-lighting HTTP endpoint.");
        return;
      }
      try {
        const response = await apiFetch("/lighting", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ endpoint: lightingEndpoint.trim(), state }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Lighting API unavailable");
        setMessage(`Lighting set to ${state}.`);
      } catch (lightingError) {
        setMessage(lightingError.message || "Could not control lighting");
      }
    }

    async function deleteAllData() {
      if (!window.confirm("Delete all Focus Guard sessions and derived data from this account?")) return;
      const response = await apiFetch("/data", { method: "DELETE" });
      if (!response.ok) {
        setMessage("Could not delete data");
        return;
      }
      setMessage("Deleted all account data.");
      await loadSettings();
    }

    return (
      <div className="page app-page">
        <div className="navbar">
          <h2>Focus Guard</h2>
          <div className="navbar-actions">
            <button onClick={() => setPage("dashboard")}>Dashboard</button>
            <button onClick={() => setPage("collection")}>Collection</button>
            <button onClick={() => setPage("analytics")}>Analytics</button>
            <button onClick={() => setPage("coaching")}>Coaching</button>
            <button onClick={() => setPage("settings")}>Settings</button>
            <button onClick={logoutUser}>Logout</button>
          </div>
        </div>
        <div className="feature-page">
          <h1>Settings and Privacy</h1>
          {message && <p className="status-message">{message}</p>}
          <div className="status-card">
            <h2>What is stored</h2>
            <p>
              Numerical scores and derived features are stored. Raw frames,
              recordings, full URLs and page titles are never stored.
            </p>
          </div>
          <div className="status-card">
            <h2>Browser extension</h2>
            {browserContext ? (
              <p>
                Connected: <strong>{browserContext.domain}</strong> is{" "}
                <strong>{browserContext.category}</strong>.
              </p>
            ) : (
              <p>The extension is not reporting a domain for the running session.</p>
            )}
          </div>
          <div className="status-card">
            <h2>Cloud sync</h2>
            <p>
              Sync is opt-in and exports derived session data only.
              Raw frames, recordings and full URLs are never included.
            </p>
            {syncState.map((device) => (
              <p key={device.device_id}>
                <strong>{device.name || device.device_id}</strong>:{" "}
                {device.enabled ? "Enabled" : "Disabled"}
                {device.last_synced_at != null &&
                  ` — last synced ${new Date(device.last_synced_at * 1000).toLocaleString()}`}
              </p>
            ))}
            <button
              className="start-button"
              onClick={() => configureSync(true)}
            >
              Enable Sync
            </button>
            <button
              className="secondary-button"
              onClick={() => configureSync(false)}
            >
              Disable Sync
            </button>
          </div>
          <div className="status-card">
            <h2>Optional smart lighting</h2>
            <p>Configure a real HTTP lighting endpoint. No device is contacted until you enable it.</p>
            <input
              value={lightingEndpoint}
              onChange={(event) => setLightingEndpoint(event.target.value)}
              placeholder="https://device.local/api/state"
            />
            <button onClick={() => setLightingState("focused")}>Focused</button>
            <button onClick={() => setLightingState("break")}>Break</button>
            <button onClick={() => setLightingState("idle")}>Idle</button>
          </div>
          <div className="status-card">
            <h2>Wearable biometrics</h2>
            {biometrics.length === 0 ? (
              <p>No biometric samples recorded. Live wearables require a tested real source.</p>
            ) : (
              <p>
                Latest heart rate: <strong>{Math.round(biometrics[0].heart_rate)} bpm</strong>
                {biometrics[0].hrv != null &&
                  ` — HRV ${Math.round(biometrics[0].hrv)}`}
                {" "}from <strong>{biometrics[0].source_device}</strong>.
              </p>
            )}
          </div>
          <div className="status-card">
            <h2>Context category rules</h2>
            <form className="rule-form" onSubmit={saveRule}>
              <select value={ruleType} onChange={(event) => setRuleType(event.target.value)}>
                <option value="domain">Domain</option>
                <option value="app">Application</option>
              </select>
              <input
                value={ruleValue}
                onChange={(event) => setRuleValue(event.target.value)}
                placeholder={ruleType === "domain" ? "youtube.com" : "Safari"}
                required
              />
              <select value={ruleCategory} onChange={(event) => setRuleCategory(event.target.value)}>
                <option value="productive">Productive</option>
                <option value="neutral">Neutral</option>
                <option value="distracting">Distracting</option>
              </select>
              <button type="submit">Save Rule</button>
            </form>
            {rules.length === 0 ? (
              <p className="empty">No custom category rules.</p>
            ) : (
              rules.map((rule) => (
                <div className="daily-row" key={rule.id}>
                  <strong>{rule.rule_type}: {rule.rule_value}</strong>
                  <span>{rule.category}</span>
                  <button className="secondary-button" onClick={() => deleteRule(rule.id)}>
                    Delete
                  </button>
                </div>
              ))
            )}
          </div>
          <div className="status-card">
            <h2>Retention</h2>
            <label>
              Retain telemetry for
              <input
                type="number"
                min="1"
                max="3650"
                value={retention}
                onChange={(event) => setRetention(event.target.value)}
                placeholder="No automatic deletion"
              />
            </label>
            <button onClick={saveRetention}>Save Retention</button>
          </div>
          <div className="status-card">
            <h2>Delete and export</h2>
            <button onClick={exportData}>Export All Data</button>
            <button className="end-button" onClick={deleteAllData}>Delete All Data</button>
            {history.map((session) => (
              <div className="daily-row" key={session.id}>
                <strong>Session {session.id}</strong>
                <span>{Math.round(session.elapsed_seconds || 0)} seconds</span>
                <button className="secondary-button" onClick={() => deleteSession(session.id)}>
                  Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  function Collection() {
    const [session, setSession] = useState(null);
    const [labels, setLabels] = useState([]);
    const [consented, setConsented] = useState(false);
    const [message, setMessage] = useState("");
    const [promptVisible, setPromptVisible] = useState(false);

    async function load() {
      try {
        const response = await apiFetch("/sessions/current");
        if (!response.ok) throw new Error("Could not load current session");
        const current = await response.json();
        setSession(current);
        if (current.id) {
          const [collectionResponse, labelsResponse] = await Promise.all([
            apiFetch(`/sessions/${current.id}/collection`),
            apiFetch(`/sessions/${current.id}/labels`),
          ]);
          if (collectionResponse.ok) {
            const status = await collectionResponse.json();
            setConsented(Boolean(status.consent));
          }
          if (labelsResponse.ok) setLabels(await labelsResponse.json());
        }
      } catch (loadError) {
        setMessage(loadError.message || "Could not load collection status");
      }
    }

    useEffect(() => {
      load();
      const timer = window.setInterval(() => {
        if (consented) setPromptVisible(true);
      }, 10 * 60 * 1000);
      return () => window.clearInterval(timer);
    }, [consented]);

    async function updateConsent(nextConsent) {
      if (!session?.id) {
        setMessage("Start a session before enabling collection.");
        return;
      }
      try {
        const response = await apiFetch(`/sessions/${session.id}/collection/consent`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ consent: nextConsent }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not save consent");
        setConsented(nextConsent);
        setPromptVisible(false);
        setMessage(
          nextConsent
            ? "Consent saved. Raw frames are never stored or exported."
            : "Collection disabled.",
        );
      } catch (updateError) {
        setMessage(updateError.message || "Could not save consent");
      }
    }

    async function createLabel(label) {
      if (!session?.id) return;
      const end = Number(session.elapsed_seconds || 0);
      const start = Math.max(0, end - 30);
      if (end <= start) {
        setMessage("Wait at least 30 seconds before recording a label.");
        return;
      }
      try {
        const response = await apiFetch(`/sessions/${session.id}/labels`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            start_elapsed_seconds: start,
            end_elapsed_seconds: end,
            label,
          }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not save label");
        setPromptVisible(false);
        setMessage(`Recorded ${label} for the latest 30 seconds.`);
        await load();
      } catch (labelError) {
        setMessage(labelError.message || "Could not save label");
      }
    }

    async function exportDataset() {
      if (!session?.id) {
        setMessage("Start a session before exporting.");
        return;
      }
      try {
        const response = await apiFetch(`/sessions/${session.id}/dataset.csv`);
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || "Could not export dataset");
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `focus-guard-session-${session.id}.csv`;
        link.click();
        window.URL.revokeObjectURL(url);
      } catch (exportError) {
        setMessage(exportError.message || "Could not export dataset");
      }
    }

    const labelledMinutes =
      labels.reduce(
        (total, item) =>
          total +
          Math.max(
            0,
            (item.end_elapsed_seconds || 0) -
              (item.start_elapsed_seconds || 0),
          ),
        0,
      ) / 60;

    return (
      <div className="page app-page">
        <div className="navbar">
          <h2>Focus Guard</h2>
          <div className="navbar-actions">
            <button onClick={() => setPage("dashboard")}>Dashboard</button>
            <button onClick={() => setPage("collection")}>Collection</button>
            <button onClick={() => setPage("analytics")}>Analytics</button>
            <button onClick={() => setPage("coaching")}>Coaching</button>
            <button onClick={() => setPage("settings")}>Settings</button>
            <button onClick={logoutUser}>Logout</button>
          </div>
        </div>
        <div className="feature-page">
          <h1>Data Collection</h1>
          <div className="consent-card">
            <h2>Privacy consent</h2>
            <p>
              Collection stores numerical vision and context features only.
              Raw camera frames, recordings, URLs and page titles are never stored.
            </p>
            <button
              className={consented ? "secondary-button" : "start-button"}
              onClick={() => updateConsent(!consented)}
              disabled={!session?.id}
            >
              {consented ? "Disable Collection" : "I Consent to Collection"}
            </button>
          </div>
          {message && <p className="status-message">{message}</p>}
          {promptVisible && (
            <div className="label-prompt" role="dialog" aria-label="Focus state prompt">
              <strong>How focused were you in the last 30 seconds?</strong>
              <div>
                {["focused", "drifting", "distracted", "fatigued"].map((label) => (
                  <button key={label} onClick={() => createLabel(label)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="metrics">
            <div className="box">
              <h3>Labelled minutes</h3>
              <p className="big-number">{labelledMinutes.toFixed(1)}</p>
            </div>
            <div className="box">
              <h3>Recorded labels</h3>
              <p className="big-number">{labels.length}</p>
            </div>
          </div>
          <div className="session-controls">
            <button onClick={() => createLabel("focused")}>Focused</button>
            <button onClick={() => createLabel("drifting")}>Drifting</button>
            <button onClick={() => createLabel("distracted")}>Distracted</button>
            <button onClick={() => createLabel("fatigued")}>Tired</button>
            <button onClick={exportDataset}>Export Dataset CSV</button>
          </div>
        </div>
      </div>
    );
  }
  // SESSION SUMMARY
  function Summary() {
    const [summary, setSummary] =
      useState(null);
    const [loading, setLoading] =
      useState(true);
    useEffect(() => {
      async function loadSummary() {
        try {
          const response = await apiFetch("/history");
          if (!response.ok) throw new Error("Could not load session history");
          const data =
            await response.json();
          if (
            data &&
            data.length > 0
          ) {
            setSummary(data[0]);
          }
        } catch (error) {
          console.log(error);
        }
        setLoading(false);
      }
      loadSummary();
    }, []);
    function formatDuration(seconds) {
      const mins =
        Math.floor(
          seconds / 60
        );
      const secs =
        Math.floor(
          seconds % 60
        );
      if (mins === 0) {
        return `${secs} seconds`;
      }
      return `${mins} min ${secs} sec`;
    }
    return (
      <div className="page summary-page">
        <h1>
          Session Summary
        </h1>
        <h3>
          Session Completed
        </h3>
        <hr />
        {loading ? (
          <p>
            Loading session data...
          </p>
        ) : summary ? (
          <>
            <p>
              Duration:{" "}
              <b>
                {formatDuration(
                  summary.elapsed_seconds ||
                    0
                )}
              </b>
            </p>
            <p>
              State:{" "}
              <b>
                {summary.state ||
                  "Completed"}
              </b>
            </p>
            <p>
              Session ID:{" "}
              <b>
                {summary.id}
              </b>
            </p>
          </>
        ) : (
          <p>
            Session completed.
          </p>
        )}
        <br />
        <button
          onClick={() =>
            setPage("dashboard")
          }
        >
          Back to Dashboard
        </button>
        <br />
        <button onClick={logoutUser}>
          Logout
        </button>
      </div>
    );
  }
  // ADMIN DASHBOARD
  function AdminDashboard() {
    const [users, setUsers] = useState([]);
    const [admins, setAdmins] = useState([]);
    const [error, setError] = useState("");
    const [resetPassword, setResetPassword] = useState(null);

    async function resetUserPassword(user) {
      if (!window.confirm(`Reset the password for ${user.name}? They will be signed out and must choose a new password.`)) {
        return;
      }
      const authorization = `Basic ${btoa(`${adminCredentials.username}:${adminCredentials.password}`)}`;
      try {
        const response = await fetch(`${API}/admin/users/${user.id}/password-reset`, {
          method: "POST",
          headers: { Authorization: authorization },
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Could not reset password");
        setResetPassword({ id: user.id, name: user.name, password: result.temporary_password });
        setError("");
      } catch (resetError) {
        setError(resetError.message || "Could not reset password");
      }
    }

    async function deleteUser(user) {
      if (!window.confirm(`Permanently delete ${user.name} and all of their sessions? This cannot be undone.`)) {
        return;
      }
      const authorization = `Basic ${btoa(`${adminCredentials.username}:${adminCredentials.password}`)}`;
      try {
        const response = await fetch(`${API}/admin/users/${user.id}`, {
          method: "DELETE",
          headers: { Authorization: authorization },
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Could not delete user");
        setUsers((current) => current.filter((item) => item.id !== user.id));
        setResetPassword((current) => current?.id === user.id ? null : current);
        setError("");
      } catch (deleteError) {
        setError(deleteError.message || "Could not delete user");
      }
    }

    useEffect(() => {
      if (!adminCredentials) {
        setPage("admin");
        return;
      }
      const authorization = `Basic ${btoa(`${adminCredentials.username}:${adminCredentials.password}`)}`;
      Promise.all([
        fetch(`${API}/users`, { headers: { Authorization: authorization } }),
        fetch(`${API}/admins`, { headers: { Authorization: authorization } }),
      ])
        .then(async ([userResponse, adminResponse]) => {
          if (!userResponse.ok || !adminResponse.ok) throw new Error("Could not load admin records");
          setUsers(await userResponse.json());
          setAdmins(await adminResponse.json());
        })
        .catch((loadError) => setError(loadError.message));
    }, []);

    return (
      <div>
        <div className="navbar">
          <h2>
            Admin Dashboard
          </h2>
          <button
            onClick={() => {
              setAdminCredentials(null);
              setPage("home");
            }}
          >
            Logout
          </button>
        </div>
        <div className="dashboard">
          <h1>
            Users ({users.length})
          </h1>
          <p>
            Registered account details.
          </p>
          {error && <p className="error-banner">{error}</p>}
          {resetPassword && (
            <div className="reset-password-result" role="status">
              <div>
                Temporary password for <strong>{resetPassword.name}</strong>
                <code>{resetPassword.password}</code>
                <small>This is shown once. The user must change it at sign-in.</small>
              </div>
              <button onClick={() => setResetPassword(null)} aria-label="Dismiss temporary password">Dismiss</button>
            </div>
          )}
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>
                  Name
                </th>
                <th>
                  Email
                </th>
                <th>Registered</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? <tr><td colSpan="5">No registered users</td></tr> : users.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.name}</td>
                  <td>{user.email}</td>
                  <td>{user.created_at ? new Date(user.created_at * 1000).toLocaleString() : "—"}</td>
                  <td>
                    <button onClick={() => resetUserPassword(user)}>Reset password</button>
                    <button className="delete-user-button" onClick={() => deleteUser(user)}>Delete user</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <h2>Admin Accounts</h2>
          <table>
            <thead><tr><th>Username</th><th>Email</th></tr></thead>
            <tbody>{admins.length === 0 ? <tr><td colSpan="2">No admin accounts</td></tr> : admins.map((admin) => (
              <tr key={admin.id}><td>{admin.username}</td><td>{admin.email || "—"}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    );
  }
  // SHOW CURRENT PAGE
  if (page === "home") {
    return <Home />;
  }
  if (page === "signup") {
    return <Signup />;
  }
  if (page === "login") {
    return <Login />;
  }
  if (page === "changePassword") {
    return <ChangePassword />;
  }
  if (page === "admin") {
    return <AdminLogin />;
  }
  if (page === "camera") {
    return <Camera />;
  }
  if (page === "collection") {
    return <Collection />;
  }
  if (page === "analytics") {
    return <Analytics />;
  }
  if (page === "coaching") {
    return <Coaching />;
  }
  if (page === "settings") {
    return <Settings />;
  }
  if (page === "dashboard") {
    return <Dashboard />;
  }
  if (page === "summary") {
    return <Summary />;
  }
  if (page === "adminDashboard") {
    return <AdminDashboard />;
  }
  return <Home />;
}
export default App;