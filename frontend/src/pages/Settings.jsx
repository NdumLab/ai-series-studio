import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Bot,
  Image as ImageIcon,
  Video,
  Mic2,
  Music2,
  Film,
  CircleDot,
  Save,
  PlugZap,
  ShieldAlert,
  CreditCard,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { apiErrorMessage, Billing, Credits, ProviderSettings } from "../lib/api";

const SECTIONS = [
  {
    key: "llm",
    title: "LLM (Story rewrite)",
    icon: Bot,
    blurb: "Used to rewrite raw ideas into structured episode drafts and split scenes.",
  },
  {
    key: "image",
    title: "Image",
    icon: ImageIcon,
    blurb: "Generates the visual anchor for each scene.",
  },
  {
    key: "video",
    title: "Video",
    icon: Video,
    blurb: "Renders 5-second video segments per scene.",
  },
  {
    key: "voice",
    title: "Voice",
    icon: Mic2,
    blurb: "Narration and character voiceover synthesis.",
  },
  {
    key: "music",
    title: "Music",
    icon: Music2,
    blurb: "Per-scene background music tracks.",
  },
  {
    key: "export",
    title: "Export (FFmpeg)",
    icon: Film,
    blurb: "Stitches approved segments into the final cut.",
  },
];

export default function Settings() {
  const [catalog, setCatalog] = useState(null);
  const [settings, setSettings] = useState(null);
  const [billing, setBilling] = useState(null);
  const [credits, setCredits] = useState(null);
  const [draft, setDraft] = useState({});
  const [checkoutBusy, setCheckoutBusy] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([
      ProviderSettings.options(),
      ProviderSettings.get(),
      Billing.status(),
      Credits.status(),
    ]).then(([opt, s, b, c]) => {
      setCatalog(opt.catalog);
      setSettings(s);
      setBilling(b);
      setCredits(c);
      const d = {};
      for (const k of SECTIONS.map((x) => x.key)) d[k] = { ...s[k] };
      setDraft(d);
    });
  }, []);

  if (!catalog || !settings) {
    return <div className="text-[#A1A1AA] text-sm">Loading provider settings…</div>;
  }

  const patch = (key, field, value) => {
    setDraft((prev) => {
      const next = { ...prev[key], [field]: value };
      // Reset model when provider changes
      if (field === "provider") {
        const provs = catalog[key];
        const p = provs.find((x) => x.id === value);
        next.model = p?.models?.[0] || "";
        if (value !== "custom") {
          next.custom_provider = "";
          next.custom_model = "";
        }
      }
      return { ...prev, [key]: next };
    });
  };

  const dirty = JSON.stringify(draft) !== JSON.stringify(
    SECTIONS.reduce((acc, s) => ({ ...acc, [s.key]: settings[s.key] }), {})
  );

  const save = async () => {
    setSaving(true);
    try {
      const res = await ProviderSettings.update(draft);
      setSettings(res);
      toast.success("Provider settings saved");
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const test = async (key) => {
    try {
      const r = await ProviderSettings.test(key);
      toast(r.message, { icon: "🧪" });
    } catch {
      toast.error("Test failed");
    }
  };

  const buyCredits = async () => {
    setCheckoutBusy(true);
    try {
      const res = await Billing.createCheckoutSession();
      window.location.assign(res.checkout_url);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Stripe test checkout is not configured."));
    } finally {
      setCheckoutBusy(false);
    }
  };

  return (
    <div className="es-fade">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-8 gap-4">
        <div>
          <p className="es-label mb-2">Workspace · Configuration</p>
          <h1 className="font-display text-4xl font-black tracking-tight">
            Provider <span className="text-[#FF3B30]">Settings</span>
          </h1>
          <p className="text-sm text-[#A1A1AA] mt-2 max-w-2xl">
            Pick the provider and model you'll wire up later for each modality.
            Selections are saved to your workspace but are <strong>not used</strong> right now —
            all generation runs through mocks.
          </p>
        </div>
        <Button
          onClick={save}
          disabled={saving || !dirty}
          data-testid="save-settings-btn"
          className="bg-[#FF3B30] hover:bg-[#FF453A] text-white h-11 px-5"
        >
          <Save className="w-4 h-4 mr-2" /> {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}
        </Button>
      </div>

      <MockBanner />
      <KeysBanner />
      {billing && (
        <BillingBanner
          billing={billing}
          credits={credits}
          busy={checkoutBusy}
          onBuy={buyCredits}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6" data-testid="provider-grid">
        {SECTIONS.map((sec) => (
          <ProviderCard
            key={sec.key}
            section={sec}
            providers={catalog[sec.key]}
            value={draft[sec.key]}
            onChange={(field, v) => patch(sec.key, field, v)}
            onTest={() => test(sec.key)}
          />
        ))}
      </div>
    </div>
  );
}

function BillingBanner({ billing, credits, busy, onBuy }) {
  return (
    <div
      data-testid="billing-status-banner"
      className="es-card p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4 mt-3 border-white/10"
    >
      <div className="flex items-start gap-3">
        <CreditCard className="w-5 h-5 text-[#A1A1AA] mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-white">
            Stripe test checkout {billing.checkout_enabled ? "configured" : "disabled"}
          </p>
          <p className="text-xs text-[#A1A1AA] mt-1">
            {billing.message} Live payments are disabled; only server-side test-mode
            environment variables are recognized.
          </p>
          <p className="text-xs text-[#A1A1AA] mt-2 font-mono">
            Wallet: {credits?.credits_available ?? "—"} credits · Pack: {billing.credit_pack_credits ?? 500} test credits
          </p>
          {billing.missing_config?.length > 0 && (
            <p className="text-[11px] text-[#FFCC00] mt-1 font-mono">
              Missing: {billing.missing_config.join(", ")}
            </p>
          )}
        </div>
      </div>
      <Button
        type="button"
        onClick={onBuy}
        disabled={busy}
        data-testid="buy-test-credits-btn"
        className="bg-[#FF3B30] hover:bg-[#FF453A] text-white"
      >
        <CreditCard className="w-4 h-4 mr-2" />
        {busy ? "Opening..." : "Buy test credits"}
      </Button>
    </div>
  );
}

function MockBanner() {
  return (
    <div
      data-testid="mock-mode-banner"
      className="es-card p-4 flex items-start gap-3 border-[#FFCC00]/30 bg-[#FFCC00]/5"
    >
      <CircleDot className="w-5 h-5 text-[#FFCC00] mt-0.5" />
      <div>
        <p className="text-sm font-semibold text-[#FFCC00]">
          Mock mode active — no real provider calls are made
        </p>
        <p className="text-xs text-[#A1A1AA] mt-1">
          Save your provider preferences here so the real pipeline can read them once
          you wire up the integrations. Until then every "generate" button runs against
          the built-in mock generators.
        </p>
      </div>
    </div>
  );
}

function KeysBanner() {
  return (
    <div
      data-testid="keys-disabled-banner"
      className="es-card p-4 flex items-start gap-3 mt-3 border-white/10"
    >
      <ShieldAlert className="w-5 h-5 text-[#A1A1AA] mt-0.5" />
      <div>
        <p className="text-sm font-semibold text-white">
          API keys are intentionally disabled
        </p>
        <p className="text-xs text-[#A1A1AA] mt-1">
          We only persist <em>provider</em> and <em>model</em> selection. Key inputs will
          be added when the corresponding provider goes live, so nothing sensitive is
          stored prematurely.
        </p>
      </div>
    </div>
  );
}

function ProviderCard({ section, providers, value, onChange, onTest }) {
  if (!value) return null;
  const Icon = section.icon;
  const isCustom = value.provider === "custom";
  const selected = providers.find((p) => p.id === value.provider);
  const hasPresetModels = selected && selected.models && selected.models.length > 0;

  return (
    <div className="es-card p-5" data-testid={`provider-card-${section.key}`}>
      <div className="flex items-start justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-md bg-white/5 border border-white/10 flex items-center justify-center">
            <Icon className="w-4 h-4 text-[#FF3B30]" />
          </span>
          <h3 className="font-display text-lg font-bold">{section.title}</h3>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onTest}
          data-testid={`test-${section.key}-btn`}
          className="border-white/15 bg-transparent text-white hover:bg-white/10 hover:text-white h-8"
        >
          <PlugZap className="w-3.5 h-3.5 mr-1.5" /> Test connection
        </Button>
      </div>
      <p className="text-xs text-[#A1A1AA] mb-4">{section.blurb}</p>

      <div className="space-y-3">
        <div>
          <label className="es-label block mb-1.5">Provider</label>
          <Select
            value={value.provider}
            onValueChange={(v) => onChange("provider", v)}
          >
            <SelectTrigger
              className="bg-[#0A0A0A] border-white/10 text-white"
              data-testid={`provider-select-${section.key}`}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#121212] border-white/10 text-white">
              {providers.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {isCustom ? (
          <>
            <div>
              <label className="es-label block mb-1.5">Custom provider ID</label>
              <Input
                value={value.custom_provider}
                onChange={(e) => onChange("custom_provider", e.target.value)}
                placeholder="e.g. my-internal-image-svc"
                data-testid={`custom-provider-${section.key}`}
                className="bg-[#0A0A0A] border-white/10 text-white"
              />
            </div>
            <div>
              <label className="es-label block mb-1.5">Custom model ID</label>
              <Input
                value={value.custom_model}
                onChange={(e) => onChange("custom_model", e.target.value)}
                placeholder="e.g. flux-pro-finetune-001"
                data-testid={`custom-model-${section.key}`}
                className="bg-[#0A0A0A] border-white/10 text-white"
              />
            </div>
          </>
        ) : hasPresetModels ? (
          <div>
            <label className="es-label block mb-1.5">Model</label>
            <Select
              value={value.model}
              onValueChange={(v) => onChange("model", v)}
            >
              <SelectTrigger
                className="bg-[#0A0A0A] border-white/10 text-white"
                data-testid={`model-select-${section.key}`}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#121212] border-white/10 text-white">
                {selected.models.map((m) => (
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
