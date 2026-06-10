from __future__ import annotations

import json
import socket
import time
from collections.abc import Iterator
from typing import Any


WATCH_COMMAND = '?WATCH={"enable":true,"json":true};\n'


class GpsdClient:
    def __init__(self, host: str = "localhost", port: int = 2947, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def reports(self) -> Iterator[dict[str, Any]]:
        while True:
            try:
                yield from self._connect_and_read()
            except OSError as exc:
                yield {"class": "ERROR", "message": f"gpsd connection failed: {exc}"}
                time.sleep(2.0)

    def _connect_and_read(self) -> Iterator[dict[str, Any]]:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            sock.sendall(WATCH_COMMAND.encode("ascii"))
            with sock.makefile("r", encoding="utf-8", newline="\n") as stream:
                for line in stream:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        report = json.loads(line)
                    except json.JSONDecodeError:
                        yield {"class": "ERROR", "message": "gpsd sent invalid JSON"}
                        continue
                    if isinstance(report, dict):
                        yield report


def apply_report(state: Any, report: dict[str, Any]) -> None:
    report_class = report.get("class")
    state.connected = report_class != "ERROR"

    if report_class == "TPV":
        state.apply_tpv(report)
    elif report_class == "SKY":
        state.apply_sky(report)
    elif report_class == "ERROR":
        state.message = str(report.get("message", "gpsd error"))
    elif report_class in {"VERSION", "DEVICES", "WATCH"}:
        state.message = f"gpsd {str(report_class).lower()}"
