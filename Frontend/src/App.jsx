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

  // =====================================================
  // HOME PAGE
  // =====================================================

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

  // =====================================================
  // SIGN UP
  // =====================================================

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

  // =====================================================
  // USER LOGIN
  // =====================================================

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

  // =====================================================
  // ADMIN LOGIN
  // =====================================================

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

  // =====================================================
  // CAMERA ACCESS
  // =====================================================

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

  // =====================================================
  // DASHBOARD
  // =====================================================

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

    const [error, setError] = useState("");

    const [loading, setLoading] = useState(true);

    // -------------------------------------------------
    // STOP CAMERA
    // -------------------------------------------------

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

    // -------------------------------------------------
    // GET DATA FROM BACKEND
    // -------------------------------------------------

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

    // -------------------------------------------------
    // REFRESH DATA
    // -------------------------------------------------

    async function refresh() {
      try {
        const [current, past] = await Promise.all([
          request("/sessions/current"),
          request("/history"),
        ]);
        const live = current.state === "running" ? await requestAttention() : null;

        setSession(current);

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

    // -------------------------------------------------
    // START API POLLING
    // -------------------------------------------------

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

    // -------------------------------------------------
    // CAMERA DISPLAY
    // -------------------------------------------------

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

    // -------------------------------------------------
    // BACKEND SESSION TIME
    // -------------------------------------------------

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
          <button
            onClick={logoutUser}
          >
            Logout
          </button>
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
                <strong>Not measured</strong>
              </div>
            </div>
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