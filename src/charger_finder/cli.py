"""Command-line entry point: screen one configured area and write the results."""

import argparse
import logging
import sys

from charger_finder import config
from charger_finder.distance import in_bounding_box
from charger_finder.epdk import load_stations
from charger_finder.overpass import load_candidates
from charger_finder.reporting import log_summary, write_cards, write_rejections
from charger_finder.screening import public_only, screen

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define and read the command-line options."""
    parser = argparse.ArgumentParser(
        prog="charger-finder",
        description="Find candidate locations for new EV charging stations.",
    )
    parser.add_argument(
        "--area",
        default="ankara",
        choices=sorted(config.AREAS),
        help="which configured search area to screen (default: %(default)s)",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=config.SEARCH_RADIUS_KM,
        help="an existing station within this distance covers a candidate "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show DEBUG level logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline. Returns a process exit code."""
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(name)s: %(message)s",
    )

    box = config.AREAS[args.area]
    logger.info("screening %s within %.0f m", args.area, args.radius_km * 1000)

    try:
        stations, station_rejections = load_stations()
        candidates, candidate_rejections = load_candidates(args.area, box)
    except Exception as exc:
        logger.error("could not load the sources: %s", exc)
        return 1

    usable = [s for s in public_only(stations) if in_bounding_box(s, box)]
    cards = screen(candidates, usable, args.radius_km)
    rejections = [*station_rejections, *candidate_rejections]

    write_cards(cards, args.area)
    write_rejections(rejections, args.area)
    log_summary(
        area_name=args.area,
        stations_total=len(stations),
        stations_used=len(usable),
        candidates=len(candidates),
        cards=len(cards),
        rejections=len(rejections),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())