#!/usr/bin/env python3
"""Build public aggregate class JSON from the single maintained CSV."""

import argparse
import csv
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANKS = [f"O-{grade}" for grade in range(1, 11)] + [f"W-{grade}" for grade in range(1, 6)] + ["Other", "Not disclosed"]
INDUSTRIES = [
    "Self-employed / entrepreneur", "Tech / software", "Law", "Civil service / government",
    "Defense / aerospace / government contracting", "Construction / trades / real estate",
    "Engineering / manufacturing", "Finance / banking / insurance", "Consulting / business services",
    "Healthcare / medicine", "Education / academia", "Energy / utilities",
    "Transportation / aviation / maritime / logistics", "Sales / marketing / retail",
    "Media / entertainment / arts", "Nonprofit / ministry", "Politics / public policy",
    "Law enforcement / first responder", "Student / graduate school",
    "Not working / retired / caregiving", "Other", "Not disclosed",
]
# Multi-select: respondents may list every community they served in (e.g. lateral transfers).
# Names must not contain commas or semicolons (GitHub joins multi-select answers with ", ";
# the CSV stores combinations joined with "; ").
COMMUNITIES = [
    "Surface", "Submarine", "Aviation", "Special Warfare (SEAL)", "Special Operations (EOD)",
    "Nuclear Power (Naval Reactors / Instructor)", "Intelligence", "Cryptologic Warfare",
    "Information Professional", "Oceanography (METOC)", "Maritime Space", "Foreign Area Officer",
    "Engineering Duty", "Aerospace Engineering Duty", "Aviation Maintenance Duty",
    "Human Resources", "Public Affairs", "Medical", "Supply", "Civil Engineer Corps", "JAG",
    "Chaplain", "Infantry", "Artillery", "Armor / Assault Amphibian", "Combat Engineer",
    "Logistics", "Communications", "Military Police", "Air Command and Control",
    "Other service (Army / Air Force / Space Force / Coast Guard)", "Other", "Not disclosed",
]
COMMUNITY_SEPARATOR = "; "


def parse_communities(value):
    """Return a canonical community list; reject unknown, duplicate, or out-of-order values."""
    communities = (value or "").split(COMMUNITY_SEPARATOR) if value else []
    if not communities or any(item not in COMMUNITIES for item in communities):
        raise ValueError(f"invalid community value: {value!r}")
    if len(set(communities)) != len(communities):
        raise ValueError(f"duplicate community: {value!r}")
    if "Not disclosed" in communities and len(communities) > 1:
        raise ValueError("Not disclosed cannot be combined with other communities")
    if communities != sorted(communities, key=COMMUNITIES.index):
        raise ValueError(f"communities must follow the canonical order: {value!r}")
    return communities


def read_sources(source_file):
    classes = {}
    seen_services = set()
    seen_reports = set()
    with source_file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV row does not match the header; check comma quoting")
            year = int(row["year"])
            source = classes.setdefault(year, {
                "year": year, "by_service": {}, "sources": [], "voluntary_rows": [],
            })
            kind = row["kind"]
            if kind == "class":
                if "commissioned_total" in source:
                    raise ValueError(f"duplicate class metadata: {year}")
                source.update(
                    commissioned_total=int(row["count"]), as_of=row["as_of"],
                    confidence=row["title"], coverage_note=row["notes"],
                )
            elif kind == "method":
                if "method" in source:
                    raise ValueError(f"duplicate method: {year}")
                source["method"] = row["notes"]
            elif kind == "service":
                key = (year, row["service"])
                if not row["service"] or key in seen_services:
                    raise ValueError(f"empty or duplicate commissioning service: {key}")
                seen_services.add(key)
                source["by_service"][row["service"]] = {
                    "commissioned": int(row["count"]),
                    "assumed_retention_rate": row["retention_rate"],
                }
            elif kind == "source":
                if not row["title"] or not row["url"].startswith("https://"):
                    raise ValueError("sources require a title and HTTPS URL")
                source["sources"].append({"title": row["title"], "url": row["url"]})
            elif kind == "voluntary":
                parse_communities(row["community"])
                key = (year, row["service"], row["status"], row["rank"], row["community"], row["industry"])
                if key in seen_reports:
                    raise ValueError(f"duplicate voluntary aggregate: {key}")
                seen_reports.add(key)
                source["voluntary_rows"].append(row)
            else:
                raise ValueError(f"unknown CSV row kind: {kind}")
    for source in classes.values():
        for field in ["commissioned_total", "as_of", "confidence", "coverage_note", "method"]:
            if not source.get(field):
                raise ValueError(f"missing class metadata: {field}")
        if not source["sources"]:
            raise ValueError("at least one cited public source is required")
    return list(classes.values())


def distribution(labels, counts, total, key):
    return [
        {key: label, "count": counts[label],
         "percent": round(100 * counts[label] / total, 1) if total else None}
        for label in labels
    ]


def build_voluntary(rows):
    counts = {rank: 0 for rank in RANKS}
    highest = {rank: 0 for rank in RANKS}
    industries = {industry: 0 for industry in INDUSTRIES}
    communities = {community: 0 for community in COMMUNITIES}
    responses = []
    still_in = out = multiple = 0
    report_dates = []
    for row in rows:
        count = int(row["count"])
        if count < 0 or not row["service"]:
            raise ValueError("voluntary counts must be nonnegative and have a service")
        report_date = date.fromisoformat(row["as_of"])
        if report_date > date.today():
            raise ValueError("report aggregate date cannot be in the future")
        report_dates.append(row["as_of"])
        industry = row.get("industry", "")
        community_list = parse_communities(row.get("community", ""))
        if row["status"] == "still_in" and row["rank"] in RANKS and industry == "":
            still_in += count
            counts[row["rank"]] += count
        elif row["status"] == "out" and row["rank"] in RANKS and industry in INDUSTRIES:
            out += count
            highest[row["rank"]] += count
            industries[industry] += count
        else:
            raise ValueError("invalid voluntary status/rank/industry combination")
        for community in community_list:
            communities[community] += count
        if len(community_list) > 1:
            multiple += count
        if count:
            responses.append({
                "status": row["status"], "service": row["service"], "rank": row["rank"],
                "communities": community_list, "industry": industry or None, "count": count,
            })
    total = still_in + out
    return {
        "reported_still_in": still_in,
        "reported_out": out,
        "as_of": max(report_dates) if report_dates else None,
        "rank_distribution": distribution(RANKS, counts, still_in, "rank"),
        "highest_rank_distribution": distribution(RANKS, highest, out, "rank"),
        "industry_distribution": distribution(INDUSTRIES, industries, out, "industry"),
        "reported_multiple_communities": multiple,
        "community_distribution": distribution(COMMUNITIES, communities, total, "community"),
        "responses": responses,
    }


def build_class(source):
    year = source["year"]
    if type(year) is not int or not 1845 <= year <= date.today().year:
        raise ValueError("year must be a valid USNA class year")
    date.fromisoformat(source["as_of"])
    services = source["by_service"]
    if not services:
        raise ValueError("at least one commissioning service is required")
    by_service = {}
    for name, service in services.items():
        count = service["commissioned"]
        rate = Decimal(str(service["assumed_retention_rate"]))
        if type(count) is not int or count < 0 or not rate.is_finite() or not 0 <= rate <= 1:
            raise ValueError(f"invalid commissioning count or retention assumption: {name}")
        still_in = int((count * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        by_service[name] = {
            "commissioned": count,
            "estimated_still_in": still_in,
            "estimated_out": count - still_in,
            "assumed_retention_rate": float(rate),
        }
    total = sum(service["commissioned"] for service in by_service.values())
    if total <= 0 or total != source["commissioned_total"]:
        raise ValueError("service counts must sum to the positive commissioned_total")
    still_in = sum(service["estimated_still_in"] for service in by_service.values())
    percent_in = round(100 * still_in / total, 1)
    return {
        "year": year,
        "commissioned_total": total,
        "by_service": by_service,
        "estimated_still_in": still_in,
        "estimated_out": total - still_in,
        "percent_in": percent_in,
        "percent_out": round(100 - percent_in, 1),
        "as_of": source["as_of"],
        "method": source["method"],
        "confidence": source["confidence"],
        "coverage_note": source["coverage_note"],
        "sources": source["sources"],
        "voluntary": build_voluntary(source.get("voluntary_rows", [])),
    }


def build(source_file, output_dir):
    classes = [build_class(source) for source in read_sources(source_file)]
    if not classes:
        raise ValueError("no class rows found in CSV")
    years = [entry["year"] for entry in classes]
    if len(years) != len(set(years)):
        raise ValueError("duplicate class years")
    output_dir.mkdir(parents=True, exist_ok=True)
    for entry in classes:
        (output_dir / f'{entry["year"]}.json').write_text(
            json.dumps(entry, indent=2) + "\n", encoding="utf-8"
        )
    (output_dir / "index.json").write_text(
        json.dumps({"years": sorted(years, reverse=True)}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Built {len(classes)} class(es) in {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-file", type=Path, default=ROOT / "data" / "cohorts.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    build(args.source_file, args.output_dir)
