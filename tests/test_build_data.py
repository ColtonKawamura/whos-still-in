import copy
import csv
import importlib.util
import json
import tempfile
import unittest
from datetime import date, timedelta
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
                "USN": {"commissioned": 7},
                "USMC": {"commissioned": 4},
            },
            "as_of": "2026-10-04",
            "coverage_note": "Documented commissions only.",
            "sources": [{"title": "Example source", "url": "https://example.com"}],
        }

    def test_publishes_commissions_without_estimates(self):
        result = builder.build_class(self.source)
        self.assertEqual(result["commissioned_total"], 11)
        self.assertEqual(result["by_service"]["USN"], {"commissioned": 7})
        self.assertEqual(result["coverage_note"], self.source["coverage_note"])
        for key in ["estimated_still_in", "estimated_out", "percent_in", "percent_out", "method", "confidence"]:
            self.assertNotIn(key, result)

    def test_rejects_invalid_counts(self):
        for count in [-1, 1.5, True]:
            with self.subTest(count=count):
                source = copy.deepcopy(self.source)
                source["by_service"]["USN"] = {"commissioned": count}
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
            source_file = Path(directory) / "cohorts.csv"
            output_dir = Path(directory) / "public"
            with (ROOT / "data" / "cohorts.csv").open(newline="") as handle:
                reader = csv.DictReader(handle)
                fields = reader.fieldnames
                rows = list(reader)
            with source_file.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for year in [2012, 2013]:
                    writer.writerows(dict(row, year=year) for row in rows)
            builder.build(source_file, output_dir)
            self.assertEqual(json.loads((output_dir / "index.json").read_text()),
                             {"years": [2013, 2012]})
            self.assertEqual(json.loads((output_dir / "2013.json").read_text())["year"], 2013)

    def test_documented_sources_match_generated_data(self):
        source_file = ROOT / "data" / "cohorts.csv"
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            builder.build(source_file, output_dir)
            for generated in output_dir.glob("*.json"):
                self.assertEqual(generated.read_text(), (ROOT / "data" / generated.name).read_text())
                if generated.name != "index.json":
                    data = json.loads(generated.read_text())
                    self.assertEqual(
                        sum(service["commissioned"] for service in data["by_service"].values()),
                        data["commissioned_total"],
                    )

    def test_rank_percentages_use_still_in_respondents_only(self):
        rows = [
            {"service": "USN", "status": "still_in", "rank": "O-4", "community": "Surface", "count": "2", "as_of": "2026-10-04"},
            {"service": "USMC", "status": "still_in", "rank": "O-5", "community": "Surface", "count": "1", "as_of": "2026-10-04"},
            {"service": "USN", "status": "still_in", "rank": "Not disclosed", "community": "Surface", "count": "1", "as_of": "2026-10-04"},
            {"service": "USN", "status": "out", "rank": "O-3", "community": "Not disclosed", "industry": "Tech / software",
             "separation_year": "2020", "count": "3", "as_of": "2026-10-04"},
        ]
        result = builder.build_voluntary(rows)
        ranks = {entry["rank"]: entry for entry in result["rank_distribution"]}
        self.assertEqual(result["reported_still_in"], 4)
        self.assertEqual(result["reported_out"], 3)
        self.assertEqual(ranks["O-4"]["percent"], 50)
        self.assertEqual(ranks["O-5"]["percent"], 25)
        self.assertEqual(ranks["Not disclosed"]["percent"], 25)

    def test_empty_rank_data_is_not_a_zero_percent_estimate(self):
        result = builder.build_voluntary([])
        self.assertEqual(result["reported_still_in"], 0)
        self.assertIsNone(result["as_of"])
        for key in ["rank_distribution", "highest_rank_distribution", "industry_distribution"]:
            self.assertTrue(all(entry["percent"] is None for entry in result[key]))

    def test_out_highest_rank_and_industry_use_out_respondents_only(self):
        rows = [
            {"service": "USN", "status": "still_in", "rank": "O-4", "community": "Surface", "industry": "", "count": "5", "as_of": "2026-10-04"},
            {"service": "USN", "status": "out", "rank": "O-3", "community": "Surface", "industry": "Tech / software", "separation_year": "2020", "count": "2", "as_of": "2026-10-04"},
            {"service": "USMC", "status": "out", "rank": "O-4", "community": "Surface", "industry": "Law", "separation_year": "2023", "count": "1", "as_of": "2026-10-04"},
            {"service": "USN", "status": "out", "rank": "Not disclosed", "community": "Surface", "industry": "Not disclosed", "separation_year": "Not disclosed", "count": "1", "as_of": "2026-10-04"},
        ]
        result = builder.build_voluntary(rows)
        highest = {entry["rank"]: entry for entry in result["highest_rank_distribution"]}
        industries = {entry["industry"]: entry for entry in result["industry_distribution"]}
        self.assertEqual(result["reported_out"], 4)
        self.assertEqual(highest["O-3"]["percent"], 50)
        self.assertEqual(highest["O-4"]["percent"], 25)
        self.assertEqual(highest["Not disclosed"]["percent"], 25)
        self.assertEqual(industries["Tech / software"]["percent"], 50)
        self.assertEqual(industries["Law"]["percent"], 25)
        current = {entry["rank"]: entry for entry in result["rank_distribution"]}
        self.assertEqual(current["O-4"]["percent"], 100)
        self.assertEqual(current["O-3"]["count"], 0)

    def test_rejects_invalid_voluntary_rows(self):
        row = {"service": "USN", "status": "still_in", "rank": "O-4", "community": "Surface", "industry": "",
               "count": "1", "as_of": "2026-10-04"}
        for key, value in [("count", "-1"), ("count", "1.5"), ("rank", "O-99"),
                           ("status", "out"), ("service", ""), ("industry", "Law"),
                           ("as_of", (date.today() + timedelta(days=1)).isoformat())]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    builder.build_voluntary([dict(row, **{key: value})])
        with self.assertRaises(ValueError):
            builder.build_voluntary([dict(row, separation_year="2020")])
        out_row = dict(row, status="out", industry="Law", separation_year="2020", year="2012")
        builder.build_voluntary([out_row])
        builder.build_voluntary([dict(out_row, separation_year="Not disclosed")])
        for key, value in [("industry", ""), ("industry", "Astronaut"), ("rank", ""), ("rank", "O-99"),
                           ("separation_year", ""), ("separation_year", "20"), ("separation_year", "2011"),
                           ("separation_year", str(date.today().year + 1)), ("separation_year", "２０２０")]:
            with self.subTest(out_key=key, value=value):
                with self.assertRaises(ValueError):
                    builder.build_voluntary([dict(out_row, **{key: value})])

    def test_csv_rejects_duplicate_service_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cohorts.csv"
            source = (ROOT / "data" / "cohorts.csv").read_text()
            source += "2012,service,USN,,,,,,810,,,,\n"
            path.write_text(source)
            with self.assertRaises(ValueError):
                builder.read_sources(path)

    def test_csv_voluntary_rows_flow_to_generated_rank_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cohorts.csv"
            output = Path(directory) / "public"
            source = "".join(line for line in (ROOT / "data" / "cohorts.csv").read_text().splitlines(True)
                             if ",voluntary," not in line)
            report = "2012,voluntary,USN,still_in,O-4,Surface,,,2,2026-10-04,,,\n"
            path.write_text(source + report)
            builder.build(path, output)
            result = json.loads((output / "2012.json").read_text())
            self.assertEqual(result["commissioned_total"], 1077)
            self.assertEqual(result["voluntary"]["reported_still_in"], 2)
            rank = next(entry for entry in result["voluntary"]["rank_distribution"]
                        if entry["rank"] == "O-4")
            self.assertEqual(rank["percent"], 100)
            out_report = '2012,voluntary,USMC,out,O-3,Infantry,"Construction / trades / real estate",2019,1,2026-10-04,,,\n'
            path.write_text(source + report + out_report)
            builder.build(path, output)
            result = json.loads((output / "2012.json").read_text())
            self.assertEqual(result["voluntary"]["reported_out"], 1)
            industry = next(entry for entry in result["voluntary"]["industry_distribution"]
                            if entry["industry"] == "Construction / trades / real estate")
            self.assertEqual(industry["percent"], 100)
            out = next(entry for entry in result["voluntary"]["responses"] if entry["status"] == "out")
            self.assertEqual(out["separation_year"], "2019")
            path.write_text(source + report + report)
            with self.assertRaises(ValueError):
                builder.read_sources(path)

    def test_multiple_communities_count_once_per_community(self):
        rows = [
            {"service": "USN", "status": "still_in", "rank": "O-4", "community": "Surface; Foreign Area Officer",
             "industry": "", "count": "2", "as_of": "2026-10-04"},
            {"service": "USN", "status": "out", "rank": "O-3", "community": "Surface",
             "industry": "Law", "separation_year": "2021", "count": "1", "as_of": "2026-10-04"},
            {"service": "USMC", "status": "out", "rank": "O-3", "community": "Not disclosed",
             "industry": "Law", "separation_year": "Not disclosed", "count": "1", "as_of": "2026-10-04"},
        ]
        result = builder.build_voluntary(rows)
        communities = {entry["community"]: entry for entry in result["community_distribution"]}
        self.assertEqual(communities["Surface"]["count"], 3)
        self.assertEqual(communities["Surface"]["percent"], 75)
        self.assertEqual(communities["Foreign Area Officer"]["percent"], 50)
        self.assertEqual(communities["Not disclosed"]["percent"], 25)
        self.assertEqual(result["reported_multiple_communities"], 2)
        self.assertEqual(result["responses"][0]["communities"], ["Surface", "Foreign Area Officer"])
        self.assertIsNone(result["responses"][0]["industry"])
        self.assertIsNone(result["responses"][0]["separation_year"])
        self.assertEqual(result["responses"][1]["separation_year"], "2021")

    def test_rejects_invalid_community_values(self):
        row = {"service": "USN", "status": "still_in", "rank": "O-4", "industry": "",
               "count": "1", "as_of": "2026-10-04"}
        for value in ["", "Astronaut", "Surface; Surface", "Foreign Area Officer; Surface",
                      "Surface; Not disclosed", "Surface;Submarine"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    builder.build_voluntary([dict(row, community=value)])

    def test_communities_match_issue_form(self):
        form = (ROOT / ".github" / "ISSUE_TEMPLATE" / "voluntary-report.yml").read_text()
        block = form.split("id: community", 1)[1].split("validations:", 1)[0]
        options = [line.strip()[2:] for line in block.splitlines() if line.startswith("        - ")]
        self.assertEqual(options, [c for c in builder.COMMUNITIES if c != "Not disclosed"])
        for community in builder.COMMUNITIES:
            self.assertNotIn(",", community)
            self.assertNotIn(";", community)


if __name__ == "__main__":
    unittest.main()
