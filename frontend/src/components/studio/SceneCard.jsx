import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Textarea } from "../ui/textarea";
import { Scenes } from "../../lib/api";
import { FieldInput } from "./FieldInput";
import { SceneCostWidget } from "./SceneCostWidget";

export function SceneCard({
  index,
  scene,
  characters,
  options,
  voiceResolution,
  costRow,
  dragHandle,
  reload,
}) {
  const [local, setLocal] = useState(scene);
  useEffect(() => setLocal(scene), [scene]);
  const patch = (k, v) => setLocal((p) => ({ ...p, [k]: v }));
  const save = async (k, v) => {
    await Scenes.update(scene.id, { [k]: v });
  };
  const removeScene = async () => {
    await Scenes.remove(scene.id);
    toast.success("Scene deleted");
    reload();
  };

  const voiceByChar = {};
  (voiceResolution?.characters || []).forEach((c) => {
    voiceByChar[c.id] = c.voice;
  });

  return (
    <div className="es-card p-5" data-testid={`scene-${scene.id}`}>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          {dragHandle}
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA]">
            Scene {String(index + 1).padStart(2, "0")}
          </span>
          <Badge
            variant="outline"
            className="border-white/15 text-[#A1A1AA] font-mono text-[10px]"
          >
            {local.status || "draft"}
          </Badge>
          <SceneCostWidget
            scene={scene}
            options={options}
            costRow={costRow}
            reload={reload}
          />
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={removeScene}
          data-testid={`delete-scene-${scene.id}`}
          className="text-[#A1A1AA] hover:text-[#FF3B30] hover:bg-white/5"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <FieldInput
          label="Title"
          value={local.title}
          onChange={(v) => patch("title", v)}
          onBlur={() => save("title", local.title)}
          testId={`scene-title-${scene.id}`}
        />
        <FieldInput
          label="Duration (s)"
          type="number"
          value={local.duration}
          onChange={(v) => patch("duration", parseInt(v || "0", 10))}
          onBlur={() => save("duration", local.duration)}
          testId={`scene-duration-${scene.id}`}
        />
        <FieldInput
          label="Location"
          value={local.location || ""}
          onChange={(v) => patch("location", v)}
          onBlur={() => save("location", local.location)}
          testId={`scene-location-${scene.id}`}
        />
        <FieldInput
          label="Camera direction"
          value={local.camera_direction || ""}
          onChange={(v) => patch("camera_direction", v)}
          onBlur={() => save("camera_direction", local.camera_direction)}
          testId={`scene-camera-${scene.id}`}
        />
        <div className="md:col-span-2">
          <label className="es-label block mb-1.5">Visual prompt</label>
          <Textarea
            data-testid={`scene-prompt-${scene.id}`}
            value={local.visual_prompt || ""}
            onChange={(e) => patch("visual_prompt", e.target.value)}
            onBlur={() => save("visual_prompt", local.visual_prompt)}
            className="bg-[#0A0A0A] border-white/10 text-white"
          />
        </div>
        <div className="md:col-span-2">
          <label className="es-label block mb-1.5">Dialogue</label>
          <Textarea
            data-testid={`scene-dialogue-${scene.id}`}
            value={local.dialogue || ""}
            onChange={(e) => patch("dialogue", e.target.value)}
            onBlur={() => save("dialogue", local.dialogue)}
            className="bg-[#0A0A0A] border-white/10 text-white min-h-[60px]"
          />
        </div>
        {characters.length > 0 && (
          <div className="md:col-span-2">
            <label className="es-label block mb-1.5">Characters in scene</label>
            <div className="flex flex-wrap gap-2">
              {characters.map((c) => {
                const active = (local.characters || []).includes(c.id);
                const hasOverride = !!c.voice_provider;
                const eff = voiceByChar[c.id];
                const tooltip = eff
                  ? `Voice: ${eff.provider || "—"}/${eff.model || "—"}\nSource: ${
                      eff.source === "character"
                        ? "Character Override"
                        : eff.source === "project"
                          ? "Project Override"
                          : "Global Default"
                    }`
                  : `${c.name}`;
                return (
                  <button
                    key={c.id}
                    type="button"
                    data-testid={`scene-toggle-char-${scene.id}-${c.id}`}
                    onClick={() => {
                      const next = active
                        ? (local.characters || []).filter((x) => x !== c.id)
                        : [...(local.characters || []), c.id];
                      patch("characters", next);
                      save("characters", next);
                    }}
                    title={tooltip}
                    className={`px-3 py-1 text-xs rounded-md border transition-colors inline-flex items-center gap-1.5 ${
                      active
                        ? "bg-[#FF3B30] border-[#FF3B30] text-white"
                        : "bg-transparent border-white/15 text-[#A1A1AA] hover:text-white hover:bg-white/5"
                    }`}
                  >
                    {c.name}
                    {hasOverride && (
                      <span
                        data-testid={`char-voice-chip-${scene.id}-${c.id}`}
                        className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider bg-[#FFCC00]/15 text-[#FFCC00] border border-[#FFCC00]/30"
                      >
                        Voice Override
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
