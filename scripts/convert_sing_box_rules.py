#!/usr/bin/env python3
"""Convert Clash-style domain lists to sing-box source rule sets."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


RULE_TYPES = {
    "DOMAIN": "domain",
    "DOMAIN-SUFFIX": "domain_suffix",
    "DOMAIN-KEYWORD": "domain_keyword",
}
RULE_NAMES = ("Block", "Direct", "GFW")


class RuleFormatError(ValueError):
    """Raised when an input rule cannot be converted safely."""


def parse_rules(path: Path) -> dict[str, list[str]]:
    values: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith(("#", ";", "//")):
            continue

        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2 or not all(parts):
            raise RuleFormatError(
                f"{path}:{line_number}: expected RULE-TYPE,value, got {raw_line!r}"
            )

        rule_type, value = parts
        field = RULE_TYPES.get(rule_type.upper())
        if field is None:
            supported = ", ".join(RULE_TYPES)
            raise RuleFormatError(
                f"{path}:{line_number}: unsupported rule type {rule_type!r}; "
                f"supported types: {supported}"
            )

        if value not in seen[field]:
            values[field].append(value)
            seen[field].add(value)

    return {field: values[field] for field in RULE_TYPES.values() if values[field]}


def convert_file(source: Path, destination: Path) -> None:
    rule = parse_rules(source)
    document = {
        "version": 3,
        "rules": [rule] if rule else [],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def convert_all(repository: Path) -> None:
    source_dir = repository / "Rule"
    destination_dir = repository / "sing-box" / "Rule" / "JSON"

    for name in RULE_NAMES:
        convert_file(source_dir / f"{name}.txt", destination_dir / f"{name}.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args()
    convert_all(args.repository.resolve())


if __name__ == "__main__":
    main()
