from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pmtk import Ack, LocusStatus, Sentence, build_command, parse_ack, parse_sentence


DEFAULT_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUD = 9600
DEFAULT_GPSD_HOST = "localhost"
DEFAULT_GPSD_PORT = 2947


@dataclass(frozen=True)
class LocusDump:
    lines: list[str]
    complete: bool
    ack: Ack | None

    @property
    def expected_packets(self) -> int | None:
        for line in self.lines:
            sentence = parse_sentence(line)
            if sentence is not None and sentence.kind == "PMTKLOX" and _field(sentence, 1) == "0":
                value = _field(sentence, 2)
                if value is None:
                    return None
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    @property
    def data_packets(self) -> int:
        count = 0
        for line in self.lines:
            sentence = parse_sentence(line)
            if sentence is not None and sentence.kind == "PMTKLOX" and _field(sentence, 1) == "1":
                count += 1
        return count

    @property
    def is_erased(self) -> bool:
        words = _locus_dump_words(self.lines)
        return bool(words) and all(word == "FFFFFFFF" for word in words)


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


class GpsdGps:
    def __init__(self, host: str, port: int, device: str, timeout: float) -> None:
        self.host = host
        self.port = port
        self.device = device
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._stream: Any = None

    def __enter__(self) -> "GpsdGps":
        self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._socket.settimeout(self.timeout)
        self._stream = self._socket.makefile("rb")
        self._send_gpsd("?WATCH={\"enable\":true,\"raw\":1};\n")
        self._read_until_watch()
        return self

    def __exit__(self, *_args: object) -> None:
        if self._stream is not None:
            self._stream.close()
        if self._socket is not None:
            self._socket.close()

    def send(self, payload: str) -> None:
        self._send_gpsd(_gpsd_device_request(self.device, payload))

    def read_sentences(
        self,
        should_stop: Callable[[Sentence], bool],
        max_lines: int,
    ) -> list[Sentence]:
        sentences: list[Sentence] = []
        raw_lines = 0
        while raw_lines < max_lines:
            line = self._readline()
            if line is None:
                break
            raw_lines += 1
            if not line.startswith("$"):
                continue
            sentence = parse_sentence(line)
            if sentence is None:
                continue
            sentences.append(sentence)
            if should_stop(sentence):
                break
        return sentences

    def _send_gpsd(self, command: str) -> None:
        if self._socket is None:
            raise RuntimeError("gpsd socket is not connected")
        self._socket.sendall(command.encode("ascii"))

    def _read_until_watch(self) -> None:
        for _ in range(20):
            line = self._readline()
            if line is None:
                return
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("class") == "WATCH":
                    return

    def _readline(self) -> str | None:
        if self._stream is None:
            return None
        try:
            raw = self._stream.readline()
        except TimeoutError:
            return None
        if not raw:
            return None
        return raw.decode("ascii", errors="replace").strip()


def main() -> None:
    args = _parse_args()
    if args.command in {"locus-status", "status"}:
        _locus_status(args)
    elif args.command in {"locus-dump", "dump-locus"}:
        _locus_dump(args)
    elif args.command == "locus-start":
        _locus_control(args, action="start", payload="PMTK185,0")
    elif args.command == "locus-stop":
        _locus_control(args, action="stop", payload="PMTK185,1")
    else:
        raise SystemExit(f"unknown command: {args.command}")


def _locus_status(args: argparse.Namespace) -> None:
    with _open_transport(args) as gps:
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

    with _open_transport(args) as gps:
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
                    "expected_packets": dump.expected_packets,
                    "data_packets": dump.data_packets,
                    "complete": dump.complete,
                    "erased": dump.is_erased,
                    "ack": _ack_payload(dump.ack),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    print(f"Wrote {len(dump.lines)} LOCUS dump lines to {output}")
    if dump.expected_packets is not None:
        print(f"Expected data packets: {dump.expected_packets}")
    print(f"Data packets received: {dump.data_packets}")
    print(f"Flash contents: {'erased/empty' if dump.is_erased else 'contains non-empty data'}")
    print(f"Complete marker received: {'yes' if dump.complete else 'no'}")
    if dump.ack is not None:
        print(f"Ack: {dump.ack.command} {dump.ack.flag} ({dump.ack.message})")
    if not dump.complete:
        print("Warning: no PMTKLOX completion marker was received before timeout.", file=sys.stderr)
        raise SystemExit(2)


def _locus_control(args: argparse.Namespace, action: str, payload: str) -> None:
    with _open_transport(args) as gps:
        gps.send(payload)
        sentences = gps.read_sentences(
            lambda sentence: _is_ack_for(sentence, "185"),
            max_lines=args.max_lines,
        )

    ack = _find_ack(sentences, "185")
    if args.json:
        print(
            json.dumps(
                {
                    "action": action,
                    "payload": payload,
                    "ack": _ack_payload(ack),
                    "raw": [sentence.raw for sentence in sentences],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if ack is None:
        print(f"LOCUS {action}: no PMTK001 acknowledgement received.", file=sys.stderr)
        _print_raw(sentences)
        raise SystemExit(1)

    print(f"LOCUS {action}: {ack.message}")
    print(f"Ack: {ack.command} {ack.flag}")
    if not ack.ok:
        raise SystemExit(1)


def _parse_args() -> argparse.Namespace:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--transport",
        choices=("gpsd", "serial"),
        default="gpsd",
        help="device command transport, default gpsd",
    )
    common.add_argument("--host", default=DEFAULT_GPSD_HOST, help=f"gpsd host, default {DEFAULT_GPSD_HOST}")
    common.add_argument("--port", type=int, default=DEFAULT_GPSD_PORT, help=f"gpsd port, default {DEFAULT_GPSD_PORT}")
    common.add_argument("--device", default=DEFAULT_DEVICE, help=f"serial device, default {DEFAULT_DEVICE}")
    common.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"serial baud rate for --transport serial, default {DEFAULT_BAUD}",
    )
    common.add_argument("--timeout", type=float, default=2.0, help="serial read/write timeout in seconds")
    common.add_argument("--max-lines", type=int, default=20000, help="maximum response lines to read")
    common.add_argument("--json", action="store_true", help="print machine-readable JSON")

    parser = argparse.ArgumentParser(description="GPS module management commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("locus-status", parents=[common], help="query LOCUS logger status")
    subparsers.add_parser("status", parents=[common], help="alias for locus-status")
    subparsers.add_parser("locus-start", parents=[common], help="start LOCUS logging")
    subparsers.add_parser("locus-stop", parents=[common], help="stop LOCUS logging")

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


def _open_transport(args: argparse.Namespace) -> GpsdGps | SerialGps:
    if args.transport == "serial":
        return SerialGps(args.device, args.baud, args.timeout)
    return GpsdGps(args.host, args.port, args.device, args.timeout)


def _gpsd_device_request(device: str, payload: str) -> str:
    request = {
        "path": device,
        "hexdata": build_command(payload).encode("ascii").hex(),
    }
    return f"?DEVICE={json.dumps(request, separators=(',', ':'))};\n"


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


def _locus_dump_words(lines: list[str]) -> list[str]:
    words: list[str] = []
    for line in lines:
        sentence = parse_sentence(line)
        if sentence is None or sentence.kind != "PMTKLOX" or _field(sentence, 1) != "1":
            continue
        for field in sentence.fields[3:]:
            if re.fullmatch(r"[0-9A-Fa-f]{8}", field):
                words.append(field.upper())
    return words


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
