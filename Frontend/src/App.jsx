import { useState, useEffect } from "react";

function App() {
  // This controls which page is displayed
  const [page, setPage] = useState("home");
  // =====================================================
  // HOME PAGE
  // =====================================================
  function Home() {
    return (
      <div className="page">
        <h1>Focus Tracker</h1>
        <p>
          Track your focus and performance.
        </p>
        <br />
        <button
          onClick={() => setPage("signup")}
        >
          Sign Up
        </button>
        <button
          onClick={() => setPage("login")}
        >
          Sign In
        </button>
        <br />
        <br />
        <button
          onClick={() => setPage("admin")}
        >
          Admin Login
        </button>
      </div>
    );
  }
  // =====================================================
  // SIGN UP PAGE
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
      // Go to camera page
      setPage("camera");
    }
    return (
      <div className="page">
        <h2>Sign Up</h2>
        <p>
          Create a new account.
        </p>
        <form onSubmit={signup}>
          <input
            type="text"
            placeholder="Name"
            value={name}
            onChange={(e) =>
              setName(e.target.value)
            }
            required
          />
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) =>
              setEmail(e.target.value)
            }
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) =>
              setPassword(e.target.value)
            }
            required
          />
          <button type="submit">
            Create Account
          </button>
        </form>
        <br />
        <button
          onClick={() => setPage("login")}
        >
          Already have an account?
        </button>
        <br />
        <button
          onClick={() => setPage("home")}
        >
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
      // Go to camera page
      setPage("camera");
    }
    return (
      <div className="page">
        <h2>Sign In</h2>
        <p>
          Sign in to your account.
        </p>
        <form onSubmit={login}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) =>
              setEmail(e.target.value)
            }
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) =>
              setPassword(e.target.value)
            }
            required
          />
          <button type="submit">
            Sign In
          </button>
        </form>
        <br />
        <button
          onClick={() => setPage("signup")}
        >
          Create Account
        </button>
        <br />
        <button
          onClick={() => setPage("home")}
        >
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
      // Temporary admin login
      // We will connect this to the backend later
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
        <p>
          Login to the admin panel.
        </p>
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
        <button
          onClick={() => setPage("home")}
        >
          Back
        </button>
      </div>
    );
  }
  // =====================================================
  // CAMERA ACCESS PAGE
  // =====================================================
  function Camera() {
    const [cameraEnabled, setCameraEnabled] =
      useState(false);
    async function enableCamera() {
      try {
        // Ask browser for camera access
        const stream =
          await navigator.mediaDevices.getUserMedia({
            video: true
          });
        // Save camera stream
        window.cameraStream = stream;
        // Camera is now enabled
        setCameraEnabled(true);
        alert("Camera access allowed!");
      }
      catch (error) {
        console.log(error);
        alert("Camera access denied.");
      }
    }
    return (
      <div className="page">
        <h2>Camera Access</h2>
        <p>
          Focus Tracker needs access to your camera
          to measure vision and focus.
        </p>
        <button
          onClick={enableCamera}
        >
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
        <button
          onClick={() => setPage("home")}
        >
          Back
        </button>
      </div>
    );
  }
  // =====================================================
  // DASHBOARD
  // =====================================================
  function Dashboard() {
    const [seconds, setSeconds] =
      useState(0);
    // =========================================
    // STOPWATCH
    // ==========================================
    useEffect(() => {
      const timer = setInterval(() => {
        setSeconds(
          oldSeconds => oldSeconds + 1
        );
      }, 1000);
      return () => {
        clearInterval(timer);
      };
    }, []);
    // ==========================================
    // CAMERA
    // ==========================================
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
    }, []);
    // ==========================================
    // FORMAT TIME
    // ==========================================
    function formatTime(totalSeconds) {
      const minutes =
        Math.floor(totalSeconds / 60);
      const seconds =
        totalSeconds % 60;
      return (
        String(minutes).padStart(2, "0")
        +
        ":"
        +
        String(seconds).padStart(2, "0")
      );
    }
    return (
      <div>
        {/* =========================
            NAVBAR
        ========================= */}
        <div className="navbar">
          <h2>
            Focus Tracker
          </h2>
          <button
            onClick={() => setPage("home")}
          >
            Logout
          </button>
        </div>
        {/* =========================
            DASHBOARD
        ========================= */}
        <div className="dashboard">
          <h1>
            Dashboard
          </h1>
          <p>
            Your session is running.
          </p>
          {/* =========================
              CAMERA
          ========================= */}
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
          {/* =========================
              METRICS
          ========================= */}
          <div className="metrics">
            <div className="box">
              <h3>
                Score
              </h3>
              <p>
                85
              </p>
            </div>
            <div className="box">
              <h3>
                State
              </h3>
              <p>
                Focused
              </p>
            </div>
            <div className="box">
              <h3>
                Stopwatch
              </h3>
              <p>
                {formatTime(seconds)}
              </p>
            </div>
            <div className="box">
              <h3>
                Vision
              </h3>
              <p>
                90%
              </p>
            </div>
            <div className="box">
              <h3>
                Current App
              </h3>
              <p>
                Chrome
              </p>
            </div>
          </div>
          {/* =========================
              END SESSION
          ========================= */}
          <button
            className="end-button"
            onClick={() =>
              setPage("summary")
            }
          >
            End Session
          </button>
        </div>
      </div>
    );
  }
  // =====================================================
  // SESSION SUMMARY
  // =====================================================
  function Summary() {
    return (
      <div className="page">
        <h1>
          Session Summary
        </h1>
        <h3>
          Session Completed
        </h3>
        <hr />
        <p>
          Score:
          <b> 85</b>
        </p>
        <p>
          Vision:
          <b> 90%</b>
        </p>
        <p>
          State:
          <b> Focused</b>
        </p>
        <p>
          Duration:
          <b> 25 minutes</b>
        </p>
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
  // =====================================================
  // ADMIN DASHBOARD
  // =====================================================
  function AdminDashboard() {
    return (
      <div>
        {/* NAVBAR */}
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
        {/* ADMIN CONTENT */}
        <div className="dashboard">
          <h1>
            Users
          </h1>
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
  // =====================================================
  // CHOOSE WHICH PAGE TO DISPLAY
  // =====================================================
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
}
export default App;