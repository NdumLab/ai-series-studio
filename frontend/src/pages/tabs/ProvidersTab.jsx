import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Settings as SettingsIcon,
  PlugZap,
  KeyRound,
  Info,
  Save,
} from "lucide-react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { PROVIDER_SECTIONS } from "../../components/studio/constants";
import { ProjectProviders, ProviderSettings } from "../../lib/api";

export function ProvidersTab({ projectId, onChanged }) {
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
      <LLMModeBanner flags={data.feature_flags} />
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
              When override is on, this project saves its own provider selections. When
              off, the workspace defaults are used.
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
            <Save className="w-4 h-4 mr-2" />{" "}
            {saving ? "Saving…" : "Save project providers"}
          </Button>
        </div>
      )}
    </div>
  );
}

function LLMModeBanner({ flags }) {
  const enabled = !!flags?.llm;
  return (
    <div
      data-testid="llm-mode-banner"
      data-active={enabled}
      className={`es-card p-4 flex items-start gap-3 ${
        enabled
          ? "border-[#34C759]/40 bg-[#34C759]/5"
          : "border-white/10 bg-white/[0.02]"
      }`}
    >
      <PlugZap
        className="w-5 h-5 mt-0.5 shrink-0"
        style={{ color: enabled ? "#34C759" : "#A1A1AA" }}
      />
      <div className="flex-1">
        <p
          className="text-sm font-semibold"
          style={{ color: enabled ? "#34C759" : "white" }}
        >
          {enabled ? "Real LLM enabled" : "Mock LLM active"}
        </p>
        <p className="text-xs text-[#A1A1AA] mt-1">
          {enabled
            ? "Story rewrite, improve-story, and prompt enhancements use the configured server-side real LLM runtime. If the real call fails or times out, the mock fallback runs so workflows never break."
            : "Story rewrite, improve-story, and prompt enhancements run through the deterministic mock. Image, video, voice, music, and export remain mock-only regardless."}
        </p>
      </div>
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
    <div
      className="grid grid-cols-1 md:grid-cols-2 gap-4"
      data-testid="effective-global-grid"
    >
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
            </dl>
            <GuardStateRows modality={sec.key} effective={eff} variant="eff" />
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
          <Select
            value={providerValue || ""}
            onValueChange={(v) => onChange("provider", v)}
          >
            <SelectTrigger
              className="bg-[#0A0A0A] border-white/10 text-white"
              data-testid={`project-provider-select-${sec.key}`}
            >
              <SelectValue placeholder="— use global —" />
            </SelectTrigger>
            <SelectContent className="bg-[#121212] border-white/10 text-white">
              {providers.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.label}
                </SelectItem>
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
              placeholder={
                sec.key === "export"
                  ? "e.g. internal-stitch-worker"
                  : "e.g. flux-pro-finetune-001"
              }
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
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        <GuardStateRows modality={sec.key} effective={effective} variant="project" />
      </div>
    </div>
  );
}

function GuardStateRows({ modality, effective, variant = "global" }) {
  const sourceLabel =
    effective?.source === "project"
      ? "Project override"
      : effective?.source === "global-fallback"
        ? "Fallback to global"
        : effective?.source === "hard-fallback"
          ? "Fallback mock"
          : "Global default";
  const tid = (suffix) => `${variant}-${suffix}-${modality}`;
  const realCapable = modality === "llm";
  return (
    <dl
      data-testid={tid("guard-state")}
      className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] font-mono border-t border-white/5 pt-3"
    >
      <dt className="text-[#A1A1AA]">Source</dt>
      <dd className="text-right text-[#A1A1AA]" data-testid={tid("source")}>
        {sourceLabel}
      </dd>
      <dt className="text-[#A1A1AA]">Mode</dt>
      <dd className="text-right text-[#FFCC00]" data-testid={tid("mode")}>
        Mock
      </dd>
      <dt className="text-[#A1A1AA]">Feature flag</dt>
      <dd className="text-right text-[#A1A1AA]" data-testid={tid("flag")}>
        disabled
      </dd>
      <dt className="text-[#A1A1AA]">Key status</dt>
      <dd className="text-right text-[#A1A1AA]" data-testid={tid("key")}>
        {realCapable ? "configured" : "not configured"}
      </dd>
      <dt className="text-[#A1A1AA]">Real call</dt>
      <dd
        className="text-right"
        style={{ color: realCapable ? "#FFCC00" : "#34C759" }}
        data-testid={tid("real-call")}
      >
        {realCapable ? "real-capable · flag off" : "blocked · mock-only"}
      </dd>
    </dl>
  );
}
