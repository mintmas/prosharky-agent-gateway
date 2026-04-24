# Distribution submission drafts — 2026-04-24

Ready-to-paste drafts for each external listing. Operator submits these with
one click each from an authed browser session (to avoid automation flags).

## 1. awesome-mcp-servers (github.com/punkpeye/awesome-mcp-servers)

**Action:** open `https://github.com/punkpeye/awesome-mcp-servers/blob/main/README.md` → Edit (pencil icon) → add line under appropriate section → Commit → Create PR.

Section: **"🌐 Browser Automation / Cloud / Commerce"** or new **"💰 DeFi / Finance"** section.

Line to add:
```
- [prosharky-agent-gateway](https://github.com/insayder/prosharky-gateway) - Unified swap/bridge/LLM gateway for autonomous agents across EVM + Solana. Live ERC-4337 paymaster observability. Integrator-fee routing pre-baked. Jupiter v6 Solana. x402 USDC billing on Base.
```

## 2. Smithery.ai submission

**Action:** open `https://smithery.ai/new` → sign in with GitHub → paste repo URL.

Already-prepared `smithery.yaml` lives at `/opt/prosharky_gateway/smithery.yaml` — Smithery reads it directly.

If Smithery asks for a manifest URL directly: `https://prosharky-gw.173-249-14-219.sslip.io/mcp/manifest`

## 3. MCPay registry

**Action:** message `@mcpay` or `@caolofc` on Farcaster with:
```
Hey! Built a paid MCP gateway with x402 USDC billing + integrator-fee routing across EVM (0x/LI.FI/Kyber/Relay/Mayan) and Solana (Jupiter v6, Token-2022 compatible). Manifest at https://prosharky-gw.173-249-14-219.sslip.io/mcp/manifest — would love to list on MCPay. Revenue share welcome.
```

## 4. Jupiter welcome-partners (ecosystem listing)

**Scope check:** their `list.json` is for end-user dapps, not middleware/integrators. PROBABLY NOT A FIT — skip unless we add a user-facing Prosharky dApp UI later.

## 5. Farcaster post (zero-friction visibility)

Single post on your Warpcast account:
```
shipped jupiter v6 fee-slot integration on prosharky-gateway 
50 bps on any routed swap lands in our solana ATA 
8 ATAs live including pyusd on token-2022 
mcp manifest at prosharky-gw.173-249-14-219.sslip.io/mcp/manifest 
wire your agent → earn the spread on ur own flow 
```

## 6. Warpcast Frame (for distribution track Wave-19)

Optional deeper play — build a Frame that demos a Jupiter quote through our gateway. Requires Frame hosting (can co-locate on our gateway). ~1h build.

## 7. Jupiter station post (real ecosystem reach)

**Action:** create post at https://station.jup.ag or engage on Jupiter Discord `#integrations` channel:

Title: `Prosharky Gateway — Jupiter v6 middleware with fee-slot pre-injection for autonomous agents`

Body:
```
Just wired the Jupiter v6 platformFeeBps param into the Prosharky Agent Gateway alongside our EVM integrator slots.

What it is:
- Drop-in REST endpoint at `/v1/jupiter/quote` that proxies Jupiter v6 with fee auto-routing
- Solana wallet fee-owner: Hhi4RfSTMhVX2xUGPGKzD14PSRsRQgtozQVw5qjiPQAu
- 8 ATAs pre-created: USDC / USDT / wSOL / JUP / BONK / JTO / PYUSD(Token-2022) / mSOL
- Token-2022 compatibility for newer mints

Use case: if you're building an agent or MCP server and want to capture the 50bps spread on Jupiter swaps you route, you can either (a) use our endpoint directly and split, (b) fork the integrator code — single-file, solders-based ATA derivation.

Manifest: https://prosharky-gw.173-249-14-219.sslip.io/mcp/manifest

Would love feedback or integration pairs.
```
