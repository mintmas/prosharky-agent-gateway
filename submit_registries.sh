#!/usr/bin/env bash
# Prosharky Gateway — registry submission helper.
#
# Run AFTER `systemctl restart prosharky-gateway` so /mcp responds.
# All submissions are idempotent — safe to re-run.

set -euo pipefail

GATEWAY_BASE="${GATEWAY_BASE:-https://prosharky-gw.173-249-14-219.sslip.io}"

echo "=== Prosharky Gateway registry submission ==="
echo "Base URL: $GATEWAY_BASE"
echo

# --- Health check ---
echo "[1/5] Health check"
if ! curl -sf -m 10 "$GATEWAY_BASE/health" > /dev/null; then
    echo "ERROR: gateway not reachable at $GATEWAY_BASE/health"
    exit 1
fi
echo "  ✓ gateway healthy"
echo

# --- MCP JSON-RPC verify ---
echo "[2/5] Verify /mcp JSON-RPC 2.0"
TOOLS_COUNT=$(curl -sS -X POST "$GATEWAY_BASE/mcp" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
    -m 15 \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['result']['tools']))")
if [ "$TOOLS_COUNT" -lt 8 ]; then
    echo "ERROR: expected ≥8 tools, got $TOOLS_COUNT"
    exit 1
fi
echo "  ✓ /mcp returns $TOOLS_COUNT tools"
echo

# --- Glama.ai discovery ---
echo "[3/5] Glama.ai discovery"
if curl -sf "$GATEWAY_BASE/.well-known/glama.json" -m 10 > /dev/null; then
    echo "  ✓ /.well-known/glama.json reachable"
    echo "  → Manually submit at https://glama.ai/mcp/servers/submit"
    echo "  → Server URL: $GATEWAY_BASE/mcp"
fi
echo

# --- MCPay registration ---
echo "[4/5] MCPay — x402 pay-per-call billing layer"
echo "  → Manual: https://mcpay.tech/mcp/add (connect wallet: 0x5f9B8f3BD13e5320eF5EFAEa906442Fb9B64802c)"
echo "  → Server URL: $GATEWAY_BASE/mcp"
echo "  → Pricing declared in /mcp/manifest (paid tools: paymaster_top/mempool_middleware/recurring_bots)"
echo

# --- mcp.so (unofficial directory) ---
echo "[5/5] mcp.so"
if ! curl -sf "$GATEWAY_BASE/.well-known/mcp/server-card.json" -m 10 > /dev/null; then
    echo "WARN: server-card not reachable"
else
    echo "  ✓ server-card.json reachable"
    echo "  → Manual submission (if still required): https://mcp.so/submit"
fi
echo

# --- Summary ---
echo "=== Summary ==="
echo "Gateway live at $GATEWAY_BASE"
echo "MCP JSON-RPC 2.0 endpoint: $GATEWAY_BASE/mcp ($TOOLS_COUNT tools)"
echo "Static server-card: $GATEWAY_BASE/.well-known/mcp/server-card.json"
echo "Farcaster manifest: $GATEWAY_BASE/.well-known/farcaster.json (needs op's accountAssociation sig)"
echo "Glama discovery:    $GATEWAY_BASE/.well-known/glama.json"
echo
echo "Smithery status: previously PUBLIC as oracle42/agent-gateway (re-check after restart for auto-refresh)"
echo "All submission pages are manual (registries require wallet-connect or OAuth); URLs printed above."
echo

# --- x402scan (x402 resource registry) ---
echo "[bonus] x402scan resource registration"
if curl -sf -X GET "$GATEWAY_BASE/v1/paymaster/top" -m 10 -w "%{http_code}" -o /dev/null 2>/dev/null | grep -q 402; then
    echo "  ✓ /v1/paymaster/top returns HTTP 402 with x402 challenge"
fi
echo "  → Submit at https://x402scan.com/register (paste URL: $GATEWAY_BASE/v1/paymaster/top)"
echo "  → Also list in Bazaar (Coinbase x402 registry): https://bazaar.coinbase.com/"
