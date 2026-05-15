import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "../../components/ui/button";
import { SortableList } from "../../components/SortableList";
import { SceneCard } from "../../components/studio/SceneCard";
import { InfoCallout } from "../../components/studio/InfoCallout";
import { EpisodeArcStrip } from "../../components/studio/EpisodeArcStrip";
import { Scenes } from "../../lib/api";

export function ScenesTab({
  project,
  scenes,
  characters,
  options,
  voiceResolution,
  sceneCosts,
  setData,
  reload,
}) {
  if (!scenes.length) {
    return (
      <div className="es-card p-12 text-center">
        <p className="text-[#A1A1AA] mb-4">No scenes yet.</p>
        <p className="text-sm text-[#A1A1AA]">
          Go to the Story tab and click <strong>Save & split into scenes</strong>.
        </p>
      </div>
    );
  }
  let totalText = null;
  if (sceneCosts?.status === "loading" && !sceneCosts.data) totalText = "calculating…";
  else if (sceneCosts?.status === "error") totalText = "estimate unavailable";
  else if (sceneCosts?.data) totalText = `~${sceneCosts.data.grand_total_credits} credits`;
  const sceneCostMap = {};
  (sceneCosts?.data?.scenes || []).forEach((row) => {
    sceneCostMap[row.scene_id] = row;
  });
  return (
    <div className="space-y-4" data-testid="scenes-list">
      <div
        className="flex items-end justify-between flex-wrap gap-3"
        data-testid="scenes-tab-header"
      >
        <div>
          <p className="es-label mb-1">Scenes</p>
          <h3 className="font-display text-2xl font-bold">
            {scenes.length} {scenes.length === 1 ? "scene" : "scenes"}
            {totalText ? (
              <span
                className="ml-3 text-sm font-mono text-[#FFCC00] font-normal"
                data-testid="scenes-grand-total"
              >
                · {totalText}
              </span>
            ) : null}
          </h3>
          <p className="text-xs text-[#A1A1AA] mt-1">
            Estimated project scene cost · live mock estimate
          </p>
        </div>
      </div>
      <InfoCallout text="Edit titles, locations, prompts and dialogue here. Drag the grip handle to reorder scenes. Image and video generation happen in their own tabs." />
      <EpisodeArcStrip scenes={scenes} />
      <SortableList
        items={scenes}
        getId={(s) => s.id}
        testId="sortable-scenes"
        onReorder={async (ids) => {
          // Optimistic: reorder locally first
          const byId = new Map(scenes.map((s) => [s.id, s]));
          const next = ids.map((id, i) => ({ ...byId.get(id), order: i }));
          const prev = scenes;
          setData((d) => (d ? { ...d, scenes: next } : d));
          try {
            await Scenes.reorder(project.id, ids);
            // Refresh derived data (cost-costs etc.) without snapping the list
            reload({ skipProject: true });
          } catch {
            setData((d) => (d ? { ...d, scenes: prev } : d));
            toast.error("Reorder failed — restored");
          }
        }}
        renderItem={(s, handle) => (
          <SceneCard
            scene={s}
            index={scenes.findIndex((x) => x.id === s.id)}
            characters={characters}
            options={options}
            voiceResolution={voiceResolution}
            costRow={sceneCostMap[s.id]}
            dragHandle={handle}
            reload={reload}
          />
        )}
      />
      <AddSceneButton projectId={project.id} reload={reload} />
    </div>
  );
}

function AddSceneButton({ projectId, reload }) {
  const add = async () => {
    await Scenes.create(projectId, {
      title: "New Scene",
      duration: 10,
      visual_prompt: "",
      music_mood: "Cinematic",
      voice: "Narrator-Warm",
    });
    toast.success("Scene added");
    reload();
  };
  return (
    <Button
      onClick={add}
      variant="outline"
      data-testid="add-scene-btn"
      className="w-full border-dashed border-white/15 bg-transparent text-white hover:bg-white/5 hover:text-white h-14"
    >
      <Plus className="w-4 h-4 mr-2" /> Add scene
    </Button>
  );
}
