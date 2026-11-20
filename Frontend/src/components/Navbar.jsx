import focusGuardLogo from "./focus_guard_logo (1).svg";

export default function Navbar({
  page,
  setPage,
  userAuth,
  adminCredentials,
  onOpenAuth,
  onLogout,
}) {
  const isAdmin = Boolean(adminCredentials);

  return (
    <header className="navbar">
      <a
        className="brand"
        href="#home"
        onClick={(event) => {
          event.preventDefault();
          setPage("home");
        }}
      >
        {/* Use the supplied Focus Guard mark in the shared application header. */}
        <img className="brand-logo" src={focusGuardLogo} alt="" aria-hidden="true" />
        <span>Focus Guard</span>
      </a>
      <nav className="navbar-actions" aria-label="Main navigation">
        {isAdmin ? (
          <>
            <button onClick={() => setPage("adminDashboard")}>Admin</button>
            <button className="button-quiet" onClick={onLogout}>Log out</button>
          </>
        ) : userAuth?.user?.must_change_password ? (
          <button className="button-quiet" onClick={onLogout}>Log out</button>
        ) : userAuth ? (
          <>
            <button
              aria-current={page === "dashboard" ? "page" : undefined}
              onClick={() => setPage("dashboard")}
            >
              Dashboard
            </button>
            <button onClick={() => setPage("session")}>Start Session</button>
            <button onClick={() => setPage("analytics")}>Analytics</button>
            <button onClick={() => setPage("coaching")}>Coaching</button>
            <button onClick={() => setPage("settings")}>Settings</button>
            <span className="badge" title={userAuth.user?.email}>
              {userAuth.user?.name || "Your account"}
            </span>
            <button className="button-quiet" onClick={onLogout}>Log out</button>
          </>
        ) : (
          <>
            <button className="button-quiet" onClick={() => setPage("home")}>Home</button>
            <button className="button-quiet" onClick={() => onOpenAuth("signin")}>Sign In</button>
            <button onClick={() => onOpenAuth("signup")}>Sign Up</button>
          </>
        )}
      </nav>
    </header>
  );
}
