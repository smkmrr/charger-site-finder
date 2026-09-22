"""Great-circle distance and spatial filtering on WGS84 coordinates."""

from collections.abc import Iterable
from math import asin, cos, radians, sin, sqrt
from typing import TypeVar

from charger_finder.config import BoundingBox
from charger_finder.models import GeoRecord

#: Mean Earth radius (IUGG), in kilometres.
EARTH_RADIUS_KM = 6371.0088

T = TypeVar("T", bound=GeoRecord)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in kilometres."""
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = phi2 - phi1
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def in_bounding_box(record: GeoRecord, box: BoundingBox) -> bool:
    """Whether a record falls inside the rectangular search area."""
    return (
        box.min_lat <= record.latitude <= box.max_lat
        and box.min_lon <= record.longitude <= box.max_lon
    )


def within_radius(centre: GeoRecord, records: Iterable[T], radius_km: float) -> list[T]:
    """Return the records lying at most `radius_km` from `centre`."""
    return [
        record
        for record in records
        if haversine_km(
            centre.latitude, centre.longitude, record.latitude, record.longitude
        )
        <= radius_km
    ]