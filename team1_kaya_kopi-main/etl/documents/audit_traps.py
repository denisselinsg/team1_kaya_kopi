"""Print aggregate document-trap evidence without message bodies or identities."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from etl.documents.document_parser import parse_whatsapp


def audit(path: Path) -> dict:
    raw = path.read_bytes()
    parsed = parse_whatsapp(raw.decode("utf-8-sig"))
    if parsed.issues or not parsed.records:
        raise ValueError("Resolve chat parsing issues before trusting aggregate evidence")
    rows = parsed.records
    templates = Counter(
        re.sub(r"\b[A-Z]{3}-[0-9][A-Z0-9]\b", "{X}", row.body)
        for row in rows
    )
    labelled = [
        (re.search(r"\((TPY|AMK|BDK)\)$", row.sender or ""), row.outlets)
        for row in rows
    ]
    labelled = [(match[1], outlets) for match, outlets in labelled if match and outlets]
    fridge = [row for row in rows if "fridge spoil" in row.body]
    groups = Counter(
        (code, row.timestamp.strftime("%Y-%m"))
        for row in fridge for code in row.outlets
    )
    wastage = [row for row in rows if "wastage quite high" in row.body]
    supplier_dates = [row.timestamp for row in rows if "Mewah" in row.body]
    return {
        "messages": len(rows),
        "parser_issues": len(parsed.issues),
        "backward_pairs": sum(
            b.timestamp < a.timestamp for a, b in zip(rows, rows[1:])
        ),
        "templates": len(templates),
        "distinct_bodies": len({row.body for row in rows}),
        "repeated_sender_body": len(rows) - len({(row.sender, row.body) for row in rows}),
        "template_counts": sorted(templates.values()),
        "date_range": [min(row.timestamp for row in rows).isoformat(),
                       max(row.timestamp for row in rows).isoformat()],
        "distinct_days": len({row.timestamp.date() for row in rows}),
        "monthly_counts": dict(sorted(Counter(
            row.timestamp.strftime("%Y-%m") for row in rows
        ).items())),
        "trailing_newline": raw.endswith(b"\n"),
        "old_alias_mentions": sum("AMK-03" in row.body for row in rows),
        "old_alias_2026": sum(
            "AMK-03" in row.body and row.timestamp.year == 2026 for row in rows
        ),
        "new_alias_mentions": sum("AMK-3A" in row.body for row in rows),
        "outlet_messages": sum(bool(row.outlets) for row in rows),
        "labelled_with_outlet": len(labelled),
        "prefix_mismatches": sum(
            not outlets[0].startswith(prefix) for prefix, outlets in labelled
        ),
        "fridge_mentions": len(fridge),
        "max_outlet_month_mentions": max(groups.values(), default=0),
        "wastage_mentions": len(wastage),
        "wastage_outlets": len({code for row in wastage for code in row.outlets}),
        "holiday_requests": sum(row.body.startswith("tmr PH") for row in rows),
        "named_supplier_mentions": {
            name: sum(name in row.body for row in rows) for name in ("Mewah", "Ban Seng")
        },
        "latest_named_supplier_message": (
            max(supplier_dates).isoformat() if supplier_dates else None
        ),
        "expanded_phrase_matches": {
            phrase: sum(phrase in row.body.lower() for row in rows)
            for phrase in ("public holiday", "carton", "medical leave")
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", nargs="?", type=Path,
        default=Path("data") / "docs" / "whatsapp_exports" / "ops_chat_export.txt",
    )
    args = parser.parse_args()
    try:
        result = audit(args.path)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f"Chat audit failed: {type(exc).__name__}; check input and parser.\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
