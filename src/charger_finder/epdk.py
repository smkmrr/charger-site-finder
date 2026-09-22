"""The EPDK source: fetch the national station registry and validate it."""

import logging
from typing import Any

from pydantic import ValidationError

from charger_finder.http_client import fetch_json
from charger_finder.models import Rejection, Station

logger = logging.getLogger(__name__)

SOURCE = "epdk"
URL = "https://apigateway.epdk.gov.tr/sarjIstasyonlari"


def _to_station(raw: dict[str, Any]) -> Station:
    """Map one EPDK record onto our own Station model."""
    return Station(
        source=SOURCE,
        source_id=raw["sarjIstasyonuNo"],
        name=raw["sarjIstasyonuAdi"],
        brand=raw.get("marka"),
        address=raw.get("adres"),
        access_type=raw["hizmetSekli"],
        latitude=raw["enlem"],
        longitude=raw["boylam"],
        sockets=[
            {"socket_type": s["soketTipi"], "power_kw": s["soketGucu"]}
            for s in raw.get("soketler") or []
        ],
    )


def load_stations() -> tuple[list[Station], list[Rejection]]:
    """Return every EPDK station that validates, plus the ones that did not."""
    payload = fetch_json(SOURCE, URL, json={})
    records = payload["data"]

    stations: list[Station] = []
    rejected: list[Rejection] = []

    for raw in records:
        try:
            stations.append(_to_station(raw))
        except (ValidationError, KeyError, TypeError) as exc:
            rejected.append(
                Rejection(
                    source=SOURCE,
                    identifier=str(raw.get("sarjIstasyonuNo", "<no id>")),
                    reason=str(exc).replace("\n", " | ")[:200],
                )
            )

    logger.info(
        "%s: %d records in, %d valid, %d rejected",
        SOURCE,
        len(records),
        len(stations),
        len(rejected),
    )
    for rejection in rejected[:5]:
        logger.warning("%s rejected %s — %s", SOURCE, rejection.identifier, rejection.reason)

    return stations, rejected