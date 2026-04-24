"""
Jupiter Referral Program — our referral token accounts.

When a caller builds a /v6/swap TX and includes `feeAccount` referencing one of
these referralTokenAccount pubkeys, Jupiter's on-chain swap program deposits the
platformFeeBps into our account instead of going to the raw-ATA path.

Why it matters:
- platformFeeBps=50 (raw ATA) gives us 50 bps of the output swap, keeps the
  whole 50 bps, but Jupiter clients are not guaranteed to honour it (off-chain
  quote-only; Jupiter UI strips it).
- Referral Program route is ENFORCED at the Jupiter Swap program contract:
  referralTokenAccount MUST be a valid referral under a registered project.
  Jupiter takes a 20% cut, we keep 80% (i.e. 50 bps asked → 40 bps net).
  In return, we show up in Jupiter referral dashboard + anti-rug guarantee.

Referral account (partner=Hhi4...): Cg4qcxPBgN4zXD5XvNQiPMwHvikT7dQSrJXkeQDTuThM
Project (Jupiter Swap):              45ruCyfdRkWpRNGEqWzjCiXRHkZs8WXCLQ67Pnpye7Hp
Program:                             REFER4ZgmyYx9c6He5XfaTMiGfdLwRnkV4RPp9t9iF3

Initialized 2026-04-24 01:00 UTC via /opt/jupiter_referral/init_referral.ts.
"""
import os
import json
from typing import Optional


REFERRAL_ACCOUNT = "Cg4qcxPBgN4zXD5XvNQiPMwHvikT7dQSrJXkeQDTuThM"
REFERRAL_PROJECT = "45ruCyfdRkWpRNGEqWzjCiXRHkZs8WXCLQ67Pnpye7Hp"
REFERRAL_PROGRAM = "REFER4ZgmyYx9c6He5XfaTMiGfdLwRnkV4RPp9t9iF3"
REFERRAL_NAME    = "prosharky-gw"


# mint → referralTokenAccount pubkey (loaded from state file at import)
_REFERRAL_TA_BY_MINT: dict = {}


def _load_state() -> None:
    path = os.environ.get("JUPITER_REFERRAL_STATE", "/opt/jupiter_referral/referral_state.json")
    try:
        with open(path) as f:
            state = json.load(f)
        for sym, obj in (state.get("token_accounts") or {}).items():
            mint = obj.get("mint")
            ta = obj.get("referralTokenAccount")
            if mint and ta:
                _REFERRAL_TA_BY_MINT[mint] = ta
    except Exception:
        pass


_load_state()


def referral_ta_for(mint: str) -> Optional[str]:
    """Return our referralTokenAccount pubkey for the given mint, or None if
    we don't have one registered yet."""
    return _REFERRAL_TA_BY_MINT.get(mint)


def known_referral_tokens() -> dict:
    """All mints that have live referralTokenAccounts."""
    return dict(_REFERRAL_TA_BY_MINT)


def referral_context() -> dict:
    """Metadata for llms.txt / MCP manifest."""
    return {
        "program": REFERRAL_PROGRAM,
        "project": REFERRAL_PROJECT,
        "referralAccount": REFERRAL_ACCOUNT,
        "name": REFERRAL_NAME,
        "registered_mints": list(_REFERRAL_TA_BY_MINT.keys()),
    }
