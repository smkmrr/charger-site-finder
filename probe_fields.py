"""Temporary: inspect the cached EPDK response before modelling it."""

import json
from collections import Counter
from pathlib import Path

RAW = Path("data/cache/epdk_raw.json")


def main() -> None:
    payload = json.loads(RAW.read_text(encoding="utf-8"))
    stations = payload["data"]
    print("stations:", len(stations))

    print("\nhizmetSekli:")
    for value, count in Counter(s.get("hizmetSekli") for s in stations).most_common():
        print(f"  {value!r:28} {count}")

    print("\nsoketTipi:")
    types = Counter(
        socket.get("soketTipi")
        for s in stations
        for socket in s.get("soketler") or []
    )
    for value, count in types.most_common():
        print(f"  {value!r:28} {count}")

    print("\nsoketGucu values that are not plain numbers:")
    odd = Counter(
        socket.get("soketGucu")
        for s in stations
        for socket in s.get("soketler") or []
        if not str(socket.get("soketGucu") or "").replace(".", "", 1).isdigit()
    )
    for value, count in odd.most_common(10):
        print(f"  {value!r:28} {count}")

    missing_coords = sum(
        1 for s in stations if s.get("enlem") is None or s.get("boylam") is None
    )
    no_sockets = sum(1 for s in stations if not s.get("soketler"))
    print("\nmissing coordinates:", missing_coords)
    print("stations with no sockets:", no_sockets)


if __name__ == "__main__":
    main()