# Prosharky Agent Gateway

> Unified swap / bridge / LLM gateway for autonomous agents. Live ERC-4337 paymaster observability. Integrator-fee routing baked into every quote. x402 USDC billing on Base.

**Live:** https://prosharky-gw.173-249-14-219.sslip.io

## Why

Most agent frameworks hit five different APIs to complete a DeFi swap:
- OpenRouter / Anthropic for the LLM
- 0x / 1inch / Paraswap for the quote
- LI.FI / Socket for the bridge
- Dune / Etherscan for on-chain data

Each one has its own auth, its own billing, its own rate limit. Each swap call has to remember to include integrator fee params. Most don't.

Prosharky Gateway collapses all five into **one API key** (or no key — x402 USDC on Base for paid endpoints), with integrator-fee routing pre-baked so every executed swap earns the fee automatically.

## Endpoints

### Free (no auth)
| Path | What |
|------|------|
| `POST /v1/chat/completions` | 39 LLM models. OpenAI-compatible. Routes to Claude/GPT/Grok/DeepSeek/Venice uncensored/Qwen3 abliterated. |
| `GET /v1/models` | List available models. |
| `GET /v1/swap/quote` | 0x Swap v2 quote. **50 bps fee pre-injected.** Pass `chainId`, `sellToken`, `buyToken`, `sellAmount`, `taker`. |
| `GET /v1/bridge/quote` | LI.FI bridge quote. `integrator=prosharky` pre-injected. Pass `fromChain`, `toChain`, `fromToken`, `toToken`, `fromAmount`, `fromAddress`. |

### Paid (x402 USDC on Base)
| Path | Price | What |
|------|-------|------|
| `GET /v1/paymaster/top?chain=base` | $0.05 | **Live ERC-4337 paymaster revenue leaderboard.** Paginated userOps from EntryPoint v0.6 + v0.7, ranked by actualGasCost. Not available on Dune or Etherscan. |
| `GET /v1/mempool/middleware?chain=base&hours=6` | $0.02 | Live middleware tx stream (Permit2 / 0x / 1inch / Paraswap / LI.FI / Universal Router / CoWSwap / Kyber / ERC-4337). |
| `GET /v1/recurring_bots?hours=24` | $0.10 | Recurring bot leaderboard from multi-chain sweep. Identifies searcher bots that appear across Paraswap + Kyber + EntryPoint. |

### Discovery
| Path | What |
|------|------|
| `GET /llms.txt` | Agent-readable endpoint docs |
| `GET /.well-known/x402` | x402 facilitator config |
| `GET /mcp/manifest` | MCP tool manifest |

## How to pay (x402 USDC on Base)

Every paid endpoint responds with `HTTP 402 Payment Required` and a `WWW-Authenticate: x402` header until you include a signed `X-Payment` header. The facilitator at the URL in `/.well-known/x402` settles your USDC transfer to `0x5f9B8f3BD13e5320eF5EFAEa906442Fb9B64802c` on Base.

## Example: pull live paymaster leaderboard

```bash
curl -s -H "X-Payment: <signed-x402-attestation>" \
  "https://prosharky-gw.173-249-14-219.sslip.io/v1/paymaster/top?chain=base&blocks_back=10"
```

Returns:
```json
{
  "chain": "base",
  "total_userops": 82,
  "top_paymasters_by_revenue": [
    {"paymaster": "0x2faeb0760d4230ef2ac21496bb4f0b47d634fd4c",
     "op_count": 50, "unique_senders": 48, "total_usd": 0.4062},
    ...
  ]
}
```

## Example: swap quote with integrator fee

```bash
curl -s "https://prosharky-gw.173-249-14-219.sslip.io/v1/swap/quote?chainId=8453&sellToken=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&buyToken=0x4200000000000000000000000000000000000006&sellAmount=1000000&taker=0xYOUR"
```

Returned quote already has `swapFeeBps=50` and `swapFeeRecipient=0x5f9B8f3BD13e5320eF5EFAEa906442Fb9B64802c` baked in. When you execute the transaction, 50 bps of the output token routes automatically.

## What's unique

- Live observability on ERC-4337 paymaster revenue — a layer most analytics tools don't even expose
- Fee routing is included in the quote endpoint, not bolted on
- 40+ LLM models behind one key (Venice uncensored, Qwen3 abliterated, all major frontier models)
- x402 payments — agents can pay USDC inline, no account signup, no API key provisioning

## MCP clients

```json
{
  "mcpServers": {
    "prosharky": {
      "transport": {
        "type": "http",
        "url": "https://prosharky-gw.173-249-14-219.sslip.io/mcp"
      }
    }
  }
}
```

(Note: native MCP JSON-RPC transport coming in v0.2. For now, REST manifest at `/mcp/manifest`.)

## License

MIT. Feel free to fork. If you run one, let us know — we cross-link gateways that expose unique data sources.
