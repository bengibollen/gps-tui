from __future__ import annotations

import argparse
import curses
import threading
import time
from pathlib import Path
from queue import Queue
from typing import Any

from .geonames import GeoNamesIndex, haversine_km
from .gpsd import GpsdClient
from .model import GpsState, Location
from .sim import simulated_reports
from .ui import run_ui


def main() -> None:
    args = _parse_args()
    queue: Queue[dict[str, Any]] = Queue(maxsize=100)
    state = GpsState(source="simulated" if args.simulate else f"{args.host}:{args.port}")

    if args.simulate:
        iterator = simulated_reports()
    else:
        iterator = GpsdClient(args.host, args.port).reports()

    worker = threading.Thread(target=_reader, args=(iterator, queue), daemon=True)
    worker.start()

    geonames = _load_geonames(args.geonames_dir)
    if geonames is not None:
        location_worker = threading.Thread(target=_location_reader, args=(state, geonames), daemon=True)
        location_worker.start()

    curses.wrapper(
        run_ui,
        state,
        queue,
        args.theme,
        args.refresh,
    )


def _reader(iterator: Any, queue: Queue[dict[str, Any]]) -> None:
    for report in iterator:
        try:
            queue.put(report, timeout=0.5)
        except Exception:
            pass


def _location_reader(state: GpsState, geonames: GeoNamesIndex) -> None:
    last_lookup: tuple[float, float] | None = None
    while True:
        fix = state.fix
        if fix.lat is None or fix.lon is None or fix.mode < 2:
            time.sleep(2.0)
            continue

        should_lookup = last_lookup is None or haversine_km(last_lookup[0], last_lookup[1], fix.lat, fix.lon) >= 1.0
        if should_lookup:
            result = geonames.nearest(fix.lat, fix.lon)
            if result is not None:
                state.location = Location(name=result.display_name, distance_km=result.distance_km)
                last_lookup = (fix.lat, fix.lon)

        time.sleep(30.0)


def _load_geonames(data_dir: Path | None) -> GeoNamesIndex | None:
    if data_dir is None:
        return None
    cities_path = data_dir / "cities1000.txt"
    if not cities_path.exists():
        return None
    index = GeoNamesIndex.from_dir(data_dir)
    return index if index.cities else None


def _parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="A btop-inspired GPS dashboard for gpsd.")
    parser.add_argument("--host", default="localhost", help="gpsd host")
    parser.add_argument("--port", type=int, default=2947, help="gpsd port")
    parser.add_argument("--simulate", action="store_true", help="use generated GPS data")
    parser.add_argument("--theme", type=Path, default=root / "themes" / "btop-ish.toml", help="theme TOML file")
    parser.add_argument("--refresh", type=float, default=0.5, help="screen refresh interval in seconds")
    parser.add_argument(
        "--geonames-dir",
        type=Path,
        default=root / "data" / "geonames",
        help="GeoNames data directory, default data/geonames",
    )
    return parser.parse_args()
