"""Read-only Reap catalogue probe; reads API key from the process environment."""

import os

from src.reap_client import ReapClient


query = os.getenv("REAP_PRODUCT_QUERY", "Iced Black")
result = ReapClient(os.environ["REAP_API_KEY"]).search_products(query)
for item in result.get("products", [])[:20]:
    print({"id": item.get("id"), "name": item.get("name"),
           "merchant": (item.get("merchant") or {}).get("name"),
           "available": item.get("available")})
