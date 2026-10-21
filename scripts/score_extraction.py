#!/usr/bin/env python3
"""Deterministic X2 instrument for single-vs-multi-experiment-2026-10-21.

Reuse measure_agreement's value comparator and abstention rule, not its
measurement pipeline (different universe, assignments and denominators).
All classifications are candidates for X4 review, not semantic adjudication.
Completed runs, including input failures, exit 0; only CLI misuse exits 2.
Standard library only. No CI integration or automatic operational decision.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

if __package__:
    from .measure_agreement import DEFAULT_TOL, is_abstention, values_equal
else:
    from measure_agreement import DEFAULT_TOL, is_abstention, values_equal

DESIGN = Path(__file__).resolve().parents[1] / 'docs/single-vs-multi-experiment-2026-10-21.md'
LABELS = ('正解', '事実誤り', '書式差のみ', '棄権', '欠落')
WORKERS = {'S': 'single', 'P1': 'parallel', 'P2': 'parallel', 'P3': 'parallel'}


def read(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'),
                      parse_constant=lambda x: fail(f'non-finite JSON: {x}'))
    require(isinstance(data, dict), f'{path}: expected JSON object')
    # Also rejects overflow such as 1e999, which parse_constant does not see.
    json.dumps(data, allow_nan=False)
    return data


def fail(message):
    raise ValueError(message)


def require(condition, message):
    if not condition:
        fail(message)


def assignments():
    """Read only the frozen question/owner table; never infer from output rows."""
    owners = {}
    for line in DESIGN.read_text(encoding='utf-8').splitlines():
        if line.startswith('| Q'):
            cells = [s.strip() for s in line.split('|')]
            owners[cells[1]] = cells[-2]
    require(len(owners) == 51 and all(list(owners.values()).count(w) == 17
                                   for w in ('P1', 'P2', 'P3')), 'invalid design assignment')
    return owners


def index(rows, label):
    require(isinstance(rows, list), f'{label}: expected list')
    result = {}
    for row in rows:
        require(isinstance(row, dict) and isinstance(row.get('id'), str), f'{label}: invalid row')
        require(row['id'] not in result, f'{label}: duplicate {row["id"]}')
        result[row['id']] = row
    return result


def instant(value):
    require(isinstance(value, str), 'timestamp must be UTC ISO 8601')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.utcoffset() is not None and dt.utcoffset().total_seconds() == 0,
            'timestamp must be UTC')
    return dt


def elapsed(start, end):
    if start is None or end is None:
        return None
    seconds = (instant(end) - instant(start)).total_seconds()
    require(seconds >= 0, 'negative duration')
    return seconds


def count(value):
    require(type(value) is int and value >= 0, 'count must be nonnegative integer')
    return value


def total(values):
    return None if any(v is None for v in values) else sum(values)


def same_literal(a, b):
    return type(a) is type(b) and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def formatting(a, b, tol):
    """Conservative same-type punctuation normalization; never coerce numeric strings."""
    if isinstance(a, str) and isinstance(b, str):
        return values_equal(a.rstrip().rstrip('.,;:!?。！？，；：'),
                            b.rstrip().rstrip('.,;:!?。！？，；：'), tol)
    return False


def same_type(a, b):
    return (type(a) is type(b) or
            (type(a) in (int, float) and type(b) in (int, float)))


def classify(row, truth, tol):
    if row is None:
        return '欠落'
    value = row['value']
    if is_abstention(value):
        return '棄権'
    if values_equal(value, truth['value'], tol):
        return '正解' if same_literal(value, truth['value']) else '書式差のみ'
    # Variants retain JSON-type strictness; no numeric/string coercion.
    if formatting(value, truth['value'], tol) or any(
            same_type(value, truth['value']) and values_equal(value, variant, tol)
            for variant in truth.get('variants', [])):
        return '書式差のみ'
    return '事実誤り'


def summary(rows):
    counts = {label: sum(r['candidate'] == label for r in rows) for label in LABELS}
    n = sum(counts.values())
    answered = n - counts['棄権'] - counts['欠落']
    return {'counts': counts, 'n_truth_known': n,
            'error_rate': counts['事実誤り'] / n if n else None,
            'unanswered_rate': (counts['棄権'] + counts['欠落']) / n if n else None,
            'answered_error_rate': counts['事実誤り'] / answered if answered else None}


def score(output_paths, truth_path, log_paths=(), operations_path=None, tol=DEFAULT_TOL):
    require(math.isfinite(tol) and tol >= 0, 'tol must be finite and nonnegative')
    owners = assignments()
    truth = read(truth_path)
    known = index(truth['items'], 'truth items')
    excluded = index(truth['excluded'], 'excluded')
    require(not set(known) & set(excluded) and set(known) | set(excluded) == set(owners),
            'truth items + excluded must partition all 51 design IDs')
    for row in known.values():
        require('value' in row and not is_abstention(row['value']) and
                'location' in row and 'evidence_excerpt' in row, 'invalid known truth')
        require(isinstance(row.get('variants', []), list), 'variants must be list')
    for row in excluded.values():
        require('category' in row and 'reason' in row, 'excluded needs category/reason')
    require('source' in truth and 'base_commit' in truth, 'truth needs source/base_commit')
    outputs, logs = {}, {}
    for path in output_paths:
        data = read(path)
        worker = data['worker']
        require(worker in WORKERS and data['arm'] == WORKERS[worker], 'invalid arm/worker')
        require(worker not in outputs, 'duplicate output worker')
        outputs[worker] = data
        if isinstance(data.get('session_log'), dict):
            logs[worker] = data['session_log']
    for path in log_paths:
        log = read(path)
        require(log['worker'] not in logs, 'duplicate session log (embedded and external)')
        logs[log['worker']] = log
    require(set(outputs) == set(WORKERS) and set(logs) == set(WORKERS),
            'need outputs and logs for S/P1/P2/P3')
    rows, workers, warnings, repairs = [], {}, [], []
    for worker, arm in WORKERS.items():
        data, log = outputs[worker], logs[worker]
        required = ('arm', 'worker', 'branch', 'base_commit', 'started_at_utc',
                    'finished_at_utc', 'tool_calls', 'files_read', 'output_files')
        require(all(k in log for k in required), f'{worker}: missing session fields')
        require(log['worker'] == worker and log['arm'] == arm, 'log identity mismatch')
        require(all(v is not None or log.get('notes') for v in (log[k] for k in required)),
                'null session fields need notes')
        for key in ('files_read', 'output_files'):
            value = log[key]
            require(value is None or (isinstance(value, list) and all(isinstance(x, str) for x in value)
                                     and len(value) == len(set(value))), f'invalid {key}')
        require(data['base_commit'] == log['base_commit'], 'output/log base mismatch')
        if data['base_commit'] != truth['base_commit']:
            warnings.append(f'{worker}: base_commit differs from truth (check abbreviated hashes manually)')
        entries = index(data['items'], worker)
        assigned = {q for q in owners if worker == 'S' or owners[q] == worker}
        for q in sorted(set(entries) - assigned):
            repairs.append({'worker': worker, 'id': q, 'reason': '担当外/未知ID（採点外）'})
        for q in sorted(assigned):
            entry = entries.get(q)
            if entry is not None:
                require('value' in entry and 'location' in entry and
                        entry.get('confidence') in ('high', 'medium', 'low'), f'{worker}/{q}: invalid item')
                if isinstance(entry['value'], str) and is_abstention(entry['value']):
                    repairs.append({'worker': worker, 'id': q, 'reason': 'unknown → null'})
            rows.append({'arm': arm, 'worker': worker, 'id': q, 'present': entry is not None,
                         'value': entry['value'] if entry else None,
                         'truth': known[q]['value'] if q in known else None,
                         'review_note': '型不一致も機械上は不一致。%残存・意味同値等はX4が書式差候補を確認。',
                         'candidate': classify(entry, known[q], tol) if q in known else '項目側の問題'})
        calls = log['tool_calls']
        if isinstance(calls, dict):
            n_calls = count(calls['total'])
            require(isinstance(calls['by_kind'], dict) and
                    sum(count(v) for v in calls['by_kind'].values()) == n_calls,
                    'tool_calls total/by_kind mismatch')
        else:
            n_calls = None if calls is None else count(calls)
        workers[worker] = summary([r for r in rows if r['worker'] == worker])
        workers[worker].update(session_seconds=elapsed(log['started_at_utc'], log['finished_at_utc']),
                               tool_calls=n_calls, session_log=log)
    operations = read(operations_path) if operations_path else {}
    arms = {}
    for arm in ('single', 'parallel'):
        members = [workers[w] for w in WORKERS if WORKERS[w] == arm]
        info = summary([r for r in rows if r['arm'] == arm])
        info['session_seconds'] = total([m['session_seconds'] for m in members])
        info['tool_calls'] = total([m['tool_calls'] for m in members])
        info['seconds_per_truth_item'] = (info['session_seconds'] / len(known)
                                          if known and info['session_seconds'] is not None else None)
        op = operations.get(arm)
        info['wall_seconds'] = None
        info['overhead'] = None
        if op is not None:
            require(isinstance(op, dict), 'operations arm must be object')
            expected = {w for w in WORKERS if WORKERS[w] == arm}
            require(set(op['workers']) == expected, 'operations worker set mismatch')
            starts = [instant(x['prompt_at_utc']) for x in op['workers'].values()]
            ends = [instant(x['merged_at_utc']) for x in op['workers'].values()]
            for x in op['workers'].values():
                elapsed(x['prompt_at_utc'], x['merged_at_utc'])
            info['wall_seconds'] = (max(ends) - min(starts)).total_seconds()
            info['overhead'] = {k: {'count': len(op[k]), 'events': op[k]} for k in
                                ('merge_conflicts', 'repairs', 'human_interventions')
                                if isinstance(op[k], list)}
            require(len(info['overhead']) == 3, 'overhead events must be lists')
            info['operations'] = op
        arms[arm] = info
    disagreements = []
    for q in sorted(owners):
        pair = [r for r in rows if r['id'] == q]
        left, right = pair
        if (not left['present'] or not right['present'] or
                not same_literal(left['value'], right['value'])):
            disagreements.append({'id': q, 'sides': pair, 'excluded': excluded.get(q)})
    common = sorted(q for q in known if all(r['candidate'] == '事実誤り'
                                            for r in rows if r['id'] == q))
    return {'definitions': {'error_rate': '事実誤り / 真値確定項目（棄権・欠落を含む）',
                            'answered_error_rate': '事実誤り / (正解+事実誤り+書式差のみ)',
                            'unanswered_rate': '(棄権+欠落) / 真値確定項目',
                            'status': '全分類はX4目視確認用候補。M1/M4未提供はnull。ツール数は自己申告。'},
            'tol': tol, 'arms': arms, 'workers': workers, 'items': rows,
            'discrepancies': [r for r in rows if r['candidate'] != '正解'],
            'arm_disagreements': disagreements, 'excluded': [excluded[q] for q in sorted(excluded)],
            'common_error_ids': common, 'common_error_count': len(common),
            'repair_candidates': repairs, 'warnings': warnings +
            ['M1/M4は人間の補助記録が必要。自動判定・相関推定は行わない。']}


def format_human(report):
    lines = ['抽出採点（分類候補・計測器）', *report['definitions'].values()]
    for group in ('arms', 'workers'):
        for name, info in report[group].items():
            lines.append(f'{name}: ' + json.dumps({k: v for k, v in info.items()
                                                  if k not in ("session_log", "operations")}, ensure_ascii=False))
    for key in ('discrepancies', 'arm_disagreements', 'excluded', 'repair_candidates',
                'common_error_ids', 'warnings'):
        lines.append(key + ':')
        lines.extend(json.dumps(row, ensure_ascii=False) for row in report[key])
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outputs', nargs='+', type=Path, required=True)
    parser.add_argument('--truth', type=Path, required=True)
    parser.add_argument('--logs', nargs='*', type=Path, default=[])
    parser.add_argument('--operations', type=Path)
    parser.add_argument('--tol', type=float, default=DEFAULT_TOL)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = score(args.outputs, args.truth, args.logs, args.operations, args.tol)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f'error: {exc}\nmeasurement tool: exit code stays 0 (not a gate)', file=sys.stderr)
        return 0
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) if args.json else format_human(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
