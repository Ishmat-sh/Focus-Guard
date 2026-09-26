import { useState, useEffect } from "react";

function App() {
  // This controls which page is displayed
  const [page, setPage] = useState("home");
  const [adminCredentials, setAdminCredentials] = useState(null);
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
    async function signup(e) {
      e.preventDefault();

      try {
        const response = await fetch("http://localhost:8000/users", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ name, email, password })
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.detail || "Could not create account");
        }

        alert("Account created!");
        setPage("camera");
      } catch (error) {
        alert(error.message || "Failed to create account");
      }
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
    async function adminLogin(e) {
      e.preventDefault();
      try {
        const response = await fetch("http://localhost:8000/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password })
        });

        if (!response.ok) {
          throw new Error("Invalid admin credentials");
        }

        setAdminCredentials({ username, password });
        alert("Admin login successful!");
        setPage("adminDashboard");
      } catch (error) {
        alert(error.message || "Wrong username or password");
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
    const [tables, setTables] = useState([]);
    const [activeTable, setActiveTable] = useState("");
    const [tableData, setTableData] = useState(null);
    const [tableSearch, setTableSearch] = useState("");
    const [offset, setOffset] = useState(0);
    const [activeView, setActiveView] = useState("documents");
    const [refreshKey, setRefreshKey] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const pageSize = 100;

    useEffect(() => {
      async function loadTables() {
        try {
          const authorization = `Basic ${btoa(`${adminCredentials.username}:${adminCredentials.password}`)}`;
          const response = await fetch("http://localhost:8000/admin/database/tables", {
            headers: { Authorization: authorization }
          });
          if (!response.ok) throw new Error("Could not load database tables");
          const data = await response.json();
          setTables(data);
          setActiveTable((current) => current || data[0]?.name || "");
          setError("");
        } catch (loadError) {
          setError(loadError.message || "Could not connect to the database");
        }
      }

      loadTables();
    }, [refreshKey, adminCredentials]);

    useEffect(() => {
      if (!activeTable) {
        setLoading(false);
        return;
      }

      let cancelled = false;
      async function loadTable() {
        setLoading(true);
        try {
          const response = await fetch(
            `http://localhost:8000/admin/database/tables/${encodeURIComponent(activeTable)}?limit=${pageSize}&offset=${offset}`,
            { headers: { Authorization: `Basic ${btoa(`${adminCredentials.username}:${adminCredentials.password}`)}` } }
          );
          if (!response.ok) throw new Error("Could not load this table");
          const data = await response.json();
          if (!cancelled) {
            setTableData(data);
            setError("");
          }
        } catch (loadError) {
          if (!cancelled) setError(loadError.message || "Could not load this table");
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      loadTable();
      return () => { cancelled = true; };
    }, [activeTable, offset, refreshKey]);

    const visibleTables = tables.filter((table) =>
      table.name.toLowerCase().includes(tableSearch.toLowerCase())
    );

    function selectTable(name) {
      setActiveTable(name);
      setOffset(0);
    }

    return (
      <div className="database-page">
        <header className="database-navbar">
          <div className="database-brand"><span className="database-brand-mark">FG</span><strong>Focus Guard</strong><span className="database-divider" /> <span>Database</span></div>
          <div className="database-navbar-actions">
            <span className="database-engine">SQLite</span>
             <button className="database-logout" onClick={() => { setAdminCredentials(null); setPage("home"); }}>Log out</button>
          </div>
        </header>
        <div className="database-crumb"><span>Connections</span><span>/</span><strong>focus_guard.db</strong></div>
        <main className="database-workspace">
          <aside className="database-sidebar">
            <div className="database-sidebar-title"><span>COLLECTIONS</span><span>{tables.length}</span></div>
            <label className="database-search">
              <span aria-hidden="true">⌕</span>
              <input value={tableSearch} onChange={(event) => setTableSearch(event.target.value)} placeholder="Filter tables" aria-label="Filter tables" />
            </label>
            <div className="database-table-list">
              {visibleTables.map((table) => (
                <button
                  className={`database-table-item ${activeTable === table.name ? "active" : ""}`}
                  key={table.name}
                  onClick={() => selectTable(table.name)}
                >
                  <span className="database-table-icon" aria-hidden="true">▤</span>
                  <span className="database-table-name">{table.name}</span>
                  <span className="database-table-count">{table.row_count}</span>
                </button>
              ))}
              {visibleTables.length === 0 && <div className="database-sidebar-empty">No matching tables</div>}
            </div>
            <div className="database-sidebar-footer"><span className="database-status-dot" /> Connected to local database</div>
          </aside>
          <section className="database-main">
            <div className="database-toolbar">
              <div>
                <div className="database-eyebrow">TABLE</div>
                <h1>{activeTable || "Database tables"}</h1>
              </div>
              <button className="database-refresh" title="Refresh database" aria-label="Refresh database" onClick={() => setRefreshKey((key) => key + 1)}>↻</button>
            </div>
            {error && <div className="database-error">{error}</div>}
            <div className="database-tabs">
              <button className={activeView === "documents" ? "selected" : ""} onClick={() => setActiveView("documents")}>Documents <b>{tableData?.total ?? 0}</b></button>
              <button className={activeView === "schema" ? "selected" : ""} onClick={() => setActiveView("schema")}>Schema <b>{tableData?.columns?.length ?? 0}</b></button>
            </div>
            {activeView === "documents" ? <>
              <div className="database-grid-wrap">
                {loading ? <div className="database-empty">Loading table data…</div> : tableData?.rows?.length ? (
                  <table className="database-grid">
                    <thead><tr>{tableData.columns.map((column) => <th key={column.name}><span>{column.name}</span><small>{column.type || "ANY"}{column.primary_key ? " · PK" : ""}</small></th>)}</tr></thead>
                    <tbody>{tableData.rows.map((row, rowIndex) => (
                      <tr key={`${activeTable}-${offset}-${rowIndex}`}>
                        {tableData.columns.map((column) => {
                          const value = row[column.name];
                          const display = value === null || value === undefined ? "NULL" : typeof value === "object" ? JSON.stringify(value) : String(value);
                          return <td key={column.name} title={display} className={value == null ? "is-null" : ""}>{display}</td>;
                        })}
                      </tr>
                    ))}</tbody>
                  </table>
                ) : <div className="database-empty">{activeTable ? "This table is empty" : "No tables found"}</div>}
              </div>
              <footer className="database-grid-footer">
                <span>{tableData ? `${tableData.total === 0 ? 0 : offset + 1}–${Math.min(offset + pageSize, tableData.total)} of ${tableData.total} rows` : "Select a table to browse its rows"}</span>
                <div className="database-pagination">
                  <button disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - pageSize))} aria-label="Previous page">‹</button>
                  <span>{tableData?.total ? Math.floor(offset / pageSize) + 1 : 0}</span>
                  <button disabled={!tableData || offset + pageSize >= tableData.total || loading} onClick={() => setOffset(offset + pageSize)} aria-label="Next page">›</button>
                </div>
              </footer>
            </> : <section className="database-schema">
              <div className="database-schema-heading"><h2>{activeTable} fields</h2><span>{tableData?.columns?.length ?? 0} fields</span></div>
              <div className="database-schema-list">
                {tableData?.columns?.map((column) => (
                  <div className="database-schema-row" key={column.name}>
                    <code>{column.name}</code><span>{column.type || "ANY"}</span>
                    <small>{column.primary_key ? "PRIMARY KEY" : column.not_null ? "REQUIRED" : "NULLABLE"}</small>
                  </div>
                ))}
              </div>
            </section>}
          </section>
        </main>
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