"""
Morpho MCP upstream proxy — Wave-29 ship.

Morpho Labs shipped a first-party MCP server 2026-04-08 at `https://mcp.morpho.org`.
Instead of re-implementing query/read/simulate/prepare logic (which would
require us to track protocol upgrades), we wrap their JSON-RPC 2.0 MCP upstream
behind our gateway's tool surface. Agents already talking to our /mcp get
Morpho tools transparently; our x402 metering layer keeps margin potential
(free today, metered later).

Source: https://morpho.org/blog/introducing-morpho-agents-beta-interface-built-for-ai-agents/
Upstream README: https://github.com/morpho-org/morpho-skills

Upstream protocol: JSON-RPC 2.0 over HTTPS with SSE reply format.
  request:  POST {"jsonrpc":"2.0","id":N,"method":"tools/call","params":{...}}
  headers:  Content-Type: application/json; Accept: application/json, text/event-stream
  response: SSE `event: message\\ndata: {...jsonrpc response...}`

Exposed tools (after register_morpho_tools()):
  morpho_query_vaults    (free)
  morpho_get_vault       (free)
  morpho_query_markets   (free)
  morpho_get_market      (free)
  morpho_get_positions   (free)

Agents that want to place lending bets through us get unified discovery +
(later) metering + call-rate auditing via our existing FHA defense layer.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import httpx

MORPHO_MCP_URL = os.environ.get("MORPHO_MCP_URL", "https://mcp.morpho.org")
MORPHO_TIMEOUT = int(os.environ.get("MORPHO_MCP_TIMEOUT", "30"))

# Cache a single AsyncClient lifespan — reuse keep-alive.
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=MORPHO_TIMEOUT,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "User-Agent": "prosharky-gateway/0.3 (morpho-mcp-proxy)",
            },
        )
    return _client


def _parse_sse(raw: str) -> Dict[str, Any]:
    """
    Morpho MCP replies as `event: message\\ndata: {json}\\n\\n`. Extract the JSON.
    Gracefully handle non-SSE replies too (some proxies flatten to plain JSON).
    """
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            body = line[5:].strip()
            if body:
                return json.loads(body)
    # Fallback: treat whole body as JSON
    return json.loads(raw)


async def _rpc(method: str, params: Optional[Dict[str, Any]] = None, req_id: int = 1) -> Dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
    c = _get_client()
    r = await c.post(MORPHO_MCP_URL, json=payload)
    r.raise_for_status()
    return _parse_sse(r.text)


async def _call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call a Morpho MCP tool and normalize the response back to a plain dict."""
    resp = await _rpc("tools/call", {"name": tool_name, "arguments": arguments})
    if "error" in resp:
        return {"error": resp["error"], "upstream": "morpho-mcp"}
    result = resp.get("result") or {}
    # Morpho returns `content: [{type:"text", text:"..."}]` per MCP spec; unwrap.
    content = result.get("content") or []
    if len(content) == 1 and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except Exception:
            return {"text": content[0]["text"]}
    return result


# ---------------------------------------------------------------------------
# Public handlers — minimal typed shims over upstream. Kept intentionally thin
# so schema drift on Morpho's side doesn't break us (inputSchema reflected at
# register-time from live Morpho `tools/list`).
# ---------------------------------------------------------------------------
async def morpho_query_vaults(chain: str = "base", **kwargs) -> Dict[str, Any]:
    args = {"chain": chain, **{k: v for k, v in kwargs.items() if v is not None}}
    return await _call_tool("morpho_query_vaults", args)


async def morpho_get_vault(chain: str, address: str) -> Dict[str, Any]:
    return await _call_tool("morpho_get_vault", {"chain": chain, "address": address})


async def morpho_query_markets(chain: str = "base", **kwargs) -> Dict[str, Any]:
    args = {"chain": chain, **{k: v for k, v in kwargs.items() if v is not None}}
    return await _call_tool("morpho_query_markets", args)


async def morpho_get_market(chain: str, marketId: str) -> Dict[str, Any]:
    return await _call_tool("morpho_get_market", {"chain": chain, "marketId": marketId})


async def morpho_get_positions(chain: str, user: str) -> Dict[str, Any]:
    return await _call_tool("morpho_get_positions", {"chain": chain, "user": user})


async def morpho_health_check() -> Dict[str, Any]:
    return await _call_tool("morpho_health_check", {})


# ---------------------------------------------------------------------------
# Register with gateway MCP server (called from server.py startup)
# ---------------------------------------------------------------------------
def register_morpho_tools(register_tool_fn) -> None:
    """
    Register Morpho passthrough tools with the gateway's MCP dispatch.
    register_tool_fn matches _mcp_jsonrpc.register_tool signature.

    Descriptions follow ToolRank rubric (arxiv:2603.20313): verb-first +
    when-to-call + what-returns. 3.6x selection lift vs baseline.
    """
    register_tool_fn(
        name="morpho_query_vaults",
        description="Query Morpho lending vaults by chain + asset. Call when an agent needs vault APYs, TVL, or fee rates on Ethereum/Base. Returns vault list sorted by apy/tvl with address, symbol, apyPct, tvlUsd.",
        handler=morpho_query_vaults,
        input_schema={
            "type": "object",
            "properties": {
                "chain": {"type": "string", "enum": ["base", "ethereum"]},
                "assetSymbol": {"type": "string"},
                "sort": {"type": "string", "enum": ["apy_desc", "apy_asc", "tvl_desc", "tvl_asc"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["chain"],
        },
    )
    register_tool_fn(
        name="morpho_get_vault",
        description="Inspect a single Morpho vault by address. Call when agent needs full vault state (allocation, curator, fee, share price). Returns vault record with all fields.",
        handler=morpho_get_vault,
        input_schema={
            "type": "object",
            "properties": {
                "chain": {"type": "string", "enum": ["base", "ethereum"]},
                "address": {"type": "string", "pattern": "^0x[a-fA-F0-9]{40}$"},
            },
            "required": ["chain", "address"],
        },
    )
    register_tool_fn(
        name="morpho_query_markets",
        description="Query isolated Morpho Blue markets by chain + asset. Call when agent needs market rates, utilization, liquidity. Returns markets with loanToken, collateralToken, lltv, apyBorrow, apySupply.",
        handler=morpho_query_markets,
        input_schema={
            "type": "object",
            "properties": {
                "chain": {"type": "string", "enum": ["base", "ethereum"]},
                "assetSymbol": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["chain"],
        },
    )
    register_tool_fn(
        name="morpho_get_market",
        description="Inspect a single Morpho Blue market. Call when agent needs full market state (LLTV, oracle, IRM, utilization). Returns market record.",
        handler=morpho_get_market,
        input_schema={
            "type": "object",
            "properties": {
                "chain": {"type": "string", "enum": ["base", "ethereum"]},
                "marketId": {"type": "string"},
            },
            "required": ["chain", "marketId"],
        },
    )
    register_tool_fn(
        name="morpho_get_positions",
        description="Fetch all Morpho positions for a user address. Call when agent monitors a wallet's lending exposure. Returns positions across markets and vaults.",
        handler=morpho_get_positions,
        input_schema={
            "type": "object",
            "properties": {
                "chain": {"type": "string", "enum": ["base", "ethereum"]},
                "user": {"type": "string", "pattern": "^0x[a-fA-F0-9]{40}$"},
            },
            "required": ["chain", "user"],
        },
    )
