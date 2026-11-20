import { useEffect, useState } from "react";
import AdminUsersTable from "./AdminUsersTable.jsx";
import TelemetryInspector from "./TelemetryInspector.jsx";
import DatabaseTables from "./DatabaseTables.jsx";
import { apiRequest } from "../../services/api.js";

export default function AdminDashboard({ apiFetch, onLogout }) {
  const [telemetry, setTelemetry] = useState(null);
  const [admins, setAdmins] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");
  const [error, setError] = useState("");
  const [resetPassword, setResetPassword] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setError("");
    try {
      const [overview, adminAccounts] = await Promise.all([
        apiRequest(apiFetch, "/admin/telemetry"),
        apiRequest(apiFetch, "/admins"),
      ]);
      setTelemetry(overview);
      setAdmins(adminAccounts || []);
      setSelectedUser((selected) =>
        selected ? overview.users.find((user) => user.id === selected.id) || null : null,
      );
    } catch (loadError) {
      setError(loadError.message || "Could not load admin telemetry");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 15000);
    return () => window.clearInterval(timer);
  }, [apiFetch]);

  async function actOnUser(user, action) {
    if (action === "delete" && !window.confirm(
      `Permanently delete ${user.name} and all of their sessions? This cannot be undone.`,
    )) return;
    if (action === "reset" && !window.confirm(
      `Reset the password for ${user.name}? They will need to choose a new password.`,
    )) return;
    if (action === "end" && !window.confirm(`Force-end ${user.name}'s active session?`)) return;

    try {
      const result = await apiRequest(
        apiFetch,
        action === "delete"
          ? `/admin/users/${user.id}`
          : action === "reset"
            ? `/admin/users/${user.id}/password-reset`
            : `/admin/users/${user.id}/sessions/end`,
        { method: action === "reset" || action === "end" ? "POST" : "DELETE" },
      );
      if (action === "reset") {
        setResetPassword({ name: user.name, password: result.temporary_password });
      } else {
        setSelectedUser(null);
      }
      await load();
    } catch (actionError) {
      setError(actionError.message || "The admin action could not be completed");
    }
  }

  const summary = telemetry?.summary;
  return (
    <main className="page-wrap">
      <header className="controls-row" style={{ marginBottom: "1.25rem" }}>
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Admin telemetry</h1>
        </div>
        <button className="button-quiet" onClick={onLogout}>Log out</button>
      </header>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {resetPassword && (
        <div className="reset-password-result" role="status">
          <div>
            <strong>Temporary password for {resetPassword.name}</strong>
            <code>{resetPassword.password}</code>
            <small>This is shown once. The user must change it at sign-in.</small>
          </div>
          <button className="button-secondary" onClick={() => setResetPassword(null)}>Dismiss</button>
        </div>
      )}
      {loading ? (
        <p className="loading">Loading telemetry…</p>
      ) : (
        <>
          <section className="kpi-grid" aria-label="Admin summary">
            {[
              ["Registered users", summary?.registered_users ?? "—"],
              ["Active sessions", summary?.active_sessions ?? "—"],
              [
                "Average focus rate",
                summary?.average_focus_score == null
                  ? "—"
                  : `${Math.round(summary.average_focus_score)}%`,
              ],
              ["Admin accounts", admins.length],
            ].map(([label, value]) => (
              <article className="kpi-card" key={label}>
                <span className="kpi-label">{label}</span>
                <strong className="kpi-value tabular">{value}</strong>
              </article>
            ))}
          </section>
          <section style={{ marginTop: "1rem" }}>
            <p className="eyebrow">User management</p>
            <AdminUsersTable
              users={telemetry?.users || []}
              selectedUser={selectedUser}
              onSelect={setSelectedUser}
              search={search}
              setSearch={setSearch}
              filter={filter}
              setFilter={setFilter}
            />
          </section>
          <section style={{ marginTop: "1rem" }}>
            {/* Restrict raw table inspection to the authenticated admin dashboard. */}
            <DatabaseTables apiFetch={apiFetch} />
          </section>
        </>
      )}
      <TelemetryInspector
        user={selectedUser}
        onClose={() => setSelectedUser(null)}
        onResetPassword={(user) => actOnUser(user, "reset")}
        onDeleteUser={(user) => actOnUser(user, "delete")}
        onEndSession={(user) => actOnUser(user, "end")}
      />
    </main>
  );
}
