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
  Music2,
  Mic2,
  Link2,
  Info,
  Settings as SettingsIcon,
  PlugZap,
  ShieldAlert,
  KeyRound,
  AlertCircle,
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import { SortableList } from "../components/SortableList";
import {
  Projects,
  Scenes,
  Characters,
  Segments,
  Meta,
  ProjectProviders,
  ProviderSettings,
} from "../lib/api";

const STAGES = [
  { value: "story", label: "Story" },
  { value: "scenes", label: "Scenes" },
  { value: "characters", label: "Characters" },
  { value: "images", label: "Images" },
  { value: "segments", label: "Video Segments" },
  { value: "voice-music", label: "Voice / Music" },
  { value: "export", label: "Export" },
];

export default function ProjectStudio() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [providers, setProviders] = useState(null);
  const [voiceRes, setVoiceRes] = useState(null);
  const [sceneCosts, setSceneCosts] = useState({ status: "idle", data: null });
  const [costDelta, setCostDelta] = useState(null); // { value, key }
  const [options, setOptions] = useState({ voices: [], music_moods: [], costs: {} });
  const [tab, setTab] = useState("story");

  const load = useCallback(() => Projects.get(id).then(setData), [id]);
  const loadProviders = useCallback(
    () => ProjectProviders.get(id).then(setProviders),
    [id]
  );
  const loadVoiceRes = useCallback(
    () => ProjectProviders.voiceResolution(id).then(setVoiceRes),
    [id]
  );
  const loadSceneCosts = useCallback(
    ({ trackDelta = false } = {}) => {
      setSceneCosts((p) => {
        return { ...p, status: "loading" };
      });
      const prevTotal =
        sceneCosts.status === "ok" ? sceneCosts.data?.grand_total_credits : null;
      return Projects.sceneCosts(id)
        .then((d) => {
          setSceneCosts({ status: "ok", data: d });
          if (trackDelta && prevTotal != null) {
            const delta = d.grand_total_credits - prevTotal;
            if (delta !== 0) {
              setCostDelta({ value: delta, key: Date.now() });
            }
          }
        })
        .catch(() => setSceneCosts({ status: "error", data: null }));
    },
    [id, sceneCosts]
  );

  // Auto-fade the delta after 1.5s
  useEffect(() => {
    if (!costDelta) return;
    const t = setTimeout(() => setCostDelta(null), 1500);
    return () => clearTimeout(t);
  }, [costDelta]);

  const reloadAll = useCallback(
    (opts = {}) => {
      if (!opts.skipProject) load();
      loadVoiceRes();
      loadSceneCosts({ trackDelta: true });
    },
    [load, loadVoiceRes, loadSceneCosts]
  );

  useEffect(() => {
    load();
    loadProviders();
    loadVoiceRes();
    loadSceneCosts();
    Meta.options().then(setOptions);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!data) return <div className="text-[#A1A1AA] text-sm">Loading project…</div>;
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
      <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-6 gap-4">
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
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setTab("providers")}
            data-testid="header-providers-shortcut"
            className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white h-11"
          >
            <SettingsIcon className="w-4 h-4 mr-1.5" /> Providers
          </Button>
          <CostBadge sceneCosts={sceneCosts} delta={costDelta} />
        </div>
      </div>

      <StageProgress current={tab} onJump={setTab} />

      <Tabs value={tab} onValueChange={setTab} className="mt-6">
        <TabsList className="bg-[#121212] border border-white/10 flex flex-wrap h-auto">
          {STAGES.map((s) => (
            <TabsTrigger
              key={s.value}
              value={s.value}
              data-testid={`tab-${s.value}`}
            >
              {s.label}
            </TabsTrigger>
          ))}
          <TabsTrigger value="providers" data-testid="tab-providers">
            <span className="inline-flex items-center gap-1.5">
              <SettingsIcon className="w-3.5 h-3.5" /> Providers
            </span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="story" className="mt-6">
          <StoryTab
            project={project}
            providers={providers}
            options={options}
            reload={load}
            onContinue={() => setTab("scenes")}
          />
        </TabsContent>
        <TabsContent value="scenes" className="mt-6">
          <ScenesTab
            project={project}
            scenes={scenes}
            characters={characters}
            options={options}
            voiceResolution={voiceRes}
            sceneCosts={sceneCosts}
            setData={setData}
            reload={reloadAll}
          />
        </TabsContent>
        <TabsContent value="characters" className="mt-6">
          <CharactersTab
            project={project}
            characters={characters}
            voices={options.voices}
            voiceCatalog={providers?.effective ? null : null}
            reload={reloadAll}
          />
        </TabsContent>
        <TabsContent value="images" className="mt-6">
          <ImagesTab
            scenes={scenes}
            providers={providers}
            options={options}
            reload={reloadAll}
          />
        </TabsContent>
        <TabsContent value="segments" className="mt-6">
          <SegmentsTab
            scenes={scenes}
            providers={providers}
            options={options}
            setData={setData}
            reload={reloadAll}
          />
        </TabsContent>
        <TabsContent value="voice-music" className="mt-6">
          <VoiceMusicTab
            scenes={scenes}
            options={options}
            providers={providers}
            characters={characters}
            voiceResolution={voiceRes}
            onCharacterEdit={() => setTab("characters")}
            reload={reloadAll}
          />
        </TabsContent>
        <TabsContent value="export" className="mt-6">
          <ExportTab projectId={id} providers={providers} options={options} />
        </TabsContent>
        <TabsContent value="providers" className="mt-6">
          <ProvidersTab
            projectId={id}
            onChanged={() => {
              loadProviders();
              loadVoiceRes();
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stage progress strip
// ---------------------------------------------------------------------------
function StageProgress({ current, onJump }) {
  const idx = STAGES.findIndex((s) => s.value === current);
  return (
    <div className="es-card p-4" data-testid="stage-progress">
      <div className="flex items-center justify-between mb-3">
        <span className="es-label">Workflow</span>
        <span className="text-xs font-mono text-[#A1A1AA]">
          Step {idx + 1} of {STAGES.length}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {STAGES.map((s, i) => {
          const active = i === idx;
          const done = i < idx;
          return (
            <button
              key={s.value}
              type="button"
              data-testid={`stage-jump-${s.value}`}
              onClick={() => onJump(s.value)}
              className={`text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
                active
                  ? "bg-[#FF3B30] border-[#FF3B30] text-white"
                  : done
                    ? "bg-white/5 border-white/15 text-white"
                    : "bg-transparent border-white/10 text-[#A1A1AA] hover:bg-white/5 hover:text-white"
              }`}
            >
              <span className="font-mono mr-1.5 opacity-70">
                {String(i + 1).padStart(2, "0")}
              </span>
              {s.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cost badge (live, backed by /scene-costs) + Wallet ring
// ---------------------------------------------------------------------------
const WALLET_STATE_COLOR = {
  normal: "#34C759",
  warning: "#FFCC00",
  high: "#FF9500",
  insufficient: "#FF3B30",
};

function WalletRing({ pct, state, walletCredits, totalCredits }) {
  const radius = 18;
  const stroke = 4;
  const c = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, Number.isFinite(pct) ? pct : 0));
  const dash = (clamped / 100) * c;
  const color = WALLET_STATE_COLOR[state] || WALLET_STATE_COLOR.normal;
  const tooltip = `This episode would use about ${Math.round(pct)}% of your available ${walletCredits} credits.`;
  return (
    <div
      className="flex flex-col items-center"
      title={tooltip}
      data-testid="wallet-ring"
      data-state={state}
    >
      <svg width="48" height="48" viewBox="0 0 48 48" className="rotate-[-90deg]">
        <circle
          cx="24"
          cy="24"
          r={radius}
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx="24"
          cy="24"
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${dash} ${c}`}
          style={{ transition: "stroke-dasharray 350ms ease, stroke 200ms ease" }}
        />
      </svg>
      <span
        className="text-[10px] font-mono mt-0.5"
        style={{ color }}
        data-testid="wallet-ring-pct"
      >
        {Math.round(pct)}%
      </span>
    </div>
  );
}

function CostBadge({ sceneCosts, delta }) {
  let body;
  let ring = null;
  if (sceneCosts.status === "loading" && !sceneCosts.data) {
    body = (
      <div className="font-display text-lg font-bold text-[#A1A1AA]" data-testid="cost-badge-loading">
        Calculating…
      </div>
    );
  } else if (sceneCosts.status === "error") {
    body = (
      <div className="font-display text-sm font-semibold text-[#A1A1AA]" data-testid="cost-badge-error">
        Estimate unavailable
      </div>
    );
  } else {
    const d = sceneCosts.data;
    const total = d?.grand_total_credits ?? 0;
    const pct = d?.wallet_pct ?? 0;
    const wallet = d?.wallet_credits ?? 0;
    const showDelta = !!delta && delta.value !== 0;
    const deltaUp = showDelta && delta.value > 0;
    body = (
      <div data-testid="cost-badge-total">
        <div className="font-display text-lg font-bold leading-tight inline-flex items-center gap-2">
          <span>
            ~{total} <span className="text-xs text-[#A1A1AA] font-mono">credits</span>
          </span>
          {showDelta && (
            <span
              key={delta.key}
              data-testid="cost-trend"
              data-direction={deltaUp ? "up" : "down"}
              className="es-trend text-[11px] font-mono inline-flex items-center"
              style={{ color: deltaUp ? "#FF9500" : "#34C759" }}
            >
              {deltaUp ? "↑" : "↓"} {deltaUp ? "+" : ""}
              {delta.value}
            </span>
          )}
        </div>
        {wallet ? (
          <div
            className="text-[10px] font-mono"
            style={{ color: WALLET_STATE_COLOR[d.wallet_state] || "#A1A1AA" }}
            data-testid="wallet-pct-line"
          >
            {Math.round(pct)}% of wallet
            {d.wallet_state === "insufficient" && " · insufficient credits"}
          </div>
        ) : null}
      </div>
    );
    if (wallet) {
      ring = (
        <WalletRing
          pct={pct}
          state={d.wallet_state}
          walletCredits={wallet}
          totalCredits={total}
        />
      );
    }
  }
  return (
    <div className="es-card px-4 py-2.5 inline-flex items-center gap-3" data-testid="cost-estimate">
      <Coins className="w-4 h-4 text-[#FFCC00]" />
      <div>
        <div className="es-label">Project scene cost</div>
        {body}
      </div>
      {ring}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Story tab
// ---------------------------------------------------------------------------
function StoryTab({ project, providers, options, reload, onContinue }) {
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
    <div className="space-y-4">
      <ProviderHint
        providers={providers}
        modality="llm"
        action="story rewrite"
        credits={options?.costs?.rewrite ? `~${options.costs.rewrite} credits` : null}
      />
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
          <div>
            <h3 className="font-display text-lg font-bold">Episode draft</h3>
            <p className="text-xs text-[#A1A1AA] mt-0.5">
              Edit freely before splitting into scenes.
            </p>
          </div>
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
          <Split className="w-4 h-4 mr-2" /> {busy ? "Splitting…" : "Save & split into scenes →"}
        </Button>
      </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scenes tab — text/structure editing only (no media generation here)
// ---------------------------------------------------------------------------
function ScenesTab({ project, scenes, characters, options, voiceResolution, sceneCosts, setData, reload }) {
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
  const threshold = sceneCosts?.data?.high_cost_scene_threshold_percent ?? 25;
  return (
    <div className="space-y-4" data-testid="scenes-list">
      <div className="flex items-end justify-between flex-wrap gap-3" data-testid="scenes-tab-header">
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
      <InfoCallout
        text="Edit titles, locations, prompts and dialogue here. Drag the grip handle to reorder scenes. Image and video generation happen in their own tabs."
      />
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
            // Quietly refresh derived data (cost-costs etc.) without snapping the list
            reload({ skipProject: true });
          } catch {
            setData((d) => (d ? { ...d, scenes: prev } : d));
            toast.error("Reorder failed — restored");
          }
        }}
        renderItem={(s, handle) => (
          <SceneEditor
            scene={s}
            index={scenes.findIndex((x) => x.id === s.id)}
            characters={characters}
            options={options}
            voiceResolution={voiceResolution}
            costRow={sceneCostMap[s.id]}
            highCostThreshold={threshold}
            dragHandle={handle}
            setData={setData}
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

function SceneEditor({ index, scene, characters, options, voiceResolution, costRow, highCostThreshold, dragHandle, reload }) {
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

  // Per-scene credit estimate from options.costs (mock).
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
  // voice override lookup by character id
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
          <Badge variant="outline" className="border-white/15 text-[#A1A1AA] font-mono text-[10px]">
            {local.status || "draft"}
          </Badge>
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
              <span className="text-[#A1A1AA]" data-testid={`scene-credits-breakdown-${scene.id}`}>
                · img {breakdown.image} · vid {breakdown.video}
                {segmentsCount > 1 ? ` (${segmentsCount}×)` : ""} · voice {breakdown.voice}
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
        <FieldInput label="Title" value={local.title}
          onChange={(v) => patch("title", v)} onBlur={() => save("title", local.title)}
          testId={`scene-title-${scene.id}`} />
        <FieldInput label="Duration (s)" type="number" value={local.duration}
          onChange={(v) => patch("duration", parseInt(v || "0", 10))}
          onBlur={() => save("duration", local.duration)} testId={`scene-duration-${scene.id}`} />
        <FieldInput label="Location" value={local.location || ""}
          onChange={(v) => patch("location", v)} onBlur={() => save("location", local.location)}
          testId={`scene-location-${scene.id}`} />
        <FieldInput label="Camera direction" value={local.camera_direction || ""}
          onChange={(v) => patch("camera_direction", v)}
          onBlur={() => save("camera_direction", local.camera_direction)}
          testId={`scene-camera-${scene.id}`} />
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

function InfoCallout({ text }) {
  return (
    <div className="es-card p-3 flex items-start gap-2 border-white/10 bg-white/[0.02]">
      <Info className="w-4 h-4 text-[#A1A1AA] mt-0.5 shrink-0" />
      <p className="text-xs text-[#A1A1AA]">{text}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline provider hint — informational only, mock-only
// ---------------------------------------------------------------------------
function ProviderHint({ providers, modality, action, credits, testId }) {
  if (!providers) return null;
  const eff = providers.effective?.[modality];
  if (!eff) return null;
  const overrideOn = providers.provider_override_enabled;
  const usingProject = overrideOn && eff.source === "project";
  const provider = eff.provider || "—";
  const model = eff.model || (eff.custom_model || "—");
  const displayProvider =
    eff.provider === "custom"
      ? `custom${eff.custom_provider ? `:${eff.custom_provider}` : ""}`
      : provider;
  return (
    <div
      className="es-card p-3 flex flex-wrap items-center gap-2 border-white/10 bg-white/[0.02]"
      data-testid={testId || `provider-hint-${modality}`}
    >
      <PlugZap className="w-3.5 h-3.5 text-[#FF3B30] shrink-0" />
      <span className="text-xs text-[#A1A1AA]">
        This {action} would use:{" "}
        <span
          className="text-white font-mono"
          data-testid={`hint-text-${modality}`}
        >
          {displayProvider}/{model}
        </span>
        {credits ? (
          <span
            className="text-[#FFCC00] font-mono ml-2"
            data-testid={`hint-credits-${modality}`}
          >
            · {credits}
          </span>
        ) : null}
      </span>
      <span
        data-testid={`hint-badge-${modality}`}
        className={`ml-auto px-2 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-widest border ${
          usingProject
            ? "border-[#FF3B30]/40 text-[#FF3B30]"
            : "border-white/15 text-[#A1A1AA]"
        }`}
      >
        {usingProject ? "Project Override Active" : "Using Global Default"}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Images tab — generate / approve scene images
// ---------------------------------------------------------------------------
function ImagesTab({ scenes, providers, options, reload }) {
  if (!scenes.length) {
    return <EmptyState text="Split your story into scenes first to generate images." />;
  }
  const c = options?.costs?.image;
  return (
    <div className="space-y-3">
      <ProviderHint
        providers={providers}
        modality="image"
        action="image generation"
        credits={c ? `~${c} credits per scene image` : null}
      />
      <InfoCallout text="Generate or regenerate one image per scene. The image becomes the visual anchor for video generation." />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="images-grid">
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
          <img src={scene.image_url} alt={scene.title} className="w-full h-full object-cover" />
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

// ---------------------------------------------------------------------------
// Video Segments tab
// ---------------------------------------------------------------------------
function SegmentsTab({ scenes, providers, options, setData, reload }) {
  if (!scenes.length) {
    return <EmptyState text="Split your story into scenes first." />;
  }
  const c = options?.costs?.video_segment;
  return (
    <div className="space-y-4" data-testid="segments-tab">
      <ProviderHint
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

function SceneSegmentBlock({ scene, index, reload }) {
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
        <p className="text-xs text-[#A1A1AA]">No segments yet. Generate the first 5 seconds.</p>
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

function SegmentCard({ segment, index, parent, dragHandle, reload }) {
  const [busy, setBusy] = useState(false);
  const [continuity, setContinuity] = useState(segment.continuity_prompt || "");
  const [saveState, setSaveState] = useState("idle"); // idle | saving | saved | error
  useEffect(() => {
    setContinuity(segment.continuity_prompt || "");
  }, [segment.continuity_prompt]);

  const persistContinuity = async () => {
    if ((continuity || "").trim() === (segment.continuity_prompt || "").trim()) return;
    setSaveState("saving");
    try {
      await Segments.update(segment.id, { continuity_prompt: continuity });
      setSaveState("saved");
      setTimeout(() => setSaveState((s) => (s === "saved" ? "idle" : s)), 1500);
    } catch {
      setSaveState("error");
    }
  };

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
  const removeSeg = async () => {
    setBusy(true);
    try {
      await Segments.remove(segment.id);
      toast.success("Segment deleted");
      reload();
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

  const start = segment.start_second ?? index * 5;
  const dur = segment.duration ?? 5;
  const mode = segment.expand_mode || (index === 0 ? "initial" : "expand");

  return (
    <div className="es-card p-3" data-testid={`segment-${segment.id}`}>
      <div className="aspect-video bg-black rounded-md overflow-hidden mb-3 border border-white/10 relative">
        <video src={segment.video_url} controls className="w-full h-full" muted />
        {dragHandle && (
          <div className="absolute top-1 left-1 bg-black/70 rounded backdrop-blur">
            {dragHandle}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[10px] uppercase tracking-widest text-[#A1A1AA]">
          #{String((segment.order ?? index) + 1).padStart(2, "0")} · {mode}
        </span>
        <Badge variant="outline" className={`font-mono text-[10px] ${statusColor}`}>
          {segment.status}
        </Badge>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] mb-3 font-mono">
        <dt className="text-[#A1A1AA]">Start</dt>
        <dd className="text-white text-right" data-testid={`segment-start-${segment.id}`}>{start}s</dd>
        <dt className="text-[#A1A1AA]">Duration</dt>
        <dd className="text-white text-right" data-testid={`segment-duration-${segment.id}`}>{dur}s</dd>
        <dt className="text-[#A1A1AA] flex items-center gap-1">
          <Link2 className="w-3 h-3" /> Parent
        </dt>
        <dd
          className="text-white text-right truncate"
          data-testid={`segment-parent-${segment.id}`}
          title={segment.parent_segment_id || "—"}
        >
          {parent
            ? `#${String((parent.order ?? 0) + 1).padStart(2, "0")}`
            : segment.parent_segment_id
              ? segment.parent_segment_id.slice(0, 6)
              : "—"}
        </dd>
      </dl>

      {segment.continuity_prompt !== undefined && (
        <div className="mb-3" data-testid={`continuity-edit-${segment.id}`}>
          <label className="es-label flex items-center justify-between mb-1">
            <span>Continuity prompt</span>
            <span
              className="font-mono normal-case tracking-normal"
              data-testid={`continuity-state-${segment.id}`}
              style={{
                color:
                  saveState === "saving"
                    ? "#A1A1AA"
                    : saveState === "saved"
                      ? "#34C759"
                      : saveState === "error"
                        ? "#FF3B30"
                        : "#52525B",
              }}
            >
              {saveState === "saving"
                ? "Saving…"
                : saveState === "saved"
                  ? "Saved"
                  : saveState === "error"
                    ? "Failed to save"
                    : ""}
            </span>
          </label>
          <Textarea
            value={continuity}
            onChange={(e) => setContinuity(e.target.value)}
            onBlur={persistContinuity}
            data-testid={`continuity-input-${segment.id}`}
            placeholder="↳ Continue smoothly from the previous clip…"
            className="bg-[#0A0A0A] border-white/10 text-white text-xs min-h-[52px]"
          />
        </div>
      )}

      <div className="grid grid-cols-4 gap-1.5">
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
        <Button
          size="sm"
          disabled={busy}
          onClick={removeSeg}
          variant="outline"
          data-testid={`delete-segment-${segment.id}`}
          className="border-white/15 bg-transparent text-[#A1A1AA] hover:bg-[#FF3B30]/15 hover:text-[#FF3B30] hover:border-[#FF3B30]/30 h-8"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Voice / Music tab
// ---------------------------------------------------------------------------
function VoiceMusicTab({ scenes, options, providers, characters, voiceResolution, onCharacterEdit, reload }) {
  if (!scenes.length) {
    return <EmptyState text="Split your story into scenes first." />;
  }
  const cv = options?.costs?.voice;
  const cm = options?.costs?.music;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ProviderHint
          providers={providers}
          modality="voice"
          action="voice generation"
          credits={cv ? `~${cv} credit per scene` : null}
        />
        <ProviderHint
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
          <VoiceMusicRow key={s.id} scene={s} index={i} options={options} reload={reload} />
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
    <div className="es-card p-4 grid grid-cols-1 md:grid-cols-12 gap-3 items-center" data-testid={`vm-row-${scene.id}`}>
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
          <SelectTrigger className="bg-[#0A0A0A] border-white/10 text-white" data-testid={`vm-voice-${scene.id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-[#121212] border-white/10 text-white">
            {options.voices.map((v) => (
              <SelectItem key={v} value={v}>{v}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="md:col-span-4">
        <label className="es-label block mb-1.5 inline-flex items-center gap-1">
          <Music2 className="w-3 h-3" /> Music mood
        </label>
        <Select value={scene.music_mood} onValueChange={(v) => update("music_mood", v)}>
          <SelectTrigger className="bg-[#0A0A0A] border-white/10 text-white" data-testid={`vm-mood-${scene.id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-[#121212] border-white/10 text-white">
            {options.music_moods.map((m) => (
              <SelectItem key={m} value={m}>{m}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Characters tab
// ---------------------------------------------------------------------------
const VOICE_PROVIDER_OPTIONS = [
  { id: "elevenlabs", label: "ElevenLabs" },
  { id: "openai-tts", label: "OpenAI TTS" },
  { id: "google-tts", label: "Google Cloud TTS" },
  { id: "custom", label: "Custom voice provider" },
];

function CharactersTab({ project, characters, voices, reload }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null); // null | character object
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
                      <SelectItem key={v} value={v}>{v}</SelectItem>
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
                          <SelectItem key={v.id} value={v.id}>{v.label}</SelectItem>
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
        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          data-testid="characters-grid"
        >
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
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Export tab
// ---------------------------------------------------------------------------
function ExportTab({ projectId, providers, options }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    Projects.export(projectId).then(setData);
  }, [projectId]);
  if (!data) return <div className="text-[#A1A1AA] text-sm">Loading export…</div>;
  const c = options?.costs?.export;

  return (
    <div className="space-y-4" data-testid="export-view">
      <ProviderHint
        providers={providers}
        modality="export"
        action="export"
        credits={c ? `~${c} credits per final export` : null}
      />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 es-card p-4">
        <div className="aspect-video bg-black rounded-md border border-white/10 overflow-hidden mb-4 relative">
          {data.ready ? (
            <video src={data.final_video_url} controls className="w-full h-full" data-testid="final-video" />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-center text-[#A1A1AA] text-sm">
              Approve at least one segment to preview the stitched final cut.
            </div>
          )}
        </div>
        <h3 className="font-display text-xl font-bold mb-2">Final Cut</h3>
        <p className="text-sm text-[#A1A1AA]">
          A mocked stitched output of all approved segments. Real pipeline will use FFmpeg
          to concat segments with music and voice.
        </p>
      </div>
      <div className="es-card p-4" data-testid="approved-list">
        <div className="flex items-center justify-between mb-3">
          <h4 className="es-label">Approved timeline</h4>
          <span className="font-mono text-xs text-[#A1A1AA]">{data.total_duration_seconds}s</span>
        </div>
        {data.approved_segments.length === 0 ? (
          <p className="text-xs text-[#A1A1AA]">Nothing approved yet.</p>
        ) : (
          <ul className="space-y-2">
            {data.approved_segments.map((seg, i) => (
              <li key={seg.segment_id}
                className="flex items-center justify-between text-sm py-2 border-b border-white/5 last:border-0">
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
    </div>
  );
}

function EmptyState({ text }) {
  return <div className="es-card p-12 text-center text-[#A1A1AA] text-sm">{text}</div>;
}

// ---------------------------------------------------------------------------
// Providers tab — per-project override (mock-only)
// ---------------------------------------------------------------------------
const PROVIDER_SECTIONS = [
  { key: "llm", label: "LLM (Story rewrite)", icon: Wand2 },
  { key: "image", label: "Image", icon: ImageIcon },
  { key: "video", label: "Video", icon: Video },
  { key: "voice", label: "Voice", icon: Mic2 },
  { key: "music", label: "Music", icon: Music2 },
  { key: "export", label: "Export", icon: Save },
];

function ProvidersTab({ projectId, onChanged }) {
  const [data, setData] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);

  const loadAll = useCallback(() => {
    return Promise.all([
      ProjectProviders.get(projectId),
      ProviderSettings.options(),
    ]).then(([d, opt]) => {
      setData(d);
      setCatalog(opt.catalog);
      setDraft({
        provider_override_enabled: d.provider_override_enabled,
        ...PROVIDER_SECTIONS.reduce((acc, s) => {
          const provField = s.key === "export" ? "export_provider" : `${s.key}_provider`;
          const modelField = s.key === "export" ? "export_mode" : `${s.key}_model`;
          acc[provField] = d.project[s.key].provider;
          acc[modelField] = d.project[s.key].model;
          return acc;
        }, {}),
      });
    });
  }, [projectId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  if (!data || !catalog || !draft) {
    return <div className="text-[#A1A1AA] text-sm">Loading providers…</div>;
  }

  const setOverride = async (next) => {
    const updated = await ProjectProviders.update(projectId, {
      provider_override_enabled: next,
    });
    setDraft((p) => ({ ...p, provider_override_enabled: next }));
    setData(updated);
    onChanged?.();
    toast.success(next ? "Project override enabled" : "Reverted to global defaults");
  };

  const patchModality = (modality, field, value) => {
    setDraft((prev) => {
      const provField = modality === "export" ? "export_provider" : `${modality}_provider`;
      const modelField = modality === "export" ? "export_mode" : `${modality}_model`;
      const next = { ...prev };
      if (field === "provider") {
        next[provField] = value;
        const list = catalog[modality];
        const found = list.find((p) => p.id === value);
        next[modelField] = found?.models?.[0] || "";
      } else {
        next[modelField] = value;
      }
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      const res = await ProjectProviders.update(projectId, draft);
      setData(res);
      onChanged?.();
      toast.success("Project providers saved");
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const test = async (modality) => {
    try {
      const r = await ProjectProviders.test(projectId, modality);
      toast(r.message, { icon: "🧪" });
    } catch {
      toast.error("Test failed");
    }
  };

  const overrideOn = draft.provider_override_enabled;

  return (
    <div className="space-y-4" data-testid="providers-tab">
      <div className="es-card p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-start gap-3">
          <SettingsIcon className="w-5 h-5 text-[#FF3B30] mt-0.5" />
          <div>
            <h3 className="font-display text-lg font-bold">Providers for this project</h3>
            <p className="text-xs text-[#A1A1AA] max-w-xl">
              Use the workspace defaults from{" "}
              <a href="/settings" className="text-white underline underline-offset-2">
                Settings
              </a>
              , or override them just for this project. Generation runs through mocks
              regardless until real providers are activated.
            </p>
          </div>
        </div>
        <Badge
          variant="outline"
          data-testid="providers-source-badge"
          className={`font-mono text-[10px] uppercase tracking-widest ${
            overrideOn
              ? "border-[#FF3B30]/40 text-[#FF3B30]"
              : "border-white/15 text-[#A1A1AA]"
          }`}
        >
          {overrideOn ? "Project override active" : "Configured from global defaults"}
        </Badge>
      </div>

      <div className="es-card p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h4 className="font-display text-base font-bold">Mode</h4>
            <p className="text-xs text-[#A1A1AA]">
              When override is on, this project saves its own provider selections.
              When off, the workspace defaults are used.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={!overrideOn ? "default" : "outline"}
              onClick={() => setOverride(false)}
              data-testid="use-global-btn"
              className={
                !overrideOn
                  ? "bg-white text-black hover:bg-white/90"
                  : "border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white"
              }
            >
              Use global defaults
            </Button>
            <Button
              size="sm"
              onClick={() => setOverride(true)}
              data-testid="use-override-btn"
              className={
                overrideOn
                  ? "bg-[#FF3B30] hover:bg-[#FF453A] text-white"
                  : "bg-transparent border border-white/15 text-white hover:bg-white/10"
              }
            >
              Override for this project
            </Button>
          </div>
        </div>
      </div>

      <FlagsBanner flags={data.feature_flags} />
      <KeyMgmtBanner />

      {!overrideOn ? (
        <EffectiveGlobalView effective={data.effective} onTest={test} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {PROVIDER_SECTIONS.map((sec) => {
            const provField =
              sec.key === "export" ? "export_provider" : `${sec.key}_provider`;
            const modelField =
              sec.key === "export" ? "export_mode" : `${sec.key}_model`;
            const providers = catalog[sec.key];
            const selected = providers.find((p) => p.id === draft[provField]);
            return (
              <ProjectProviderCard
                key={sec.key}
                sec={sec}
                providers={providers}
                providerValue={draft[provField] || ""}
                modelValue={draft[modelField] || ""}
                modelsList={selected?.models || []}
                onChange={(field, v) => patchModality(sec.key, field, v)}
                onTest={() => test(sec.key)}
                effective={data.effective[sec.key]}
              />
            );
          })}
        </div>
      )}

      {overrideOn && (
        <div className="flex justify-end">
          <Button
            onClick={save}
            disabled={saving}
            data-testid="save-project-providers-btn"
            className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
          >
            <Save className="w-4 h-4 mr-2" /> {saving ? "Saving…" : "Save project providers"}
          </Button>
        </div>
      )}
    </div>
  );
}

function FlagsBanner({ flags }) {
  return (
    <div
      data-testid="provider-flags-banner"
      className="es-card p-4 flex items-start gap-3 border-[#FFCC00]/30 bg-[#FFCC00]/5"
    >
      <Info className="w-5 h-5 text-[#FFCC00] mt-0.5" />
      <div className="flex-1">
        <p className="text-sm font-semibold text-[#FFCC00]">
          Mock mode active — no real provider calls
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {Object.entries(flags || {})
            .filter(([k]) => k !== "any_real")
            .map(([k, v]) => (
              <span
                key={k}
                className={`px-2 py-0.5 rounded-md text-[10px] font-mono uppercase tracking-widest border ${
                  v
                    ? "border-[#34C759]/40 text-[#34C759]"
                    : "border-white/10 text-[#A1A1AA]"
                }`}
                data-testid={`flag-${k}`}
              >
                USE_REAL_{k.toUpperCase()}_PROVIDER · {v ? "on" : "off"}
              </span>
            ))}
        </div>
      </div>
    </div>
  );
}

function KeyMgmtBanner() {
  return (
    <div
      data-testid="key-mgmt-banner"
      className="es-card p-4 flex items-start gap-3 border-white/10 opacity-70"
    >
      <KeyRound className="w-5 h-5 text-[#A1A1AA] mt-0.5" />
      <div>
        <p className="text-sm font-semibold text-white">API key management</p>
        <p className="text-xs text-[#A1A1AA] mt-1">
          API key management will be enabled when real provider mode is activated.
        </p>
      </div>
    </div>
  );
}

function EffectiveGlobalView({ effective, onTest }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="effective-global-grid">
      {PROVIDER_SECTIONS.map((sec) => {
        const eff = effective[sec.key];
        const Icon = sec.icon;
        return (
          <div key={sec.key} className="es-card p-4" data-testid={`eff-card-${sec.key}`}>
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-md bg-white/5 border border-white/10 flex items-center justify-center">
                  <Icon className="w-3.5 h-3.5 text-[#FF3B30]" />
                </span>
                <h4 className="font-display text-base font-bold">{sec.label}</h4>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onTest(sec.key)}
                data-testid={`test-${sec.key}-btn`}
                className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white h-7"
              >
                <PlugZap className="w-3 h-3 mr-1" /> Test
              </Button>
            </div>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs font-mono">
              <dt className="text-[#A1A1AA]">Provider</dt>
              <dd className="text-white text-right truncate">{eff.provider || "—"}</dd>
              <dt className="text-[#A1A1AA]">Model</dt>
              <dd className="text-white text-right truncate">{eff.model || "—"}</dd>
              <dt className="text-[#A1A1AA]">Source</dt>
              <dd className="text-[#A1A1AA] text-right">{eff.source}</dd>
            </dl>
          </div>
        );
      })}
    </div>
  );
}

function ProjectProviderCard({
  sec,
  providers,
  providerValue,
  modelValue,
  modelsList,
  onChange,
  onTest,
  effective,
}) {
  const Icon = sec.icon;
  const isCustom = providerValue === "custom";
  const usingFallback = effective?.source === "global-fallback";
  return (
    <div className="es-card p-5" data-testid={`project-provider-card-${sec.key}`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-md bg-white/5 border border-white/10 flex items-center justify-center">
            <Icon className="w-4 h-4 text-[#FF3B30]" />
          </span>
          <div>
            <h4 className="font-display text-base font-bold">{sec.label}</h4>
            {usingFallback && (
              <span className="text-[10px] font-mono text-[#A1A1AA]">
                empty → falling back to global ({effective.provider || "—"})
              </span>
            )}
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onTest}
          data-testid={`test-${sec.key}-btn`}
          className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white h-8"
        >
          <PlugZap className="w-3.5 h-3.5 mr-1.5" /> Test
        </Button>
      </div>

      <div className="space-y-3 mt-3">
        <div>
          <label className="es-label block mb-1.5">Provider</label>
          <Select value={providerValue || ""} onValueChange={(v) => onChange("provider", v)}>
            <SelectTrigger
              className="bg-[#0A0A0A] border-white/10 text-white"
              data-testid={`project-provider-select-${sec.key}`}
            >
              <SelectValue placeholder="— use global —" />
            </SelectTrigger>
            <SelectContent className="bg-[#121212] border-white/10 text-white">
              {providers.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {isCustom ? (
          <div>
            <label className="es-label block mb-1.5">
              {sec.key === "export" ? "Custom mode" : "Custom model ID"}
            </label>
            <Input
              value={modelValue || ""}
              onChange={(e) => onChange("model", e.target.value)}
              placeholder={sec.key === "export" ? "e.g. internal-stitch-worker" : "e.g. flux-pro-finetune-001"}
              data-testid={`project-custom-model-${sec.key}`}
              className="bg-[#0A0A0A] border-white/10 text-white"
            />
          </div>
        ) : modelsList.length > 0 ? (
          <div>
            <label className="es-label block mb-1.5">
              {sec.key === "export" ? "Mode" : "Model"}
            </label>
            <Select value={modelValue || ""} onValueChange={(v) => onChange("model", v)}>
              <SelectTrigger
                className="bg-[#0A0A0A] border-white/10 text-white"
                data-testid={`project-model-select-${sec.key}`}
              >
                <SelectValue placeholder="— pick one —" />
              </SelectTrigger>
              <SelectContent className="bg-[#121212] border-white/10 text-white">
                {modelsList.map((m) => (
                  <SelectItem key={m} value={m}>{m}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// add a mostly-unused symbol so import-linter doesn't warn on KeyRound + ShieldAlert
// (kept as future-use placeholders to satisfy "API keys disabled" iconography hooks)
// eslint-disable-next-line no-unused-vars
const _futureKeyIcons = { ShieldAlert };
