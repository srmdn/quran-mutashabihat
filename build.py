#!/usr/bin/env python3
"""
Build pairs.json from hifzlink seed (curated) + Waqar144 data (pending).

Output schema per entry:
  {"ayah1": "s:a", "ayah2": "s:a", "category": "...", "note": "...", "status": "curated|pending|dropped"}

Pairs are canonical: ayah1 has a lower absolute number than ayah2.
Multi-verse block entries from Waqar144 are skipped.

Re-running this script preserves existing curated and dropped entries.
Only new Waqar144 pairs not already in pairs.json are added as pending.
"""

import json
import sys

QURAN_JSON = "/var/www/hifzlink-staging/hifzlink/data/quran.json"
WAQAR_JSON = "waqar_raw.json"
SEED_JSON  = "/var/www/hifzlink-staging/hifzlink/data/relations.seed.json"
OUTPUT     = "pairs.json"


def build_maps(quran):
    abs_to_ref = {}  # 1-indexed absolute -> "s:a"
    ref_to_abs = {}  # "s:a" -> 1-indexed absolute
    for i, entry in enumerate(quran):
        abs_num = i + 1
        ref = f"{entry['surah']}:{entry['ayah']}"
        abs_to_ref[abs_num] = ref
        ref_to_abs[ref] = abs_num
    return abs_to_ref, ref_to_abs


def canonical(a, b):
    """Return (lower_abs, higher_abs) pair."""
    return (a, b) if a < b else (b, a)


def extract_waqar_pairs(waqar, abs_to_ref):
    pairs = set()
    skipped_multi = 0
    for surah_key, entries in waqar.items():
        for entry in entries:
            src_ayah = entry["src"]["ayah"]
            if isinstance(src_ayah, list):
                skipped_multi += 1
                continue
            for mut in entry["muts"]:
                mut_ayah = mut["ayah"]
                if isinstance(mut_ayah, list):
                    continue
                if src_ayah not in abs_to_ref or mut_ayah not in abs_to_ref:
                    print(f"WARNING: unknown absolute ayah {src_ayah} or {mut_ayah}", file=sys.stderr)
                    continue
                pairs.add(canonical(src_ayah, mut_ayah))
    print(f"Waqar144: {len(pairs)} single-verse pairs, skipped {skipped_multi} multi-verse block entries")
    return pairs


def extract_seed_pairs(seeds, ref_to_abs):
    pairs = {}  # canonical (abs1, abs2) -> {category, note}
    for s in seeds:
        a1 = ref_to_abs.get(s["ayah1"])
        a2 = ref_to_abs.get(s["ayah2"])
        if a1 is None or a2 is None:
            print(f"WARNING: unknown ref {s['ayah1']} or {s['ayah2']} in seed", file=sys.stderr)
            continue
        key = canonical(a1, a2)
        pairs[key] = {"category": s.get("category", ""), "note": s.get("note", "")}
    print(f"Seed: {len(pairs)} curated pairs")
    return pairs


def load_existing(path, ref_to_abs):
    """Load existing pairs.json; return dict of canonical key -> entry."""
    try:
        with open(path) as f:
            existing = json.load(f)
    except FileNotFoundError:
        return {}
    result = {}
    for entry in existing:
        a1 = ref_to_abs.get(entry["ayah1"])
        a2 = ref_to_abs.get(entry["ayah2"])
        if a1 and a2:
            result[canonical(a1, a2)] = entry
    return result


def main():
    with open(QURAN_JSON) as f:
        quran = json.load(f)
    with open(WAQAR_JSON) as f:
        waqar = json.load(f)
    with open(SEED_JSON) as f:
        seeds = json.load(f)

    abs_to_ref, ref_to_abs = build_maps(quran)
    waqar_pairs = extract_waqar_pairs(waqar, abs_to_ref)
    seed_pairs  = extract_seed_pairs(seeds, ref_to_abs)
    existing    = load_existing(OUTPUT, ref_to_abs)

    # Keys already reviewed (curated or dropped) -- do not overwrite
    reviewed = {k for k, v in existing.items() if v["status"] in ("curated", "dropped")}

    gap = waqar_pairs - set(seed_pairs.keys())

    # Include all reviewed pairs so find_candidates.py curations are preserved on rebuild
    all_keys = set(seed_pairs.keys()) | gap | set(reviewed)
    output = []

    for key in sorted(all_keys):
        a1, a2 = key
        if key in reviewed:
            output.append(existing[key])
        elif key in seed_pairs:
            meta = seed_pairs[key]
            output.append({
                "ayah1":    abs_to_ref[a1],
                "ayah2":    abs_to_ref[a2],
                "category": meta["category"],
                "note":     meta["note"],
                "status":   "curated",
            })
        else:
            # Preserve pending note/category if already partially worked
            prev = existing.get(key, {})
            output.append({
                "ayah1":    abs_to_ref[a1],
                "ayah2":    abs_to_ref[a2],
                "category": prev.get("category", ""),
                "note":     prev.get("note", ""),
                "status":   "pending",
            })

    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    curated = sum(1 for x in output if x["status"] == "curated")
    pending = sum(1 for x in output if x["status"] == "pending")
    dropped = sum(1 for x in output if x["status"] == "dropped")
    print(f"\nWrote {len(output)} total pairs to {OUTPUT}")
    print(f"  curated: {curated}")
    print(f"  pending: {pending}")
    print(f"  dropped: {dropped}")


if __name__ == "__main__":
    main()
