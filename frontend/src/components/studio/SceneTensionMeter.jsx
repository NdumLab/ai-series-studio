import { useState } from "react";
import { toast } from "sonner";
import { Flame, Theater, MessageSquare } from "lucide-react";
import { Button } from "../ui/button";
import { apiErrorMessage, Creative } from "../../lib/api";
import { withRealLLMToast } from "../../lib/llmToast";

function tensionColor(v) {
  const n = Number(v) || 0;
  if (n >= 75) return "#FF3B30";
  if (n >= 55) return "#FF9500";
  if (n >= 35) return "#FFCC00";
  return "#34C759";
}

export function SceneTensionMeter({ scene, onImproved }) {
  const [busy, setBusy] = useState(false);
  const tension = scene.tension_level ?? null;
  const run = async (kind) => {
    setBusy(true);
    try {
      const res = await withRealLLMToast(
        kind === "scene-drama" ? "improve scene drama" : "improve dialogue",
        () => Creative.enhanceScene(scene.id, kind)
      );
      // Only show the legacy short toast in mock mode.
      if (res?.llm_mode !== "real" && res?.llm_status !== "fallback") {
        toast.success(
          kind === "scene-drama"
            ? `Drama boosted · tension ${res.scene.tension_level}`
            : "Dialogue improved"
        );
      }
      onImproved?.(res.scene);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Enhancement failed"));
    } finally {
      setBusy(false);
    }
  };

  if (tension == null) return null;
  const color = tensionColor(tension);
  return (
    <div
      className="es-card p-3 bg-white/[0.02] border-white/5"
      data-testid={`tension-meter-${scene.id}`}
    >
      <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
        <div className="inline-flex items-center gap-1.5">
          <Flame className="w-3.5 h-3.5" style={{ color }} />
          <span className="es-label">Tension</span>
          <span
            className="text-xs font-mono font-bold"
            style={{ color }}
            data-testid={`tension-value-${scene.id}`}
          >
            {tension}
          </span>
          <span className="text-[10px] font-mono text-[#A1A1AA]">/100</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => run("scene-drama")}
            data-testid={`improve-drama-${scene.id}`}
            className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white h-7 px-2 text-xs"
          >
            <Theater className="w-3 h-3 mr-1" /> Improve drama
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => run("dialogue")}
            data-testid={`improve-dialogue-${scene.id}`}
            className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white h-7 px-2 text-xs"
          >
            <MessageSquare className="w-3 h-3 mr-1" /> Improve dialogue
          </Button>
        </div>
      </div>
      <div className="h-1.5 rounded-full bg-white/5 overflow-hidden mb-3">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${tension}%`, backgroundColor: color }}
        />
      </div>
      <dl className="grid grid-cols-1 gap-y-1 text-[11px]">
        {scene.emotional_goal && (
          <div className="flex gap-2">
            <dt className="text-[#A1A1AA] min-w-[88px]">Emotional goal</dt>
            <dd className="text-white" data-testid={`emotional-goal-${scene.id}`}>
              {scene.emotional_goal}
            </dd>
          </div>
        )}
        {scene.conflict_point && (
          <div className="flex gap-2">
            <dt className="text-[#A1A1AA] min-w-[88px]">Conflict</dt>
            <dd className="text-white" data-testid={`conflict-point-${scene.id}`}>
              {scene.conflict_point}
            </dd>
          </div>
        )}
        {scene.reveal_or_turning_point && (
          <div className="flex gap-2">
            <dt className="text-[#A1A1AA] min-w-[88px]">Turning point</dt>
            <dd className="text-white" data-testid={`turning-point-${scene.id}`}>
              {scene.reveal_or_turning_point}
            </dd>
          </div>
        )}
        {scene.cliffhanger_value != null && (
          <div className="flex gap-2">
            <dt className="text-[#A1A1AA] min-w-[88px]">Cliffhanger</dt>
            <dd
              className="text-white font-mono"
              data-testid={`cliffhanger-value-${scene.id}`}
            >
              {scene.cliffhanger_value}/100
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}
