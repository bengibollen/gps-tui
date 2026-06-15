from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pmtk import Ack, LocusStatus, Sentence, build_command, parse_ack, parse_sentence


DEFAULT_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUD = 9600


@dataclass(frozen=True)
class LocusDump:
    lines: list[str]
    complete: bool
    ack: Ack | None


class SerialGps:
    def __init__(self, device: str, baud: int, timeout: float) -> None:
        try:
            import serial
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "pyserial is required for device commands. Install with: python3 -m pip install pyserial"
            ) from exc

        self._serial = serial.Serial(device, baudrate=baud, timeout=timeout, write_timeout=timeout)

    def close(self) -> None:
        self._serial.close()

    def __enter__(self) -> "SerialGps":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def send(self, payload: str) -> None:
        self._serial.reset_input_buffer()
        self._serial.write(build_command(payload).encode("ascii"))
        self._serial.flush()

    def read_sentences(
        self,
        should_stop: Callable[[Sentence], bool],
        max_lines: int,
    ) -> list[Sentence]:
        sentences: list[Sentence] = []
        while len(sentences) < max_lines:
            raw = self._serial.readline()
            if not raw:
                break
            text = raw.decode("ascii", errors="replace").strip()
            sentence = parse_sentence(text)
            if sentence is None:
                continue
            sentences.append(sentence)
            if should_stop(sentence):
                break
        return sentences


def main() -> None:
    args = _parse_args()
    if args.command in {"locus-status", "status"}:
        _locus_status(args)
    elif args.command in {"locus-dump", "dump-locus"}:
        _locus_dump(args)
    else:
        raise SystemExit(f"unknown command: {args.command}")


def _locus_status(args: argparse.Namespace) -> None:
    with SerialGps(args.device, args.baud, args.timeout) as gps:
        gps.send("PMTK183")
        sentences = gps.read_sentences(
            lambda sentence: sentence.kind == "PMTKLOG" or _is_ack_for(sentence, "183"),
            max_lines=args.max_lines,
        )

    status = _find_locus_status(sentences)
    ack = _find_ack(sentences, "183")

    if args.json:
        print(json.dumps(_status_payload(status, ack, sentences), indent=2, sort_keys=True))
        return

    if status is None:
        print("No PMTKLOG status response received.", file=sys.stderr)
        _print_raw(sentences)
        raise SystemExit(1)

    print("LOCUS logger status")
    print(f"  serial:       {_value(status.serial)}")
    print(f"  type:         {_value(status.log_type)} ({status.type_text})")
    print(f"  mode:         {_value(status.mode)}")
    print(f"  content:      {_value(status.content)}")
    print(f"  interval:     {_seconds(status.interval)}")
    print(f"  distance:     {_meters(status.distance)}")
    print(f"  speed:        {_value(status.speed)}")
    print(f"  status:       {_value(status.status)} ({status.status_text})")
    print(f"  records:      {_value(status.records)}")
    print(f"  flash used:   {_percent(status.percent_used)}")
    if ack is not None:
        print(f"  ack:          {ack.command} {ack.flag} ({ack.message})")


def _locus_dump(args: argparse.Namespace) -> None:
    command = "PMTK622,0" if args.full else "PMTK622,1"
    seen_complete = False

    def should_stop(sentence: Sentence) -> bool:
        nonlocal seen_complete
        if sentence.kind == "PMTKLOX" and _field(sentence, 1) == "2":
            seen_complete = True
            return False
        return seen_complete and _is_ack_for(sentence, "622")

    with SerialGps(args.device, args.baud, args.timeout) as gps:
        gps.send(command)
        sentences = gps.read_sentences(should_stop, max_lines=args.max_lines)

    dump = LocusDump(
        lines=[sentence.raw for sentence in sentences if sentence.kind.startswith("PMTKLOX")],
        complete=any(sentence.kind == "PMTKLOX" and _field(sentence, 1) == "2" for sentence in sentences),
        ack=_find_ack(sentences, "622"),
    )
    output = args.output or _default_dump_path(dump.lines)
    output.write_text("\n".join(dump.lines) + ("\n" if dump.lines else ""), encoding="utf-8")

    if args.json:
        print(
            json.dumps(
                {
                    "output": str(output),
                    "command": command,
                    "lines": len(dump.lines),
                    "complete": dump.complete,
                    "ack": _ack_payload(dump.ack),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    print(f"Wrote {len(dump.lines)} LOCUS dump lines to {output}")
    print(f"Complete marker received: {'yes' if dump.complete else 'no'}")
    if dump.ack is not None:
        print(f"Ack: {dump.ack.command} {dump.ack.flag} ({dump.ack.message})")
    if not dump.complete:
        print("Warning: no PMTKLOX completion marker was received before timeout.", file=sys.stderr)
        raise SystemExit(2)


def _parse_args() -> argparse.Namespace:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--device", default=DEFAULT_DEVICE, help=f"serial device, default {DEFAULT_DEVICE}")
    common.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"serial baud rate, default {DEFAULT_BAUD}")
    common.add_argument("--timeout", type=float, default=2.0, help="serial read/write timeout in seconds")
    common.add_argument("--max-lines", type=int, default=20000, help="maximum response lines to read")
    common.add_argument("--json", action="store_true", help="print machine-readable JSON")

    parser = argparse.ArgumentParser(description="GPS module management commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("locus-status", parents=[common], help="query LOCUS logger status")
    subparsers.add_parser("status", parents=[common], help="alias for locus-status")

    dump = subparsers.add_parser(
        "locus-dump",
        parents=[common],
        help="dump used LOCUS flash to a raw PMTKLOX file",
    )
    dump.add_argument("--output", type=Path, help="output path for raw PMTKLOX lines")
    dump.add_argument("--full", action="store_true", help="dump full flash instead of used flash")

    dump_alias = subparsers.add_parser("dump-locus", parents=[common], help="alias for locus-dump")
    dump_alias.add_argument("--output", type=Path, help="output path for raw PMTKLOX lines")
    dump_alias.add_argument("--full", action="store_true", help="dump full flash instead of used flash")

    return parser.parse_args()


def _find_locus_status(sentences: list[Sentence]) -> LocusStatus | None:
    for sentence in sentences:
        if sentence.kind == "PMTKLOG":
            return LocusStatus.from_sentence(sentence)
    return None


def _find_ack(sentences: list[Sentence], command: str) -> Ack | None:
    for sentence in sentences:
        ack = parse_ack(sentence)
        if ack is not None and ack.command == command:
            return ack
    return None


def _is_ack_for(sentence: Sentence, command: str) -> bool:
    ack = parse_ack(sentence)
    return ack is not None and ack.command == command


def _field(sentence: Sentence, index: int) -> str | None:
    fields = sentence.fields
    return fields[index] if index < len(fields) else None


def _default_dump_path(lines: list[str] | None = None, captured_at: datetime | None = None) -> Path:
    timestamp = _first_text_timestamp(lines or []) or captured_at or datetime.now(timezone.utc)
    return Path(f"{timestamp.astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')}.pmtklox")


def _first_text_timestamp(lines: list[str]) -> datetime | None:
    for line in lines:
        timestamp = _parse_iso_timestamp(line) or _parse_compact_timestamp(line) or _parse_nmea_rmc_timestamp(line)
        if timestamp is not None:
            return timestamp
    return None


def _parse_iso_timestamp(line: str) -> datetime | None:
    match = re.search(r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z\b", line)
    if match is None:
        return None
    try:
        return datetime.fromisoformat(match.group(1)).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_compact_timestamp(line: str) -> datetime | None:
    match = re.search(r"\b(20\d{12})\b", line)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_nmea_rmc_timestamp(line: str) -> datetime | None:
    sentence = parse_sentence(line)
    if sentence is None or not sentence.kind.endswith("RMC"):
        return None
    fields = sentence.fields
    if len(fields) < 10:
        return None
    time_value = fields[1].split(".", 1)[0]
    date_value = fields[9]
    if len(time_value) != 6 or len(date_value) != 6:
        return None
    try:
        return datetime.strptime(date_value + time_value, "%d%m%y%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _status_payload(status: LocusStatus | None, ack: Ack | None, sentences: list[Sentence]) -> dict[str, Any]:
    return {
        "status": None if status is None else status.as_dict(),
        "ack": _ack_payload(ack),
        "raw": [sentence.raw for sentence in sentences],
    }


def _ack_payload(ack: Ack | None) -> dict[str, Any] | None:
    if ack is None:
        return None
    return {"command": ack.command, "flag": ack.flag, "ok": ack.ok, "message": ack.message}


def _print_raw(sentences: list[Sentence]) -> None:
    if not sentences:
        print("No response lines received.", file=sys.stderr)
        return
    print("Raw response:", file=sys.stderr)
    for sentence in sentences:
        print(f"  {sentence.raw}", file=sys.stderr)


def _value(value: object) -> str:
    return "--" if value is None else str(value)


def _seconds(value: int | None) -> str:
    return "--" if value is None else f"{value} s"


def _meters(value: int | None) -> str:
    return "--" if value is None else f"{value} m"


def _percent(value: int | None) -> str:
    return "--" if value is None else f"{value}%"


if __name__ == "__main__":
    main()
