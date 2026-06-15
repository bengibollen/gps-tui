from unittest import TestCase

from gps_tui.pmtk import LocusStatus, build_command, parse_ack, parse_sentence


class PmtkTests(TestCase):
    def test_build_command_adds_checksum_and_line_ending(self) -> None:
        self.assertEqual(build_command("PMTK220,1000"), "$PMTK220,1000*1F\r\n")

    def test_parse_sentence_validates_checksum(self) -> None:
        sentence = parse_sentence("$PMTK001,183,3*3A")

        self.assertIsNotNone(sentence)
        assert sentence is not None
        self.assertEqual(sentence.payload, "PMTK001,183,3")
        self.assertTrue(sentence.checksum_ok)

    def test_parse_ack(self) -> None:
        sentence = parse_sentence("$PMTK001,622,3*36")
        assert sentence is not None

        ack = parse_ack(sentence)

        self.assertIsNotNone(ack)
        assert ack is not None
        self.assertEqual(ack.command, "622")
        self.assertTrue(ack.ok)

    def test_parse_locus_status(self) -> None:
        sentence = parse_sentence("$PMTKLOG,12,0,1,3,15,0,0,1,123,42*00")
        assert sentence is not None

        status = LocusStatus.from_sentence(sentence)

        self.assertEqual(status.serial, 12)
        self.assertEqual(status.type_text, "overlap when full")
        self.assertEqual(status.interval, 15)
        self.assertEqual(status.status_text, "logging")
        self.assertEqual(status.records, 123)
        self.assertEqual(status.percent_used, 42)
