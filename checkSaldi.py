#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()
API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
API_URL    = os.getenv("BINANCE_API_URL", "")
TESTNET    = API_URL.startswith("https://testnet")

client = Client(API_KEY, API_SECRET, testnet=TESTNET)
if API_URL:
    client.API_URL = API_URL

def main():
    print("\n📊 Tutti i saldi (free / locked):\n")
    balances = client.get_account().get("balances", [])
    for b in balances:
        asset  = b["asset"]
        free   = float(b["free"])
        locked = float(b.get("locked", 0))
        print(f"– {asset}: Free = {free:.8f}, Locked = {locked:.8f}")

if __name__ == "__main__":
    main()
