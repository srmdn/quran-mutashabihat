#!/usr/bin/env python3
"""Export compact, labeled candidates for HifzLink's private review queue."""

import json
import sys
from pathlib import Path


FIELDS = (
    "ayah1",
    "ayah2",
    "suggested_category",
    "category_suggestion_confidence",
    "category_suggestion_basis",
    "review_priority",
    "type",
    "phrase_len",
    "jaccard",
)
OPTIONAL_DEFAULTS = {"phrase_len": 0, "jaccard": 0}


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: python3 export_hifzlink_candidates.py INPUT_JSON OUTPUT_JSON")

    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    candidates = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(candidates, list):
        raise ValueError("input must be a JSON array")

    compact = []
    for index, candidate in enumerate(candidates, start=1):
        missing = [field for field in FIELDS if field not in candidate and field not in OPTIONAL_DEFAULTS]
        if missing:
            raise ValueError(f"candidate {index} is missing fields: {', '.join(missing)}")
        compact.append({field: candidate.get(field, OPTIONAL_DEFAULTS.get(field)) for field in FIELDS})

    destination.write_text(
        json.dumps(compact, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Exported {len(compact)} candidates to {destination}")


if __name__ == "__main__":
    main()
