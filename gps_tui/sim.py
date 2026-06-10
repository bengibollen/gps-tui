from __future__ import annotations

import math
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any


def simulated_reports() -> Iterator[dict[str, Any]]:
    step = 0
    while True:
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        lat = 59.3293 + math.sin(step / 90.0) * 0.0018
        lon = 18.0686 + math.cos(step / 80.0) * 0.0022
        speed = 2.5 + math.sin(step / 18.0) * 1.4
        eph = 3.5 + abs(math.sin(step / 30.0)) * 5.0

        yield {
            "class": "TPV",
            "device": "simulated",
            "mode": 3,
            "time": now,
            "lat": lat,
            "lon": lon,
            "altMSL": 34.0 + math.sin(step / 40.0) * 2.0,
            "eph": eph,
            "epv": eph * 1.8,
            "sep": eph * 2.1,
            "speed": max(speed, 0.0),
            "track": (step * 4.0) % 360.0,
            "climb": math.sin(step / 16.0) * 0.3,
        }

        yield {
            "class": "SKY",
            "time": now,
            "nSat": 14,
            "uSat": 8,
            "hdop": 0.8 + abs(math.sin(step / 33.0)) * 0.8,
            "vdop": 1.2 + abs(math.cos(step / 28.0)) * 1.0,
            "pdop": 1.7 + abs(math.sin(step / 24.0)) * 1.4,
            "satellites": [_satellite(step, index) for index in range(14)],
        }

        step += 1
        time.sleep(0.5)


def _satellite(step: int, index: int) -> dict[str, Any]:
    wave = math.sin(step / 9.0 + index * 0.72)
    signal = max(0.0, 29.0 + wave * 18.0 + (index % 5) * 2.2)
    return {
        "PRN": index + 1,
        "ss": round(signal, 1),
        "el": round(12.0 + ((index * 13 + step) % 78), 1),
        "az": round((index * 29 + step * 3) % 360, 1),
        "used": index in {0, 1, 2, 4, 5, 7, 9, 11},
    }
