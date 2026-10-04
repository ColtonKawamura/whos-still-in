import csv
import json
import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("add_report", ROOT / "scripts" / "add_report.py")
add_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(add_report)

REVIEW = date(2026, 10, 4)
CONSENT = "\n".join(["- [X] one", "- [X] two", "- [X] three"])


def body(**answers):
    values = {
        "year": "2012", "status": "Still in (active or reserve)", "service": "U.S. Navy", "rank": "O-4",
        "community": "Foreign Area Officer, Surface", "highest_rank": "_No response_",
        "industry": "_No response_", "as_of": "2026-10-01", "consent": CONSENT,
    } | answers
    return "\n\n".join(f"### {add_report.LABELS[key]}\n\n{value}" for key, value in values.items())


class AddReportTests(unittest.TestCase):
    def test_labels_match_issue_form(self):
        form = (ROOT / ".github" / "ISSUE_TEMPLATE" / "voluntary-report.yml").read_text()
        for label in add_report.LABELS.values():
            self.assertIn(f"label: {label}\n", form)
        for option in list(add_report.STATUSES) + list(add_report.SERVICES):
            self.assertIn(f"- {option}\n", form)

    def test_still_in_report_canonicalizes_communities(self):
        row = add_report.report_row(body(), REVIEW)
        self.assertEqual(row["status"], "still_in")
        self.assertEqual(row["rank"], "O-4")
        self.assertEqual(row["community"], "Surface; Foreign Area Officer")
        self.assertEqual(row["industry"], "")

    def test_out_report_uses_highest_rank_and_defaults(self):
        row = add_report.report_row(body(
            status="Out (separated or retired)", rank="Not disclosed / not applicable",
            highest_rank="O-3", community="_No response_", service="U.S. Marine Corps"), REVIEW)
        self.assertEqual((row["service"], row["rank"], row["community"], row["industry"]),
                         ("USMC", "O-3", "Not disclosed", "Not disclosed"))

    def test_accepts_issues_filed_with_legacy_highest_rank_label(self):
        text = body(status="Out (separated or retired)", rank="Not disclosed / not applicable", highest_rank="O-4")
        old = add_report.LEGACY_LABELS["highest_rank"][0]
        text = text.replace(f"### {add_report.LABELS['highest_rank']}\n", f"### {old}\n")
        self.assertNotIn(add_report.LABELS["highest_rank"], text)
        self.assertEqual(add_report.report_row(text, REVIEW)["rank"], "O-4")

    def test_rejects_invalid_reports(self):
        for answers in [{"consent": "- [X] one\n- [ ] two\n- [X] three"}, {"community": "Astronaut"},
                        {"as_of": "2026-10-05"}, {"industry": "Law"},
                        {"status": "Out (separated or retired)"}]:
            with self.subTest(answers=answers):
                with self.assertRaises(ValueError):
                    add_report.report_row(body(**answers), REVIEW)

    def test_apply_adds_and_subtracts_aggregate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cohorts.csv"
            original = "".join(line for line in (ROOT / "data" / "cohorts.csv").read_text().splitlines(True)
                               if ",voluntary," not in line)
            path.write_text(original)
            row = add_report.report_row(body(), REVIEW)
            self.assertEqual(add_report.apply(path, row, 1, REVIEW), 1)
            self.assertEqual(add_report.apply(path, row, 1, REVIEW), 2)
            with path.open(newline="") as handle:
                reports = [r for r in csv.DictReader(handle) if r["kind"] == "voluntary"]
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0]["count"], "2")
            add_report.apply(path, row, -1, REVIEW)
            add_report.apply(path, row, -1, REVIEW)
            self.assertEqual(path.read_text(), original)
            with self.assertRaises(ValueError):
                add_report.apply(path, row, -1, REVIEW)
            with self.assertRaises(ValueError):
                add_report.apply(path, dict(row, year="1999"), 1, REVIEW)

    def test_replacing_previous_row_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cohorts.csv"
            original = "".join(line for line in (ROOT / "data" / "cohorts.csv").read_text().splitlines(True)
                               if ",voluntary," not in line)
            path.write_text(original)
            old = add_report.report_row(body(), REVIEW)
            new = add_report.report_row(body(rank="O-5"), REVIEW)
            add_report.apply(path, old, 1, REVIEW)
            add_report.apply_changes(path, [(old, -1), (new, 1)], REVIEW)
            with path.open(newline="") as handle:
                reports = [r for r in csv.DictReader(handle) if r["kind"] == "voluntary"]
            self.assertEqual([(r["rank"], r["count"]) for r in reports], [("O-5", "1")])
            before = path.read_text()
            with self.assertRaises(ValueError):
                add_report.apply_changes(path, [(old, -1), (new, 1)], REVIEW)
            self.assertEqual(path.read_text(), before)

    def test_previous_row_rejects_tampered_values(self):
        row = add_report.report_row(body(), REVIEW)
        self.assertEqual(add_report.previous_row(json.dumps(row)), row)
        for change in [{"kind": "class"}, {"rank": "O-99"}, {"community": "Astronaut"},
                       {"year": "2012; rm"}, {"extra": "x"}, {"service": "Navy"}]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    add_report.previous_row(json.dumps(row | change))


if __name__ == "__main__":
    unittest.main()
