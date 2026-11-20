const FILTERS = ["All", "Active Now", "Flagged / Distracted"];

export default function AdminUsersTable({ users, selectedUser, onSelect, search, setSearch, filter, setFilter }) {
  const query = search.trim().toLowerCase();
  const rows = users.filter((user) => {
    const matchesText =
      !query ||
      [user.name, user.email, String(user.id)].some((value) =>
        String(value || "").toLowerCase().includes(query),
      );
    const matchesFilter =
      filter === "All" ||
      (filter === "Active Now" && Boolean(user.current_session)) ||
      (filter === "Flagged / Distracted" && user.dominant_state === "distracted");
    return matchesText && matchesFilter;
  });

  return (
    <section className="panel">
      <div className="controls-row" style={{ marginBottom: "1rem" }}>
        <input
          aria-label="Search users"
          placeholder="Search name, email, or ID"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          style={{ maxWidth: "320px" }}
        />
        <div className="auth-tabs" role="group" aria-label="Filter users" style={{ margin: 0 }}>
          {FILTERS.map((item) => (
            <button
              key={item}
              aria-pressed={filter === item}
              onClick={() => setFilter(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Status</th>
              <th>Focus score</th>
              <th>Last active</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((user) => (
              <tr
                key={user.id}
                onClick={() => onSelect(user)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") onSelect(user);
                }}
                tabIndex={0}
                aria-selected={selectedUser?.id === user.id}
                style={{ cursor: "pointer" }}
              >
                <td>
                  <strong>{user.name}</strong>
                  <small style={{ display: "block" }}>{user.email} · #{user.id}</small>
                </td>
                <td>
                  <span className={`badge ${user.current_session ? "focused" : ""}`}>
                    {user.current_session?.state || "idle"}
                  </span>
                </td>
                <td className="tabular">
                  {user.average_focus_score == null
                    ? "—"
                    : `${Math.round(user.average_focus_score)}%`}
                </td>
                <td>{user.last_active_at
                  ? new Date(user.last_active_at * 1000).toLocaleString()
                  : "No telemetry"}</td>
              </tr>
            )) : (
              <tr><td colSpan="4" className="empty">No matching users.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
