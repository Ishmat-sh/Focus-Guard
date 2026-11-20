// Timeline state colors match the muted focus palette used throughout the interface.
const COLORS = {
  focused: "#47745a",
  drifting: "#a77a37",
  distracted: "#a9514b",
};

function formatTimestamp(seconds) {
  if (!Number.isFinite(seconds)) return "Unknown time";
  return new Date(seconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function makeSegments(samples, sessionDuration) {
  const segments = [];
  for (let index = 0; index < samples.length - 1; index += 1) {
    const sample = samples[index];
    const next = samples[index + 1];
    const gap = Number(next.elapsed_seconds) - Number(sample.elapsed_seconds);
    const duration = gap > 0 && gap <= 30 ? gap : 0;
    if (!duration || !COLORS[sample.state]) continue;
    const previous = segments.at(-1);
    if (previous && previous.state === sample.state && previous.domain === sample.domain) {
      previous.duration += duration;
      previous.endElapsed = Number(next.elapsed_seconds);
    } else {
      segments.push({
        state: sample.state,
        domain: sample.domain || sample.app_name || "Unknown context",
        startElapsed: Number(sample.elapsed_seconds),
        endElapsed: Number(next.elapsed_seconds),
        startTimestamp: Number(sample.recorded_at),
        duration,
      });
    }
  }
  if (samples.length) {
    const last = samples.at(-1);
    const gap = sessionDuration - Number(last.elapsed_seconds);
    const remaining = gap > 0 && gap <= 30 ? gap : 0;
    if (remaining && COLORS[last.state]) {
      segments.push({
        state: last.state,
        domain: last.domain || last.app_name || "Unknown context",
        startElapsed: Number(last.elapsed_seconds),
        endElapsed: Number(last.elapsed_seconds) + remaining,
        startTimestamp: Number(last.recorded_at),
        duration: remaining,
      });
    }
  }
  return segments;
}

export default function DriftTimeline({ samples = [], sessionDuration = 0 }) {
  const segments = makeSegments(samples, sessionDuration);
  const totalElapsed = Math.max(1, sessionDuration || samples.at(-1)?.elapsed_seconds || 1);
  if (!segments.length) {
    return <p className="empty">No session state samples are available for this timeline.</p>;
  }

  return (
    <div>
      <svg
        className="timeline-track"
        viewBox="0 0 1000 32"
        preserveAspectRatio="none"
        role="img"
        aria-label="Focused, drifting, and distracted states over session time"
      >
        {segments.map((segment, index) => {
          const x = (segment.startElapsed / totalElapsed) * 1000;
          const width = Math.max(1, (segment.duration / totalElapsed) * 1000);
          const time = formatTimestamp(segment.startTimestamp);
          return (
            <rect
              key={`${segment.state}-${segment.startElapsed}-${index}`}
              x={x}
              y="0"
              width={width}
              height="32"
              fill={COLORS[segment.state]}
            >
              <title>
                {`${time} · ${segment.state} · ${segment.domain} · ${Math.round(segment.duration)}s`}
              </title>
            </rect>
          );
        })}
      </svg>
      <div className="timeline-legend">
        {Object.entries(COLORS).map(([state, color]) => (
          <span key={state}>
            <i className="legend-dot" style={{ "--legend-color": color }} />
            {state}
          </span>
        ))}
      </div>
      <small style={{ display: "block", marginTop: "0.75rem" }}>
        Hover a segment for its timestamp and active context. Unobserved gaps are left blank.
      </small>
    </div>
  );
}
