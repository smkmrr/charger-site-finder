"""Configuration: environment, search area, business thresholds and paths."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class BoundingBox:
    """A rectangular search area in WGS84 degrees."""

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


ANKARA = BoundingBox(min_lat=39.85, min_lon=32.60, max_lat=40.05, max_lon=33.00)

AREAS = {"ankara": ANKARA}

# --- business rules ------------------------------------------------------

#: Brands we distribute. Matched case-insensitively against EPDK's `marka`.
OWN_BRANDS = ("trugo", "zes")

#: A candidate is dropped when one of OUR brands already has a DC socket
#: above this power within the radius: there is nothing left to sell.
OWN_BRAND_POWER_KW = 60.0

#: Other brands never exclude a candidate, but a DC socket at or above this
#: power is reported on the card as commercial context.
COMPETITOR_POWER_KW = 120.0

#: Straight-line distance from the candidate's own coordinate.
SEARCH_RADIUS_KM = 0.2

#: Refetch a source when its cached response is older than this.
CACHE_MAX_AGE_DAYS = 7

#: Candidate types we look for. overpass.py maps these to OSM tags.
POI_CATEGORIES = ("mall", "hospital", "clinic", "business_centre")


def get_ocm_api_key() -> str:
    """Return the Open Charge Map API key, or fail with a clear message."""
    key = os.getenv("OCM_API_KEY")
    if not key:
        raise RuntimeError(
            "OCM_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return key