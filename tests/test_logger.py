import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gps_tui.logger import DailyJsonlWriter, _fix_record, _has_fix


class LoggerTests(TestCase):
    def test_has_fix_requires_mode_and_coordinates(self) -> None:
        self.assertTrue(_has_fix({"mode": 2, "lat": 57.1, "lon": 11.2}))
        self.assertFalse(_has_fix({"mode": 1, "lat": 57.1, "lon": 11.2}))
        self.assertFalse(_has_fix({"mode": 3, "lat": 57.1}))

    def test_fix_record_keeps_raw_report(self) -> None:
        report = {
            "class": "TPV",
            "time": "2026-06-24T12:00:00.000Z",
            "mode": 3,
            "lat": 57.1,
            "lon": 11.2,
            "altMSL": 42.0,
            "speed": 1.2,
        }

        record = _fix_record(report)

        self.assertEqual(record["type"], "fix")
        self.assertEqual(record["alt_m"], 42.0)
        self.assertEqual(record["raw"], report)

    def test_daily_writer_rotates_by_record_date(self) -> None:
        with TemporaryDirectory() as directory:
            writer = DailyJsonlWriter(Path(directory))
            writer.write({"type": "event", "time": "2026-06-24T23:59:59.000Z"})
            writer.write({"type": "event", "time": "2026-06-25T00:00:00.000Z"})
            writer.close()

            first = Path(directory) / "2026-06-24.jsonl"
            second = Path(directory) / "2026-06-25.jsonl"

            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertEqual(json.loads(first.read_text(encoding="utf-8"))["time"], "2026-06-24T23:59:59.000Z")
            self.assertEqual(json.loads(second.read_text(encoding="utf-8"))["time"], "2026-06-25T00:00:00.000Z")
