# Jupiter v6 Fee Integrator

## What
Gateway routes `/v1/jupiter/quote` and `/v1/jupiter/atas` attach our SOL wallet's ATA as `feeAccount` and set `platformFeeBps=50` on every Jupiter swap quote.

Upstream: `https://lite-api.jup.ag/swap/v1/quote` (Jupiter free tier, post-deprecation of `quote-api.jup.ag` at end of 2025).

## Wallet
- owner: `Hhi4RfSTMhVX2xUGPGKzD14PSRsRQgtozQVw5qjiPQAu`
- secret (for setup signing): `/opt/prosharky_collector/sol.json`
- current balance: **0.067 SOL (~$5.78)** — production-ready (bridged 0.0837 SOL 2026-04-24 via Jumper Base→Solana)
- 8/8 ATAs created on-chain 2026-04-24 00:40 UTC

## Pre-computed ATAs
| Mint | Symbol | ATA |
|---|---|---|
| EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v | USDC | GT6px8fm8nnAYfUZ3NzJ2cD3YWyCqPyqPMahxJyPtXam |
| Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB | USDT | DYPQ6iTbe8UnyzPoBthKuHK2aqprFTB8xSFdPe9kPikr |
| So11111111111111111111111111111111111111112 | wSOL | BGDvzVKrrFFBYGGqyMAfoVrUFooXRh6FGB6v82vrHhiB |
| JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN | JUP | BUbLxRZYoQq6EDZohGrBFPZeb6ZtCrqaDtwXobpEDuB5 |
| DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 | BONK | ETGMt8xcoqn4bfDu3XRNBH1V3aQeiMLwAZJnngg4PN8v |
| jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL | JTO | 6AZSWfWA32jyUXfxHC2o9MaJsTsarTSWkJvzKnn16S5s |
| 2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo | PYUSD (Token-2022) | 2HSA6tsSVjNiayp2xRX3as7PTyHsCrdeNXJtL8zsVwtw |
| mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So | mSOL | 6pQdQVR6hsHX24KQBsRB211LF3UFPJFjevdBWT5aPhhF |

None of these exist on-chain yet — creation costs ~0.00203 SOL each (rent-exempt minimum).

## Activation sequence (when operator funds wallet)

1. **Fund wallet** — send ~0.05 SOL to `Hhi4RfSTMhVX2xUGPGKzD14PSRsRQgtozQVw5qjiPQAu` (mainnet).
2. **Restart gateway** so new routes are served:
   `systemctl restart prosharky-gateway`
3. **Create ATAs**:
   `python3 /opt/prosharky_gateway/setup_solana_atas.py --confirm`
4. **Verify**: `curl http://127.0.0.1:4080/v1/jupiter/atas | jq`
5. **Test end-to-end**: `curl 'http://127.0.0.1:4080/v1/jupiter/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000000'`

## Distribution

Once live, promote via:
- List at `https://station.jup.ag/partner-directory` (community list; submit)
- Docs entry on our gateway's `/llms.txt` — already done via llms_txt handler
- MCP manifest broadcast to agent directories (Smithery, Glama, MCPay)
- Posting at forum.jup.ag with performance benchmarks after 1 week of traffic

## Economics

- Fee: 50 bps on every swap routed through `/v1/jupiter/quote`
- Expected volume at zero marketing: $0-100/mo (0-5 USDC/mo to us)
- Expected volume with distribution (Month-3): $10k-100k/mo routed → $50-500/mo to us
- Ceiling (top integrator benchmark): $5k-50k/mo

## Files

- `_jupiter.py` — ATA derivation + known-mint cache
- `server.py` — `/v1/jupiter/quote` and `/v1/jupiter/atas` routes (added 2026-04-23)
- `setup_solana_atas.py` — one-shot ATA creator, run with `--confirm` after funding
