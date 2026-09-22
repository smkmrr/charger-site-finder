"""Write screening results to disk and summarise the run."""

import csv
import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from charger_finder.config import OUTPUT_DIR
from charger_finder.models import LocationCard, Rejection

logger = logging.getLogger(__name__)

#: Column order for the sales output. Most useful column first.
CARD_FIELDS = [
    "priority",
    "name",
    "category",
    "latitude",
    "longitude",
    "own_brand_note",
    "competitor_count",
    "competitor_brands",
    "competitor_max_kw",
    "source_id",
    "next_step",
]

REJECTION_FIELDS = ["source", "identifier", "reason"]


def _timestamp() -> str:
    """UTC timestamp for output filenames, sortable as text."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _write_csv(path: Path, fieldnames: list[str], rows: Sequence[BaseModel]) -> None:
    """Write Pydantic models as CSV rows, keeping only `fieldnames`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.model_dump())


def write_cards(cards: Sequence[LocationCard], area_name: str) -> Path:
    """Write the sales cards, highest priority first."""
    path = OUTPUT_DIR / f"cards_{area_name}_{_timestamp()}.csv"
    ordered = sorted(cards, key=lambda card: (card.priority != "HIGH", card.name))
    _write_csv(path, CARD_FIELDS, ordered)
    logger.info("wrote %d cards to %s", len(ordered), path.name)
    return path


def write_rejections(rejections: Sequence[Rejection], area_name: str) -> Path | None:
    """Write the quarantined records, or nothing if there were none."""
    if not rejections:
        logger.info("no rejected records to write")
        return None
    path = OUTPUT_DIR / f"rejected_{area_name}_{_timestamp()}.csv"
    _write_csv(path, REJECTION_FIELDS, rejections)
    logger.warning("wrote %d rejected records to %s", len(rejections), path.name)
    return path


def log_summary(
    area_name: str,
    stations_total: int,
    stations_used: int,
    candidates: int,
    cards: int,
    rejections: int,
) -> None:
    """Log one block that explains what the run actually did."""
    logger.info("--- run summary: %s ---", area_name)
    logger.info("stations from EPDK      : %d", stations_total)
    logger.info("public, inside the area : %d", stations_used)
    logger.info("candidates from OSM     : %d", candidates)
    logger.info("cards written           : %d", cards)
    logger.info("records quarantined     : %d", rejections)