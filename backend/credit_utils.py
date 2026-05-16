"""Side-effect-free helpers for MVP credit guardrails."""


def wallet_state(pct: float) -> str:
    if pct > 100:
        return "insufficient"
    if pct >= 71:
        return "high"
    if pct >= 41:
        return "warning"
    return "normal"


def wallet_pct(total_credits: int, wallet_credits: int) -> float:
    if not wallet_credits:
        return 0.0
    return round((total_credits / wallet_credits) * 100.0, 1)
