function tensionColor(v) {
  const n = Number(v) || 0;
  if (n >= 75) return "#FF3B30";
  if (n >= 55) return "#FF9500";
  if (n >= 35) return "#FFCC00";
  return "#34C759";
}

function interpretArc(values) {
  if (!values.length) return "No scenes yet";
  if (values.length === 1) return "Single scene — too short to read an arc";
  const max = Math.max(...values);
  const min = Math.min(...values);
  if (max - min < 15) return "Flat tension curve";

  // Split into three buckets to detect a sag.
  const third = Math.max(1, Math.floor(values.length / 3));
  const first = values.slice(0, third);
  const middle = values.slice(third, values.length - third);
  const last = values.slice(values.length - third);
  const avg = (a) => (a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0);
  const a1 = avg(first);
  const a2 = avg(middle.length ? middle : first);
  const a3 = avg(last);

  // Strong climax: last bucket is the highest AND the very last value >= 75.
  if (a3 > a1 && a3 > a2 && values[values.length - 1] >= 75) {
    return "Strong climax build";
  }
  // Sag: middle is noticeably lower than both ends.
  if (a2 + 5 < a1 && a2 + 5 < a3) return "Middle sag detected";
  // Generally rising: last bucket > first bucket by >= 8.
  if (a3 >= a1 + 8) return "Rising tension arc";
  // Generally falling.
  if (a1 >= a3 + 8) return "Falling tension arc";
  return "Steady tension";
}

export function EpisodeArcStrip({ scenes }) {
  if (!scenes || scenes.length === 0) return null;
  const usable = scenes.filter((s) => s.tension_level != null);
  if (usable.length === 0) return null;
  const values = usable.map((s) => Number(s.tension_level) || 0);
  const label = interpretArc(values);
  return (
    <div className="es-card p-4" data-testid="episode-arc-strip">
      <div className="flex items-end justify-between mb-3 gap-3">
        <div>
          <p className="es-label">Episode arc</p>
          <h4
            className="font-display text-lg font-bold mt-0.5"
            data-testid="episode-arc-label"
          >
            {label}
          </h4>
          <p className="text-xs text-[#A1A1AA] mt-1">
            One bar per scene · height ≈ tension_level / 100. Hover a bar for details.
          </p>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA]">
          {usable.length} scenes
        </div>
      </div>
      <div
        className="flex items-end gap-1.5 h-24"
        data-testid="episode-arc-bars"
      >
        {usable.map((s, i) => {
          const v = Number(s.tension_level) || 0;
          const tooltip = [
            `Scene ${i + 1}: ${s.title || "Untitled"}`,
            `Tension: ${v}/100`,
            s.emotional_goal && `Goal: ${s.emotional_goal}`,
            s.conflict_point && `Conflict: ${s.conflict_point}`,
            s.cliffhanger_value != null && `Cliffhanger: ${s.cliffhanger_value}/100`,
          ]
            .filter(Boolean)
            .join("\n");
          return (
            <div
              key={s.id}
              data-testid={`episode-arc-bar-${s.id}`}
              data-tension={v}
              title={tooltip}
              className="flex-1 min-w-[6px] rounded-t-sm transition-all duration-300 hover:opacity-80"
              style={{
                height: `${Math.max(4, v)}%`,
                backgroundColor: tensionColor(v),
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
