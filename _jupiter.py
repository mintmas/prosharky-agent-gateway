"""
Jupiter v6 integrator helpers.

Derives the Associated Token Account (ATA) for our Solana fee wallet
(Hhi4RfSTMhVX2xUGPGKzD14PSRsRQgtozQVw5qjiPQAu) for any SPL mint, so Jupiter
can deposit platform fees into our account.

Jupiter v6 accepts `feeAccount` param on /v6/swap — it must be a token account
for either the input or output mint of the swap. We always use the OUTPUT mint
(user just received those tokens, easiest to route).

Note: ATA creation on-chain costs ~0.00203 SOL (rent-exempt). Until our wallet
is funded + ATAs created on-chain for common mints, Jupiter returns an error
"feeAccount not initialized" and DOES NOT charge the fee. Precompute all ATAs
so the set-up script can batch-create them once wallet is funded.
"""
import os
import functools
from typing import Optional

try:
    from solders.pubkey import Pubkey
    _HAVE_SOLDERS = True
except Exception:
    _HAVE_SOLDERS = False


FEE_OWNER = os.environ.get("FEE_RECIPIENT_SOL", "Hhi4RfSTMhVX2xUGPGKzD14PSRsRQgtozQVw5qjiPQAu")
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ATA_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"

# Common fee-collectable mints on Solana (pre-computed ATAs to skip runtime PDA)
KNOWN_MINTS = {
    "USDC":  "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT":  "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "wSOL":  "So11111111111111111111111111111111111111112",
    "JUP":   "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "BONK":  "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JTO":   "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
    "PYUSD": "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo",
    "mSOL":  "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
}


# Mints that use the Token-2022 extension program (PYUSD is one; more coming).
# Computed via mint account's owner field.
TOKEN_2022_MINTS = {"2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"}  # PYUSD


@functools.lru_cache(maxsize=4096)
def derive_ata(owner: str, mint: str, token_program: str = None) -> Optional[str]:
    """
    Return ATA pubkey (base58) for (owner, mint) under the given token program.

    Returns None if solders lib unavailable.
    """
    if not _HAVE_SOLDERS:
        return None
    try:
        if token_program is None:
            token_program = TOKEN_2022_PROGRAM if mint in TOKEN_2022_MINTS else TOKEN_PROGRAM
        owner_pk = Pubkey.from_string(owner)
        mint_pk = Pubkey.from_string(mint)
        tp_pk = Pubkey.from_string(token_program)
        ata_pk = Pubkey.from_string(ATA_PROGRAM)
        ata, _bump = Pubkey.find_program_address(
            [bytes(owner_pk), bytes(tp_pk), bytes(mint_pk)],
            ata_pk,
        )
        return str(ata)
    except Exception:
        return None


def our_ata_for(mint: str) -> Optional[str]:
    """Shortcut — our fee wallet's ATA for a given mint."""
    return derive_ata(FEE_OWNER, mint)


def known_mint_atas() -> dict:
    """Pre-compute ATAs for all KNOWN_MINTS — used by setup script."""
    out = {}
    for sym, mint in KNOWN_MINTS.items():
        ata = our_ata_for(mint)
        if ata:
            out[sym] = {"mint": mint, "ata": ata}
    return out


if __name__ == "__main__":
    import json
    print(json.dumps({"fee_owner": FEE_OWNER, "atas": known_mint_atas()}, indent=2))
