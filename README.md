# quran-mutashabihat

A curated dataset of mutashabihat (similar or repeated) Quran verse pairs. It
helps huffaz distinguish verses that are easy to confuse during recitation.

## Format

All pairs are stored in `pairs.json` as a flat array:

```json
[
  {
    "ayah1": "2:255",
    "ayah2": "20:111",
    "category": "lafzi",
    "note": "Both contain 'al-Hayy al-Qayyum' as divine attributes; the phrase appears identically in both verses.",
    "status": "curated"
  }
]
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `ayah1` | `"surah:ayah"` | First verse reference (lower absolute number) |
| `ayah2` | `"surah:ayah"` | Second verse reference (higher absolute number) |
| `category` | string | Similarity type (see below); empty when the live relation has no category |
| `note` | string | Human-readable explanation of how the verses differ; may be empty when live has no note |
| `status` | `"curated"`, `"pending"`, or `"dropped"` | `curated` = accepted relation; for pairs in HifzLink production, category and note mirror live exactly, including blanks; `pending` = baseline or live candidate awaiting review; `dropped` = reviewed and rejected (note explains why) |

### Categories

| Value | Meaning |
|-------|---------|
| `lafzi` | Word-for-word identical phrases in both verses |
| `word_swap` | Same structure but one or more words differ |
| `addition_omission` | One verse has a word or phrase the other lacks |
| `ending_variation` | Verses differ primarily in their ending word or phrase |
| `order_change` | The same words or phrases appear in a different order |
| `pronoun_shift` | The verses differ primarily in their pronouns |
| `structural` | Similar grammatical or rhetorical structure |

Pairs are canonical: `ayah1` always has a lower absolute Quran position than `ayah2`.

## Dataset stats

- **Curated**: 285 pairs (accepted relations, matching live values)
- **Pending**: 1,359 pairs (baseline or live candidates awaiting review)
- **Dropped**: 15 pairs (reviewed and rejected)
- **Total**: 1,659 pairs

## Data sources

Curated pairs are original work, written and reviewed for [hifzlink](https://github.com/srmdn/hifzlink).

Pending pairs are derived from:

> Waqar Akram, *Quran Mutashabihat Data*
> https://github.com/Waqar144/Quran_Mutashabihat_Data

Multi-verse block entries from that dataset are excluded. The dataset contains
single-verse pairs only. Attribution is preserved as requested by the original
author.

## Usage

Consumers must filter by `status: "curated"` for production use. Pending pairs
have not been reviewed. Dropped pairs were reviewed and rejected; the `note`
field explains why.

```js
const pairs = require('./pairs.json');
const curated = pairs.filter(p => p.status === 'curated');
```

## Maintenance Scripts

`build.py` rebuilds `pairs.json` from a Quran JSON file, `waqar_raw.json`, and a
HifzLink `relations.seed.json` file.

```bash
QURAN_JSON=/path/to/quran.json \
SEED_JSON=/path/to/relations.seed.json \
python3 build.py
```

`find_candidates.py` generates `candidates.json` from the Quran JSON file and
excludes pairs already present in `pairs.json`. Each result is labeled
`Auto-suggested` and `needs-human-review`. Its `type` identifies the matching
signal (`verbatim`, `jaccard`, or both). `suggested_category` is provisional
and uses simple token-sequence heuristics to distinguish exact wording,
additions or omissions, word swaps, changed endings, word order, and broader
structural matches. Only normalized verse-for-verse identity is marked strong;
all other categories are tentative. `category_suggestion_confidence` and
`category_suggestion_basis` explain each guess. These suggestions
do not change any pair's status or category in `pairs.json`. Optionally set
`PRODUCTION_RELATIONS_JSON` to a private HifzLink relations export; the tool
uses its verse-pair keys only to exclude live pairs and never copies export
metadata into `candidates.json`. `review_priority` ranks shared phrases of at
least eight words or Jaccard matches of at least 0.8 as high, phrases of at
least six words or Jaccard matches of at least 0.7 as medium, and the rest as
exploratory. These are search priorities only, not acceptance decisions.
Generated `candidates.json` is a local review artifact. HifzLink's versioned
`data/curation_candidates.json` is a compact copy used to initialize the
private admin review queue; candidates remain outside the public catalog until
an administrator accepts them.

To prepare the app's compact review file after generating candidates:

```bash
python3 export_hifzlink_candidates.py candidates.json /path/to/hifzlink/data/curation_candidates.json
```

```bash
QURAN_JSON=/path/to/quran.json python3 find_candidates.py
```

## License

Curated data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

Pending pairs derived from Waqar144's dataset: no formal license; attribution required (see above).

## Refining automatic runtime labels

`refine_hifzlink_curation.py` plans changes against a local curation snapshot,
preserves all human decisions, and applies the reviewed plan to an explicit local
copy with a backup and stale-state guard. Plans include private review notes and
must stay outside Git. Use `plan --help`, `apply --help`, and `export --help`.

Build the analyzer from the matching HifzLink feature revision with
`go build -o /tmp/hifzlink-analyze ./scripts/analyze_curation`. The analyzer owns
the `wording-v2` rules, shared with the application; see its `docs/CURATION.md`
for thresholds, priority, highlights, and limitations. Use `export` to refine
compact candidate suggestions before importing them. The earlier candidate
detector output alone is not the final label assignment.

This workflow does not change `pairs.json` or overwrite curated production values.
A production update requires a fresh snapshot and separate explicit approval.
