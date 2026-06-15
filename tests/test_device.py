from datetime import datetime, timezone
from unittest import TestCase

from gps_tui.device import _default_dump_path, _first_text_timestamp


class DeviceTests(TestCase):
    def test_default_dump_path_uses_captured_time_without_prefix(self) -> None:
        captured_at = datetime(2026, 6, 15, 12, 34, 56, tzinfo=timezone.utc)

        path = _default_dump_path([], captured_at)

        self.assertEqual(str(path), "20260615123456.pmtklox")

    def test_default_dump_path_prefers_first_text_timestamp(self) -> None:
        captured_at = datetime(2026, 6, 15, 12, 34, 56, tzinfo=timezone.utc)

        path = _default_dump_path(["note 20260102030405 first"], captured_at)

        self.assertEqual(str(path), "20260102030405.pmtklox")

    def test_first_text_timestamp_reads_rmc_sentence(self) -> None:
        timestamp = _first_text_timestamp(
            ["$GPRMC,092751.000,A,5321.6802,N,00630.3372,W,0.02,31.66,280511,,,A*43"]
        )

        self.assertEqual(timestamp, datetime(2011, 5, 28, 9, 27, 51, tzinfo=timezone.utc))
