"""Shared data models. Every source is normalised into these types."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AccessType(str, Enum):
    """How a station may be used, as reported by EPDK."""

    PUBLIC = "HALKA_ACIK"
    PRIVATE = "OZEL"


class SocketType(str, Enum):
    """Current type of a socket."""

    AC = "AC"
    DC = "DC"


class GeoRecord(BaseModel):
    """Anything with a name and a position, from any source."""

    model_config = ConfigDict(frozen=True)

    source: str
    source_id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Socket(BaseModel):
    """One socket on a station."""

    model_config = ConfigDict(frozen=True)

    socket_type: SocketType
    power_kw: float = Field(gt=0)


class Station(GeoRecord):
    """An existing charging station."""

    brand: str | None = None
    address: str | None = None
    access_type: AccessType
    sockets: tuple[Socket, ...] = ()

    @property
    def max_dc_power_kw(self) -> float:
        """Highest DC socket power, or 0.0 if the station has no DC socket."""
        dc_powers = [s.power_kw for s in self.sockets if s.socket_type is SocketType.DC]
        return max(dc_powers) if dc_powers else 0.0


class Candidate(GeoRecord):
    """A location that might host a new station."""

    category: str | None = None


class Rejection(BaseModel):
    """A record that failed validation, kept instead of being dropped."""

    model_config = ConfigDict(frozen=True)

    source: str
    identifier: str
    reason: str


class LocationCard(BaseModel):
    """A candidate that survived screening, as handed to the sales team."""

    model_config = ConfigDict(frozen=True)

    name: str
    category: str | None
    latitude: float
    longitude: float
    source_id: str
    own_brand_note: str
    competitor_count: int
    competitor_brands: str
    competitor_max_kw: float
    priority: str
    next_step: str