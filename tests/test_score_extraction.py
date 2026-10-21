"""Synthetic-only X2 tests; never use real worker answers or ground truth."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import score_extraction as s


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.owners = s.assignments()
        self.truth = {'source': 'synthetic', 'base_commit': 'abc', 'items': [
            {'id': q, 'value': 10, 'location': 'synthetic', 'evidence_excerpt': 'dummy'}
            for q in self.owners], 'excluded': []}
        self.outputs = {}
        for w, arm in s.WORKERS.items():
            self.outputs[w] = {'arm': arm, 'worker': w, 'base_commit': 'abc',
                                 'items': [{'id': q, 'value': 10, 'location': 'dummy',
                                            'confidence': 'high'} for q, owner in self.owners.items()
                                           if w == 'S' or owner == w],
                                 'session_log': {'arm': arm, 'worker': w, 'branch': 'dummy',
                                                 'base_commit': 'abc',
                                                 'started_at_utc': '2026-10-21T00:00:00Z',
                                                 'finished_at_utc': '2026-10-21T00:01:00Z',
                                                 'tool_calls': {'total': 3, 'by_kind': {'bash': 3}},
                                                 'files_read': [], 'output_files': []}}

    def put(self, name, data):
        p = self.root / name
        p.write_text(json.dumps(data), encoding='utf-8')
        return p

    def run_score(self, logs=(), operations=None, tol=s.DEFAULT_TOL):
        return s.score([self.put(w + '.json', data) for w, data in self.outputs.items()],
                       self.put('truth.json', self.truth), logs, operations, tol)

    def test_all_correct_deterministic_cost(self):
        a = self.run_score()
        b = self.run_score()
        self.assertEqual(a, b)
        self.assertEqual(a['arms']['parallel']['counts']['正解'], 51)
        self.assertEqual(a['arms']['parallel']['session_seconds'], 180)
        self.assertEqual(a['arms']['parallel']['tool_calls'], 9)
        self.assertEqual(a['workers']['P1']['n_truth_known'], 17)
        self.assertIsNone(a['arms']['single']['wall_seconds'])
        self.assertEqual(a['arm_disagreements'], [])
        self.assertIn('parallel', s.format_human(a))

    def test_all_five_categories_denominators_and_disagreements(self):
        rows = self.outputs['S']['items']
        rows[0]['value'] = 999
        rows[1]['value'] = 10.0000001
        rows[2]['value'] = None
        del rows[3]
        result = self.run_score()
        info = result['workers']['S']
        self.assertEqual(info['counts'], dict(zip(s.LABELS, [47, 1, 1, 1, 1])))
        self.assertEqual(info['error_rate'], 1 / 51)
        self.assertEqual(info['answered_error_rate'], 1 / 49)
        self.assertEqual(info['unanswered_rate'], 2 / 51)
        self.assertEqual(len(result['discrepancies']), 4)
        self.assertEqual(len(result['arm_disagreements']), 4)

    def test_comparison_rules_and_variants(self):
        cases = [ (' A  B ', 'a b', '書式差のみ'),
                  ([2, 1], [1, 2], '書式差のみ'),
                  ([1, 1], [1, 2], '事実誤り'),
                  ('phrase.', 'phrase', '書式差のみ'),
                  ('10%', 10, '事実誤り'), ('10', 10, '事実誤り'),
                  (True, 1, '事実誤り'), (' UNKNOWN ', 10, '棄権'),
                  (None, 10, '棄権'), (1.0000005, 1, '書式差のみ'),
                  (1.01, 1, '事実誤り') ]
        for value, truth, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(s.classify({'value': value}, {'value': truth}, 1e-6), expected)
        self.assertEqual(s.classify({'value': 'colour'},
                                   {'value': 'color', 'variants': ['colour']}, 1e-6), '書式差のみ')
        self.assertEqual(s.classify({'value': '1'}, {'value': 1, 'variants': []}, 0), '事実誤り')

    def test_excluded_and_zero_denominator(self):
        self.truth['excluded'] = [{'id': q, 'category': 'a', 'reason': 'synthetic'} for q in self.owners]
        self.truth['items'] = []
        result = self.run_score()
        self.assertIsNone(result['arms']['single']['error_rate'])
        self.assertEqual(len(result['excluded']), 51)
        self.assertEqual(len(result['items']), 102)

    def test_unknown_and_extra_id_repair_candidates(self):
        self.outputs['S']['items'][0]['value'] = 'unknown'
        self.outputs['P1']['items'].append({'id': 'Q99', 'value': 10})
        result = self.run_score()
        self.assertEqual(len(result['repair_candidates']), 2)
        self.assertEqual(result['arms']['parallel']['n_truth_known'], 51)

    def test_external_logs_and_unknown_cost(self):
        logs = []
        for worker, data in self.outputs.items():
            log = data.pop('session_log')
            log.update(started_at_utc=None, tool_calls=None, notes='not recorded')
            logs.append(self.put(worker + '-log.json', log))
        result = self.run_score(logs)
        self.assertIsNone(result['arms']['parallel']['session_seconds'])
        self.assertIsNone(result['arms']['parallel']['tool_calls'])

    def test_operations_wall_clock_and_overhead(self):
        op = {}
        for arm in ('single', 'parallel'):
            op[arm] = {'workers': {w: {'prompt_at_utc': '2026-10-21T00:00:00Z',
                                      'merged_at_utc': '2026-10-21T00:05:00Z'}
                                   for w, a in s.WORKERS.items() if a == arm},
                       'merge_conflicts': [], 'repairs': ['one file'],
                       'human_interventions': ['one reminder']}
        op['parallel']['workers']['P3']['merged_at_utc'] = '2026-10-21T00:10:00Z'
        result = self.run_score(operations=self.put('operations.json', op))
        self.assertEqual(result['arms']['parallel']['wall_seconds'], 600)
        self.assertEqual(result['arms']['single']['overhead']['repairs']['count'], 1)

    def test_common_errors_no_correlation_statistics(self):
        q = 'Q01'
        self.outputs['S']['items'][0]['value'] = 999
        next(r for r in self.outputs[self.owners[q]]['items'] if r['id'] == q)['value'] = 999
        result = self.run_score()
        self.assertEqual(result['common_error_ids'], [q])
        self.assertNotIn('lift', result)
        self.assertNotIn('rho', result)

    def test_invalid_inputs(self):
        mutations = [lambda: self.outputs['S']['items'].append(self.outputs['S']['items'][0]),
                     lambda: self.truth['items'].pop(),
                     lambda: self.outputs.pop('P3'),
                     lambda: self.outputs['S']['session_log'].update(tool_calls=True),
                     lambda: self.outputs['S']['session_log'].update(started_at_utc='2026-10-21T01:00:00Z'),
                     lambda: self.outputs['S']['session_log'].update(started_at_utc='2026-10-21T00:00:00'),
                     lambda: self.outputs['S']['session_log']['tool_calls'].update(total=4),
                     lambda: self.outputs['S']['items'][0].pop('value')]
        for mutate in mutations:
            original_outputs = json.dumps(self.outputs)
            original_truth = json.dumps(self.truth)
            mutate()
            with self.assertRaises(ValueError):
                self.run_score()
            self.outputs = json.loads(original_outputs)
            self.truth = json.loads(original_truth)
        for tol in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.run_score(tol=tol)

    def test_cli_exit_contract_and_json(self):
        self.run_score()
        args = ['--outputs', *[str(self.root / (w + '.json')) for w in self.outputs],
                '--truth', str(self.root / 'truth.json')]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(s.main(args + ['--json']), 0)
        self.assertIn('arms', json.loads(out.getvalue()))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(s.main(['--outputs', 'missing', '--truth', 'missing']), 0)
            with self.assertRaises(SystemExit) as cm:
                s.main([])
        self.assertEqual(cm.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
