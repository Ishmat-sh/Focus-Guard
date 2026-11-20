import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { apiRequest } from "../services/api.js";
import PasswordInput from "./PasswordInput.jsx";

const TAB_LABELS = {
  signin: "Sign In",
  signup: "Sign Up",
  admin: "Admin",
};

export default function AuthModal({
  apiFetch,
  initialTab = "signin",
  onClose,
  onUserAuthenticated,
  onAdminAuthenticated,
}) {
  const [tab, setTab] = useState(initialTab);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (tab === "signup" && password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      if (tab === "admin") {
        const credentials = { username: username.trim(), password };
        await apiRequest(apiFetch, "/admin/login", {
          method: "POST",
          skipAuth: true,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(credentials),
        });
        onAdminAuthenticated(credentials);
      } else {
        const path = tab === "signup" ? "/users" : "/auth/login";
        const payload = tab === "signup"
          ? { name: name.trim(), email: email.trim(), password }
          : { email: email.trim(), password };
        const result = await apiRequest(apiFetch, path, {
          method: "POST",
          skipAuth: true,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        onUserAuthenticated(result);
      }
    } catch (submitError) {
      setError(submitError.message || "Could not sign in.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <motion.div
        className="auth-backdrop"
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) onClose();
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.section
          className="auth-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="auth-title"
          initial={{ opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.98 }}
        >
          <div className="auth-header">
            <div>
              <p className="eyebrow">Focus Guard account</p>
              <h2 id="auth-title">{TAB_LABELS[tab]}</h2>
            </div>
            <button className="button-quiet" aria-label="Close dialog" onClick={onClose}>Close</button>
          </div>

          <div className="auth-tabs" role="tablist" aria-label="Account type">
            {Object.entries(TAB_LABELS).map(([key, label]) => (
              <button
                key={key}
                role="tab"
                aria-selected={tab === key}
                onClick={() => {
                  setTab(key);
                  setError("");
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <form className="form-stack" onSubmit={submit}>
            {tab === "signup" && (
              <label>
                Name
                <input value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" required />
              </label>
            )}
            {tab === "admin" ? (
              <label>
                Admin username
                <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
              </label>
            ) : (
              <label>
                Email
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
              </label>
            )}
            <label>
              Password
              {/* Reuse the accessible reveal control for sign-in, sign-up, and admin login. */}
              <PasswordInput
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={tab === "signup" ? "new-password" : "current-password"}
                minLength={tab === "signup" ? 8 : undefined}
                required
              />
            </label>
            {error && <p className="error-banner" role="alert">{error}</p>}
            <button type="submit" disabled={loading}>
              {loading && <span className="spinner" aria-hidden="true" />}
              {loading ? "Connecting…" : TAB_LABELS[tab]}
            </button>
          </form>
        </motion.section>
    </motion.div>
  );
}
