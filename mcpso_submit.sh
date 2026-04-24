#!/bin/bash
# Submit Prosharky Agent Gateway to mcp.so catalog (chatmcp/mcpso issues).
# Requires: gh authenticated (`gh auth login`) OR `GH_TOKEN=ghp_...` env var.
set -euo pipefail

REPO="chatmcp/mcpso"
TITLE="[Submit] Prosharky Agent Gateway — Unified swap/bridge/LLM gateway with 27 MCP tools + x402 billing"

# Prefer GH_TOKEN if present; else rely on gh auth status
if [[ -z "${GH_TOKEN:-}" ]] && ! gh auth status >/dev/null 2>&1; then
    echo "ERROR: neither GH_TOKEN is set nor 'gh auth status' is logged in."
    echo "Run one of:"
    echo "  gh auth login"
    echo "  export GH_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx"
    exit 1
fi

BODY=$(cat <<'EOF'
**Name**: Prosharky Agent Gateway (Thirteen Keys of Hermes)
**Homepage**: https://prosharky-gw.173-249-14-219.sslip.io/llms.txt
**Repo**: https://github.com/insayder/prosharky-agent-gateway *(placeholder — update once repo is public)*
**License**: MIT
**Type**: Remote MCP server (HTTP JSON-RPC 2.0, no install)

**Description**:
Unified agent gateway spanning EVM and Solana, exposing 27 MCP tools over JSON-RPC 2.0 at `/mcp`. Every tool has contract-enforced integrator fees pre-baked (no registration required from consumers). x402 USDC billing on Base for paid data endpoints.

Features:
- **Swap aggregators**: 0x v2 / LI.FI / deBridge DLN / Mayan / KyberSwap / Relay — each with 50 bps integrator fee pre-wired
- **Solana**: Jupiter v6 with contract-enforced Referral Program routing (USDC/USDT/SOL/JUP/BONK/JTO) + Token-2022 PYUSD fallback
- **Inference**: OpenAI-compatible chat.completions across 40+ models via LiteLLM (Claude Opus/Sonnet/Haiku, GPT-5, Grok-4, DeepSeek V3.2, Gemini 2.5, Venice uncensored, Qwen3 abliterated)
- **DeFi risk analytics**: 7-factor cross-protocol report (Aave V4 Hub/Spoke + Morpho Blue top-15 vaults) with HHI concentration, Garman-Klass volatility, Target Health Factor
- **Middleware intel**: ERC-4337 paymaster leaderboard, 9-protocol mempool stream, 24h recurring-bot leaderboard — x402-gated
- **FHA-defended**: built-in description auditor + call-rate anomaly tracker against arxiv:2604.20994 Function Hijacking Attacks. `/mcp/audit` endpoint returns real-time signature report.

**Tools exposed (27)**:

Classical names: swap_quote_0x, bridge_quote_lifi, debridge_quote, mayan_quote, kyber_quote, jupiter_quote, jupiter_atas, sol_balance, threat_snapshot, risk_report, chat_completion, paymaster_top (paid), mempool_middleware (paid), recurring_bots (paid)

Hermetic aliases (same handlers): key_poimandres, key_swap, key_bridge, key_cross_chain, key_kyber, key_jupiter, key_watchtower, key_ledger_of_hhi, key_balances, key_alchemical_risk, key_paymaster_oracle, key_mempool_veil, key_recurring_familiars

**Client config example (Claude Desktop)**:
```json
{
  "mcpServers": {
    "prosharky-gateway": {
      "transport": "http",
      "url": "https://prosharky-gw.173-249-14-219.sslip.io/mcp"
    }
  }
}
```

**Categories**: defi, swap, bridge, llm, multi-model, x402, agent-economy, solana, evm, risk-analytics, middleware-intel

**Trust signals**: JSON-RPC 2.0 MCP compliant (2024-11-05 spec). server_instructions field present for Claude Code Tool Search. Glama discovery manifest at /.well-known/glama.json. Farcaster Mini App manifest at /.well-known/farcaster.json.
EOF
)

echo "Submitting to $REPO ..."
if [[ -n "${GH_TOKEN:-}" ]]; then
    # Use GH_TOKEN path
    URL=$(GH_TOKEN="$GH_TOKEN" gh issue create --repo "$REPO" --title "$TITLE" --body "$BODY")
else
    URL=$(gh issue create --repo "$REPO" --title "$TITLE" --body "$BODY")
fi
echo "OK: $URL"
