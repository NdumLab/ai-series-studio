import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ChevronLeft, Settings as SettingsIcon } from "lucide-react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import {
  Projects,
  Meta,
  ProjectProviders,
} from "../lib/api";
import { STAGES } from "../components/studio/constants";
import { StageProgress } from "../components/studio/StageProgress";
import { CostBadge } from "../components/studio/CostBadge";
import { StoryTab } from "./tabs/StoryTab";
import { ScenesTab } from "./tabs/ScenesTab";
import { CharactersTab } from "./tabs/CharactersTab";
import { ImagesTab } from "./tabs/ImagesTab";
import { VideoSegmentsTab } from "./tabs/VideoSegmentsTab";
import { VoiceMusicTab } from "./tabs/VoiceMusicTab";
import { ExportTab } from "./tabs/ExportTab";
import { ProvidersTab } from "./tabs/ProvidersTab";

export default function ProjectStudio() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [providers, setProviders] = useState(null);
  const [voiceRes, setVoiceRes] = useState(null);
  const [sceneCosts, setSceneCosts] = useState({ status: "idle", data: null });
  const [costDelta, setCostDelta] = useState(null);
  const [options, setOptions] = useState({ voices: [], music_moods: [], costs: {} });
  const [tab, setTab] = useState("story");

  const load = useCallback(() => Projects.get(id).then(setData), [id]);
  const loadProviders = useCallback(
    () =>
      Promise.all([
        ProjectProviders.get(id),
        ProjectProviders.status(id, "image").catch(() => null),
      ]).then(([providerData, imageStatus]) => {
        const next = { ...providerData };
        if (imageStatus) {
          next.status = { ...(providerData.status || {}), image: imageStatus };
          next.effective = {
            ...(providerData.effective || {}),
            image: {
              ...(providerData.effective?.image || {}),
              provider: imageStatus.selected_provider || imageStatus.provider,
              model: imageStatus.selected_model || imageStatus.model,
              source: imageStatus.source,
              mode: imageStatus.mode,
              status: imageStatus.status,
              would_use_real_provider: imageStatus.would_use_real_provider,
            },
          };
        }
        setProviders(next);
      }),
    [id]
  );
  const loadVoiceRes = useCallback(
    () => ProjectProviders.voiceResolution(id).then(setVoiceRes),
    [id]
  );
  const loadSceneCosts = useCallback(
    ({ trackDelta = false } = {}) => {
      setSceneCosts((p) => ({ ...p, status: "loading" }));
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [id]
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
      loadProviders();
      loadVoiceRes();
      loadSceneCosts({ trackDelta: true });
    },
    [load, loadProviders, loadVoiceRes, loadSceneCosts]
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
            setData={setData}
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
          <VideoSegmentsTab
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
