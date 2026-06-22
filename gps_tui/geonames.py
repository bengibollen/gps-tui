from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path


EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class City:
    geoname_id: int
    name: str
    ascii_name: str
    lat: float
    lon: float
    country_code: str
    admin1_code: str
    population: int


@dataclass(frozen=True)
class LocationResult:
    city: City
    distance_km: float
    country_name: str | None
    admin1_name: str | None

    @property
    def display_name(self) -> str:
        parts = [self.city.name]
        if self.admin1_name:
            parts.append(self.admin1_name)
        if self.country_name:
            parts.append(self.country_name)
        elif self.city.country_code:
            parts.append(self.city.country_code)
        return ", ".join(parts)

    @property
    def distance_text(self) -> str:
        if self.distance_km < 1:
            return f"{self.distance_km * 1000:.0f} m"
        if self.distance_km < 10:
            return f"{self.distance_km:.1f} km"
        return f"{self.distance_km:.0f} km"


class GeoNamesIndex:
    def __init__(
        self,
        cities: list[City],
        countries: dict[str, str] | None = None,
        admin1: dict[str, str] | None = None,
    ) -> None:
        self.cities = cities
        self.countries = countries or {}
        self.admin1 = admin1 or {}
        self.grid: dict[tuple[int, int], list[City]] = {}
        for city in cities:
            self.grid.setdefault(_cell(city.lat, city.lon), []).append(city)

    @classmethod
    def from_dir(cls, data_dir: Path) -> "GeoNamesIndex":
        return cls(
            cities=load_cities(data_dir / "cities1000.txt"),
            countries=load_countries(data_dir / "countryInfo.txt"),
            admin1=load_admin1(data_dir / "admin1CodesASCII.txt"),
        )

    def nearest(self, lat: float, lon: float, max_radius_km: float = 250.0) -> LocationResult | None:
        if not self.cities:
            return None

        best_city: City | None = None
        best_distance = math.inf
        max_degrees = max(1, int(math.ceil(max_radius_km / 111.0)) + 1)
        base_lat, base_lon = _cell(lat, lon)

        for radius in range(max_degrees + 1):
            for lat_cell in range(base_lat - radius, base_lat + radius + 1):
                for lon_cell in range(base_lon - radius, base_lon + radius + 1):
                    if radius > 0 and abs(lat_cell - base_lat) != radius and abs(lon_cell - base_lon) != radius:
                        continue
                    for city in self.grid.get((lat_cell, lon_cell), []):
                        distance = haversine_km(lat, lon, city.lat, city.lon)
                        if distance < best_distance:
                            best_city = city
                            best_distance = distance
            if best_city is not None and best_distance <= radius * 111.0:
                break

        if best_city is None or best_distance > max_radius_km:
            return None
        return LocationResult(
            city=best_city,
            distance_km=best_distance,
            country_name=self.countries.get(best_city.country_code),
            admin1_name=self.admin1.get(f"{best_city.country_code}.{best_city.admin1_code}"),
        )


def load_cities(path: Path) -> list[City]:
    if not path.exists():
        return []
    cities: list[City] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.rstrip("\n")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) < 15:
                continue
            city = _parse_city(fields)
            if city is not None:
                cities.append(city)
    return cities


def load_countries(path: Path) -> dict[str, str]:
    countries: dict[str, str] = {}
    if not path.exists():
        return countries
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) >= 5:
                countries[fields[0]] = fields[4]
    return countries


def load_admin1(path: Path) -> dict[str, str]:
    admin1: dict[str, str] = {}
    if not path.exists():
        return admin1
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.rstrip("\n")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) >= 2:
                admin1[fields[0]] = fields[1]
    return admin1


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def main() -> None:
    parser = argparse.ArgumentParser(description="Lookup nearest GeoNames cities1000 place.")
    parser.add_argument("lat", type=float, help="latitude")
    parser.add_argument("lon", type=float, help="longitude")
    parser.add_argument("--data-dir", type=Path, default=Path("data/geonames"), help="GeoNames data directory")
    args = parser.parse_args()

    index = GeoNamesIndex.from_dir(args.data_dir)
    result = index.nearest(args.lat, args.lon)
    if result is None:
        raise SystemExit("No nearby GeoNames city found. Is data/geonames populated?")
    print(f"{result.display_name} ({result.distance_text})")


def _parse_city(fields: list[str]) -> City | None:
    try:
        return City(
            geoname_id=int(fields[0]),
            name=fields[1],
            ascii_name=fields[2],
            lat=float(fields[4]),
            lon=float(fields[5]),
            country_code=fields[8],
            admin1_code=fields[10],
            population=int(fields[14] or 0),
        )
    except ValueError:
        return None


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat), math.floor(lon)


if __name__ == "__main__":
    main()
