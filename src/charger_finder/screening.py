"""Business rules: decide which candidates are worth a sales visit."""

import logging
from collections.abc import Sequence

from charger_finder.config import COMPETITOR_POWER_KW, OWN_BRANDS, OWN_BRAND_POWER_KW
from charger_finder.models import AccessType, Candidate, LocationCard, Station
from charger_finder.distance import within_radius

logger = logging.getLogger(__name__)

NEXT_STEP = (
    "Contact the site manager, gauge interest, send an engineer to cost the "
    "installation, then prepare a commercial offer."
)


def _is_own_brand(station: Station) -> bool:
    """Whether the station belongs to a brand we distribute."""
    return (station.brand or "").casefold() in OWN_BRANDS


def public_only(stations: Sequence[Station]) -> list[Station]:
    """Keep the stations the public can actually use."""
    return [s for s in stations if s.access_type is AccessType.PUBLIC]


def _describe_own_brand(stations: Sequence[Station]) -> str:
    """Describe non-blocking own-brand stations, for context on the card."""
    if not stations:
        return ""
    return "; ".join(
        f"{s.brand} {s.max_dc_power_kw:.0f}kW" for s in stations
    )


def screen(
    candidates: Sequence[Candidate],
    stations: Sequence[Station],
    radius_km: float,
) -> list[LocationCard]:
    """Turn candidates into sales cards, dropping the ones already covered."""
    cards: list[LocationCard] = []
    blocked = 0

    for candidate in candidates:
        nearby = within_radius(candidate, stations, radius_km)

        own = [s for s in nearby if _is_own_brand(s)]
        blocking = [s for s in own if s.max_dc_power_kw > OWN_BRAND_POWER_KW]
        if blocking:
            blocked += 1
            continue

        competitors = [
            s
            for s in nearby
            if not _is_own_brand(s) and s.max_dc_power_kw >= COMPETITOR_POWER_KW
        ]
        competitor_max = max((s.max_dc_power_kw for s in competitors), default=0.0)

        cards.append(
            LocationCard(
                name=candidate.name,
                category=candidate.category,
                latitude=candidate.latitude,
                longitude=candidate.longitude,
                source_id=candidate.source_id,
                own_brand_note=_describe_own_brand(own),
                competitor_count=len(competitors),
                competitor_brands=", ".join(sorted({s.brand or "?" for s in competitors})),
                competitor_max_kw=competitor_max,
                priority="HIGH" if not competitors else "MEDIUM",
                next_step=NEXT_STEP,
            )
        )

    logger.info(
        "screening: %d candidates in, %d cards out, %d already covered by our brands",
        len(candidates),
        len(cards),
        blocked,
    )
    return cards