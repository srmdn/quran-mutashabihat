#!/usr/bin/env python3
"""Plan or apply wording refinement on an explicitly supplied local curation DB.

Uses HifzLink's analyzer binary so dashboard suggestions and batch rules agree.
Plans contain private review metadata: keep them outside both repositories.
"""
import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import unicodedata


def connect(path, writable=False):
    return sqlite3.connect(path.resolve().as_uri() + ('?mode=rw' if writable else '?mode=ro'), uri=True)


def rows(conn, table):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute('SELECT * FROM ' + table + ' ORDER BY id')]


def fingerprint(conn):
    # Include all tables, including any local account data, in the concurrency guard.
    state = {}
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        state[table] = [list(row) for row in conn.execute('SELECT * FROM "' + table.replace('"', '""') + '" ORDER BY rowid')]
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_private(path, data):
    import os
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def legacy_highlights(text1, text2):
    def norm(word):
        return ''.join('ا' if ch in 'أإآٱ' else ch for ch in word
                       if ch != 'ـ' and unicodedata.category(ch) != 'Mn')
    a, b = ([norm(w) for w in text.split()] for text in (text1, text2))
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            dp[i][j] = dp[i-1][j-1]+1 if a[i-1] == b[j-1] else max(dp[i-1][j], dp[i][j-1])
    i, j = len(a), len(b)
    ai, bi = set(), set()
    while i and j:
        if a[i-1] == b[j-1]:
            ai.add(i-1); bi.add(j-1); i -= 1; j -= 1
        elif dp[i-1][j] > dp[i][j-1]:
            i -= 1
        else:
            j -= 1
    return {'ayah1': [i for i in range(len(a)) if i not in ai],
            'ayah2': [i for i in range(len(b)) if i not in bi]}


def plan(args):
    conn = connect(args.database)
    conn.execute('BEGIN')
    baseline = fingerprint(conn)
    relations = {r['id']: r for r in rows(conn, 'relations')}
    candidates = rows(conn, 'curation_candidates')
    quran = {f"{v['surah']}:{v['ayah']}": v['text_ar'] for v in json.loads(args.quran.read_text())}
    pairs = [{'ayah1': f"{c['ayah1_surah']}:{c['ayah1_ayah']}",
              'ayah2': f"{c['ayah2_surah']}:{c['ayah2_ayah']}"} for c in candidates]
    process = subprocess.run([str(args.analyzer.resolve()), '-quran', str(args.quran.resolve())],
                             input=json.dumps(pairs), capture_output=True, text=True, check=True)
    analyses = json.loads(process.stdout)
    if len(analyses) != len(candidates):
        raise ValueError('analyzer output count differs')
    changes, preserved, conflicts, highlight_preserved = [], [], [], []
    transitions = Counter()
    for c, pair, a in zip(candidates, pairs, analyses):
        if (a['ayah1'], a['ayah2']) != (pair['ayah1'], pair['ayah2']):
            raise ValueError('analyzer output order differs')
        r = relations.get(c['relation_id'])
        # Preserve all human decisions, even when a human has reopened the pair.
        if (c['status'] != 'accepted' or not r or r['source'] != 'auto'
                or r['reviewed'] or c['manually_reviewed_at'] or c['manually_reviewed_by']):
            preserved.append(c['id'])
            if r and r['category'] != a['suggested_category']:
                conflicts.append({**pair, 'active': r['category'], 'suggested': a['suggested_category']})
            continue
        if any(c[k] != r[k] for k in ('ayah1_surah', 'ayah1_ayah', 'ayah2_surah', 'ayah2_ayah')):
            raise ValueError('candidate relation reference mismatch')
        old = json.loads(r['highlights'] or '{}')
        old = {k: old.get(k) or [] for k in ('ayah1', 'ayah2')}
        expected = legacy_highlights(quran[pair['ayah1']], quran[pair['ayah2']])
        highlights = a['highlights']
        if old != expected:
            highlights = old
            highlight_preserved.append(c['id'])
        new_highlights = json.dumps(highlights, separators=(',', ':'))
        after_relation = {'category': a['suggested_category'], 'highlights': new_highlights}
        suffix = f"Rules {a['rule_version']}; label/highlights refined by Codex; manual review pending."
        after_candidate = {'category': a['suggested_category'], 'suggested_category': a['suggested_category'],
                           'category_confidence': a['category_suggestion_confidence'],
                           'category_basis': a['rule_version'] + ': ' + a['category_suggestion_basis'],
                           'phrase_len': a['phrase_len'],
                           'internal_note': c['internal_note'] if suffix in c['internal_note'] else (c['internal_note'] + ' ' + suffix).strip()}
        transitions[(r['category'], a['suggested_category'])] += 1
        changes.append({'candidate_id': c['id'], 'relation_id': r['id'], **pair,
                        'before_relation': r, 'before_candidate': c,
                        'after_relation': after_relation, 'after_candidate': after_candidate,
                        'analysis': a})
    result = {'schema': 'hifzlink-wording-refinement/v1',
              'captured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'baseline': baseline, 'changes': changes, 'preserved': preserved,
              'manual_conflicts': conflicts, 'custom_highlights_preserved': highlight_preserved,
              'transitions': [{'from': old, 'to': new, 'count': count}
                              for (old, new), count in sorted(transitions.items())]}
    write_private(args.output, result)
    print(json.dumps({'eligible': len(changes), 'manual_or_other_preserved': len(preserved),
                      'manual_category_suggestions': len(conflicts),
                      'custom_highlights_preserved': len(highlight_preserved),
                      'transitions': result['transitions']}, indent=2))


def apply(args):
    data = json.loads(args.plan.read_text())
    if data['schema'] != 'hifzlink-wording-refinement/v1':
        raise ValueError('unknown plan format')
    # A plan is also a record of the exact before values for targeted reversal.
    # Always retain a separate SQLite backup before starting the transaction.
    backup = args.database.with_name(args.database.name + '.before-refinement')
    if backup.exists():
        raise ValueError('backup already exists; use a fresh local copy')
    import os
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    with connect(args.database) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    conn = connect(args.database, True)
    try:
        conn.execute('BEGIN IMMEDIATE')
        if fingerprint(conn) != data['baseline']:
            raise ValueError('database changed since planning; take a fresh snapshot and plan again')
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for change in data['changes']:
            r = change['before_relation']
            c = change['before_candidate']
            if r['source'] != 'auto' or r['reviewed'] or c['manually_reviewed_at'] or c['manually_reviewed_by']:
                raise ValueError('plan attempts to replace a human decision')
            new = change['after_relation']
            cur = conn.execute("UPDATE relations SET category=?,highlights=?,updated_at=? WHERE id=? AND source='auto' AND reviewed=0",
                               (new['category'], new['highlights'], now, r['id']))
            if cur.rowcount != 1:
                raise ValueError('eligible relation changed')
            new = change['after_candidate']
            conn.execute('UPDATE curation_candidates SET category=?,suggested_category=?,category_confidence=?,category_basis=?,phrase_len=?,internal_note=? WHERE id=?',
                         tuple(new[k] for k in ('category','suggested_category','category_confidence','category_basis','phrase_len','internal_note')) + (c['id'],))
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Applied {len(data['changes'])} automatic refinements to local database; backup retained.")


def export(args):
    candidates = json.loads(args.input.read_text())
    pairs = [{k: c[k] for k in ('ayah1', 'ayah2')} for c in candidates]
    if len({(p['ayah1'], p['ayah2']) for p in pairs}) != len(pairs):
        raise ValueError('duplicate candidate pairs')
    result = subprocess.run([str(args.analyzer.resolve()), '-quran', str(args.quran.resolve())],
                            input=json.dumps(pairs), capture_output=True, text=True, check=True)
    analyses = json.loads(result.stdout)
    if len(analyses) != len(candidates):
        raise ValueError('analyzer output count differs')
    # Export only the public proposal fields, never private review state.
    fields = ('ayah1', 'ayah2', 'review_priority', 'type', 'jaccard')
    public = []
    for c, a in zip(candidates, analyses):
        if (c['ayah1'], c['ayah2']) != (a['ayah1'], a['ayah2']):
            raise ValueError('analyzer output order differs')
        item = {k: c[k] for k in fields}
        for k in ('suggested_category', 'category_suggestion_confidence', 'category_suggestion_basis', 'phrase_len', 'rule_version', 'coverage1', 'coverage2'):
            item[k] = a[k]
        item['category_suggestion_basis'] = a['rule_version'] + ': ' + a['category_suggestion_basis']
        public.append(item)
    args.output.write_text(json.dumps(public, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f"Exported {len(public)} public suggestions; no review decisions exported.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--quran', type=Path, required=True)
    p.add_argument('--analyzer', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('apply')
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--plan', type=Path, required=True)
    p = sub.add_parser('export')
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--quran', type=Path, required=True)
    p.add_argument('--analyzer', type=Path, required=True)
    args = parser.parse_args()
    {'plan': plan, 'apply': apply, 'export': export}[args.mode](args)


if __name__ == '__main__':
    main()
