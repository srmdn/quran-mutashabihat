# quran-mutashabihat

A curated dataset of mutashabihat (similar/repeated) Quran verse pairs, used to help huffaz distinguish verses that are easy to confuse during recitation.

## Format

All pairs are stored in `pairs.json` as a flat array:

```json
[
  {
    "ayah1": "2:255",
    "ayah2": "20:111",
    "category": "lafzi",
    "note": "Both contain 'al-Hayy al-Qayyum' as divine attributes — the phrase appears identically in both verses.",
    "status": "curated"
  }
]
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `ayah1` | `"surah:ayah"` | First verse reference (lower absolute number) |
| `ayah2` | `"surah:ayah"` | Second verse reference (higher absolute number) |
| `category` | string | Similarity type (see below); empty for pending pairs |
| `note` | string | Human-readable explanation of how the verses differ; empty for pending pairs |
| `status` | `"curated"` or `"pending"` | `curated` = reviewed with category + note; `pending` = sourced from Waqar144, not yet reviewed |

### Categories

| Value | Meaning |
|-------|---------|
| `lafzi` | Word-for-word identical phrases in both verses |
| `word_swap` | Same structure but one or more words differ |
| `addition_omission` | One verse has a word or phrase the other lacks |
| `context_shift` | Same wording but the surrounding context changes the meaning |
| `structural` | Similar grammatical or rhetorical structure |

Pairs are canonical: `ayah1` always has a lower absolute Quran position than `ayah2`.

## Dataset stats

- **Curated**: 148 pairs (reviewed, with category and note)
- **Pending**: 1,379 pairs (sourced from Waqar144 baseline, awaiting review)
- **Total**: 1,527 pairs

## Data sources

Curated pairs are original work, written and reviewed for [hifzlink](https://github.com/srmdn/hifzlink).

Pending pairs are derived from:

> Waqar Akram, *Quran Mutashabihat Data*
> https://github.com/Waqar144/Quran_Mutashabihat_Data

Multi-verse block entries from that dataset are excluded (single-verse pairs only). Attribution is preserved as requested by the original author.

## Usage

Consumers should filter by `status: "curated"` for production use. Pending pairs have not been reviewed and may contain errors or noise.

```js
const pairs = require('./pairs.json');
const curated = pairs.filter(p => p.status === 'curated');
```

## License

Curated data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

Pending pairs derived from Waqar144's dataset: no formal license; attribution required (see above).
