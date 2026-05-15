import { useState } from "react";
import { toast } from "sonner";
import { Image as ImageIcon } from "lucide-react";
import { Button } from "../../components/ui/button";
import { ProviderHintChip } from "../../components/studio/ProviderHintChip";
import { InfoCallout } from "../../components/studio/InfoCallout";
import { EmptyState } from "../../components/studio/EmptyState";
import { Scenes } from "../../lib/api";

export function ImagesTab({ scenes, providers, options, reload }) {
  if (!scenes.length) {
    return <EmptyState text="Split your story into scenes first to generate images." />;
  }
  const c = options?.costs?.image;
  return (
    <div className="space-y-3">
      <ProviderHintChip
        providers={providers}
        modality="image"
        action="image generation"
        credits={c ? `~${c} credits per scene image` : null}
      />
      <InfoCallout text="Generate or regenerate one image per scene. The image becomes the visual anchor for video generation." />
      <div
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        data-testid="images-grid"
      >
        {scenes.map((s, i) => (
          <SceneImageCard key={s.id} scene={s} index={i} reload={reload} />
        ))}
      </div>
    </div>
  );
}

function SceneImageCard({ scene, index, reload }) {
  const [busy, setBusy] = useState(false);
  const gen = async () => {
    setBusy(true);
    try {
      const res = await Scenes.generateImage(scene.id);
      toast.success(`Image generated · -${res.cost} credits`);
      reload();
    } catch {
      toast.error("Image gen failed (mock)");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="es-card overflow-hidden" data-testid={`image-card-${scene.id}`}>
      <div className="aspect-video bg-black border-b border-white/10 overflow-hidden flex items-center justify-center">
        {scene.image_url ? (
          <img
            src={scene.image_url}
            alt={scene.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="text-[#A1A1AA] text-xs flex flex-col items-center">
            <ImageIcon className="w-6 h-6 mb-2 opacity-60" /> No image yet
          </div>
        )}
      </div>
      <div className="p-4">
        <p className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA] mb-1">
          Scene {String(index + 1).padStart(2, "0")}
        </p>
        <h4 className="font-display text-base font-bold mb-1 truncate">{scene.title}</h4>
        <p className="text-xs text-[#A1A1AA] line-clamp-2 min-h-[32px]">
          {scene.visual_prompt || "No visual prompt yet."}
        </p>
        <Button
          onClick={gen}
          disabled={busy}
          size="sm"
          data-testid={`gen-image-${scene.id}`}
          className="mt-3 w-full bg-[#FF3B30] hover:bg-[#FF453A] text-white"
        >
          <ImageIcon className="w-3.5 h-3.5 mr-1.5" />
          {scene.image_url ? "Regenerate" : "Generate"}
        </Button>
      </div>
    </div>
  );
}
