import { useState } from "react";
import { toast } from "sonner";
import { Video, Plus } from "lucide-react";
import { Button } from "../../components/ui/button";
import { SortableList } from "../../components/SortableList";
import { ProviderHintChip } from "../../components/studio/ProviderHintChip";
import { InfoCallout } from "../../components/studio/InfoCallout";
import { EmptyState } from "../../components/studio/EmptyState";
import { SegmentCard } from "../../components/studio/SegmentCard";
import { Scenes } from "../../lib/api";

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
      <InfoCallout text="Each scene contains 5-second video segments. Use 'Expand next 5s' to chain a continuation that references the previous segment. Drag a segment's grip handle to reorder." />
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
    } catch {
      toast.error("Generation failed (mock)");
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
    } catch {
      toast.error("Expansion failed (mock)");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="es-card p-5" data-testid={`scene-segments-${scene.id}`}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA]">
            Scene {String(index + 1).padStart(2, "0")}
          </p>
          <h4 className="font-display text-lg font-bold">{scene.title}</h4>
        </div>
        <div className="flex items-center gap-2">
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
