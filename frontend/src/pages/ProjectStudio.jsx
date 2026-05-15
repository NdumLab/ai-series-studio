import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Wand2,
  Split,
  Image as ImageIcon,
  Video,
  Plus,
  Trash2,
  RefreshCw,
  Check,
  X,
  ChevronLeft,
  Save,
  UserPlus,
  Coins,
} from "lucide-react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import {
  Projects,
  Scenes,
  Characters,
  Segments,
  Meta,
} from "../lib/api";

export default function ProjectStudio() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [options, setOptions] = useState({ voices: [], music_moods: [], costs: {} });
  const [tab, setTab] = useState("story");

  const load = useCallback(() => Projects.get(id).then(setData), [id]);

  useEffect(() => {
    load();
    Meta.options().then(setOptions);
  }, [load]);

  if (!data) {
    return <div className="text-[#A1A1AA] text-sm">Loading project…</div>;
  }
  const { project, scenes, characters } = data;

  return (
    <div className="es-fade">
      <Link
        to="/"
        data-testid="back-to-dashboard"
        className="inline-flex items-center gap-1 text-sm text-[#A1A1AA] hover:text-white mb-4 transition-colors"
      >
        <ChevronLeft className="w-4 h-4" /> Back to projects
      </Link>
      <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-8 gap-4">
        <div>
          <p className="es-label mb-2">Project</p>
          <h1
            className="font-display text-4xl font-black tracking-tight"
            data-testid="project-title"
          >
            {project.title}
          </h1>
          <p className="text-xs text-[#A1A1AA] mt-1 font-mono">
            {project.id} · status: {project.status}
          </p>
        </div>
        <CostBadge projectId={id} />
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-[#121212] border border-white/10">
          <TabsTrigger value="story" data-testid="tab-story">Story</TabsTrigger>
          <TabsTrigger value="scenes" data-testid="tab-scenes">Scenes</TabsTrigger>
          <TabsTrigger value="characters" data-testid="tab-characters">Characters</TabsTrigger>
          <TabsTrigger value="export" data-testid="tab-export">Export</TabsTrigger>
        </TabsList>

        <TabsContent value="story" className="mt-6">
          <StoryTab project={project} reload={load} onContinue={() => setTab("scenes")} />
        </TabsContent>
        <TabsContent value="scenes" className="mt-6">
          <ScenesTab
            project={project}
            scenes={scenes}
            characters={characters}
            options={options}
            reload={load}
          />
        </TabsContent>
        <TabsContent value="characters" className="mt-6">
          <CharactersTab
            project={project}
            characters={characters}
            voices={options.voices}
            reload={load}
          />
        </TabsContent>
        <TabsContent value="export" className="mt-6">
          <ExportTab projectId={id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cost badge
// ---------------------------------------------------------------------------
function CostBadge({ projectId }) {
  const [est, setEst] = useState(null);
  useEffect(() => {
    Projects.costEstimate(projectId).then(setEst);
  }, [projectId]);
  if (!est) return null;
  return (
    <div className="es-card px-4 py-3 inline-flex items-center gap-3" data-testid="cost-estimate">
      <Coins className="w-4 h-4 text-[#FFCC00]" />
      <div>
        <div className="es-label">Estimated to finish</div>
        <div className="font-display text-lg font-bold">
          {est.total_credits} <span className="text-xs text-[#A1A1AA] font-mono">credits</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Story tab
// ---------------------------------------------------------------------------
function StoryTab({ project, reload, onContinue }) {
  const [idea, setIdea] = useState(project.idea || "");
  const [story, setStory] = useState(project.rewritten_story || "");
  const [busy, setBusy] = useState(false);

  const saveIdea = async () => {
    await Projects.update(project.id, { idea });
    toast.success("Idea saved");
  };

  const rewrite = async () => {
    setBusy(true);
    try {
      await Projects.update(project.id, { idea });
      const res = await Projects.rewrite(project.id);
      setStory(res.rewritten_story);
      toast.success(`Story rewritten · -${res.cost} credits`);
      reload();
    } catch {
      toast.error("Rewrite failed");
    } finally {
      setBusy(false);
    }
  };

  const saveStory = async () => {
    await Projects.update(project.id, { rewritten_story: story });
    toast.success("Story saved");
    reload();
  };

  const split = async () => {
    setBusy(true);
    try {
      await Projects.update(project.id, { rewritten_story: story });
      await Projects.splitScenes(project.id);
      toast.success("Split into scenes");
      reload();
      onContinue();
    } catch {
      toast.error("Scene split failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="es-card p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display text-lg font-bold">Idea / Logline</h3>
          <Button
            size="sm"
            variant="outline"
            onClick={saveIdea}
            data-testid="save-idea-btn"
            className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" /> Save
          </Button>
        </div>
        <Textarea
          data-testid="idea-textarea"
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="A rough premise — one or two sentences."
          className="bg-[#0A0A0A] border-white/10 text-white min-h-[180px]"
        />
        <Button
          onClick={rewrite}
          disabled={busy}
          data-testid="rewrite-btn"
          className="mt-4 bg-[#FF3B30] hover:bg-[#FF453A] text-white w-full"
        >
          <Wand2 className="w-4 h-4 mr-2" /> {busy ? "Rewriting…" : "Rewrite as episode draft"}
        </Button>
      </div>

      <div className="es-card p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display text-lg font-bold">Episode draft</h3>
          <Button
            size="sm"
            variant="outline"
            onClick={saveStory}
            data-testid="save-story-btn"
            className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" /> Save
          </Button>
        </div>
        <Textarea
          data-testid="story-textarea"
          value={story}
          onChange={(e) => setStory(e.target.value)}
          placeholder="Your rewritten episode will appear here. You can freely edit it."
          className="bg-[#0A0A0A] border-white/10 text-white min-h-[260px]"
        />
        <Button
          onClick={split}
          disabled={busy || !story.trim()}
          data-testid="split-scenes-btn"
          className="mt-4 bg-white text-black hover:bg-white/90 w-full"
        >
          <Split className="w-4 h-4 mr-2" /> {busy ? "Splitting…" : "Split into scenes →"}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scenes tab
// ---------------------------------------------------------------------------
function ScenesTab({ project, scenes, characters, options, reload }) {
  if (!scenes.length) {
    return (
      <div className="es-card p-12 text-center">
        <p className="text-[#A1A1AA] mb-4">No scenes yet.</p>
        <p className="text-sm text-[#A1A1AA]">
          Go to the Story tab and click <strong>Split into scenes</strong>.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-4" data-testid="scenes-list">
      {scenes.map((s, i) => (
        <SceneCard
          key={s.id}
          index={i}
          scene={s}
          characters={characters}
          options={options}
          reload={reload}
        />
      ))}
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

function SceneCard({ index, scene, characters, options, reload }) {
  const [local, setLocal] = useState(scene);
  const [busy, setBusy] = useState(false);

  useEffect(() => setLocal(scene), [scene]);

  const patch = (k, v) => setLocal((p) => ({ ...p, [k]: v }));

  const saveField = async (k, v) => {
    await Scenes.update(scene.id, { [k]: v });
  };

  const genImage = async () => {
    setBusy(true);
    try {
      const res = await Scenes.generateImage(scene.id);
      toast.success(`Image generated · -${res.cost} credits`);
      reload();
    } catch {
      toast.error("Image generation failed (mock)");
    } finally {
      setBusy(false);
    }
  };

  const genSegment = async () => {
    setBusy(true);
    try {
      await Scenes.generateSegment(scene.id);
      toast.success("Video segment generated");
      reload();
    } catch {
      toast.error("Video gen failed (mock)");
    } finally {
      setBusy(false);
    }
  };

  const expand = async () => {
    setBusy(true);
    try {
      await Scenes.expand(scene.id);
      toast.success("+5s segment added");
      reload();
    } catch {
      toast.error("Expansion failed");
    } finally {
      setBusy(false);
    }
  };

  const removeScene = async () => {
    await Scenes.remove(scene.id);
    toast.success("Scene deleted");
    reload();
  };

  return (
    <div className="es-card p-5" data-testid={`scene-${scene.id}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA]">
            Scene {String(index + 1).padStart(2, "0")}
          </span>
          <Badge
            variant="outline"
            className="border-white/15 text-[#A1A1AA] font-mono text-[10px]"
          >
            {local.status || "draft"}
          </Badge>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Image preview */}
        <div className="lg:row-span-2">
          <div className="aspect-video bg-black rounded-md border border-white/10 overflow-hidden flex items-center justify-center relative">
            {local.image_url ? (
              <img
                src={local.image_url}
                alt={local.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="text-[#A1A1AA] text-xs text-center px-4">
                <ImageIcon className="w-6 h-6 mx-auto mb-2 opacity-60" />
                No image yet
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 mt-2">
            <Button
              onClick={genImage}
              disabled={busy}
              size="sm"
              data-testid={`gen-image-${scene.id}`}
              className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
            >
              <ImageIcon className="w-3.5 h-3.5 mr-1.5" />
              {local.image_url ? "Regenerate" : "Generate"}
            </Button>
            <Button
              onClick={genSegment}
              disabled={busy}
              size="sm"
              variant="outline"
              data-testid={`gen-video-${scene.id}`}
              className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
            >
              <Video className="w-3.5 h-3.5 mr-1.5" /> Generate 5s
            </Button>
          </div>
        </div>

        {/* Fields */}
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-3">
          <FieldInput
            label="Title"
            value={local.title}
            onChange={(v) => patch("title", v)}
            onBlur={() => saveField("title", local.title)}
            testId={`scene-title-${scene.id}`}
          />
          <FieldInput
            label="Duration (s)"
            type="number"
            value={local.duration}
            onChange={(v) => patch("duration", parseInt(v || "0", 10))}
            onBlur={() => saveField("duration", local.duration)}
            testId={`scene-duration-${scene.id}`}
          />
          <FieldInput
            label="Location"
            value={local.location || ""}
            onChange={(v) => patch("location", v)}
            onBlur={() => saveField("location", local.location)}
            testId={`scene-location-${scene.id}`}
          />
          <FieldInput
            label="Camera direction"
            value={local.camera_direction || ""}
            onChange={(v) => patch("camera_direction", v)}
            onBlur={() => saveField("camera_direction", local.camera_direction)}
            testId={`scene-camera-${scene.id}`}
          />
          <div className="md:col-span-2">
            <label className="es-label block mb-1.5">Visual prompt</label>
            <Textarea
              data-testid={`scene-prompt-${scene.id}`}
              value={local.visual_prompt || ""}
              onChange={(e) => patch("visual_prompt", e.target.value)}
              onBlur={() => saveField("visual_prompt", local.visual_prompt)}
              className="bg-[#0A0A0A] border-white/10 text-white"
            />
          </div>
          <div className="md:col-span-2">
            <label className="es-label block mb-1.5">Dialogue</label>
            <Textarea
              data-testid={`scene-dialogue-${scene.id}`}
              value={local.dialogue || ""}
              onChange={(e) => patch("dialogue", e.target.value)}
              onBlur={() => saveField("dialogue", local.dialogue)}
              className="bg-[#0A0A0A] border-white/10 text-white min-h-[60px]"
            />
          </div>
          <div>
            <label className="es-label block mb-1.5">Music mood</label>
            <Select
              value={local.music_mood}
              onValueChange={(v) => {
                patch("music_mood", v);
                saveField("music_mood", v);
              }}
            >
              <SelectTrigger
                className="bg-[#0A0A0A] border-white/10 text-white"
                data-testid={`scene-mood-${scene.id}`}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#121212] border-white/10 text-white">
                {options.music_moods.map((m) => (
                  <SelectItem key={m} value={m}>{m}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="es-label block mb-1.5">Voice</label>
            <Select
              value={local.voice}
              onValueChange={(v) => {
                patch("voice", v);
                saveField("voice", v);
              }}
            >
              <SelectTrigger
                className="bg-[#0A0A0A] border-white/10 text-white"
                data-testid={`scene-voice-${scene.id}`}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#121212] border-white/10 text-white">
                {options.voices.map((v) => (
                  <SelectItem key={v} value={v}>{v}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {characters.length > 0 && (
            <div className="md:col-span-2">
              <label className="es-label block mb-1.5">Characters in scene</label>
              <div className="flex flex-wrap gap-2">
                {characters.map((c) => {
                  const active = (local.characters || []).includes(c.id);
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
                        saveField("characters", next);
                      }}
                      className={`px-3 py-1 text-xs rounded-md border transition-colors ${
                        active
                          ? "bg-[#FF3B30] border-[#FF3B30] text-white"
                          : "bg-transparent border-white/15 text-[#A1A1AA] hover:text-white hover:bg-white/5"
                      }`}
                    >
                      {c.name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Segments */}
      <div className="mt-5 pt-5 border-t border-white/10">
        <div className="flex items-center justify-between mb-3">
          <h4 className="es-label">Video segments · 5s each</h4>
          <Button
            size="sm"
            onClick={expand}
            disabled={busy}
            data-testid={`expand-5s-${scene.id}`}
            variant="outline"
            className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" /> Expand next 5s
          </Button>
        </div>
        {(scene.segments || []).length === 0 ? (
          <p className="text-xs text-[#A1A1AA]">No segments yet. Generate one above.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {scene.segments.map((seg, i) => (
              <SegmentCard
                key={seg.id}
                segment={seg}
                index={i}
                reload={reload}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FieldInput({ label, value, onChange, onBlur, testId, type = "text" }) {
  return (
    <div>
      <label className="es-label block mb-1.5">{label}</label>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        data-testid={testId}
        className="bg-[#0A0A0A] border-white/10 text-white"
      />
    </div>
  );
}

function SegmentCard({ segment, index, reload }) {
  const [busy, setBusy] = useState(false);

  const setStatus = async (status) => {
    setBusy(true);
    try {
      await Segments.setStatus(segment.id, status);
      toast.success(`Segment ${status}`);
      reload();
    } finally {
      setBusy(false);
    }
  };
  const regen = async () => {
    setBusy(true);
    try {
      await Segments.regenerate(segment.id);
      toast.success("Regenerated");
      reload();
    } catch {
      toast.error("Regen failed (mock)");
    } finally {
      setBusy(false);
    }
  };

  const statusColor =
    segment.status === "approved"
      ? "border-[#34C759] text-[#34C759]"
      : segment.status === "rejected"
        ? "border-[#FF3B30] text-[#FF3B30]"
        : "border-white/20 text-[#A1A1AA]";

  return (
    <div className="es-card p-3" data-testid={`segment-${segment.id}`}>
      <div className="aspect-video bg-black rounded-md overflow-hidden mb-3 border border-white/10">
        <video
          src={segment.video_url}
          controls
          className="w-full h-full"
          muted
        />
      </div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-[#A1A1AA]">
          +{index * 5}s — +{(index + 1) * 5}s
        </span>
        <Badge variant="outline" className={`font-mono text-[10px] ${statusColor}`}>
          {segment.status}
        </Badge>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        <Button
          size="sm"
          disabled={busy}
          onClick={() => setStatus("approved")}
          data-testid={`approve-${segment.id}`}
          className="bg-[#34C759]/20 hover:bg-[#34C759]/30 text-[#34C759] border border-[#34C759]/30 h-8"
        >
          <Check className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="sm"
          disabled={busy}
          onClick={() => setStatus("rejected")}
          data-testid={`reject-${segment.id}`}
          className="bg-[#FF3B30]/15 hover:bg-[#FF3B30]/25 text-[#FF3B30] border border-[#FF3B30]/30 h-8"
        >
          <X className="w-3.5 h-3.5" />
        </Button>
        <Button
          size="sm"
          disabled={busy}
          onClick={regen}
          variant="outline"
          data-testid={`regen-${segment.id}`}
          className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white h-8"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Characters tab
// ---------------------------------------------------------------------------
function CharactersTab({ project, characters, voices, reload }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [voice, setVoice] = useState("Narrator-Warm");

  const create = async () => {
    if (!name.trim()) {
      toast.error("Name required");
      return;
    }
    await Characters.create(project.id, {
      name: name.trim(),
      description: desc.trim(),
      voice_style: voice,
    });
    toast.success("Character added");
    setOpen(false);
    setName("");
    setDesc("");
    reload();
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
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button
              data-testid="open-add-character-btn"
              className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
            >
              <UserPlus className="w-4 h-4 mr-2" /> Add character
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#121212] border-white/10 text-white">
            <DialogHeader>
              <DialogTitle className="font-display">New character</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div>
                <label className="es-label block mb-1.5">Name</label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  data-testid="char-name-input"
                  className="bg-[#0A0A0A] border-white/10 text-white"
                />
              </div>
              <div>
                <label className="es-label block mb-1.5">Description</label>
                <Textarea
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  data-testid="char-desc-input"
                  className="bg-[#0A0A0A] border-white/10 text-white"
                />
              </div>
              <div>
                <label className="es-label block mb-1.5">Voice style</label>
                <Select value={voice} onValueChange={setVoice}>
                  <SelectTrigger className="bg-[#0A0A0A] border-white/10 text-white" data-testid="char-voice-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#121212] border-white/10 text-white">
                    {voices.map((v) => (
                      <SelectItem key={v} value={v}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setOpen(false)}
                className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
              >
                Cancel
              </Button>
              <Button
                onClick={create}
                data-testid="submit-add-character-btn"
                className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
              >
                Add
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {characters.length === 0 ? (
        <div className="es-card p-12 text-center text-[#A1A1AA]">
          No characters yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="characters-grid">
          {characters.map((c) => (
            <div key={c.id} className="es-card overflow-hidden" data-testid={`char-${c.id}`}>
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
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove(c.id)}
                    data-testid={`delete-char-${c.id}`}
                    className="text-[#A1A1AA] hover:text-[#FF3B30] hover:bg-white/5"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
                {c.description && (
                  <p className="text-sm text-[#A1A1AA] mt-2 line-clamp-3">{c.description}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Export tab
// ---------------------------------------------------------------------------
function ExportTab({ projectId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    Projects.export(projectId).then(setData);
  }, [projectId]);

  if (!data) return <div className="text-[#A1A1AA] text-sm">Loading export…</div>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4" data-testid="export-view">
      <div className="lg:col-span-2 es-card p-4">
        <div className="aspect-video bg-black rounded-md border border-white/10 overflow-hidden mb-4 relative">
          {data.ready ? (
            <video
              src={data.final_video_url}
              controls
              className="w-full h-full"
              data-testid="final-video"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-center text-[#A1A1AA] text-sm">
              Approve at least one segment to preview the stitched final cut.
            </div>
          )}
        </div>
        <h3 className="font-display text-xl font-bold mb-2">Final Cut</h3>
        <p className="text-sm text-[#A1A1AA]">
          A mocked stitched output of all approved segments. The real pipeline
          will use FFmpeg to concat segments with music and voice.
        </p>
      </div>
      <div className="es-card p-4" data-testid="approved-list">
        <div className="flex items-center justify-between mb-3">
          <h4 className="es-label">Approved timeline</h4>
          <span className="font-mono text-xs text-[#A1A1AA]">
            {data.total_duration_seconds}s
          </span>
        </div>
        {data.approved_segments.length === 0 ? (
          <p className="text-xs text-[#A1A1AA]">Nothing approved yet.</p>
        ) : (
          <ul className="space-y-2">
            {data.approved_segments.map((seg, i) => (
              <li
                key={seg.segment_id}
                className="flex items-center justify-between text-sm py-2 border-b border-white/5 last:border-0"
              >
                <div>
                  <div className="font-mono text-[10px] uppercase text-[#A1A1AA]">
                    #{String(i + 1).padStart(2, "0")}
                  </div>
                  <div className="text-white">{seg.scene_title}</div>
                </div>
                <span className="font-mono text-xs text-[#34C759]">+{seg.duration}s</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
