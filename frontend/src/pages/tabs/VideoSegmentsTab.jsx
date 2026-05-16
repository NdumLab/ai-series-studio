import { useState } from "react";
import { toast } from "sonner";
import { Video, Plus, Wand2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import { SortableList } from "../../components/SortableList";
import { ProviderHintChip } from "../../components/studio/ProviderHintChip";
import { InfoCallout } from "../../components/studio/InfoCallout";
import { EmptyState } from "../../components/studio/EmptyState";
import { SegmentCard } from "../../components/studio/SegmentCard";
import { apiErrorMessage, Creative, Scenes } from "../../lib/api";
import { withRealLLMToast } from "../../lib/llmToast";

const VIDEO_HINT =
  "This video prompt is enhanced for: motion, continuity, emotion, camera movement.";

export function VideoSegmentsTab({ scenes, providers, options, setData, reload }) {
  if (!scenes.length) {
    return <EmptyState text="Split your story into scenes first." />;
  }
  const c = options?.costs?.video_segment;
  return (
    <div className="space-y-4" data-testid="segments-tab">
      <ProviderHintChip
        providers={providers}
        modality="video"
        action="video generation"
        credits={c ? `~${c} credits per 5-second segment` : null}
      />
      <InfoCallout text={VIDEO_HINT} />
      {scenes.map((s, i) => (
        <SceneSegmentBlock
          key={s.id}
          scene={s}
          index={i}
          setData={setData}
          reload={reload}
        />
      ))}
    </div>
  );
}

function SceneSegmentBlock({ scene, index, setData, reload }) {
  const [busy, setBusy] = useState(false);
  const segments = scene.segments || [];

  const genFirst = async () => {
    setBusy(true);
    try {
      await Scenes.generateSegment(scene.id);
      toast.success("Initial 5s segment generated");
      reload();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Generation failed (mock)"));
    } finally {
      setBusy(false);
    }
  };

  const expand = async () => {
    setBusy(true);
    try {
      await Scenes.expand(scene.id);
      toast.success("+5s expansion added");
      reload();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Expansion failed (mock)"));
    } finally {
      setBusy(false);
    }
  };

  const enhance = async () => {
    setBusy(true);
    try {
      const res = await withRealLLMToast(
        "enhance video prompt",
        () => Creative.enhanceScene(scene.id, "video-prompt")
      );
      if (res?.llm_mode !== "real" && res?.llm_status !== "fallback") {
        toast.success("Video prompt enhanced");
      }
      reload();
    } catch {
      toast.error("Enhance failed");
    } finally {
      setBusy(false);
    }
  };

  const enhanced = !!scene.enhanced_video_prompt;

  return (
    <div className="es-card p-5" data-testid={`scene-segments-${scene.id}`}>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA]">
            Scene {String(index + 1).padStart(2, "0")}
            {enhanced && (
              <span
                className="ml-2 inline-flex items-center gap-1 px-1.5 py-0 rounded border border-[#34C759]/30 bg-[#34C759]/5 text-[#34C759]"
                data-testid={`video-enhanced-chip-${scene.id}`}
              >
                <Wand2 className="w-2.5 h-2.5" /> enhanced
              </span>
            )}
          </p>
          <h4 className="font-display text-lg font-bold">{scene.title}</h4>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={enhance}
            disabled={busy}
            data-testid={`enhance-video-prompt-${scene.id}`}
            className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
          >
            <Wand2 className="w-3.5 h-3.5 mr-1.5" />
            {enhanced ? "Re-enhance" : "Enhance prompt"}
          </Button>
          {segments.length === 0 && (
            <Button
              size="sm"
              onClick={genFirst}
              disabled={busy}
              data-testid={`gen-video-${scene.id}`}
              className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
            >
              <Video className="w-3.5 h-3.5 mr-1.5" /> Generate 5s
            </Button>
          )}
          {segments.length > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={expand}
              disabled={busy}
              data-testid={`expand-5s-${scene.id}`}
              className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Expand next 5s
            </Button>
          )}
        </div>
      </div>

      {segments.length === 0 ? (
        <p className="text-xs text-[#A1A1AA]">
          No segments yet. Generate the first 5 seconds.
        </p>
      ) : (
        <SortableList
          items={segments}
          getId={(seg) => seg.id}
          direction="grid"
          testId={`sortable-segments-${scene.id}`}
          onReorder={async (ids) => {
            const prev = segments;
            const byId = new Map(segments.map((s) => [s.id, s]));
            // Optimistic local update with recomputed start_second
            let start = 0;
            const next = ids.map((id, i) => {
              const seg = byId.get(id);
              const dur = seg?.duration ?? 5;
              const updated = { ...seg, order: i, start_second: start };
              start += dur;
              return updated;
            });
            setData?.((d) =>
              d
                ? {
                    ...d,
                    scenes: d.scenes.map((sc) =>
                      sc.id === scene.id ? { ...sc, segments: next } : sc
                    ),
                  }
                : d
            );
            try {
              await Scenes.reorderSegments(scene.id, ids);
              // refresh derived data (cost-costs) without resetting the list
              reload({ skipProject: true });
            } catch {
              setData?.((d) =>
                d
                  ? {
                      ...d,
                      scenes: d.scenes.map((sc) =>
                        sc.id === scene.id ? { ...sc, segments: prev } : sc
                      ),
                    }
                  : d
              );
              toast.error("Reorder failed — restored");
            }
          }}
          renderItem={(seg, handle, i) => (
            <SegmentCard
              segment={seg}
              index={i}
              parent={segments.find((p) => p.id === seg.parent_segment_id) || null}
              dragHandle={handle}
              reload={reload}
            />
          )}
        />
      )}
    </div>
  );
}
