"""Temporary: measure how many charging stations Open Charge Map has per area."""

import httpx

from charger_finder.config import get_ocm_api_key

AREAS = {
    "Ankara (Cankaya)": (39.9080, 32.8300),
    "Istanbul (Kadikoy)": (40.9900, 29.0300),
    "Goteborg (centrum)": (57.7000, 11.9700),
}

RADIUS_KM = 10
MAX_RESULTS = 1000


def count_stations(latitude: float, longitude: float) -> int:
    """Return how many stations OCM reports within RADIUS_KM of a point."""
    response = httpx.get(
        "https://api.openchargemap.io/v3/poi",
        params={
            "output": "json",
            "latitude": latitude,
            "longitude": longitude,
            "distance": RADIUS_KM,
            "distanceunit": "KM",
            "maxresults": MAX_RESULTS,
            "compact": "true",
            "verbose": "false",
        },
        headers={"X-API-Key": get_ocm_api_key()},
        timeout=30.0,
    )
    response.raise_for_status()
    return len(response.json())


def main() -> None:
    for name, (lat, lon) in AREAS.items():
        count = count_stations(lat, lon)
        print(f"{name:20} {count:>5} stations within {RADIUS_KM} km")


if __name__ == "__main__":
    main()