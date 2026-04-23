#!/usr/bin/env python3
"""
Prosharky Agent Gateway — wraps LiteLLM + integrator APIs so every downstream
call routes through our registered integrator IDs and accrues fees to our
feeRecipient. Also exposes Wave-17 swarm data (middleware flow, paymaster
revenue leaderboard, recurring bots) as paid x402 endpoints.

Run: uvicorn server:app --host 0.0.0.0 --port 4080

Endpoints:
  /v1/chat/completions    — LiteLLM pass-through (free tier, small markup later)
  /v1/swap/quote          — 0x swap quote w/ our swapFeeBps=50 pre-baked
  /v1/bridge/quote        — LI.FI bridge quote w/ integrator=prosharky
  /v1/mayan/quote         — Mayan cross-chain swap quote w/ referrerBps=50
  /v1/kyber/quote         — KyberSwap aggregator route w/ feeReceiver
  /v1/relay/quote         — Relay bridge+swap quote w/ appFees=50 bps
  /v1/paymaster/top       — [PAID $0.05] top ERC-4337 paymasters by revenue
  /v1/mempool/middleware  — [PAID $0.02] live middleware tx stream
  /v1/recurring_bots      — [PAID $0.10] recurring bot leaderboard, 24h
  /llms.txt               — agent discovery
  /.well-known/x402       — x402 facilitator discovery
  /mcp/manifest           — MCP tool manifest
"""

import os
import json
import sqlite3
import time
from typing import Optional, Any, Dict
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, PlainTextResponse, Response

# ---------------------------------------------------------------------------
# CONFIG — integrator IDs (loaded from env, defaults from Triple Arbiter)
# ---------------------------------------------------------------------------
LITELLM_URL        = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000")
LITELLM_KEY        = os.environ.get("LITELLM_KEY", "sk-prosharky-402520998c5a42a95a492e66040d49f82da2d25b151b3726")
FEE_RECIPIENT_EVM  = os.environ.get("FEE_RECIPIENT_EVM", "0x5f9B8f3BD13e5320eF5EFAEa906442Fb9B64802c")
FEE_RECIPIENT_SOL  = os.environ.get("FEE_RECIPIENT_SOL", "Hhi4RfSTMhVX2xUGPGKzD14PSRsRQgtozQVw5qjiPQAu")
ZEROX_API_KEY      = os.environ.get("ZEROX_API_KEY", "e8bebb55-6f9d-4b68-a4ad-bcb30dfabf99")
LIFI_INTEGRATOR    = os.environ.get("LIFI_INTEGRATOR", "prosharky")
RANGO_AFFILIATE    = os.environ.get("RANGO_AFFILIATE_REF", "prosharky")
SWAP_FEE_BPS       = int(os.environ.get("SWAP_FEE_BPS", "50"))
BRIDGE_FEE_BPS     = int(os.environ.get("BRIDGE_FEE_BPS", "50"))
MAYAN_REFERRER_BPS = int(os.environ.get("MAYAN_REFERRER_BPS", "50"))
KYBER_FEE_BPS      = int(os.environ.get("KYBER_FEE_BPS", "50"))
RELAY_APP_FEE_BPS  = int(os.environ.get("RELAY_APP_FEE_BPS", "50"))
FINDINGS_DB        = os.environ.get("FINDINGS_DB", "/opt/wave17_swarm/findings.db")

# x402 facilitator (our own)
X402_FACILITATOR   = os.environ.get("X402_FACILITATOR", "https://mardi-worldwide-sacred-model.trycloudflare.com")

# Public domain for llms.txt + MCP discovery
PUBLIC_URL         = os.environ.get("PUBLIC_URL", "http://173.249.14.219:4080")

# Per-endpoint pricing (USDC)
PRICING = {
    "/v1/paymaster/top":     0.05,
    "/v1/mempool/middleware": 0.02,
    "/v1/recurring_bots":    0.10,
    "/v1/middleware/analyze": 0.05,
}

app = FastAPI(title="Prosharky Agent Gateway", version="0.1")

# Load insider_worker functions once at startup (avoid subprocess cold-start per request)
import sys as _sys
_sys.path.insert(0, "/opt/wave17_swarm")
try:
    import insider_worker as _iw  # type: ignore
except Exception as _e:
    _iw = None
    print(f"[warn] insider_worker not loadable: {_e}")

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _x402_challenge(path: str) -> JSONResponse:
    """Return HTTP 402 with x402 payment challenge for gated endpoints."""
    price = PRICING.get(path, 0.05)
    return JSONResponse(
        status_code=402,
        headers={
            "WWW-Authenticate": "x402",
            "Payment-Required": f'network="base",asset="USDC",amount="{price}",recipient="{FEE_RECIPIENT_EVM}"',
        },
        content={
            "error": "payment_required",
            "path": path,
            "price_usdc": price,
            "network": "base",
            "asset": "USDC",
            "recipient": FEE_RECIPIENT_EVM,
            "facilitator": X402_FACILITATOR,
            "docs": f"{PUBLIC_URL}/llms.txt",
        },
    )


def _check_payment(x_payment: Optional[str]) -> bool:
    """
    Minimal x402 payment verification.
    For MVP: accept presence of X-Payment header. Real facilitator integration
    swap this for an actual settle() call. This unblocks agents that pass the
    header with any signed attestation; we audit-log them and settle async.
    """
    return bool(x_payment and len(x_payment) > 20)


def _audit_log(path: str, payment_ref: str, body_preview: str) -> None:
    try:
        conn = sqlite3.connect(FINDINGS_DB)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS gateway_calls (ts INTEGER, path TEXT, payment_ref TEXT, body TEXT)"
        )
        conn.execute(
            "INSERT INTO gateway_calls(ts,path,payment_ref,body) VALUES(?,?,?,?)",
            (int(time.time()), path, payment_ref[:120], body_preview[:1000]),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# FREE: LiteLLM pass-through
# ---------------------------------------------------------------------------
@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.body()
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            content=body,
            headers={
                "Authorization": f"Bearer {LITELLM_KEY}",
                "Content-Type": "application/json",
            },
        )
    return Response(content=r.content, status_code=r.status_code, media_type="application/json")


@app.get("/v1/models")
async def models():
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{LITELLM_URL}/v1/models",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        )
    return Response(content=r.content, status_code=r.status_code, media_type="application/json")


# ---------------------------------------------------------------------------
# FREE: 0x swap quote — OUR swapFeeBps/feeRecipient pre-injected
# ---------------------------------------------------------------------------
@app.get("/v1/swap/quote")
async def swap_quote(
    chainId: int = 8453,
    sellToken: str = "",
    buyToken: str = "",
    sellAmount: Optional[str] = None,
    buyAmount: Optional[str] = None,
    taker: str = "",
):
    """
    0x swap quote with our swapFeeBps=50 and swapFeeRecipient pre-baked.
    Every call generates 50 bps fee to us on any executed swap.
    """
    if not (sellToken and buyToken and taker):
        raise HTTPException(status_code=400, detail="sellToken/buyToken/taker required")

    params = {
        "chainId": chainId,
        "sellToken": sellToken,
        "buyToken": buyToken,
        "taker": taker,
        "swapFeeBps": SWAP_FEE_BPS,
        "swapFeeRecipient": FEE_RECIPIENT_EVM,
        "swapFeeToken": buyToken,  # take fee in output token
    }
    if sellAmount:
        params["sellAmount"] = sellAmount
    if buyAmount:
        params["buyAmount"] = buyAmount

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            "https://api.0x.org/swap/allowance-holder/quote",
            params=params,
            headers={"0x-api-key": ZEROX_API_KEY, "0x-version": "v2"},
        )
    data = r.json() if r.status_code == 200 else {"error": r.text}
    data["_prosharky"] = {
        "feeBps": SWAP_FEE_BPS,
        "feeRecipient": FEE_RECIPIENT_EVM,
        "integrator": "prosharky",
    }
    return data


# ---------------------------------------------------------------------------
# FREE: LI.FI bridge quote — integrator=prosharky pre-injected
# ---------------------------------------------------------------------------
@app.get("/v1/bridge/quote")
async def bridge_quote(
    fromChain: int = 1,
    toChain: int = 8453,
    fromToken: str = "",
    toToken: str = "",
    fromAmount: str = "",
    fromAddress: str = "",
    toAddress: str = "",
):
    if not (fromToken and toToken and fromAmount and fromAddress):
        raise HTTPException(status_code=400, detail="fromToken/toToken/fromAmount/fromAddress required")

    params = {
        "fromChain": fromChain,
        "toChain": toChain,
        "fromToken": fromToken,
        "toToken": toToken,
        "fromAmount": fromAmount,
        "fromAddress": fromAddress,
        "toAddress": toAddress or fromAddress,
        "integrator": LIFI_INTEGRATOR,
        "fee": BRIDGE_FEE_BPS / 10000,   # LI.FI fee is fraction (0.005 = 50bps)
        "referrer": FEE_RECIPIENT_EVM,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get("https://li.quest/v1/quote", params=params)
    data = r.json() if r.status_code == 200 else {"error": r.text}
    data["_prosharky"] = {
        "feeBps": BRIDGE_FEE_BPS,
        "integrator": LIFI_INTEGRATOR,
        "referrer": FEE_RECIPIENT_EVM,
    }
    return data


# ---------------------------------------------------------------------------
# FREE: Mayan Finance cross-chain swap — referrer + referrerBps pre-injected
# ---------------------------------------------------------------------------
@app.get("/v1/mayan/quote")
async def mayan_quote(
    fromChain: str = "ethereum",
    toChain: str = "solana",
    fromToken: str = "",
    toToken: str = "",
    amount: str = "",
    slippageBps: int = 300,
):
    """
    Mayan Finance cross-chain quote (EVM<->SOL<->SUI etc).
    referrerBps + referrer forcibly set -> fee accrues to our collector on each fill.
    No registration required, parameter-only integration.
    """
    if not (fromToken and toToken and amount):
        raise HTTPException(status_code=400, detail="fromToken/toToken/amount required")

    # Mayan wants amountIn as NUMBER (float), not string and not wei.
    try:
        amount_num = float(amount)
    except Exception:
        raise HTTPException(status_code=400, detail="amount must be numeric (human units, not wei)")

    params = {
        "fromChain": fromChain,
        "toChain": toChain,
        "fromToken": fromToken,
        "toToken": toToken,
        "amountIn": amount_num,
        "slippageBps": slippageBps,
        "referrer": FEE_RECIPIENT_EVM,
        "referrerBps": MAYAN_REFERRER_BPS,
        "solanaReferrerAddress": FEE_RECIPIENT_SOL,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get("https://price-api.mayan.finance/v3/quote", params=params)
    try:
        data = r.json()
    except Exception:
        data = {"error": r.text[:500], "status": r.status_code}
    if isinstance(data, dict):
        data["_prosharky"] = {
            "referrerBps": MAYAN_REFERRER_BPS,
            "referrer_evm": FEE_RECIPIENT_EVM,
            "referrer_sol": FEE_RECIPIENT_SOL,
        }
    return data


# ---------------------------------------------------------------------------
# FREE: KyberSwap aggregator route — feeReceiver + chargeFeeBy + feeAmount pre-injected
# ---------------------------------------------------------------------------
_KYBER_CHAIN_MAP = {
    1: "ethereum", 8453: "base", 42161: "arbitrum", 10: "optimism",
    137: "polygon", 56: "bsc", 43114: "avalanche", 250: "fantom",
    324: "zksync", 59144: "linea", 534352: "scroll", 5000: "mantle",
    81457: "blast", 1101: "polygon-zkevm",
}


@app.get("/v1/kyber/quote")
async def kyber_quote(
    chainId: int = 8453,
    tokenIn: str = "",
    tokenOut: str = "",
    amountIn: str = "",
):
    """
    KyberSwap aggregator route with our feeReceiver + 50 bps chargeFeeBy=currency_out.
    feeAmount is bps here (KyberSwap accepts bps when isInBps=true).
    """
    if not (tokenIn and tokenOut and amountIn):
        raise HTTPException(status_code=400, detail="tokenIn/tokenOut/amountIn required")
    chain_slug = _KYBER_CHAIN_MAP.get(chainId, "base")

    params = {
        "tokenIn": tokenIn,
        "tokenOut": tokenOut,
        "amountIn": amountIn,
        "feeAmount": KYBER_FEE_BPS,
        "chargeFeeBy": "currency_out",
        "feeReceiver": FEE_RECIPIENT_EVM,
        "isInBps": "true",
        "source": "prosharky",
    }
    url = f"https://aggregator-api.kyberswap.com/{chain_slug}/api/v1/routes"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params,
                             headers={"x-client-id": "prosharky"})
    try:
        data = r.json()
    except Exception:
        data = {"error": r.text[:500], "status": r.status_code}
    if isinstance(data, dict):
        data["_prosharky"] = {
            "feeBps": KYBER_FEE_BPS,
            "feeReceiver": FEE_RECIPIENT_EVM,
            "chargeFeeBy": "currency_out",
            "chain": chain_slug,
        }
    return data


# ---------------------------------------------------------------------------
# FREE: Relay bridge+swap quote — appFees pre-injected
# ---------------------------------------------------------------------------
@app.post("/v1/relay/quote")
async def relay_quote(request: Request):
    """
    Relay bridge/swap quote with appFees forcibly set to our collector at 50 bps.
    Relay accepts appFees: [{recipient, fee_bps}] — we pre-inject ours regardless of caller body.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Force-inject our fee
    body["appFees"] = [{
        "recipient": FEE_RECIPIENT_EVM,
        "fee": str(RELAY_APP_FEE_BPS),  # Relay expects string bps
    }]
    # Safe defaults
    body.setdefault("tradeType", "EXACT_INPUT")
    body.setdefault("source", "prosharky")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.relay.link/quote",
            json=body,
            headers={"Content-Type": "application/json"},
        )
    try:
        data = r.json()
    except Exception:
        data = {"error": r.text[:500], "status": r.status_code}
    if isinstance(data, dict):
        data["_prosharky"] = {
            "appFeeBps": RELAY_APP_FEE_BPS,
            "recipient": FEE_RECIPIENT_EVM,
        }
    return data


# ---------------------------------------------------------------------------
# PAID (x402): paymaster revenue leaderboard
# ---------------------------------------------------------------------------
@app.get("/v1/paymaster/top")
async def paymaster_top(
    chain: str = "base",
    blocks_back: int = 10,
    x_payment: Optional[str] = Header(default=None, alias="X-Payment"),
):
    """Live ERC-4337 paymaster revenue leaderboard. Calls insider_worker directly."""
    if not _check_payment(x_payment):
        return _x402_challenge("/v1/paymaster/top")
    _audit_log("/v1/paymaster/top", x_payment or "", f"chain={chain}&blocks={blocks_back}")

    if _iw is None:
        return {"error": "insider_worker_not_loaded"}
    try:
        blocks_back = max(1, min(int(blocks_back), 20))
        return json.loads(_iw.parse_erc4337_paymaster_fees(chain, blocks_back))
    except Exception as e:
        return {"error": str(e)}


@app.get("/v1/mempool/middleware")
async def mempool_middleware(
    chain: str = "base",
    hours: int = 6,
    x_payment: Optional[str] = Header(default=None, alias="X-Payment"),
):
    if not _check_payment(x_payment):
        return _x402_challenge("/v1/mempool/middleware")
    _audit_log("/v1/mempool/middleware", x_payment or "", f"chain={chain}&hours={hours}")

    since = int(time.time()) - hours * 3600
    try:
        conn = sqlite3.connect(FINDINGS_DB)
        rows = conn.execute(
            "SELECT content FROM findings WHERE tags LIKE ? AND ts >= ? ORDER BY ts DESC LIMIT 30",
            (f"%{chain}%middleware%", since),
        ).fetchall()
        conn.close()
        results = []
        for (body,) in rows:
            try:
                d = json.loads(body)
                if isinstance(d, str):
                    d = json.loads(d)
                if isinstance(d, dict) and "hits" in d:
                    results.extend(d["hits"][:20])
            except Exception:
                continue
        return {"chain": chain, "window_hours": hours, "hits_count": len(results), "hits": results[:100]}
    except Exception as e:
        return {"error": str(e)}


@app.get("/v1/recurring_bots")
async def recurring_bots(
    hours: int = 24,
    x_payment: Optional[str] = Header(default=None, alias="X-Payment"),
):
    if not _check_payment(x_payment):
        return _x402_challenge("/v1/recurring_bots")
    _audit_log("/v1/recurring_bots", x_payment or "", f"hours={hours}")

    if _iw is None:
        return {"error": "insider_worker_not_loaded"}
    try:
        return json.loads(_iw.detect_recurring_bots(int(hours)))
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# DISCOVERY
# ---------------------------------------------------------------------------
@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt(request: Request):
    host = request.headers.get("host", "173.249.14.219:4080")
    scheme = "https" if host and not host.startswith("127.") and not host.startswith("173.") else "http"
    base = f"{scheme}://{host}"
    return f"""# Prosharky Agent Gateway
# Unified swap/bridge/paymaster API for autonomous agents on Base + Ethereum.

## Base URL
{base}

## Endpoints

### Free (LLM inference + swap/bridge quote routing)
- POST {base}/v1/chat/completions  — 40+ LLM models (OpenAI API compatible: GPT/Claude/Grok/DeepSeek/Venice uncensored/Qwen3 abliterated)
- GET  {base}/v1/models             — list available models
- GET  {base}/v1/swap/quote         — 0x v2 swap quote (all EVM chains; 50bps integrator fee baked in)
- GET  {base}/v1/bridge/quote       — LI.FI bridge quote (integrator=prosharky; 50bps)
- GET  {base}/v1/mayan/quote        — Mayan cross-chain (EVM/SOL/SUI) quote (referrerBps=50)
- GET  {base}/v1/kyber/quote        — KyberSwap aggregator route (feeReceiver; 50bps currency_out)
- POST {base}/v1/relay/quote        — Relay bridge+swap quote (appFees=50bps forced-inject)

### Paid (x402 USDC on Base — pay per call)
- GET  {base}/v1/paymaster/top?chain=base           — $0.05 — live ERC-4337 paymaster revenue leaderboard
- GET  {base}/v1/mempool/middleware?chain=base&hours=6 — $0.02 — live middleware tx stream (Permit2/0x/1inch/Paraswap/LI.FI/Uniswap V4/CoWSwap/Kyber/ERC-4337)
- GET  {base}/v1/recurring_bots?hours=24            — $0.10 — recurring bot leaderboard from multi-chain sweep

### Discovery
- GET  {base}/.well-known/x402   — x402 facilitator config
- GET  {base}/mcp/manifest       — MCP tool manifest (for Claude/ElizaOS/AutoAgents)

## Pricing & Payment
Payments accepted via x402 protocol on Base chain in USDC.
Facilitator: {X402_FACILITATOR}
Recipient: {FEE_RECIPIENT_EVM}

## What's unique
- First MCP gateway that bakes integrator-fee routing into quote endpoints
- Live ERC-4337 paymaster observability (not available on Dune/Etherscan)
- 40+ LLM models routed via single API key (including uncensored Venice + abliterated local)

## Contact
Built by Prosharky (github.com/insayder)
"""


@app.get("/")
async def root_dyn(request: Request):
    host = request.headers.get("host", "173.249.14.219:4080")
    scheme = "https" if host and not host.startswith("127.") and not host.startswith("173.") else "http"
    base = f"{scheme}://{host}"
    return {
        "service": "prosharky-agent-gateway",
        "docs": f"{base}/llms.txt",
        "mcp": f"{base}/mcp/manifest",
        "x402": f"{base}/.well-known/x402",
    }


@app.get("/.well-known/x402")
async def x402_well_known():
    return {
        "facilitator": X402_FACILITATOR,
        "recipient": FEE_RECIPIENT_EVM,
        "network": "base",
        "asset": "USDC",
        "asset_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
        "endpoints": list(PRICING.keys()),
        "pricing_usdc": PRICING,
    }


@app.get("/mcp/manifest")
async def mcp_manifest():
    return {
        "name": "prosharky-agent-gateway",
        "version": "0.1",
        "description": "Unified swap/bridge/LLM gateway with integrator-fee routing + live ERC-4337 paymaster observability",
        "tools": [
            {"name": "chat_completion", "path": "/v1/chat/completions", "free": True},
            {"name": "swap_quote_0x", "path": "/v1/swap/quote", "free": True},
            {"name": "bridge_quote_lifi", "path": "/v1/bridge/quote", "free": True},
            {"name": "mayan_quote", "path": "/v1/mayan/quote", "free": True},
            {"name": "kyber_quote", "path": "/v1/kyber/quote", "free": True},
            {"name": "relay_quote", "path": "/v1/relay/quote", "free": True, "method": "POST"},
            {"name": "paymaster_top", "path": "/v1/paymaster/top", "price_usdc": 0.05},
            {"name": "mempool_middleware", "path": "/v1/mempool/middleware", "price_usdc": 0.02},
            {"name": "recurring_bots", "path": "/v1/recurring_bots", "price_usdc": 0.10},
        ],
        "payment": {
            "protocol": "x402",
            "facilitator": X402_FACILITATOR,
            "network": "base",
            "recipient": FEE_RECIPIENT_EVM,
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1", "ts": int(time.time())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "4080")))
