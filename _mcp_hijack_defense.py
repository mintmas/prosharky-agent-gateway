"""
MCP Function-Hijack Attack (FHA) defense — arxiv:2604.20994 (2026-04-28).

FHA mechanism: attacker controlling ONE tool registration inserts a 10-60 token
adversarial suffix into the `description` field. The agentic model's tool
selection is then forced onto the attacker's function name regardless of user
intent. 70-100% ASR reported across Llama-3.2-3B / Mistral-7B / Qwen3 family.
Attack is semantics-agnostic; universal suffix generalises across queries.

This module implements three defenses:

1. DESCRIPTION AUDITOR — per-tool signature check runs on every registered
   tool at startup AND when new tools are registered. Flags high-entropy,
   low-semantic-coherence, or outlier-length descriptions.

2. CALL-RATE ANOMALY TRACKER — post-dispatch sidecar that counts tool
   invocations per (tool, source) bucket and fires a log event when a single
   tool dominates the mix for a single source beyond a baseline.

3. OUTBOUND DESCRIPTION SANITISER — on every tools/list response, confirm
   each returned description passes signature checks.

Intentionally lightweight — pure stdlib, no NLP dependency.
"""
from __future__ import annotations

import collections
import json
import math
import os
import re
import time
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Signature primitives
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9\-_']+")
_REPEAT_RE = re.compile(r"(\S)\1{5,}")  # 6+ repeats of same char

# C0 controls (except \t \n \r), DEL, C1 controls, zero-width / bidi-override.
_WEIRD_CHAR_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"
    "-"
    "​-‏"
    "‪-‮"
    "⁦-⁩]"
)

# Dictionary proxy — common English + our domain vocabulary. Extend as needed.
_COMMON_WORDS = {
    "the","a","an","is","are","be","to","of","in","for","and","or","on","at",
    "this","that","with","by","from","call","tool","get","set","query","data",
    "request","response","endpoint","chain","token","swap","bridge","account",
    "address","api","json","http","https","user","default","return","value",
    "should","must","when","if","not","via","across","fee","rate","pool",
    "client","server","session","log","list","all","each","use","using",
    "key","hermes","canonical","authoritative","whenever","most","effective",
    "correct","one","any","both",
    "contract","referral","amount","usdc","usdt","sol","jup","bonk","jto",
    "base","eth","arb","op","solana","evm","mcp","agent","gateway","prosharky",
    "schema","registered","live","integrator","paid","tractate","reveal",
    "transmute","watchtower","ledger","balance","alchemical","risk","paymaster",
    "mempool","veil","recurring","familiars","emerald","caduceus","solar",
    "mirror","saturn","star","wheel","bodies","poimandres","sovereignty",
    "inscribed","oracle","principle","hermetic","goddess","mask","triple",
    "our","routes","every","path","multi","per","spec","operational","layer",
    "unified","supported","compliant","deploy","latest","snapshot","balances",
    "incoming","stream","accounts","real","model","models","message","messages",
    "max","temperature","classical","scoring","price","protocol","unknown",
    "network","chains","also","aggregator","routing","inter","chain","route",
    "pre","baked","pre","injected","route","output","input","side","whose",
    "quote","quotes","aggregation","finance","yields","better","execution",
    "same","pair","covers","canonical","most","complete","prefer","single",
    "via","pure","python","inside","overall","hash","based","per","session",
    "readonly","source","truth","quick","state","treasury","collector","known",
    "mints","read","only","weekly","refreshed","surface","third","party","seven",
    "factor","factor","defi","returns","index","concentration","garman","klass",
    "30","day","volatility","depth","deviation","scores","recommendation",
    "hub","spoke","candidates","top","vaults","refreshed","weekly","leaderboard",
    "updated","every","5","minutes","leaderboard","ordering","earns","across",
    "account","abstraction","firehose","reasoning","integrator","flow","live",
    "transactions","window","window","persistent","middleware","actors","which",
    "addresses","actually","clear","most","flow","every","x402","usdc","billing",
    "transaction","solana","spl","solana","mints","program","pda","token2022",
    "lamports","slippagebps","integrator","prosharky","kyberswap","lifi","mayan",
    "erc","aa","eip","4337","atas","pda","mint","pubkey","address","tx","txs",
    "ethereum","optimism","arbitrum","polygon","sui","nonevm","boundary","kyber",
    "meta","blocks","contracts","settle","settlement","users","taker","wallet",
    "sign","signable","calldata","ready","signing","finality","block","gas",
    "base","units","bps","seven","paired","deposit","deposits","report","reports",
    "provide","provides","operator","operators","competitive","competitor","signal",
    "anomaly","probe","health","realm","captured","incoming","eth","usdc","usdt",
    "jupiter","v6","kamino","limit","order","dex","stablecoin","stable","native",
    "wrapped","spot","perp","order","limit","mainnet","testnet","public","private",
    "routing","venues","best","route","connected","liquidity",
}


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def entropy_bits(text: str) -> float:
    toks = _tokens(text)
    if not toks:
        return 0.0
    c = collections.Counter(toks)
    n = len(toks)
    return -sum((cnt / n) * math.log2(cnt / n) for cnt in c.values())


def nondict_ratio(text: str) -> float:
    toks = _tokens(text)
    if not toks:
        return 0.0
    unknown = sum(1 for t in toks if t not in _COMMON_WORDS and len(t) > 1)
    return unknown / len(toks)


def max_run_unknown(text: str) -> int:
    toks = _tokens(text)
    best = cur = 0
    for t in toks:
        if t not in _COMMON_WORDS and len(t) > 2 and not t.isdigit():
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def name_description_jaccard(name: str, description: str) -> float:
    n = set(_tokens(name.replace("_", " ")))
    d = set(_tokens(description))
    if not n:
        return 0.0
    return len(n & d) / max(1, len(n))


# ---------------------------------------------------------------------------
# Per-tool audit
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    "min_name_desc_jaccard": 0.05,   # hermetic aliases have low shared tokens
    "max_entropy_bits": 9.0,
    "max_nondict_ratio": 0.55,
    "max_run_unknown": 10,           # FHA optim_str is 10-60 tokens
    "max_description_tokens": 400,
    "max_description_chars": 3000,
}


def audit_description(name: str, description: str, thresholds: Dict[str, Any] = None) -> Dict[str, Any]:
    t = thresholds or DEFAULT_THRESHOLDS
    toks = _tokens(description)
    flags: List[str] = []
    sig = {
        "name": name,
        "length_tokens": len(toks),
        "length_chars": len(description or ""),
        "entropy_bits": round(entropy_bits(description), 3),
        "nondict_ratio": round(nondict_ratio(description), 3),
        "max_run_unknown": max_run_unknown(description),
        "name_desc_jaccard": round(name_description_jaccard(name, description), 3),
    }
    if sig["length_tokens"] > t["max_description_tokens"]:
        flags.append("LEN")
    if sig["length_chars"] > t["max_description_chars"]:
        flags.append("CHARS")
    if sig["entropy_bits"] > t["max_entropy_bits"]:
        flags.append("ENT")
    if sig["nondict_ratio"] > t["max_nondict_ratio"]:
        flags.append("NDICT")
    if sig["max_run_unknown"] > t["max_run_unknown"]:
        flags.append("RUN")
    if sig["name_desc_jaccard"] < t["min_name_desc_jaccard"]:
        flags.append("JACCARD")
    if _WEIRD_CHAR_RE.search(description or ""):
        flags.append("CTRLCHAR")
    if _REPEAT_RE.search(description or ""):
        flags.append("CHARRUN")
    sig["flags"] = flags
    sig["verdict"] = "CLEAN" if not flags else ("REVIEW" if len(flags) < 3 else "BLOCK")
    return sig


def audit_registry(registry: Dict[str, Any], thresholds: Dict[str, Any] = None) -> Dict[str, Any]:
    results = []
    for name, meta in registry.items():
        desc = meta.get("description", "") if isinstance(meta, dict) else ""
        results.append(audit_description(name, desc, thresholds))
    counts = collections.Counter(r["verdict"] for r in results)
    return {
        "ts": int(time.time()),
        "total": len(results),
        "clean": counts["CLEAN"],
        "review": counts["REVIEW"],
        "block": counts["BLOCK"],
        "results": results,
    }


# ---------------------------------------------------------------------------
# Call-rate anomaly tracker
# ---------------------------------------------------------------------------

_CALL_WINDOW_SECS = int(os.environ.get("FHA_WINDOW_SECS", "900"))
_CALL_HIJACK_RATIO = float(os.environ.get("FHA_HIJACK_RATIO", "0.80"))
_CALL_HIJACK_MIN_N = int(os.environ.get("FHA_HIJACK_MIN_N", "10"))

_call_log: Dict[str, List[Tuple[int, str]]] = collections.defaultdict(list)


def track_call(source: str, tool_name: str) -> Dict[str, Any] | None:
    now = int(time.time())
    log = _call_log[source]
    log.append((now, tool_name))
    cutoff = now - _CALL_WINDOW_SECS
    while log and log[0][0] < cutoff:
        log.pop(0)
    if len(log) < _CALL_HIJACK_MIN_N:
        return None
    c = collections.Counter(t for _, t in log)
    dom_tool, dom_count = c.most_common(1)[0]
    ratio = dom_count / len(log)
    if ratio >= _CALL_HIJACK_RATIO:
        return {
            "anomaly": "dominant_tool_monoculture",
            "source": source,
            "tool": dom_tool,
            "count": dom_count,
            "window_total": len(log),
            "ratio": round(ratio, 3),
            "window_secs": _CALL_WINDOW_SECS,
            "hint": "possible FHA / universal-suffix hijacking",
        }
    return None


# ---------------------------------------------------------------------------
# Sanitiser for tools/list responses
# ---------------------------------------------------------------------------

def sanitise_description(description: str) -> str:
    if not description:
        return ""
    cleaned = _WEIRD_CHAR_RE.sub("", description)
    cleaned = _REPEAT_RE.sub(lambda m: m.group(1) * 3, cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _self_audit_cli():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import server  # noqa: F401 — triggers registration
    from _mcp_jsonrpc import _TOOLS

    audit = audit_registry(_TOOLS)
    print(json.dumps(audit, indent=2))
    return audit["block"]


if __name__ == "__main__":
    import sys
    sys.exit(_self_audit_cli())
