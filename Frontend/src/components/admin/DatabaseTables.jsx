import { useEffect, useState } from "react";
import { apiRequest } from "../../services/api.js";

export default function DatabaseTables({ apiFetch }) {
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("");
  const [inspection, setInspection] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    apiRequest(apiFetch, "/admin/database/tables")
      .then((result) => {
        if (!active) return;
        setTables(result);
        setSelectedTable((current) => current || result[0]?.name || "");
      })
      .catch((loadError) => {
        if (active) setError(loadError.message || "Could not load database tables");
      });
    return () => {
      active = false;
    };
  }, [apiFetch]);

  useEffect(() => {
    if (!selectedTable) return undefined;
    let active = true;
    setInspection(null);
    apiRequest(
      apiFetch,
      `/admin/database/tables/${encodeURIComponent(selectedTable)}?limit=25`,
    )
      .then((result) => {
        if (active) setInspection(result);
      })
      .catch((loadError) => {
        if (active) setError(loadError.message || "Could not inspect this table");
      });
    return () => {
      active = false;
    };
  }, [apiFetch, selectedTable]);

  return (
    <section className="panel database-browser">
      <header>
        <p className="eyebrow">Storage</p>
        <h2>Database tables</h2>
        <p className="muted">
          Select a table to inspect its columns and latest rows. Sensitive fields are redacted.
        </p>
      </header>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {/* This inspection view uses the existing redacted admin endpoint. */}
      <div className="database-browser-layout">
        <nav className="database-table-list" aria-label="Database tables">
          {tables.map((table) => (
            <button
              className={selectedTable === table.name ? "selected" : ""}
              key={table.name}
              onClick={() => {
                setError("");
                setSelectedTable(table.name);
              }}
            >
              <span>{table.name}</span>
              <small>{table.row_count.toLocaleString()}</small>
            </button>
          ))}
        </nav>
        <div className="database-preview">
          {!inspection ? (
            <p className="loading">Loading table preview…</p>
          ) : (
            <>
              <div className="controls-row">
                <h3>{inspection.name}</h3>
                <span className="muted">{inspection.total.toLocaleString()} rows</span>
              </div>
              {inspection.rows.length ? (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {inspection.columns.map((column) => (
                          <th key={column.name}>{column.name}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {inspection.rows.map((row, rowIndex) => (
                        <tr key={`${inspection.name}-${rowIndex}`}>
                          {inspection.columns.map((column) => (
                            <td key={column.name}>
                              {row[column.name] == null
                                ? "—"
                                : typeof row[column.name] === "object"
                                  ? JSON.stringify(row[column.name])
                                  : String(row[column.name])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty">This table has no rows yet.</p>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
