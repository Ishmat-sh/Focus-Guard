import { useState, useEffect } from "react";

const API = "http://localhost:8000";

function App() {
  const [page, setPage] = useState("home");

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

    function signup(e) {
      e.preventDefault();

      console.log("Name:", name);
      console.log("Email:", email);
      console.log("Password:", password);

      alert("Account created!");

      setPage("camera");
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

    function login(e) {
      e.preventDefault();

      console.log("Email:", email);
      console.log("Password:", password);

      alert("Login successful!");

      setPage("camera");
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

    function adminLogin(e) {
      e.preventDefault();

      if (
        username === "admin" &&
        password === "admin123"
      ) {
        alert("Admin login successful!");
        setPage("adminDashboard");
      } else {
        alert("Wrong username or password");
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

        <button onClick={() => setPage("home")}>
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
      blink_frequency: 0,
      gaze: "Unknown",
      head_pose: "Unknown",
      posture: "Unknown",
      vision_score: 0,
    });

    const [history, setHistory] = useState([]);

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
      const response = await fetch(
        `${API}${path}`,
        options
      );

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

    // -------------------------------------------------
    // REFRESH DATA
    // -------------------------------------------------

    async function refresh() {
      try {
        const [
          current,
          live,
          past,
        ] = await Promise.all([
          request("/sessions/current"),
          request("/attention"),
          request("/history"),
        ]);

        setSession(current);

        setAttention((old) => ({
          ...old,
          ...live,
        }));

        setHistory(past);

        setError("");

        setLoading(false);
      } catch (requestError) {
        console.log(requestError);

        setError(
          "Backend offline. Start FastAPI on port 8000."
        );

        setLoading(false);
      }
    }

    // -------------------------------------------------
    // START API POLLING
    // -------------------------------------------------

    useEffect(() => {
      refresh();

      const interval = setInterval(
        refresh,
        1000
      );

      return () => clearInterval(interval);
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
            onClick={() => {
              stopCamera();
              setPage("home");
            }}
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
                Score
              </h3>
              <p className="big-number">
                {score}
              </p>
            </div>
            <div className="box">
              <h3>
                State
              </h3>
              <p>
                {attention.state}
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
                {visionScore}%
              </p>
            </div>
          </div>
          {/* SESSION CONTROLS */}
          <div className="session-controls">
            <button
              className="start-button"
              onClick={() =>
                action(
                  "/sessions/start"
                )
              }
            >
              Start
            </button>
            <button
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
                <span>
                  Blink Count
                </span>
                <strong>
                  {attention.blink_count ??
                    0}
                </strong>
              </div>
              <div className="vision-box">
                <span>
                  Blink Frequency
                </span>
                <strong>
                  {attention.blink_frequency ??
                    0}
                </strong>
              </div>
              <div className="vision-box">
                <span>
                  Gaze
                </span>
                <strong>
                  {attention.gaze ||
                    "Unknown"}
                </strong>
              </div>
              <div className="vision-box">
                <span>
                  Head Pose
                </span>
                <strong>
                  {attention.head_pose ||
                    "Unknown"}
                </strong>
              </div>
              <div className="vision-box">
                <span>
                  Posture
                </span>
                <strong>
                  {attention.posture ||
                    "Unknown"}
                </strong>
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
          const response =
            await fetch(
              `${API}/history`
            );
          const data =
            await response.json();
          if (
            data &&
            data.length > 0
          ) {
            setSummary(
              data[data.length - 1]
            );
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
        <button
          onClick={() =>
            setPage("home")
          }
        >
          Logout
        </button>
      </div>
    );
  }
  // ADMIN DASHBOARD
  function AdminDashboard() {
    return (
      <div>
        <div className="navbar">
          <h2>
            Admin Dashboard
          </h2>
          <button
            onClick={() =>
              setPage("home")
            }
          >
            Logout
          </button>
        </div>
        <div className="dashboard">
          <h1>
            Users
          </h1>
          <p>
            Registered users and
            performance information.
          </p>
          <table>
            <thead>
              <tr>
                <th>
                  Name
                </th>
                <th>
                  Email
                </th>
                <th>
                  Score
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  User 1
                </td>
                <td>
                  user1@gmail.com
                </td>
                <td>
                  85
                </td>
              </tr>
              <tr>
                <td>
                  User 2
                </td>
                <td>
                  user2@gmail.com
                </td>
                <td>
                  78
                </td>
              </tr>
            </tbody>
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