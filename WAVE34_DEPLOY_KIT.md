# Wave-34 Deploy Kit — Step-by-Step Bundle

Generated 2026-04-24 by Claude. Use this when GH_TOKEN is available.

---

## Step 2 — Commit & push prosharky-gateway

Files to commit (ALREADY-MODIFIED locally):
- `server.py` (+1296/-30 lines accumulated drift across Wave-30/32/34)
- `smithery.yaml` (+80 lines: 13 Hermetic Keys + emerald/pneuma/thoth keywords)
- New files (untracked, OK to add): `_jupiter.py`, `_jupiter_referral.py`, `_mcp_hijack_defense.py`, `_mcp_jsonrpc.py`, `_morpho_upstream_mcp.py`, `setup_solana_atas.py`, `mcpso_submit.sh`, `submit_registries.sh`, `RESTART_REQUIRED.md`, `MCPSO_SUBMISSION.md`, `DISTRIBUTION_DRAFTS.md`, `README_jupiter.md`

DO NOT commit: `__pycache__/*.pyc`

Suggested commit message:

```
gateway: Wave-30→34 bundle — JSON-RPC 2.0 MCP, Jupiter Referral, FHA defense, Hermetic Keys X-XIII

- POST /mcp JSON-RPC 2.0 endpoint with 11+ tools (initialize/ping/tools/list/tools/call/resources/list/read)
- Jupiter Referral Program (/v1/jupiter/quote prefers referralTokenAccount, 6 PDAs, ~40bps net)
- /v1/risk/premium x402-gated — Emerald Synthesis cross-protocol risk report (Aave V4 + Morpho Blue)
- /v1/mempool/middleware x402-gated — Pneuma Transmission live middleware tx stream
- _mcp_hijack_defense.py — /mcp/audit endpoint with FHA detector (entropy/nondict/jaccard/ctrlchar)
- /.well-known/farcaster.json + /.well-known/glama.json discovery
- smithery.yaml — 13 Hermetic Keys (I-XIII), aliases parallel to classical names
- X402_FACILITATOR default flipped from cloudflare tunnel → official x402.org/facilitator
- ENDPOINT_META scaffolding for x402 bazaar discovery
```

Commands:
```bash
cd /opt/prosharky_gateway
git add server.py smithery.yaml _jupiter.py _jupiter_referral.py _mcp_hijack_defense.py _mcp_jsonrpc.py _morpho_upstream_mcp.py setup_solana_atas.py
git add mcpso_submit.sh submit_registries.sh RESTART_REQUIRED.md MCPSO_SUBMISSION.md DISTRIBUTION_DRAFTS.md README_jupiter.md
git status  # confirm
git commit -m "gateway: Wave-30→34 bundle — JSON-RPC 2.0 MCP, Jupiter Referral, FHA defense, Hermetic Keys X-XIII

[full body as above]

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main  # pushes to mintmas/prosharky-agent-gateway
```

---

## Step 3 — x402 PR #2116 description update

PR: https://github.com/x402-foundation/x402/pull/2116
Status: open, mergeable=True, 1 file changed
Branch: add-prosharky-agent-gateway

Append to PR body (BELOW existing summary, NOT replacing it):

```markdown
## Update 2026-04-24 — Hermetic Key XIII: Thoth Inscription

The gateway facilitator endpoint is now exposed under the Hermetic Keys naming scheme as **Thoth Inscription** (Key XIII), with classical name `x402_facilitator` retained as backward-compatible alias.

Both names point to the same x402 facilitator routing logic — agents may select either based on their preferred lexicon. This is informational; no functional change to the resource itself.

- **Tool name (classical)**: `x402_facilitator`
- **Tool name (alias)**: `thoth_inscription`
- **Display name**: Thoth Inscription: x402 Facilitator
- **Settlement**: USDC on Base via official https://x402.org/facilitator
- **Coverage**: 5 paid endpoints under x402 challenge-response
- **Audit**: passes our internal /mcp/audit FHA detector (CLEAN)

Audit endpoint: https://prosharky-gw.173-249-14-219.sslip.io/mcp/audit
```

NOTE: I removed the false-claim boilerplate from the worker output (`"1000+ recent invocations"`, `"Catches hallucination patterns"`, `"RFC-9110 HEAD semantics"`). Those are not true for a new gateway and would risk maintainer rejection as ToolRank-style spam.

Update via:
```bash
GH_TOKEN=ghp_xxx gh pr edit 2116 --repo x402-foundation/x402 --body "$(cat /tmp/pr_2116_new_body.md)"
```

Or paste manually in GitHub UI.

---

## Step 4 — Verification after deploy

```bash
# 1. Restart picked up:
curl -sS https://prosharky-gw.173-249-14-219.sslip.io/v1/risk/premium | python3 -m json.tool | grep description
# Expect: "Emerald Synthesis — canonical 7-factor..."

# 2. /mcp/audit still clean:
curl -sS https://prosharky-gw.173-249-14-219.sslip.io/mcp/audit | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"CLEAN={d['clean']}/{d['total']}, REVIEW={d['review']}, BLOCK={d['block']}\")"

# 3. tools/list serves Hermetic aliases:
curl -sS -X POST https://prosharky-gw.173-249-14-219.sslip.io/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 -c "import json,sys; d=json.load(sys.stdin); names=[t['name'] for t in d['result']['tools']]; print(f'Total tools: {len(names)}'); print('Hermetic aliases:', [n for n in names if 'key_' in n or 'emerald' in n.lower() or 'pneuma' in n.lower()])"

# 4. Smithery rescan trigger (after push):
curl -sS https://api.smithery.ai/api/v1/registry/lookup?q=prosharky 2>&1 | head -5

# 5. Agentic.market crawler hit (auto, ~hours):
# manual check: https://agentic.market/?q=prosharky-agent-gateway
```

---

## Realistic expectations after full deploy

- Smithery listing within 24-48h (registry rescans on push)
- Agentic.market index within hours (HTTP 402 response auto-crawled)
- x402 PR review timeline: maintainer-dependent, days-weeks
- Traffic: ZERO guaranteed. If MCP agents pull from these registries and select our tool over competitors, MAYBE $5-10/day within week 2 (Wave-34 worker estimate, NOT verified)
- Wave-31 verdict still stands: gap is DISTRIBUTION not inventory — listing alone doesn't create traffic
