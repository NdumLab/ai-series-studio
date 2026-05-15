import { Coins } from "lucide-react";
import { WALLET_STATE_COLOR } from "./constants";
import { WalletRing } from "./WalletRing";

export function CostBadge({ sceneCosts, delta }) {
  let body;
  let ring = null;
  if (sceneCosts.status === "loading" && !sceneCosts.data) {
    body = (
      <div
        className="font-display text-lg font-bold text-[#A1A1AA]"
        data-testid="cost-badge-loading"
      >
        Calculating…
      </div>
    );
  } else if (sceneCosts.status === "error") {
    body = (
      <div
        className="font-display text-sm font-semibold text-[#A1A1AA]"
        data-testid="cost-badge-error"
      >
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
    <div
      className="es-card px-4 py-2.5 inline-flex items-center gap-3"
      data-testid="cost-estimate"
    >
      <Coins className="w-4 h-4 text-[#FFCC00]" />
      <div>
        <div className="es-label">Project scene cost</div>
        {body}
      </div>
      {ring}
    </div>
  );
}
