import { useState } from "react";
import { toast } from "sonner";
import { UserPlus, Trash2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Textarea } from "../../components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { VOICE_PROVIDER_OPTIONS } from "../../components/studio/constants";
import { SortableList } from "../../components/SortableList";
import { Characters } from "../../lib/api";

export function CharactersTab({ project, characters, voices, setData, reload }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    name: "",
    description: "",
    voice_style: "Narrator-Warm",
    voice_provider: "",
    voice_model: "",
  });

  const reset = () => {
    setEditing(null);
    setForm({
      name: "",
      description: "",
      voice_style: "Narrator-Warm",
      voice_provider: "",
      voice_model: "",
    });
  };

  const startEdit = (c) => {
    setEditing(c);
    setForm({
      name: c.name || "",
      description: c.description || "",
      voice_style: c.voice_style || "Narrator-Warm",
      voice_provider: c.voice_provider || "",
      voice_model: c.voice_model || "",
    });
    setOpen(true);
  };

  const submit = async () => {
    if (!form.name.trim()) {
      toast.error("Name required");
      return;
    }
    try {
      if (editing) {
        await Characters.update(editing.id, {
          name: form.name.trim(),
          description: form.description.trim(),
          voice_style: form.voice_style,
          voice_provider: form.voice_provider,
          voice_model: form.voice_model,
        });
        toast.success("Character updated");
      } else {
        await Characters.create(project.id, {
          name: form.name.trim(),
          description: form.description.trim(),
          voice_style: form.voice_style,
          voice_provider: form.voice_provider,
          voice_model: form.voice_model,
        });
        toast.success("Character added");
      }
      setOpen(false);
      reset();
      reload();
    } catch {
      toast.error("Save failed");
    }
  };

  const remove = async (id) => {
    await Characters.remove(id);
    toast.success("Removed");
    reload();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-xl font-bold">Cast</h3>
        <Dialog
          open={open}
          onOpenChange={(o) => {
            setOpen(o);
            if (!o) reset();
          }}
        >
          <DialogTrigger asChild>
            <Button
              data-testid="open-add-character-btn"
              className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
            >
              <UserPlus className="w-4 h-4 mr-2" /> Add character
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#121212] border-white/10 text-white max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-display">
                {editing ? "Edit character" : "New character"}
              </DialogTitle>
              <DialogDescription className="text-[#A1A1AA]">
                Define a recurring cast member, optionally with a voice override.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div>
                <label className="es-label block mb-1.5">Name</label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  data-testid="char-name-input"
                  className="bg-[#0A0A0A] border-white/10 text-white"
                />
              </div>
              <div>
                <label className="es-label block mb-1.5">Description</label>
                <Textarea
                  value={form.description}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, description: e.target.value }))
                  }
                  data-testid="char-desc-input"
                  className="bg-[#0A0A0A] border-white/10 text-white"
                />
              </div>
              <div>
                <label className="es-label block mb-1.5">Voice style</label>
                <Select
                  value={form.voice_style}
                  onValueChange={(v) => setForm((p) => ({ ...p, voice_style: v }))}
                >
                  <SelectTrigger
                    className="bg-[#0A0A0A] border-white/10 text-white"
                    data-testid="char-voice-select"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#121212] border-white/10 text-white">
                    {voices.map((v) => (
                      <SelectItem key={v} value={v}>
                        {v}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="es-card p-3 bg-white/[0.02]">
                <p className="es-label mb-2">Voice override (optional)</p>
                <p className="text-[10px] text-[#A1A1AA] mb-3">
                  Beats project + global voice settings for this character.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="es-label block mb-1.5">Provider</label>
                    <Select
                      value={form.voice_provider || "__none__"}
                      onValueChange={(v) =>
                        setForm((p) => ({
                          ...p,
                          voice_provider: v === "__none__" ? "" : v,
                          voice_model: v === "__none__" ? "" : p.voice_model,
                        }))
                      }
                    >
                      <SelectTrigger
                        className="bg-[#0A0A0A] border-white/10 text-white"
                        data-testid="char-voice-provider-select"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#121212] border-white/10 text-white">
                        <SelectItem value="__none__">— inherit —</SelectItem>
                        {VOICE_PROVIDER_OPTIONS.map((v) => (
                          <SelectItem key={v.id} value={v.id}>
                            {v.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="es-label block mb-1.5">Model / voice id</label>
                    <Input
                      value={form.voice_model}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, voice_model: e.target.value }))
                      }
                      placeholder="e.g. eleven-v3"
                      disabled={!form.voice_provider}
                      data-testid="char-voice-model-input"
                      className="bg-[#0A0A0A] border-white/10 text-white"
                    />
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setOpen(false);
                  reset();
                }}
                className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
              >
                Cancel
              </Button>
              <Button
                onClick={submit}
                data-testid="submit-add-character-btn"
                className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
              >
                {editing ? "Save" : "Add"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {characters.length === 0 ? (
        <div className="es-card p-12 text-center text-[#A1A1AA]">No characters yet.</div>
      ) : (
        <SortableList
          items={characters}
          getId={(c) => c.id}
          direction="grid"
          testId="characters-grid"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          onReorder={async (ids) => {
            const byId = new Map(characters.map((c) => [c.id, c]));
            const next = ids.map((id, i) => ({ ...byId.get(id), order: i }));
            const prev = characters;
            setData?.((d) => (d ? { ...d, characters: next } : d));
            try {
              await Characters.reorder(project.id, ids);
              reload({ skipProject: true });
            } catch {
              setData?.((d) => (d ? { ...d, characters: prev } : d));
              toast.error("Reorder failed — restored");
            }
          }}
          renderItem={(c, handle) => (
            <div className="es-card overflow-hidden relative" data-testid={`char-${c.id}`}>
              <div className="absolute top-2 left-2 z-10 rounded-md bg-black/70 backdrop-blur border border-white/10">
                {handle}
              </div>
              <div className="aspect-[4/5] bg-black overflow-hidden">
                <img
                  src={c.reference_image_url}
                  alt={c.name}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="font-display text-lg font-bold">{c.name}</h4>
                    <p className="text-xs text-[#A1A1AA] font-mono">{c.voice_style}</p>
                    {c.voice_provider && (
                      <p
                        className="text-[10px] text-[#FFCC00] font-mono mt-1"
                        data-testid={`char-voice-tag-${c.id}`}
                      >
                        ↳ {c.voice_provider}/{c.voice_model || "—"}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => startEdit(c)}
                      data-testid={`edit-char-${c.id}`}
                      className="text-[#A1A1AA] hover:text-white hover:bg-white/5 h-7"
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => remove(c.id)}
                      data-testid={`delete-char-${c.id}`}
                      className="text-[#A1A1AA] hover:text-[#FF3B30] hover:bg-white/5 h-7"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                {c.description && (
                  <p className="text-sm text-[#A1A1AA] mt-2 line-clamp-3">{c.description}</p>
                )}
              </div>
            </div>
          )}
        />
      )}
    </div>
  );
}
