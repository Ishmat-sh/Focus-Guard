import { useState } from "react";

export default function CameraPreview({ videoRef, stream, attention }) {
  const [minimized, setMinimized] = useState(false);
  if (!stream) return null;

  return (
    <aside className={`camera-pip${minimized ? " minimized" : ""}`} aria-label="Camera preview">
      <div className="camera-pip-header">
        {!minimized && (
          <span className="status-indicator online">
            <span className="status-dot" />
            {attention ? "Vision sampling" : "Camera on"}
          </span>
        )}
        {minimized && <span className="badge focused">Camera On</span>}
        <button
          className="button-secondary"
          onClick={() => setMinimized((value) => !value)}
          aria-expanded={!minimized}
          aria-label={minimized ? "Expand camera preview" : "Minimize camera preview"}
        >
          {minimized ? "Expand" : "Minimize"}
        </button>
      </div>
      {!minimized && <video ref={videoRef} autoPlay playsInline muted aria-label="Live camera preview" />}
    </aside>
  );
}
