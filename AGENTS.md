# AGENTS.md

## Purpose

This repository curates mutashabihat Quran verse pairs for HifzLink. It is a
data source repository, not the HifzLink application or a runtime database.

## Scope and boundaries

- Keep all pair data in `pairs.json`.
- Treat `curated` pairs as reviewed production-quality data.
- Treat `pending` pairs as leads that require human Quranic review.
- Keep rejected candidates as `dropped` with an explanatory note when useful.
- Do not copy `.env` files, live SQLite databases, app binaries, or VPS paths
  into this public repository.

## Quran integrity

- Never edit Quran Arabic text or diacritics in external source datasets.
- Verify both ayah references against a trusted mushaf or Quran source before
  marking a pair `curated`.
- Preserve canonical ordering: `ayah1` has the lower Quran position.
- Treat reversed pairs as duplicates.
- Use one accurate category and a concise note that explains the memorization
  risk.
- Preserve source attribution and licensing notes for imported material.

## Workflow

1. Inspect the Git working tree before editing.
2. Review a candidate pair in Arabic and confirm both references.
3. Update `pairs.json` with the correct status, category, and note.
4. Check JSON syntax and duplicate canonical pair keys.
5. Update README statistics if the status totals change.
6. Commit a focused, human-authored change after validation.

When syncing curated pairs into HifzLink, update the application seed in the
HifzLink `staging` worktree and follow its test and deployment workflow. Do not
change live HifzLink SQLite rows as part of an ordinary dataset update.

## Shell commands

Run all terminal commands through RTK. For example:

```sh
rtk git status
rtk python3 -m json.tool pairs.json
```

## Commit hygiene

- Keep commits small and data-focused.
- Use clear human-authored commit messages.
- Do not add AI attribution trailers or branding.
- Never force-push or rewrite shared history without Boss Said's explicit
  approval.
