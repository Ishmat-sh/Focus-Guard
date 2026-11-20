import { useEffect, useRef, useState } from "react";

const MINIMIZED_KEY = "focus_guard_camera_preview_minimized";
const POSITION_KEY = "focus_guard_camera_preview_position";

function readSavedPosition() {
  const saved = window.localStorage.getItem(POSITION_KEY);
  if (!saved) return null;
  const [left, top] = saved.split(",").map(Number);
  return Number.isFinite(left) && Number.isFinite(top) ? { left, top } : null;
}

function clampPosition(left, top, bounds) {
  return {
    left: Math.max(8, Math.min(window.innerWidth - bounds.width - 8, left)),
    top: Math.max(8, Math.min(window.innerHeight - bounds.height - 8, top)),
  };
}

export default function CameraPreview({ videoRef, stream, attention }) {
  // These local preferences are non-sensitive and preserve the preview layout between sessions.
  const [minimized, setMinimized] = useState(
    () => window.localStorage.getItem(MINIMIZED_KEY) === "true",
  );
  const [position, setPosition] = useState(readSavedPosition);
  const pipRef = useRef(null);
  const dragRef = useRef(null);

  useEffect(() => {
    window.localStorage.setItem(MINIMIZED_KEY, String(minimized));
  }, [minimized]);

  useEffect(() => {
    if (!position) return;
    window.localStorage.setItem(POSITION_KEY, `${position.left},${position.top}`);
  }, [position]);

  useEffect(() => {
    if (!stream || !position || !pipRef.current) return;
    const clamped = clampPosition(
      position.left,
      position.top,
      pipRef.current.getBoundingClientRect(),
    );
    if (clamped.left !== position.left || clamped.top !== position.top) {
      setPosition(clamped);
    }
  }, [minimized, position, stream]);

  useEffect(() => {
    if (!stream) return undefined;
    function keepPreviewVisible() {
      const bounds = pipRef.current?.getBoundingClientRect();
      if (!bounds) return;
      setPosition((current) => (
        current ? clampPosition(current.left, current.top, bounds) : current
      ));
    }
    window.addEventListener("resize", keepPreviewVisible);
    return () => window.removeEventListener("resize", keepPreviewVisible);
  }, [stream]);

  if (!stream) return null;

  // Pointer and keyboard movement share the same viewport-clamped position.
  function startDrag(event) {
    if (event.target.closest?.("button")) return;
    if (event.button !== 0 && event.pointerType !== "touch") return;

    const bounds = pipRef.current.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - bounds.left,
      offsetY: event.clientY - bounds.top,
    };
    setPosition({ left: bounds.left, top: bounds.top });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function drag(event) {
    const dragState = dragRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    const bounds = pipRef.current.getBoundingClientRect();
    setPosition({
      ...clampPosition(
        event.clientX - dragState.offsetX,
        event.clientY - dragState.offsetY,
        bounds,
      ),
    });
  }

  function stopDrag(event) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function moveWithKeyboard(event) {
    const directions = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const direction = directions[event.key];
    if (!direction) return;

    event.preventDefault();
    const bounds = pipRef.current.getBoundingClientRect();
    const distance = event.shiftKey ? 24 : 10;
    setPosition({
      ...clampPosition(
        bounds.left + direction[0] * distance,
        bounds.top + direction[1] * distance,
        bounds,
      ),
    });
  }

  return (
    <aside
      ref={pipRef}
      className={`camera-pip${minimized ? " minimized" : ""}`}
      aria-label="Camera preview"
      style={position ? { left: `${position.left}px`, top: `${position.top}px`, right: "auto", bottom: "auto" } : undefined}
    >
      <div
        className="camera-pip-header"
        role="group"
        tabIndex={0}
        aria-label="Move camera preview with drag or arrow keys"
        title="Drag to move · focus and use arrow keys for precise placement"
        onPointerDown={startDrag}
        onPointerMove={drag}
        onPointerUp={stopDrag}
        onPointerCancel={stopDrag}
        onKeyDown={moveWithKeyboard}
      >
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
      <video
        className={minimized ? "camera-video-hidden" : ""}
        ref={videoRef}
        autoPlay
        playsInline
        muted
        aria-label="Live camera preview"
        aria-hidden={minimized}
      />
    </aside>
  );
}
