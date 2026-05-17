import { PlugZap } from "lucide-react";

export function ProviderHintChip({ providers, modality, action, credits, testId }) {
  if (!providers) return null;
  const status = providers.status?.[modality];
  const eff = status
    ? {
        ...(providers.effective?.[modality] || {}),
        provider: status.selected_provider || status.provider,
        model: status.selected_model || status.model,
        source: status.source,
      }
    : providers.effective?.[modality];
  if (!eff) return null;
  const overrideOn = providers.provider_override_enabled;
  const usingProject = overrideOn && eff.source === "project";
  const provider = eff.provider || "—";
  const model = eff.model || eff.custom_model || "—";
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
