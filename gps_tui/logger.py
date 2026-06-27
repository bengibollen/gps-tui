from __future__ import annotations

import argparse
import json
import signal
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gpsd import GpsdClient


DEFAULT_LOG_DIR = Path("/var/log/gps")


@dataclass
class LoggerConfig:
    host: str = "localhost"
    port: int = 2947
    log_dir: Path = DEFAULT_LOG_DIR
    interval_seconds: float = 1.0
    flush: bool = True


class DailyJsonlWriter:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.current_date: str | None = None
        self.file: Any = None

    def close(self) -> None:
        if self.file is not None:
            self.file.close()
            self.file = None

    def write(self, record: dict[str, Any], flush: bool = True) -> Path:
        timestamp = _parse_record_time(record) or datetime.now(timezone.utc)
        date = timestamp.strftime("%Y-%m-%d")
        if date != self.current_date:
            self._open(date)
        assert self.file is not None
        self.file.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        if flush:
            self.file.flush()
        return self.log_dir / f"{date}.jsonl"

    def _open(self, date: str) -> None:
        self.close()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_date = date
        self.file = (self.log_dir / f"{date}.jsonl").open("a", encoding="utf-8")


class GpsLogger:
    def __init__(self, config: LoggerConfig) -> None:
        self.config = config
        self.writer = DailyJsonlWriter(config.log_dir)
        self.running = True
        self.latest_fix: dict[str, Any] | None = None
        self.last_written_fix_key: tuple[Any, ...] | None = None

    def stop(self, *_args: object) -> None:
        self.running = False

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        self.writer.write(_marker("service_start", self.config), flush=True)
        try:
            while self.running:
                self._run_session()
                if self.running:
                    time.sleep(2.0)
        finally:
            self.writer.write(_marker("service_stop", self.config), flush=True)
            self.writer.close()

    def _run_session(self) -> None:
        client = GpsdClient(self.config.host, self.config.port)
        next_sample = time.monotonic()
        for report in client.reports():
            if not self.running:
                return
            if report.get("class") == "ERROR":
                self.writer.write(
                    {
                        "type": "event",
                        "event": "gpsd_error",
                        "time": _now_iso(),
                        "message": report.get("message", "gpsd error"),
                    },
                    flush=self.config.flush,
                )
                return
            if report.get("class") == "TPV" and _has_fix(report):
                self.latest_fix = report

            now = time.monotonic()
            if now >= next_sample:
                self._write_latest_fix()
                next_sample = now + self.config.interval_seconds

    def _write_latest_fix(self) -> None:
        if self.latest_fix is None:
            return
        key = _fix_key(self.latest_fix)
        if key == self.last_written_fix_key:
            return
        self.writer.write(_fix_record(self.latest_fix), flush=self.config.flush)
        self.last_written_fix_key = key


def main() -> None:
    args = _parse_args()
    config = LoggerConfig(
        host=args.host,
        port=args.port,
        log_dir=args.log_dir,
        interval_seconds=args.interval,
        flush=not args.no_flush,
    )
    try:
        GpsLogger(config).run_forever()
    except PermissionError as exc:
        print(f"gps logger permission error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except OSError as exc:
        print(f"gps logger error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log gpsd fixes to daily JSONL files.")
    parser.add_argument("--host", default="localhost", help="gpsd host, default localhost")
    parser.add_argument("--port", type=int, default=2947, help="gpsd port, default 2947")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR, help="log directory, default /var/log/gps")
    parser.add_argument("--interval", type=float, default=1.0, help="sample interval in seconds, default 1")
    parser.add_argument("--no-flush", action="store_true", help="do not flush after each record")
    return parser.parse_args()


def _marker(event: str, config: LoggerConfig) -> dict[str, Any]:
    return {
        "type": "event",
        "event": event,
        "time": _now_iso(),
        "host": socket.gethostname(),
        "gpsd": {"host": config.host, "port": config.port},
        "interval_seconds": config.interval_seconds,
    }


def _fix_record(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "fix",
        "time": report.get("time") or _now_iso(),
        "mode": report.get("mode"),
        "lat": report.get("lat"),
        "lon": report.get("lon"),
        "alt_m": report.get("altMSL", report.get("altHAE", report.get("alt"))),
        "speed_mps": report.get("speed"),
        "track_deg": report.get("track"),
        "climb_mps": report.get("climb"),
        "eph_m": report.get("eph"),
        "epv_m": report.get("epv"),
        "sep_m": report.get("sep"),
        "device": report.get("device"),
        "raw": report,
    }


def _has_fix(report: dict[str, Any]) -> bool:
    try:
        mode = int(report.get("mode", 0) or 0)
    except (TypeError, ValueError):
        mode = 0
    return mode >= 2 and report.get("lat") is not None and report.get("lon") is not None


def _fix_key(report: dict[str, Any]) -> tuple[Any, ...]:
    return (
        report.get("time"),
        report.get("lat"),
        report.get("lon"),
        report.get("altMSL", report.get("altHAE", report.get("alt"))),
        report.get("mode"),
    )


def _parse_record_time(record: dict[str, Any]) -> datetime | None:
    value = record.get("time")
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


if __name__ == "__main__":
    main()
