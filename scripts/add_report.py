#!/usr/bin/env python3
"""Apply one reviewed voluntary-report issue to the aggregate rows in data/cohorts.csv.

The issue body (GitHub issue-form markdown) is read from a file or "-" for stdin, e.g.
    gh issue view 12 --json body -q .body | python scripts/add_report.py -
Use --subtract with a previously accepted body to remove that response, or --previous-json with
the previously accepted row to replace it atomically. --json-out writes the accepted row as JSON.
Only aggregate counts are written; no usernames or issue identifiers are stored.
"""

import argparse
import csv
import importlib.util
import io
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_data", ROOT / "scripts" / "build_data.py")
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)

LABELS = {
    "year": "USNA graduating class year",
    "status": "Current serving status",
    "service": "Current service (or last service if out)",
    "rank": "Current pay grade — Still in only",
    "community": "Warfare community / designator (select all that apply)",
    "highest_rank": "Pay grade at separation — Out only (optional)",
    "industry": "Current industry — Out only (optional)",
    "as_of": "Status as of (YYYY-MM-DD)",
    "consent": "Voluntary participation",
}
# Earlier form labels, so issues filed before a field was renamed are still parsed when re-checked.
LEGACY_LABELS = {"highest_rank": ["Highest pay grade held — Out only (optional)"]}
STATUSES = {"Still in (active or reserve)": "still_in", "Out (separated or retired)": "out"}
SERVICES = {
    "U.S. Navy": "USN", "U.S. Marine Corps": "USMC", "U.S. Army": "USA", "U.S. Air Force": "USAF",
    "U.S. Space Force": "USSF", "U.S. Coast Guard": "USCG", "Other / not disclosed": "Not disclosed",
}
BLANK = {"", "_No response_", "None", "Not disclosed / not applicable"}
CONSENT_BOXES = 3


def parse_sections(body):
    sections = {}
    for match in re.finditer(r"^### (.+?)\s*$\n(.*?)(?=^### |\Z)", body, re.M | re.S):
        sections[match.group(1).strip()] = match.group(2).strip()
    return sections


def report_row(body, review_date):
    """Return the aggregate CSV key fields for one issue body, or raise ValueError."""
    sections = parse_sections(body.replace("\r\n", "\n"))
    for key, old_labels in LEGACY_LABELS.items():
        for old in old_labels:
            if LABELS[key] not in sections and old in sections:
                sections[LABELS[key]] = sections.pop(old)
    missing = [label for label in LABELS.values() if label not in sections]
    if missing:
        raise ValueError(f"issue is missing form sections: {missing}")
    get = lambda key: sections[LABELS[key]]
    if len(re.findall(r"^- \[[xX]\] ", get("consent"), re.M)) != CONSENT_BOXES:
        raise ValueError("all consent boxes must be checked")
    year = int(get("year"))
    status = STATUSES.get(get("status"))
    service = SERVICES.get(get("service"))
    if not status or not service:
        raise ValueError("unrecognized serving status or service")
    reported = date.fromisoformat(get("as_of"))
    if reported > review_date:
        raise ValueError("status date cannot be in the future")
    rank, highest, industry = get("rank"), get("highest_rank"), get("industry")
    if status == "still_in":
        if highest not in BLANK or industry not in BLANK:
            raise ValueError("still-in report includes out-only answers; ask the submitter to correct it")
        rank = "Not disclosed" if rank in BLANK else rank
        industry = ""
    else:
        if rank not in BLANK:
            raise ValueError("out report includes a current pay grade; ask the submitter to correct it")
        rank = "Not disclosed" if highest in BLANK else highest
        industry = "Not disclosed" if industry in BLANK else industry
    raw = get("community")
    chosen = [] if raw in BLANK else [item.strip() for item in raw.split(", ")]
    unknown = [item for item in chosen if item not in builder.COMMUNITIES]
    if unknown:
        raise ValueError(f"unrecognized communities: {unknown}")
    chosen = sorted(set(chosen), key=builder.COMMUNITIES.index) or ["Not disclosed"]
    return {
        "year": str(year), "kind": "voluntary", "service": service, "status": status, "rank": rank,
        "community": builder.COMMUNITY_SEPARATOR.join(chosen), "industry": industry,
    }


ROW_KEYS = ["year", "kind", "service", "status", "rank", "community", "industry"]


def update_rows(rows, report, delta, review_date):
    """Add delta respondents to the report's aggregate row in-place; return the new count."""
    if not any(row["year"] == report["year"] and row["kind"] == "class" for row in rows):
        raise ValueError(f"class {report['year']} has no cited class rows yet")
    match = next((row for row in rows if all(row[key] == report[key] for key in ROW_KEYS)), None)
    if match is None:
        if delta < 0:
            raise ValueError("no matching aggregate row to subtract")
        match = {field: "" for field in rows[0]} | report | {"count": "0"}
        rows.append(match)
    count = int(match["count"]) + delta
    if count < 0:
        raise ValueError("aggregate count cannot become negative")
    match["count"], match["as_of"] = str(count), review_date.isoformat()
    if count == 0:
        rows.remove(match)
    return count


def apply_changes(csv_path, changes, review_date):
    """Apply [(report, delta), ...] atomically, validating the whole CSV before writing."""
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    count = None
    for report, delta in changes:
        count = update_rows(rows, report, delta, review_date)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    with tempfile.TemporaryDirectory() as directory:
        check = Path(directory) / "cohorts.csv"
        check.write_text(output.getvalue(), encoding="utf-8")
        for source in builder.read_sources(check):
            builder.build_class(source)
    csv_path.write_text(output.getvalue(), encoding="utf-8")
    return count


def apply(csv_path, report, delta, review_date):
    return apply_changes(csv_path, [(report, delta)], review_date)


def previous_row(text):
    """Parse a previously accepted row (JSON) and check it only uses allowed values."""
    row = json.loads(text)
    if not isinstance(row, dict) or sorted(row) != sorted(ROW_KEYS) or row["kind"] != "voluntary":
        raise ValueError("previous accepted report is malformed")
    if not all(isinstance(value, str) for value in row.values()) or not row["year"].isdigit():
        raise ValueError("previous accepted report is malformed")
    if row["status"] not in STATUSES.values() or row["service"] not in SERVICES.values():
        raise ValueError("previous accepted report is malformed")
    builder.parse_communities(row["community"])
    builder.build_voluntary([dict(row, count="1", as_of="2000-01-01")])
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("issue_body", help="file containing the issue body, or - for stdin")
    parser.add_argument("--subtract", action="store_true", help="remove a previously accepted response")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(),
                        help="aggregate review date (default: today)")
    parser.add_argument("--previous-json", help="previously accepted row (JSON) to replace with this report")
    parser.add_argument("--json-out", type=Path, help="write the accepted row as JSON to this file")
    parser.add_argument("--csv", type=Path, default=ROOT / "data" / "cohorts.csv")
    args = parser.parse_args()
    body = sys.stdin.read() if args.issue_body == "-" else Path(args.issue_body).read_text(encoding="utf-8")
    try:
        report = report_row(body, args.as_of)
        changes = [(report, -1 if args.subtract else 1)]
        if args.previous_json:
            if args.subtract:
                raise ValueError("--previous-json cannot be combined with --subtract")
            previous = previous_row(args.previous_json)
            changes = [] if previous == report else [(previous, -1)] + changes
        count = apply_changes(args.csv, changes, args.as_of) if changes else None
    except (ValueError, json.JSONDecodeError) as error:
        sys.exit(f"Not applied: {error}")
    if args.json_out:
        args.json_out.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    if count is None:
        print(f"Unchanged: {report} matches the previously accepted report")
        return
    print(f"{'Subtracted' if args.subtract else 'Added'} {report} -> aggregate count {count}")
    print("Next: python scripts/build_data.py && python -m unittest discover -s tests -v")


if __name__ == "__main__":
    main()
