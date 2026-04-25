#!/usr/bin/env python3
"""
Find candidate mutashabihat pairs directly from quran.json using:
  1. Shared verbatim phrases (longest shared n-gram of 4+ words)
  2. Near-identical verses (Jaccard word similarity >= threshold)

Output: candidates.json sorted by score descending.
Pairs already in pairs.json (any status) are excluded.
"""

import json
import re
from collections import defaultdict

QURAN_JSON  = "/var/www/hifzlink-staging/hifzlink/data/quran.json"
PAIRS_JSON  = "pairs.json"
OUTPUT      = "candidates.json"

MIN_PHRASE  = 4      # min shared phrase length (words)
MIN_JACCARD = 0.65   # min Jaccard for near-identical
MIN_SHARED  = 5      # min shared non-common words for Jaccard candidate
MAX_COMMON  = 80     # words appearing in more than this many verses are stopwords


def normalize(text):
    text = re.sub(r'[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۤۧۨ-ۭ]', '', text)
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = text.replace('ـ', '')
    text = re.sub(r'[^؀-ۿ\s]', '', text)
    return ' '.join(text.split())


def tokenize(text):
    return normalize(text).split()


def ngrams(words, n):
    return [tuple(words[i:i+n]) for i in range(len(words) - n + 1)]


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def main():
    with open(QURAN_JSON) as f:
        quran = json.load(f)

    abs_to_ref = {i + 1: f"{e['surah']}:{e['ayah']}" for i, e in enumerate(quran)}
    ref_to_abs = {v: k for k, v in abs_to_ref.items()}

    # Load existing pairs (all statuses) to exclude
    try:
        with open(PAIRS_JSON) as f:
            existing_raw = json.load(f)
        existing = set()
        for p in existing_raw:
            a1 = ref_to_abs.get(p["ayah1"])
            a2 = ref_to_abs.get(p["ayah2"])
            if a1 and a2:
                existing.add((min(a1, a2), max(a1, a2)))
        print(f"Excluding {len(existing)} existing pairs")
    except FileNotFoundError:
        existing = set()

    verse_tokens = [tokenize(e['text_ar']) for e in quran]

    # --- Build stopword set: words appearing in too many verses ---
    word_freq = defaultdict(int)
    for tokens in verse_tokens:
        for w in set(tokens):
            word_freq[w] += 1
    stopwords = {w for w, f in word_freq.items() if f > MAX_COMMON}
    print(f"Stopwords (freq > {MAX_COMMON}): {len(stopwords)}")

    # --- Phase 1: Longest shared phrase per pair ---
    print("Phase 1: shared phrase detection...")
    ngram_index = defaultdict(list)  # ngram_tuple -> [abs_num, ...]
    for i, tokens in enumerate(verse_tokens):
        abs_num = i + 1
        if len(tokens) < MIN_PHRASE:
            continue
        seen = set()
        for n in range(MIN_PHRASE, min(len(tokens) + 1, 15)):
            for ng in ngrams(tokens, n):
                if ng not in seen:
                    seen.add(ng)
                    ngram_index[ng].append(abs_num)

    # For each pair, track the longest shared ngram
    best_phrase = {}  # (a1,a2) -> longest ngram tuple
    for ng, verses in ngram_index.items():
        unique = list(set(verses))
        if len(unique) < 2:
            continue
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                a1 = min(unique[i], unique[j])
                a2 = max(unique[i], unique[j])
                key = (a1, a2)
                if key in existing:
                    continue
                if key not in best_phrase or len(ng) > len(best_phrase[key]):
                    best_phrase[key] = ng

    print(f"  {len(best_phrase)} pairs with shared phrase")

    # --- Phase 2: Near-identical via Jaccard ---
    print("Phase 2: near-identical detection...")
    content_word_index = defaultdict(set)
    for i, tokens in enumerate(verse_tokens):
        abs_num = i + 1
        for w in set(tokens):
            if w not in stopwords and len(w) >= 3:
                content_word_index[w].add(abs_num)

    pair_shared_count = defaultdict(int)
    for w, verses in content_word_index.items():
        if len(verses) < 2 or len(verses) > 30:
            continue
        vlist = sorted(verses)
        for i in range(len(vlist)):
            for j in range(i + 1, len(vlist)):
                key = (vlist[i], vlist[j])
                if key not in existing:
                    pair_shared_count[key] += 1

    jaccard_scores = {}
    for key, shared_count in pair_shared_count.items():
        if shared_count < MIN_SHARED:
            continue
        a1, a2 = key
        j = jaccard(verse_tokens[a1 - 1], verse_tokens[a2 - 1])
        if j >= MIN_JACCARD:
            jaccard_scores[key] = j

    print(f"  {len(jaccard_scores)} near-identical pairs")

    # --- Merge ---
    all_keys = set(best_phrase.keys()) | set(jaccard_scores.keys())
    output = []

    for key in all_keys:
        a1, a2 = key
        entry = {
            "ayah1": abs_to_ref[a1],
            "ayah2": abs_to_ref[a2],
        }

        if key in best_phrase:
            ng = best_phrase[key]
            entry["type"] = "verbatim"
            entry["phrase_len"] = len(ng)
            entry["shared_phrase"] = ' '.join(ng)

        if key in jaccard_scores:
            j = jaccard_scores[key]
            if "type" in entry:
                entry["type"] = "verbatim+jaccard"
            else:
                entry["type"] = "jaccard"
            entry["jaccard"] = round(j, 3)

        score = entry.get("phrase_len", 0) * 2 + entry.get("jaccard", 0) * 10
        entry["score"] = round(score, 2)
        output.append(entry)

    output.sort(key=lambda x: -x["score"])

    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nWrote {len(output)} candidates to {OUTPUT}")
    verbatim = sum(1 for x in output if 'verbatim' in x['type'])
    jac_only = sum(1 for x in output if x['type'] == 'jaccard')
    both     = sum(1 for x in output if x['type'] == 'verbatim+jaccard')
    print(f"  verbatim only: {verbatim - both}")
    print(f"  jaccard only:  {jac_only}")
    print(f"  both:          {both}")

    print("\nTop 30 candidates:")
    for e in output[:30]:
        phrase = e.get('shared_phrase', '')[:55]
        j = e.get('jaccard', '')
        print(f"  {e['ayah1']:8} <-> {e['ayah2']:8}  [{e['type']:20}]  score={e['score']:5}  {phrase}")


if __name__ == "__main__":
    main()
