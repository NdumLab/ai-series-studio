import { Coins, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { Scenes } from "../../lib/api";

/**
 * Inline scene-level cost widget rendered inside the SceneCard header.
 * Shows the per-scene credit breakdown chip plus the High-cost / Reduce-to-Draft
 * action when this scene exceeds the project's high-cost threshold.
 */
export function SceneCostWidget({
  scene,
  options,
  costRow,
  reload,
}) {
  const costs = options?.costs || {};
  const segmentsCount = (scene.segments || []).length;
  const planned = Math.max(1, segmentsCount);
  const imageC = costs.image;
  const videoC = costs.video_segment;
  const voiceC = costs.voice;
  const missing = [imageC, videoC, voiceC].some((v) => v == null);
  const breakdown = {
    image: imageC || 0,
    video: (videoC || 0) * planned,
    voice: voiceC || 0,
  };
  const sceneTotal = breakdown.image + breakdown.video + breakdown.voice;
  const breakdownTooltip = `Image: ${breakdown.image} · Video: ${breakdown.video} · Voice: ${breakdown.voice}`;

  return (
    <>
      <span
        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-[#FFCC00]/30 bg-[#FFCC00]/5 text-[10px] font-mono"
        data-testid={`scene-credits-${scene.id}`}
        title={missing ? "Some unit costs are missing" : breakdownTooltip}
      >
        <Coins className="w-3 h-3 text-[#FFCC00]" />
        <span className="text-[#A1A1AA] uppercase tracking-widest">
          Credits this scene
        </span>
        <span className="text-white">
          {missing ? "estimate unavailable" : `~${sceneTotal}`}
        </span>
        {!missing && (
          <span
            className="text-[#A1A1AA]"
            data-testid={`scene-credits-breakdown-${scene.id}`}
          >
            · img {breakdown.image} · vid {breakdown.video}
            {segmentsCount > 1 ? ` (${segmentsCount}×)` : ""} · voice{" "}
            {breakdown.voice}
          </span>
        )}
      </span>
      {costRow?.high_cost && (
        <span
          data-testid={`high-cost-${scene.id}`}
          title={`This scene uses ~${Math.round(costRow.share_pct)}% of the project's estimated credits.\nImage: ${costRow.breakdown.image} · Video: ${costRow.breakdown.video} · Voice: ${costRow.breakdown.voice}\nConsider reducing segments or using Draft mode.`}
          className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-[#FF9500]/40 bg-[#FF9500]/10 text-[#FF9500] text-[10px] font-mono uppercase tracking-widest"
        >
          <AlertCircle className="w-3 h-3" />
          High-cost scene · {Math.round(costRow.share_pct)}%
          {segmentsCount > 1 && (
            <button
              type="button"
              onClick={async () => {
                const r = await Scenes.reduceToDraft(scene.id);
                if (r.deleted_segments > 0) {
                  toast.success(`Saved ~${r.saved_credits} credits`);
                } else {
                  toast(`Already at draft size`, { icon: "✓" });
                }
                reload();
              }}
              data-testid={`reduce-to-draft-${scene.id}`}
              className="ml-1.5 px-1.5 py-0.5 rounded border border-[#FF9500]/50 hover:bg-[#FF9500]/20 transition-colors"
              title="Drops this scene back to 1 planned segment"
            >
              Reduce to Draft
            </button>
          )}
        </span>
      )}
    </>
  );
}
