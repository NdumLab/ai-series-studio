import { Mic2, Music2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { Button } from "../../components/ui/button";
import { ProviderHintChip } from "../../components/studio/ProviderHintChip";
import { InfoCallout } from "../../components/studio/InfoCallout";
import { EmptyState } from "../../components/studio/EmptyState";
import { Scenes } from "../../lib/api";

export function VoiceMusicTab({
  scenes,
  options,
  providers,
  characters,
  voiceResolution,
  onCharacterEdit,
  reload,
}) {
  if (!scenes.length) {
    return <EmptyState text="Split your story into scenes first." />;
  }
  const cv = options?.costs?.voice;
  const cm = options?.costs?.music;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ProviderHintChip
          providers={providers}
          modality="voice"
          action="voice generation"
          credits={cv ? `~${cv} credit per scene` : null}
        />
        <ProviderHintChip
          providers={providers}
          modality="music"
          action="music generation"
          credits={cm ? `~${cm} credits per scene` : null}
        />
      </div>
      <CharacterVoiceList
        voiceResolution={voiceResolution}
        characters={characters}
        onCharacterEdit={onCharacterEdit}
      />
      <InfoCallout text="Pick the narrator voice and music mood for each scene. Voice and music will be rendered into the final mix." />
      <div className="space-y-3" data-testid="voice-music-list">
        {scenes.map((s, i) => (
          <VoiceMusicRow
            key={s.id}
            scene={s}
            index={i}
            options={options}
            reload={reload}
          />
        ))}
      </div>
    </div>
  );
}

function CharacterVoiceList({ voiceResolution, characters, onCharacterEdit }) {
  if (!voiceResolution || !voiceResolution.characters?.length) return null;
  const sourceLabel = (src) =>
    src === "character"
      ? "Character Override"
      : src === "project"
        ? "Project Override"
        : "Global Default";
  const sourceCls = (src) =>
    src === "character"
      ? "border-[#FFCC00]/50 text-[#FFCC00]"
      : src === "project"
        ? "border-[#FF3B30]/40 text-[#FF3B30]"
        : "border-white/15 text-[#A1A1AA]";
  return (
    <div className="es-card p-4" data-testid="character-voice-list">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h4 className="font-display text-base font-bold">Per-character voices</h4>
          <p className="text-xs text-[#A1A1AA]">
            Resolution priority: character override → project override → global default.
          </p>
        </div>
      </div>
      <ul className="space-y-2">
        {voiceResolution.characters.map((c) => (
          <li
            key={c.id}
            className="flex flex-wrap items-center gap-2 py-2 border-b border-white/5 last:border-0"
            data-testid={`char-voice-${c.id}`}
          >
            <span className="text-sm text-white font-semibold min-w-[120px]">{c.name}</span>
            <span className="text-xs text-[#A1A1AA] font-mono">
              voice:{" "}
              <span className="text-white" data-testid={`char-voice-text-${c.id}`}>
                {c.voice.provider || "—"}/{c.voice.model || "—"}
              </span>
            </span>
            <span
              className={`px-2 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-widest border ${sourceCls(c.voice.source)}`}
              data-testid={`char-voice-badge-${c.id}`}
            >
              {sourceLabel(c.voice.source)}
            </span>
            {onCharacterEdit && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onCharacterEdit(characters.find((ch) => ch.id === c.id))}
                data-testid={`edit-char-voice-${c.id}`}
                className="ml-auto text-[#A1A1AA] hover:text-white hover:bg-white/5 h-7"
              >
                Edit
              </Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function VoiceMusicRow({ scene, index, options, reload }) {
  const update = async (k, v) => {
    await Scenes.update(scene.id, { [k]: v });
    reload();
  };
  return (
    <div
      className="es-card p-4 grid grid-cols-1 md:grid-cols-12 gap-3 items-center"
      data-testid={`vm-row-${scene.id}`}
    >
      <div className="md:col-span-4">
        <p className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA]">
          Scene {String(index + 1).padStart(2, "0")}
        </p>
        <h4 className="font-display text-base font-bold">{scene.title}</h4>
      </div>
      <div className="md:col-span-4">
        <label className="es-label block mb-1.5 inline-flex items-center gap-1">
          <Mic2 className="w-3 h-3" /> Voice
        </label>
        <Select value={scene.voice} onValueChange={(v) => update("voice", v)}>
          <SelectTrigger
            className="bg-[#0A0A0A] border-white/10 text-white"
            data-testid={`vm-voice-${scene.id}`}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-[#121212] border-white/10 text-white">
            {options.voices.map((v) => (
              <SelectItem key={v} value={v}>
                {v}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="md:col-span-4">
        <label className="es-label block mb-1.5 inline-flex items-center gap-1">
          <Music2 className="w-3 h-3" /> Music mood
        </label>
        <Select value={scene.music_mood} onValueChange={(v) => update("music_mood", v)}>
          <SelectTrigger
            className="bg-[#0A0A0A] border-white/10 text-white"
            data-testid={`vm-mood-${scene.id}`}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-[#121212] border-white/10 text-white">
            {options.music_moods.map((m) => (
              <SelectItem key={m} value={m}>
                {m}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
