#!/usr/bin/env python3
"""Build aggregate class data from documented JSON source inputs."""

import argparse
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    }


def build(source_dir, output_dir):
    classes = [build_class(json.loads(path.read_text(encoding="utf-8")))
               for path in sorted(source_dir.glob("*.json"))]
    if not classes:
        raise ValueError("no class source files found")
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
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data" / "sources")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
