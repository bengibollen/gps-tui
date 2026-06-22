from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Sentence:
    raw: str
    payload: str
    checksum: str | None
    checksum_ok: bool | None

    @property
    def fields(self) -> list[str]:
        return self.payload.split(",")

    @property
    def kind(self) -> str:
        fields = self.fields
        return fields[0] if fields else ""


@dataclass(frozen=True)
class Ack:
    command: str
    flag: int | None

    @property
    def ok(self) -> bool:
        return self.flag == 3

    @property
    def message(self) -> str:
        return {
            0: "invalid command or packet",
            1: "unsupported command",
            2: "valid command, action failed",
            3: "valid command, action succeeded",
        }.get(self.flag, "unknown acknowledgement")


@dataclass(frozen=True)
class LocusStatus:
    raw: str
    serial: int | None
    log_type: int | None
    mode: int | None
    content: int | None
    interval: int | None
    distance: int | None
    speed: int | None
    status: int | None
    records: int | None
    percent_used: int | None

    @classmethod
    def from_sentence(cls, sentence: Sentence) -> "LocusStatus":
        fields = sentence.fields
        values = fields[1:]
        return cls(
            raw=sentence.raw,
            serial=_int_at(values, 0),
            log_type=_int_at(values, 1),
            mode=_int_at(values, 2, base=16),
            content=_int_at(values, 3, base=16),
            interval=_int_at(values, 4),
            distance=_int_at(values, 5),
            speed=_int_at(values, 6),
            status=_int_at(values, 7),
            records=_int_at(values, 8),
            percent_used=_int_at(values, 9),
        )

    @property
    def status_text(self) -> str:
        return {0: "stopped", 1: "logging"}.get(self.status, "unknown")

    @property
    def type_text(self) -> str:
        return {0: "overlap when full", 1: "stop when full"}.get(self.log_type, "unknown")

    def as_dict(self) -> dict[str, Any]:
        return {
            "serial": self.serial,
            "type": self.log_type,
            "type_text": self.type_text,
            "mode": self.mode,
            "content": self.content,
            "interval": self.interval,
            "distance": self.distance,
            "speed": self.speed,
            "status": self.status,
            "status_text": self.status_text,
            "records": self.records,
            "percent_used": self.percent_used,
        }


def build_command(payload: str) -> str:
    normalized = payload.strip()
    if normalized.startswith("$"):
        return normalized if normalized.endswith("\r\n") else f"{normalized}\r\n"
    return f"${normalized}*{checksum(normalized)}\r\n"


def checksum(payload: str) -> str:
    value = 0
    for byte in payload.encode("ascii"):
        value ^= byte
    return f"{value:02X}"


def parse_sentence(raw: str) -> Sentence | None:
    line = raw.strip()
    if not line:
        return None
    if line.startswith("$"):
        line = line[1:]

    supplied: str | None = None
    payload = line
    checksum_ok: bool | None = None
    if "*" in line:
        payload, supplied = line.rsplit("*", 1)
        supplied = supplied[:2].upper()
        checksum_ok = checksum(payload) == supplied

    return Sentence(raw=raw.strip(), payload=payload, checksum=supplied, checksum_ok=checksum_ok)


def parse_ack(sentence: Sentence) -> Ack | None:
    fields = sentence.fields
    if len(fields) < 3 or fields[0] != "PMTK001":
        return None
    return Ack(command=fields[1], flag=_parse_int(fields[2]))


def _int_at(values: list[str], index: int, base: int = 10) -> int | None:
    if index >= len(values):
        return None
    return _parse_int(values[index], base=base)


def _parse_int(value: str, base: int = 10) -> int | None:
    try:
        return int(value, base)
    except ValueError:
        return None
