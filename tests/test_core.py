from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gps_tui.gpsd import apply_report
from gps_tui.model import GpsState
from gps_tui.sim import simulated_reports
from gps_tui.theme import load_theme


class CoreTests(TestCase):
    def test_tpv_report_updates_fix_and_stats(self) -> None:
        state = GpsState()

        apply_report(
            state,
            {
                "class": "TPV",
                "mode": 3,
                "lat": 59.1,
                "lon": 18.2,
                "speed": 10.0,
                "eph": 4.5,
            },
        )

        self.assertEqual(state.fix.mode_label, "3D")
        self.assertEqual(state.fix.speed_kmh, 36.0)
        self.assertEqual(state.min_eph_m, 4.5)
        self.assertEqual(state.max_speed_kmh, 36.0)

    def test_sky_report_sorts_used_satellites_first(self) -> None:
        state = GpsState()

        apply_report(
            state,
            {
                "class": "SKY",
                "satellites": [
                    {"PRN": 1, "ss": 50, "used": False},
                    {"PRN": 2, "ss": 20, "used": True},
                    {"PRN": 3, "ss": 40, "used": True},
                ],
            },
        )

        self.assertEqual([sat.prn for sat in state.sky.satellites], [3, 2, 1])

    def test_simulator_emits_tpv_and_sky(self) -> None:
        reports = simulated_reports()

        self.assertEqual(next(reports)["class"], "TPV")
        self.assertEqual(next(reports)["class"], "SKY")

    def test_theme_merges_toml_values(self) -> None:
        with TemporaryDirectory() as directory:
            theme_path = Path(directory) / "theme.toml"
            theme_path.write_text('[colors]\naccent = "yellow"\n[symbols]\nfix = "FIX"\n', encoding="utf-8")

            theme = load_theme(theme_path)

        self.assertEqual(theme.color("accent"), "yellow")
        self.assertEqual(theme.symbol("fix"), "FIX")
        self.assertEqual(theme.color("foreground"), "white")
