import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_data", ROOT / "scripts" / "build_data.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildDataTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "year": 2012,
            "commissioned_total": 11,
            "by_service": {
                "USN": {"commissioned": 7, "assumed_retention_rate": 0.5},
                "USMC": {"commissioned": 4, "assumed_retention_rate": 0.25},
            },
            "as_of": "2026-10-04",
            "method": "Illustrative assumptions, not observed retention.",
            "confidence": "Low",
            "sources": [{"title": "Example source", "url": "https://example.com"}],
        }

    def test_rounding_and_complements(self):
        result = builder.build_class(self.source)
        self.assertEqual(result["by_service"]["USN"]["estimated_still_in"], 4)
        self.assertEqual(result["estimated_still_in"], 5)
        self.assertEqual(result["estimated_out"], 6)
        self.assertEqual(result["percent_in"], 45.5)
        self.assertEqual(result["percent_in"] + result["percent_out"], 100)

    def test_rejects_invalid_counts_and_rates(self):
        for count, rate in [(-1, 0.5), (1.5, 0.5), (True, 0.5),
                            (7, -0.1), (7, 1.1), (7, "NaN"), (7, "Infinity")]:
            with self.subTest(count=count, rate=rate):
                source = copy.deepcopy(self.source)
                source["by_service"]["USN"] = {
                    "commissioned": count, "assumed_retention_rate": rate,
                }
                with self.assertRaises(ValueError):
                    builder.build_class(source)

    def test_rejects_inconsistent_total_and_invalid_date(self):
        for key, value in [("commissioned_total", 12), ("as_of", "2026-02-30"),
                           ("year", "../../2012"), ("by_service", {})]:
            with self.subTest(key=key):
                source = copy.deepcopy(self.source)
                source[key] = value
                with self.assertRaises(ValueError):
                    builder.build_class(source)

    def test_adding_source_populates_index(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory) / "sources"
            output_dir = Path(directory) / "public"
            source_dir.mkdir()
            for year in [2012, 2013]:
                source = dict(self.source, year=year)
                (source_dir / f"{year}.json").write_text(json.dumps(source))
            builder.build(source_dir, output_dir)
            self.assertEqual(json.loads((output_dir / "index.json").read_text()),
                             {"years": [2013, 2012]})
            self.assertEqual(json.loads((output_dir / "2013.json").read_text())["year"], 2013)

    def test_documented_sources_match_generated_data(self):
        source_dir = ROOT / "data" / "sources"
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            builder.build(source_dir, output_dir)
            for generated in output_dir.glob("*.json"):
                self.assertEqual(generated.read_text(), (ROOT / "data" / generated.name).read_text())
                if generated.name != "index.json":
                    data = json.loads(generated.read_text())
                    self.assertEqual(
                        data["estimated_still_in"] + data["estimated_out"],
                        data["commissioned_total"],
                    )


if __name__ == "__main__":
    unittest.main()
