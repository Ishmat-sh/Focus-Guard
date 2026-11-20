import { useState } from "react";

export default function DomainContext({ session, browserContext }) {
  const [message, setMessage] = useState("");

  async function copySessionId() {
    if (!session?.id) return;
    try {
      await navigator.clipboard.writeText(String(session.id));
      setMessage("Session ID copied");
    } catch {
      setMessage("Clipboard access is unavailable in this browser.");
    }
  }

  return (
    <section className="panel">
      <p className="eyebrow">Browser context</p>
      <div className="domain-row">
        <div>
          <strong className="domain-name">{browserContext?.domain || "No recent domain"}</strong>
          <p style={{ margin: "0.35rem 0 0" }}>
            {browserContext
              ? `Extension reporting · ${browserContext.category}`
              : "Extension not reporting a domain for this session"}
          </p>
        </div>
        <span className={`badge${browserContext ? " focused" : ""}`}>
          <span className="status-dot" />
          {browserContext ? "Connected" : "Waiting"}
        </span>
      </div>
      <div className="controls-row" style={{ marginTop: "1rem" }}>
        <button className="button-secondary" disabled={!session?.id} onClick={copySessionId}>
          Copy Session ID
        </button>
        <small role="status">{message}</small>
      </div>
      <small style={{ display: "block", marginTop: "0.8rem" }}>
        Only the active domain is shared; page URLs and titles are not collected.
      </small>
    </section>
  );
}
