function formatDuration(seconds = 0) {
  const minutes = Math.round(Math.max(0, seconds) / 60);
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
}

export default function KpiStrip({ analytics, streaks, domains }) {
  const current = analytics?.comparison?.current;
  const longest = streaks?.longest_streak_seconds || 0;
  const topDomain = (domains || [])
    .filter((domain) => domain.category === "productive")
    .sort((left, right) => right.sample_count - left.sample_count)[0];
  const items = [
    ["Total focus time · 30 days", formatDuration(current?.total_focus_seconds)],
    [
      "Average focus score",
      current?.average_focus_score == null
        ? "—"
        : `${Math.round(current.average_focus_score)}%`,
    ],
    ["Longest focused streak", formatDuration(longest)],
    ["Top productive domain", topDomain?.domain || "—"],
  ];

  return (
    <section className="kpi-grid" aria-label="Focus performance">
      {items.map(([label, value]) => (
        <article className="kpi-card" key={label}>
          <span className="kpi-label">{label}</span>
          <strong className="kpi-value tabular">{value}</strong>
        </article>
      ))}
    </section>
  );
}
