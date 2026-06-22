from datetime import datetime, timezone
from unittest import TestCase

from gps_tui.device import LocusDump, _default_dump_path, _first_text_timestamp, _gpsd_device_request


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

    def test_gpsd_device_request_hex_encodes_pmtk_command(self) -> None:
        request = _gpsd_device_request("/dev/ttyUSB0", "PMTK183")

        self.assertEqual(
            request,
            '?DEVICE={"path":"/dev/ttyUSB0","hexdata":"24504d544b3138332a33380d0a"};\n',
        )

    def test_gpsd_device_request_hex_encodes_locus_start(self) -> None:
        request = _gpsd_device_request("/dev/ttyUSB0", "PMTK185,0")

        self.assertEqual(
            request,
            '?DEVICE={"path":"/dev/ttyUSB0","hexdata":"24504d544b3138352c302a32320d0a"};\n',
        )

    def test_gpsd_device_request_hex_encodes_locus_stop(self) -> None:
        request = _gpsd_device_request("/dev/ttyUSB0", "PMTK185,1")

        self.assertEqual(
            request,
            '?DEVICE={"path":"/dev/ttyUSB0","hexdata":"24504d544b3138352c312a32330d0a"};\n',
        )

    def test_locus_dump_detects_erased_flash(self) -> None:
        dump = LocusDump(
            lines=[
                "$PMTKLOX,0,2*6F",
                "$PMTKLOX,1,0,FFFFFFFF,FFFFFFFF*00",
                "$PMTKLOX,1,1,FFFFFFFF,FFFFFFFF*00",
                "$PMTKLOX,2*35",
            ],
            complete=True,
            ack=None,
        )

        self.assertEqual(dump.expected_packets, 2)
        self.assertEqual(dump.data_packets, 2)
        self.assertTrue(dump.is_erased)

    def test_locus_dump_detects_non_empty_flash(self) -> None:
        dump = LocusDump(
            lines=[
                "$PMTKLOX,0,1*6C",
                "$PMTKLOX,1,0,FFFFFFFF,00000001*00",
                "$PMTKLOX,2*35",
            ],
            complete=True,
            ack=None,
        )

        self.assertFalse(dump.is_erased)
