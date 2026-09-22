"""Temporary: probe the EPDK public charging-station endpoint."""

import json
from pathlib import Path

import httpx

URL = "https://apigateway.epdk.gov.tr/sarjIstasyonlari"
OUT = Path("data/cache/epdk_raw.json")


def main() -> None:
    response = httpx.request("GET", URL, json={}, timeout=120.0)
    print("status:", response.status_code)
    print("content-type:", response.headers.get("content-type"))
    print("bytes:", len(response.content))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(response.content)
    print("saved to", OUT)

    if response.status_code != 200:
        print(response.text[:1000])
        return

    data = response.json()
    print("type:", type(data).__name__)
    if isinstance(data, list) and data:
        print("records:", len(data))
        print(json.dumps(data[0], indent=2, ensure_ascii=False)[:2000])
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()