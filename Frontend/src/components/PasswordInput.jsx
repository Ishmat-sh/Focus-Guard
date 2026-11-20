import { useState } from "react";

export default function PasswordInput(props) {
  const [visible, setVisible] = useState(false);

  return (
    <span className="password-field">
      <input {...props} type={visible ? "text" : "password"} />
      {/* Keep visibility explicit and reversible, with a label for assistive technology. */}
      <button
        className="password-visibility-toggle"
        type="button"
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        onClick={() => setVisible((current) => !current)}
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
          <circle cx="12" cy="12" r="3" />
          {visible && <path d="m4 4 16 16" />}
        </svg>
      </button>
    </span>
  );
}
