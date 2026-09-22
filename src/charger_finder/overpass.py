"""The OpenStreetMap source: candidate locations via the Overpass API."""

import logging
from typing import Any

from pydantic import ValidationError

from charger_finder.config import BoundingBox
from charger_finder.http_client import fetch_json
from charger_finder.models import Candidate, Rejection

logger = logging.getLogger(__name__)

SOURCE = "osm"
URL = "https://overpass-api.de/api/interpreter"

#: Identify this client to Overpass, as their usage policy asks.
HEADERS = {"User-Agent": "charger-site-finder/0.1 (student project)"}

#: Our own category names mapped onto the OSM tags that express them.
TAG_FILTERS = {
    "mall": ("shop", "mall"),
    "hospital": ("amenity", "hospital"),
    "clinic": ("amenity", "clinic"),
    "business_centre": ("building", "office"),
}


def _build_query(box: BoundingBox) -> str:
    """Build an Overpass QL query for every category inside the bounding box."""
    bbox = f"{box.min_lat},{box.min_lon},{box.max_lat},{box.max_lon}"
    clauses = "\n  ".join(
        f'nwr["{key}"="{value}"]({bbox});' for key, value in TAG_FILTERS.values()
    )
    return f"[out:json][timeout:180];\n(\n  {clauses}\n);\nout center tags;"


def _category_of(tags: dict[str, str]) -> str | None:
    """Return the first of our categories whose tag this element carries."""
    for category, (key, value) in TAG_FILTERS.items():
        if tags.get(key) == value:
            return category
    return None


def _to_candidate(element: dict[str, Any]) -> Candidate:
    """Map one Overpass element onto our own Candidate model."""
    tags = element.get("tags") or {}
    centre = element.get("center") or element
    return Candidate(
        source=SOURCE,
        source_id=f"{element['type']}/{element['id']}",
        name=tags["name"],
        latitude=centre["lat"],
        longitude=centre["lon"],
        category=_category_of(tags),
    )


def load_candidates(
    area_name: str, box: BoundingBox
) -> tuple[list[Candidate], list[Rejection]]:
    """Return candidate locations inside `box`, plus the records that failed."""
    payload = fetch_json(
        f"overpass_{area_name}",
        URL,
        method="POST",
        data={"data": _build_query(box)},
        headers=HEADERS,
    )
    elements = payload["elements"]

    candidates: list[Candidate] = []
    rejected: list[Rejection] = []

    for element in elements:
        try:
            candidates.append(_to_candidate(element))
        except (ValidationError, KeyError, TypeError) as exc:
            rejected.append(
                Rejection(
                    source=SOURCE,
                    identifier=f"{element.get('type')}/{element.get('id')}",
                    reason=str(exc).replace("\n", " | ")[:200],
                )
            )

    logger.info(
        "%s: %d elements in, %d valid, %d rejected",
        SOURCE,
        len(elements),
        len(candidates),
        len(rejected),
    )
    return candidates, rejected