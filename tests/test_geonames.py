from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gps_tui.geonames import GeoNamesIndex, haversine_km, load_admin1, load_cities, load_countries


class GeoNamesTests(TestCase):
    def test_load_geonames_files_and_find_nearest(self) -> None:
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            (data_dir / "cities1000.txt").write_text(
                "\n".join(
                    [
                        "2711537\tGoteborg\tGoteborg\tGoteborg\t57.70716\t11.96679\tP\tPPLA\tSE\t\t28\t\t\t\t587549\t\t\tEurope/Stockholm\t2024-01-01",
                        "2698739\tKungalv\tKungalv\tKungalv\t57.87096\t11.98054\tP\tPPL\tSE\t\t28\t\t\t\t24101\t\t\tEurope/Stockholm\t2024-01-01",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "countryInfo.txt").write_text(
                "SE\tSWE\t752\tSW\tSweden\tStockholm\t450295\t104142686\tEU\t.se\tSEK\tKrona\t46\t#####\t^\\d{5}$\tsv-SE,se,sma,fi-SE\t2661886\tDK,FI,NO\n",
                encoding="utf-8",
            )
            (data_dir / "admin1CodesASCII.txt").write_text(
                "SE.28\tVastra Gotaland\tVastra Gotaland\t3337385\n",
                encoding="utf-8",
            )

            index = GeoNamesIndex.from_dir(data_dir)
            result = index.nearest(57.87, 11.98)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.city.name, "Kungalv")
        self.assertEqual(result.country_name, "Sweden")
        self.assertEqual(result.admin1_name, "Vastra Gotaland")
        self.assertEqual(result.display_name, "Kungalv, Vastra Gotaland, Sweden")

    def test_loaders_return_empty_when_files_are_missing(self) -> None:
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)

            self.assertEqual(load_cities(data_dir / "cities1000.txt"), [])
            self.assertEqual(load_countries(data_dir / "countryInfo.txt"), {})
            self.assertEqual(load_admin1(data_dir / "admin1CodesASCII.txt"), {})

    def test_haversine_distance_is_reasonable(self) -> None:
        distance = haversine_km(57.70716, 11.96679, 57.87096, 11.98054)

        self.assertGreater(distance, 18)
        self.assertLess(distance, 19)
