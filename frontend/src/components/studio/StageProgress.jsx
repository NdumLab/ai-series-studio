import { STAGES } from "./constants";

export function StageProgress({ current, onJump }) {
  const idx = STAGES.findIndex((s) => s.value === current);
  return (
    <div className="es-card p-4" data-testid="stage-progress">
      <div className="flex items-center justify-between mb-3">
        <span className="es-label">Workflow</span>
        <span className="text-xs font-mono text-[#A1A1AA]">
          Step {idx + 1} of {STAGES.length}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {STAGES.map((s, i) => {
          const active = i === idx;
          const done = i < idx;
          return (
            <button
              key={s.value}
              type="button"
              data-testid={`stage-jump-${s.value}`}
              onClick={() => onJump(s.value)}
              className={`text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
                active
                  ? "bg-[#FF3B30] border-[#FF3B30] text-white"
                  : done
                    ? "bg-white/5 border-white/15 text-white"
                    : "bg-transparent border-white/10 text-[#A1A1AA] hover:bg-white/5 hover:text-white"
              }`}
            >
              <span className="font-mono mr-1.5 opacity-70">
                {String(i + 1).padStart(2, "0")}
              </span>
              {s.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
