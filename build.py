#!/usr/bin/env python3
"""
Build pairs.json from hifzlink seed (curated) + Waqar144 data (pending).

Output schema per entry:
  {"ayah1": "s:a", "ayah2": "s:a", "category": "...", "note": "...", "status": "curated|pending"}

Pairs are canonical: ayah1 has a lower absolute number than ayah2.
Multi-verse block entries from Waqar144 are skipped.
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

    overlap = waqar_pairs & set(seed_pairs.keys())
    gap     = waqar_pairs - set(seed_pairs.keys())

    print(f"Overlap (Waqar & seed): {len(overlap)}")
    print(f"Gap (Waqar only): {len(gap)}")

    output = []

    # Curated pairs from seed (sorted by ayah1 then ayah2)
    for key in sorted(seed_pairs.keys()):
        a1, a2 = key
        meta = seed_pairs[key]
        output.append({
            "ayah1":    abs_to_ref[a1],
            "ayah2":    abs_to_ref[a2],
            "category": meta["category"],
            "note":     meta["note"],
            "status":   "curated",
        })

    # Pending pairs from Waqar144 not in seed
    for key in sorted(gap):
        a1, a2 = key
        output.append({
            "ayah1":    abs_to_ref[a1],
            "ayah2":    abs_to_ref[a2],
            "category": "",
            "note":     "",
            "status":   "pending",
        })

    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nWrote {len(output)} total pairs to {OUTPUT}")
    print(f"  curated: {len(seed_pairs)}")
    print(f"  pending: {len(gap)}")


if __name__ == "__main__":
    main()
