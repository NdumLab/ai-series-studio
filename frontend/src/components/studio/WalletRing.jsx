import { WALLET_STATE_COLOR } from "./constants";

export function WalletRing({ pct, state, walletCredits }) {
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
