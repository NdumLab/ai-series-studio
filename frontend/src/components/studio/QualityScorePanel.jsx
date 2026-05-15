const QUALITY_LABELS = {
  hook_strength: "Hook",
  conflict_strength: "Conflict",
  emotional_tension: "Emotional tension",
  visual_potential: "Visual potential",
  cliffhanger_strength: "Cliffhanger",
  dialogue_strength: "Dialogue",
  overall_story_score: "Overall",
};

function scoreColor(v) {
  const n = Number(v) || 0;
  if (n >= 75) return "#34C759";
  if (n >= 55) return "#FFCC00";
  if (n >= 35) return "#FF9500";
  return "#FF3B30";
}

export function QualityScorePanel({ scores }) {
  if (!scores) {
    return (
      <div className="es-card p-5" data-testid="quality-score-panel-empty">
        <p className="es-label">Story quality</p>
        <p className="text-xs text-[#A1A1AA] mt-2">
          Rewrite the story to generate a quality breakdown.
        </p>
      </div>
    );
  }
  const overall = scores.overall_story_score;
  return (
    <div className="es-card p-5" data-testid="quality-score-panel">
      <div className="flex items-end justify-between mb-3">
        <div>
          <p className="es-label">Story quality</p>
          <h4 className="font-display text-lg font-bold mt-0.5">Episode breakdown</h4>
        </div>
        <div className="text-right">
          <div
            className="font-display text-3xl font-black leading-none"
            style={{ color: scoreColor(overall) }}
            data-testid="quality-overall"
          >
            {overall}
          </div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#A1A1AA]">
            overall · /100
          </div>
        </div>
      </div>
      <div className="space-y-2">
        {Object.entries(QUALITY_LABELS)
          .filter(([k]) => k !== "overall_story_score")
          .map(([k, label]) => {
            const v = scores[k] ?? 0;
            return (
              <div
                key={k}
                className="grid grid-cols-12 gap-2 items-center"
                data-testid={`quality-row-${k}`}
              >
                <span className="col-span-4 text-xs text-[#A1A1AA]">{label}</span>
                <div className="col-span-7 h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${v}%`, backgroundColor: scoreColor(v) }}
                  />
                </div>
                <span
                  className="col-span-1 text-right text-xs font-mono"
                  style={{ color: scoreColor(v) }}
                  data-testid={`quality-value-${k}`}
                >
                  {v}
                </span>
              </div>
            );
          })}
      </div>
    </div>
  );
}
