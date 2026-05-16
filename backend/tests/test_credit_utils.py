"""Unit tests for MVP credit helper logic."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from credit_utils import wallet_pct, wallet_state  # noqa: E402


def test_wallet_pct_handles_zero_wallet():
    assert wallet_pct(10, 0) == 0.0


def test_wallet_pct_rounds_to_one_decimal():
    assert wallet_pct(1, 3) == 33.3


def test_wallet_state_thresholds():
    assert wallet_state(40.9) == "normal"
    assert wallet_state(41) == "warning"
    assert wallet_state(71) == "high"
    assert wallet_state(100.1) == "insufficient"
