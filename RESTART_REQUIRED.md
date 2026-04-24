# ACTION NEEDED: restart prosharky-gateway

New files added 2026-04-24 01:02 UTC:
- `_jupiter_referral.py` — Jupiter Referral Program integration
- `referral_state.json` → `/opt/jupiter_referral/referral_state.json` (6 token accounts live on-chain)
- `server.py` — `/v1/jupiter/quote` now prefers referralTokenAccount over raw ATA

Running process is on code from before this change. Restart to load:

```
systemctl restart prosharky-gateway
systemctl is-active prosharky-gateway
curl -s http://127.0.0.1:4080/v1/jupiter/quote?inputMint=So11111111111111111111111111111111111111112\&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v\&amount=10000000 | python3 -m json.tool | grep -A 6 _prosharky
```

Expected `_prosharky.feeAccountRoute` = `"referral_program"`.

In-process smoke test passed — FastAPI TestClient returns route=referral_program + feeAccount=63v6bb9gK9J6RR2UnkUyBQkwssnzrqLUXeWVSuPQAaFC (USDC TA under referral Cg4qcxPBgN4zXD5XvNQiPMwHvikT7dQSrJXkeQDTuThM).

---

Additional bundled changes 2026-04-24 01:05-01:20 UTC (Wave-20 Steps 2+5):

- `_mcp_jsonrpc.py` — proper JSON-RPC 2.0 MCP handler (initialize, ping, tools/list, tools/call, resources/list, resources/read, notifications/initialized; batch requests supported)
- `server.py` `POST /mcp` — JSON-RPC 2.0 endpoint with 11 tools registered (incl. chat_completion)
- `server.py` `GET /mcp` — probe response for clients that GET
- `server.py` `GET /.well-known/farcaster.json` — Farcaster Mini App manifest (Step 5; eligible for $25K/wk dev reward pool)
- `server.py` `POST /farcaster/webhook` — webhook ack stub
- `server.py` `GET /.well-known/glama.json` — Glama.ai discovery pointer
- `/.well-known/mcp/server-card.json` — bumped to version 0.2 + transport endpoint now `/mcp`
- `smithery.yaml` — transport.endpoint=/mcp, protocolVersion, capabilities.resources=true

Expected post-restart:

```
curl -sS https://prosharky-gw.173-249-14-219.sslip.io/mcp -X POST \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
     | python3 -m json.tool | head -30

# Should show 11 tools.
```

Still pending (independent of restart): Farcaster accountAssociation fields (empty placeholders). Operator needs to verify gateway homeUrl via Warpcast → sign payload → paste into `/.well-known/farcaster.json`. Without this the Mini App works but isn't "verified" in Warpcast directory.
