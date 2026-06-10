from __future__ import annotations

import argparse
import curses
import threading
from pathlib import Path
from queue import Queue
from typing import Any

from .gpsd import GpsdClient
from .model import GpsState
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


def _parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="A btop-inspired GPS dashboard for gpsd.")
    parser.add_argument("--host", default="localhost", help="gpsd host")
    parser.add_argument("--port", type=int, default=2947, help="gpsd port")
    parser.add_argument("--simulate", action="store_true", help="use generated GPS data")
    parser.add_argument("--theme", type=Path, default=root / "themes" / "btop-ish.toml", help="theme TOML file")
    parser.add_argument("--refresh", type=float, default=0.5, help="screen refresh interval in seconds")
    return parser.parse_args()
