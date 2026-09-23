"""Rebuild the offline fixtures from the current cache.

The repository ships a trimmed copy of each source so that the pipeline can be
run without network access. Regenerate them after a fresh fetch:

    python scripts/make_fixtures.py
"""

import json
from pathlib import Path

from charger_finder.config import ANKARA, CACHE_DIR, FIXTURES_DIR


def _inside_ankara(record: dict) -> bool:
    """Whether a raw EPDK record falls inside the Ankara bounding box."""
    lat, lon = record.get("enlem"), record.get("boylam")
    if lat is None or lon is None:
        return False
    return (
        ANKARA.min_lat <= lat <= ANKARA.max_lat
        and ANKARA.min_lon <= lon <= ANKARA.max_lon
    )


def _trim_epdk() -> None:
    """Keep only the Ankara stations: the full dump is ~16 MB."""
    payload = json.loads((CACHE_DIR / "epdk.json").read_text(encoding="utf-8"))
    total = len(payload["data"])

    payload["data"] = [r for r in payload["data"] if _inside_ankara(r)]
    payload["numRows"] = len(payload["data"])

    target = FIXTURES_DIR / "epdk.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"epdk      : {payload['numRows']} of {total} stations -> {target.name}")


def _copy_overpass() -> None:
    """The Overpass response is already area-scoped and small enough to ship."""
    source = CACHE_DIR / "overpass_ankara.json"
    target = FIXTURES_DIR / "overpass_ankara.json"
    target.write_bytes(source.read_bytes())
    print(f"overpass  : copied {target.stat().st_size // 1024} KB -> {target.name}")


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    _trim_epdk()
    _copy_overpass()


if __name__ == "__main__":
    main()