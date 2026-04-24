#!/usr/bin/env python3
"""
One-shot setup script: creates Associated Token Accounts on Solana mainnet for
our fee wallet so Jupiter can deposit fees.

PREREQ: wallet must be funded with >= 0.05 SOL (each ATA costs ~0.00203 SOL
rent-exempt + tx fee; 8 ATAs * 0.003 ≈ 0.024 SOL total).

Run once after operator tops up:
  python3 /opt/prosharky_gateway/setup_solana_atas.py --confirm

Default is dry-run.
"""
import json
import sys
import argparse
import os

WALLET_FILE = "/opt/prosharky_collector/sol.json"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ATA_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
SOL_RPC = os.environ.get("SOL_RPC", "https://api.mainnet-beta.solana.com")


def load_keypair():
    with open(WALLET_FILE) as f:
        d = json.load(f)
    try:
        import base58
        from solders.keypair import Keypair
    except Exception as e:
        raise SystemExit(f"install solders + base58: pip install solders base58 ({e})")
    secret_b58 = d["secret_key_base58"]
    kp = Keypair.from_bytes(base58.b58decode(secret_b58))
    return kp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="actually send txs (default dry-run)")
    ap.add_argument("--rpc", default=SOL_RPC)
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _jupiter import KNOWN_MINTS, our_ata_for

    try:
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        from solana.rpc.api import Client
        from spl.token.instructions import create_associated_token_account
        from solders.transaction import Transaction
        from solders.message import Message
        from solders.system_program import transfer
    except Exception as e:
        print(f"install requirements: pip install solana solders spl-token base58 ({e})")
        sys.exit(1)

    kp = load_keypair()
    owner = kp.pubkey()
    print(f"wallet: {owner}")

    client = Client(args.rpc)
    bal = client.get_balance(owner).value
    print(f"balance: {bal / 1e9:.6f} SOL")
    if bal < 30_000_000:  # 0.03 SOL
        print("INSUFFICIENT BALANCE — need at least 0.03 SOL for 8 ATAs + tx fees")
        if not args.confirm:
            print("(dry-run mode — continuing to show plan)")
        else:
            sys.exit(2)

    TOKEN_2022 = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
    TOKEN_CLASSIC = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")

    for sym, mint in KNOWN_MINTS.items():
        mint_pk = Pubkey.from_string(mint)
        # Determine whether mint is Token-2022 or classic
        mint_info = client.get_account_info(mint_pk).value
        if mint_info is None:
            print(f"  {sym:6s} mint {mint} — NOT FOUND on chain, skip")
            continue
        mint_owner = mint_info.owner
        if mint_owner == TOKEN_2022:
            # Token-2022 ATA derivation uses same seeds but different token program
            from _jupiter import derive_ata
            ata = derive_ata(str(owner), mint, str(TOKEN_2022))
            token_program = TOKEN_2022
        else:
            ata = our_ata_for(mint)
            token_program = TOKEN_CLASSIC
        info = client.get_account_info(Pubkey.from_string(ata)).value
        if info is not None:
            print(f"  {sym:6s} ATA {ata} — already exists, skip")
            continue
        print(f"  {sym:6s} ATA {ata} — needs creation (prog={str(token_program)[:8]}...)")
        if args.confirm:
            try:
                ix = create_associated_token_account(
                    payer=owner, owner=owner, mint=mint_pk, token_program_id=token_program,
                )
                blockhash = client.get_latest_blockhash().value.blockhash
                msg = Message.new_with_blockhash([ix], owner, blockhash)
                tx = Transaction([kp], msg, blockhash)
                sig = client.send_transaction(tx).value
                print(f"    sent: {sig}")
            except Exception as e:
                print(f"    FAILED: {e}")
                continue

    print("done.")


if __name__ == "__main__":
    main()
