"""
MCP JSON-RPC 2.0 handler for the Prosharky Agent Gateway.

Exposes a single endpoint (POST /mcp) that implements the MCP spec:
- initialize            → protocol handshake
- notifications/initialized (ack — no response body for notifications)
- tools/list            → list available tools with JSON Schema
- tools/call            → invoke a tool by name with args
- resources/list        → list /llms.txt + /.well-known/* resources
- resources/read        → read resource content

Spec: https://spec.modelcontextprotocol.io/specification/2024-11-05/

Why a real JSON-RPC endpoint (not just static /mcp/manifest):
- Smithery and Glama scan runtime for `tools/list` before listing
- MCPay requires the server to accept JSON-RPC envelope + return proper envelope
- Agent frameworks (Claude, Cursor, Claude Desktop) call `initialize` then `tools/call`

Transport: HTTP + JSON. SSE optional, not implemented here (simple HTTP works for
all major clients as of April 2026).
"""
from typing import Any, Callable, Dict, List, Optional
import json
import os
import time

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "prosharky-agent-gateway"
SERVER_VERSION = "0.3"

# Registry: tool_name → {schema, handler}.
# Handlers are registered lazily from server.py to avoid circular import.
_TOOLS: Dict[str, Dict[str, Any]] = {}
_RESOURCES: Dict[str, Dict[str, Any]] = {}

# FHA defense hooks (arxiv:2604.20994) — fail-safe no-ops if module missing.
try:
    from _mcp_hijack_defense import (
        track_call as _track_call,
        sanitise_description as _sanitise,
    )
except Exception:
    def _track_call(_src: str, _tool: str): return None
    def _sanitise(s: str) -> str: return s

_EVENT_LOG = os.environ.get("MCP_EVENT_LOG", "/var/log/mcp-events.log")


def _log_event(kind: str, payload: Dict[str, Any]) -> None:
    try:
        with open(_EVENT_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": int(time.time()), "kind": kind, **payload}) + "\n")
    except Exception:
        pass


def register_tool(
    name: str,
    description: str,
    input_schema: dict,
    handler: Callable,
    is_paid: bool = False,
    price_usdc: Optional[float] = None,
) -> None:
    """Register a tool. handler is async callable that takes kwargs and returns
    a JSON-serialisable result (dict, list, or str)."""
    _TOOLS[name] = {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
        "handler": handler,
        "is_paid": is_paid,
        "price_usdc": price_usdc,
    }


def register_resource(
    uri: str,
    name: str,
    description: str,
    mime_type: str,
    reader: Callable,
) -> None:
    """Register a resource. reader is async callable returning string content."""
    _RESOURCES[uri] = {
        "uri": uri,
        "name": name,
        "description": description,
        "mimeType": mime_type,
        "reader": reader,
    }


def _ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, message: str, data: Any = None) -> dict:
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return {"jsonrpc": "2.0", "id": id_, "error": e}


async def dispatch(payload: Any, source: str = "unknown") -> Any:
    """
    Dispatch a JSON-RPC 2.0 request. Handles single or batch requests.
    `source` — caller identifier (typically IP) used by FHA anomaly tracker.
    Returns None for notifications (per spec — no response body).
    """
    if isinstance(payload, list):
        # Batch
        responses = []
        for req in payload:
            r = await _dispatch_one(req, source=source)
            if r is not None:
                responses.append(r)
        return responses if responses else None
    return await _dispatch_one(payload, source=source)


async def _dispatch_one(req: Any, source: str = "unknown") -> Optional[dict]:
    if not isinstance(req, dict):
        return _err(None, -32600, "Invalid Request")
    id_ = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}
    is_notification = id_ is None

    if not method:
        return _err(id_, -32600, "Missing method")

    try:
        if method == "initialize":
            # Per spec, we MUST return protocolVersion + serverInfo + capabilities.
            # server_instructions field is the binary discovery gate for Claude
            # Code Tool Search (arxiv:2603.20313) — without it, our tools are
            # hidden from most queries. Keep vocabulary dense with terms
            # consuming agents would actually query.
            return _ok(id_, {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "logging": {},
                },
                "instructions": (
                    "Unified agent gateway for DeFi and multi-model inference. "
                    "Search this server for: swap quote, bridge quote, cross-chain "
                    "route, aggregator route, 0x quote, LI.FI bridge, deBridge DLN, "
                    "Mayan cross-chain, KyberSwap, Relay bridge, Jupiter v6 Solana, "
                    "Jupiter referral, SPL token, Token-2022, ERC-4337 paymaster, "
                    "paymaster leaderboard, mempool middleware, MEV stream, recurring "
                    "bots, integrator fee, middleware observability, "
                    "Aave V4 risk, Aave spoke risk, Morpho Blue vault, Morpho vault "
                    "concentration, cross-protocol risk, HHI concentration, "
                    "Garman-Klass volatility, Target Health Factor, liquidation depth, "
                    "oracle deviation, 7-factor risk, cross-protocol contagion, "
                    "DeFi risk analytics, on-chain risk metrics, risk report, "
                    "Solana collector treasury, Jupiter ATAs, referral token accounts, "
                    "threat snapshot, fee slot monitoring, "
                    "LLM inference, multi-model chat, Claude Opus Sonnet Haiku, "
                    "GPT-5, Grok-4, DeepSeek V3.2, Gemini 2.5, Venice uncensored, "
                    "Qwen3 abliterated, GLM 4.7 Heretic, uncensored reasoning, "
                    "OpenAI-compatible chat completion, "
                    "Thirteen Keys of Hermes, Hermetic gateway, Emerald Transmutation, "
                    "Alchemical Risk Transmutation, Star-Wheel of Six Bodies, "
                    "x402 USDC micropayment, Base chain, Ethereum, Arbitrum, Optimism, "
                    "Polygon, Solana, x402 facilitator, MCP gateway, agent payment."
                ),
            })

        if method == "notifications/initialized":
            # Client ack — no response for notifications
            return None

        if method == "ping":
            return _ok(id_, {})

        if method == "tools/list":
            return _ok(id_, {
                "tools": [
                    {
                        "name": t["name"],
                        "description": _sanitise(t["description"]),
                        "inputSchema": t["inputSchema"],
                    }
                    for t in _TOOLS.values()
                ]
            })

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            if tool_name not in _TOOLS:
                return _err(id_, -32602, f"Unknown tool: {tool_name}")
            # FHA anomaly tracker — per-source call-rate monoculture detection
            try:
                anomaly = _track_call(source, tool_name)
                if anomaly is not None:
                    _log_event("fha_anomaly", anomaly)
            except Exception:
                pass
            tool = _TOOLS[tool_name]
            if tool["is_paid"]:
                # Surface x402 challenge as content, caller re-invokes with payment.
                return _ok(id_, {
                    "content": [
                        {"type": "text", "text": json.dumps({
                            "error": "payment_required",
                            "price_usdc": tool["price_usdc"],
                            "x402_path": f"/v1/{tool_name.replace('_', '/')}",
                            "note": "Fetch via HTTP with x402 payment header."
                        })}
                    ],
                    "isError": True,
                })
            started = time.monotonic()
            result = await tool["handler"](**arguments)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            # MCP expects content array of typed items
            if isinstance(result, (dict, list)):
                text = json.dumps(result, default=str)
            else:
                text = str(result)
            return _ok(id_, {
                "content": [{"type": "text", "text": text}],
                "_meta": {"elapsed_ms": elapsed_ms},
            })

        if method == "resources/list":
            return _ok(id_, {
                "resources": [
                    {k: v for k, v in r.items() if k != "reader"}
                    for r in _RESOURCES.values()
                ]
            })

        if method == "resources/read":
            uri = params.get("uri")
            if uri not in _RESOURCES:
                return _err(id_, -32602, f"Unknown resource: {uri}")
            r = _RESOURCES[uri]
            content = await r["reader"]()
            return _ok(id_, {
                "contents": [{
                    "uri": uri,
                    "mimeType": r["mimeType"],
                    "text": content if isinstance(content, str) else json.dumps(content),
                }]
            })

        # Unknown method — per spec code -32601
        if not is_notification:
            return _err(id_, -32601, f"Method not found: {method}")
        return None

    except Exception as e:
        if not is_notification:
            return _err(id_, -32603, f"Internal error: {type(e).__name__}: {e}")
        return None
