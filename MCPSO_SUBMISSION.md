# mcp.so submission — ready-to-paste issue

**Target**: https://github.com/chatmcp/mcpso/issues/new
**Alternative form**: https://mcp.so/submit

Since mcp.so uses Next.js server-actions + GitHub OAuth for their submit form, a truly headless HTTP POST requires an authenticated session we don't have. The two fastest paths are below; each takes under 2 minutes of operator time.

---

## PATH A — Paste as GitHub Issue (60 seconds)

1. Open https://github.com/chatmcp/mcpso/issues/new (sign in if prompted — your existing 5-year github works)
2. **Title**:
   ```
   [Submit] Prosharky Agent Gateway — Unified swap/bridge/LLM gateway with 27 MCP tools + x402 billing
   ```
3. **Body** (paste verbatim):

---

**Name**: Prosharky Agent Gateway (Thirteen Keys of Hermes)
**Homepage**: https://prosharky-gw.173-249-14-219.sslip.io/llms.txt
**Repo**: https://github.com/insayder/prosharky-agent-gateway *(placeholder — update once repo is public)*
**License**: MIT
**Type**: Remote MCP server (HTTP JSON-RPC 2.0, no install)

**Description**:
Unified agent gateway spanning EVM and Solana, exposing 27 MCP tools over JSON-RPC 2.0 at `/mcp`. Every tool has contract-enforced integrator fees pre-baked (no registration required from consumers). x402 USDC billing on Base for paid data endpoints. Features:

- **Swap aggregators**: 0x v2 / LI.FI / deBridge DLN / Mayan / KyberSwap / Relay — each with 50 bps integrator fee pre-wired
- **Solana**: Jupiter v6 with contract-enforced Referral Program routing (USDC/USDT/SOL/JUP/BONK/JTO) + Token-2022 PYUSD fallback
- **Inference**: OpenAI-compatible chat.completions across 40+ models via LiteLLM (Claude Opus/Sonnet/Haiku, GPT-5, Grok-4, DeepSeek V3.2, Gemini 2.5, Venice uncensored, Qwen3 abliterated)
- **DeFi risk analytics**: 7-factor cross-protocol report (Aave V4 Hub/Spoke + Morpho Blue top-15 vaults) with HHI concentration, Garman-Klass volatility, Target Health Factor
- **Middleware intel**: ERC-4337 paymaster leaderboard, 9-protocol mempool stream, 24h recurring-bot leaderboard — x402-gated
- **FHA-defended**: built-in description auditor + call-rate anomaly tracker against arxiv:2604.20994 Function Hijacking Attacks. `/mcp/audit` endpoint returns real-time signature report.

**Tools exposed (27)**:

*Classical names*: swap_quote_0x, bridge_quote_lifi, debridge_quote, mayan_quote, kyber_quote, jupiter_quote, jupiter_atas, sol_balance, threat_snapshot, risk_report, chat_completion, paymaster_top (paid), mempool_middleware (paid), recurring_bots (paid)

*Hermetic aliases (same handlers, alternate vocabulary)*: key_poimandres, key_swap, key_bridge, key_cross_chain, key_kyber, key_jupiter, key_watchtower, key_ledger_of_hhi, key_balances, key_alchemical_risk, key_paymaster_oracle, key_mempool_veil, key_recurring_familiars

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

**Trust signals**: JSON-RPC 2.0 MCP compliant (2024-11-05 spec). server_instructions field present for Claude Code Tool Search. Glama discovery manifest at `/.well-known/glama.json`. Farcaster Mini App manifest at `/.well-known/farcaster.json`.

---

4. Click **Submit new issue**. That's it — curator typically merges within 24-72 hours.

## PATH B — One-shot GitHub Issue via `gh` CLI

Requires a PAT (`gh auth login` → paste token, or `export GH_TOKEN=ghp_...`). Once authenticated:

```bash
bash /opt/prosharky_gateway/mcpso_submit.sh
```

Script at `/opt/prosharky_gateway/mcpso_submit.sh` is ready to run — pastes the exact body above via `gh issue create`.

## PATH C — Submit form at mcp.so/submit

Same fields (Name, URL, Server Config). Requires GitHub OAuth sign-in. Next.js server action submission — does not support headless POST without a real browser session. Use Path A instead.
