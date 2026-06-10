from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any


@dataclass
class Fix:
    mode: int = 0
    status: int | None = None
    time: str | None = None
    lat: float | None = None
    lon: float | None = None
    alt_m: float | None = None
    speed_mps: float | None = None
    track_deg: float | None = None
    climb_mps: float | None = None
    eph_m: float | None = None
    epv_m: float | None = None
    sep_m: float | None = None
    device: str | None = None

    @classmethod
    def from_tpv(cls, data: dict[str, Any]) -> "Fix":
        return cls(
            mode=int(data.get("mode", 0) or 0),
            status=_int_or_none(data.get("status")),
            time=_str_or_none(data.get("time")),
            lat=_float_or_none(data.get("lat")),
            lon=_float_or_none(data.get("lon")),
            alt_m=_float_or_none(data.get("altMSL", data.get("altHAE", data.get("alt")))),
            speed_mps=_float_or_none(data.get("speed")),
            track_deg=_float_or_none(data.get("track")),
            climb_mps=_float_or_none(data.get("climb")),
            eph_m=_float_or_none(data.get("eph")),
            epv_m=_float_or_none(data.get("epv")),
            sep_m=_float_or_none(data.get("sep")),
            device=_str_or_none(data.get("device")),
        )

    @property
    def speed_kmh(self) -> float | None:
        if self.speed_mps is None:
            return None
        return self.speed_mps * 3.6

    @property
    def mode_label(self) -> str:
        return {0: "unknown", 1: "no fix", 2: "2D", 3: "3D"}.get(self.mode, str(self.mode))


@dataclass
class Satellite:
    prn: int | None = None
    gnssid: int | None = None
    svid: int | None = None
    signal_db: float | None = None
    elevation_deg: float | None = None
    azimuth_deg: float | None = None
    used: bool = False
    health: int | None = None

    @classmethod
    def from_sky_item(cls, data: dict[str, Any]) -> "Satellite":
        return cls(
            prn=_int_or_none(data.get("PRN")),
            gnssid=_int_or_none(data.get("gnssid")),
            svid=_int_or_none(data.get("svid")),
            signal_db=_float_or_none(data.get("ss")),
            elevation_deg=_float_or_none(data.get("el")),
            azimuth_deg=_float_or_none(data.get("az")),
            used=bool(data.get("used", False)),
            health=_int_or_none(data.get("health")),
        )

    @property
    def label(self) -> str:
        if self.prn is not None:
            return f"G{self.prn:02d}"
        if self.svid is not None:
            return f"S{self.svid:02d}"
        return "--"


@dataclass
class Sky:
    time: str | None = None
    n_sat: int | None = None
    u_sat: int | None = None
    hdop: float | None = None
    vdop: float | None = None
    pdop: float | None = None
    satellites: list[Satellite] = field(default_factory=list)

    @classmethod
    def from_sky(cls, data: dict[str, Any]) -> "Sky":
        raw_sats = data.get("satellites", [])
        satellites = [
            Satellite.from_sky_item(item)
            for item in raw_sats
            if isinstance(item, dict)
        ]
        satellites.sort(key=lambda sat: (not sat.used, -(sat.signal_db or 0.0), sat.label))
        return cls(
            time=_str_or_none(data.get("time")),
            n_sat=_int_or_none(data.get("nSat")),
            u_sat=_int_or_none(data.get("uSat")),
            hdop=_float_or_none(data.get("hdop")),
            vdop=_float_or_none(data.get("vdop")),
            pdop=_float_or_none(data.get("pdop")),
            satellites=satellites,
        )


@dataclass
class GpsState:
    fix: Fix = field(default_factory=Fix)
    sky: Sky = field(default_factory=Sky)
    connected: bool = False
    source: str = "gpsd"
    message: str = "waiting for data"
    last_update: datetime | None = None
    min_eph_m: float | None = None
    max_speed_kmh: float | None = None

    def apply_tpv(self, data: dict[str, Any]) -> None:
        self.fix = Fix.from_tpv(data)
        self._touch()
        if self.fix.eph_m is not None:
            self.min_eph_m = _min_optional(self.min_eph_m, self.fix.eph_m)
        if self.fix.speed_kmh is not None:
            self.max_speed_kmh = _max_optional(self.max_speed_kmh, self.fix.speed_kmh)

    def apply_sky(self, data: dict[str, Any]) -> None:
        self.sky = Sky.from_sky(data)
        self._touch()

    def reset_stats(self) -> None:
        self.min_eph_m = None
        self.max_speed_kmh = None

    def _touch(self) -> None:
        self.last_update = datetime.now(timezone.utc)
        self.message = "receiving data"


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _min_optional(left: float | None, right: float) -> float:
    return right if left is None else min(left, right)


def _max_optional(left: float | None, right: float) -> float:
    return right if left is None else max(left, right)
