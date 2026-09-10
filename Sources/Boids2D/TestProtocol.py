#!/usr/bin/env python3
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import Provenance

import Protocol as p


class ProtocolTests(unittest.TestCase):
    def log(self):
        lines = [f'# protocol_sha256={hashlib.sha256(p.POLICY_PATH.read_bytes()).hexdigest()}',
                 '# artifact_seal_sha256=' + hashlib.sha256(b'{}').hexdigest(),
                 '# warmups=6', '# runs=12', '# source_repositories_dirty=false']
        for event in p.schedule(6, 12):
            lines.append('# event=' + ','.join(map(str, event)))
            prefix = p.PREFIXES[p.LABELS.index(event[3])]
            state = ' '.join(f'{stage}_{component}=1' for stage in ('initial', 'state')
                             for component in ('px', 'py', 'vx', 'vy', 'p2', 'v2'))
            lines.append(f'{prefix} count=4000 frames=480 fps=90.0 fixed_delta=0.016666667 state_step=4 {state} present=immediate window=960x640 pixels=1920x1280 scale=2 density=2')
        return '\n'.join(lines) + '\n'

    def analyze(self, log):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'log'
            path.write_text(log)
            path.with_name(path.name + '.seal.json').write_text('{}')
            return p.analyze(path)

    def test_balanced_positions_and_precedence(self):
        for start, stop in ((0, 18), (18, 54)):
            events = list(p.schedule(6, 12))[start:stop]
            for label in p.LABELS:
                self.assertEqual([sum(e[2:] == (pos, label) for e in events)
                                  for pos in (1, 2, 3)], [(stop - start) // 9] * 3)
        self.assertEqual(len(set(p.ORDERS)), 6)

    def test_stable_and_warming_sequences(self):
        self.assertTrue(p.summarize([90, 90.1, 89.9] * 4)['stationary'])
        report = self.analyze(self.log().replace('fps=90.0', 'fps=60.0', 18))
        self.assertEqual(report['verdict'], 'stationary')
        self.assertEqual(report['discarded_values']['silex'], [60] * 6)
        self.assertEqual(report['accepted_window'], [7, 18])

    def test_warming_inside_retained_window_is_rejected(self):
        self.assertFalse(p.summarize([60, 70, 80] + [90] * 9)['stationary'])

    def test_drift(self):
        result = p.summarize([90 - 0.25 * i for i in range(12)])
        self.assertFalse(result['stationary'])
        self.assertTrue(any('drift' in message for message in result['failures']))

    def test_outlier_is_not_trimmed(self):
        result = p.summarize([90] * 11 + [120])
        self.assertFalse(result['stationary'])
        self.assertEqual(result['maximum'], 120)

    def test_invalid_numbers(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                p.summarize([90] * 11 + [value])

    def test_falsified_order(self):
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            self.analyze(self.log().replace('# event=warmup,1,1,silex', '# event=warmup,1,1,cpp-direct'))

    def test_deleted_reordered_duplicated_rounds(self):
        lines = self.log().splitlines()
        for altered in (lines[:5] + lines[11:], lines[:5] + lines[11:17] + lines[5:11] + lines[17:],
                        lines[:11] + lines[5:11] + lines[11:]):
            with self.assertRaises(ValueError):
                self.analyze('\n'.join(altered))

    def test_wrong_policy_workload_and_count(self):
        for old, new in (('frames=480', 'frames=479'), ('# runs=12', '# runs=11'),
                         ('# protocol_sha256=', '# false_protocol_sha256=')):
            with self.assertRaises(ValueError):
                self.analyze(self.log().replace(old, new))

    def test_semantic_and_display_mutations(self):
        for old, new in (("fixed_delta=0.016666667", "fixed_delta=0.02"),
                         ("state_step=4", "state_step=5"), ("state_px=1", "state_px=99"),
                         ("state_px=1", "state_px=nan"), ("pixels=1920x1280", "pixels=960x640"),
                         ("fps=90.0", "fps=nan")):
            with self.assertRaises(ValueError):
                self.analyze(self.log().replace(old, new, 1))

    def test_dirty_capture(self):
        self.assertEqual(self.analyze(self.log().replace('dirty=false', 'dirty=true'))['verdict'], 'inconclusive')

    def test_repeat_identity_and_medians(self):
        first = self.analyze(self.log())
        first['metadata'].update({key: 'same' for key in ('artifact_seal_sha256', 'cpu', 'os', 'architecture')})
        second = copy.deepcopy(first)
        self.assertEqual(p.compare(first, second)['verdict'], 'repeatable')
        second['metadata']['artifact_seal_sha256'] = 'different'
        self.assertEqual(p.compare(first, second)['verdict'], 'inconclusive')
        second = copy.deepcopy(first)
        second['series']['silex']['median'] *= 1.02
        self.assertEqual(p.compare(first, second)['verdict'], 'inconclusive')

    def test_actual_shell_dispatch_and_failure_retention(self):
        # Execute the real shell loop with observable fake processes. Provenance
        # is stubbed only here: no compiler, GPU or real benchmark is needed.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'Benchmarks/Sources/Boids2D'
            source.mkdir(parents=True)
            original = Path(__file__).parent
            for name in ('RunComparison.sh', 'Protocol.py', 'Protocol.json'):
                (source / name).write_bytes((original / name).read_bytes())
            (source / 'Provenance.py').write_text('')
            compiler = root / 'compiler'
            compiler.write_text('#!/bin/sh\nexit 0\n')
            compiler.chmod(0o755)
            build = root / 'build'
            (build / 'cpp').mkdir(parents=True)
            (build / 'ArtifactSeal.json').write_text('{}')
            for name, prefix in zip(('gfx-boids-silex', 'cpp/BoidsCppArchitectural', 'cpp/BoidsCppDirect'), p.PREFIXES):
                binary = build / name
                state = ' '.join(f'{stage}_{component}=1' for stage in ('initial', 'state')
                                 for component in ('px', 'py', 'vx', 'vy', 'p2', 'v2'))
                binary.write_text(f'#!/bin/sh\necho "{prefix} count=4000 frames=480 fps=90 fixed_delta=0.016666667 state_step=4 {state} present=immediate window=960x640 pixels=1920x1280 scale=2 density=2"\n')
                binary.chmod(0o755)
            output = root / 'capture.log'
            command = ['bash', str(source / 'RunComparison.sh'), '--skip-build', '--silex-compiler', str(compiler),
                       '--build-dir', str(build), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            report = p.analyze(output)
            self.assertEqual(len(report['series']['silex']['values']), 12)
            self.assertEqual(len(report['discarded_values']['silex']), 6)
            (build / 'gfx-boids-silex').write_text('#!/bin/sh\necho failure-detail >&2\nexit 7\n')
            output.unlink()
            output.with_suffix(".log.json").unlink()
            output.with_suffix(".log.seal.json").unlink()
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('failure-detail', output.with_suffix('.log.partial').read_text())


class ProvenanceTests(unittest.TestCase):
    def test_stale_compiler_closure_and_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            inputs = {"compiler": "hash-a", "closure": "commit-a"}
            artifacts = {"binary": "hash-b", "shader": "hash-c"}
            argv = ['Provenance.py', 'prepare', folder, folder, folder]
            with mock.patch('sys.argv', argv), mock.patch.object(Provenance, 'inputs', return_value=inputs), mock.patch.object(Provenance, 'artifacts', return_value=artifacts):
                Provenance.main()
                argv[1] = 'seal'
                Provenance.main()
                argv[1] = 'verify'
                Provenance.main()
                for values, key in ((inputs, 'compiler'), (inputs, 'closure'), (artifacts, 'binary'), (artifacts, 'shader')):
                    old = values[key]
                    values[key] = 'changed'
                    with self.assertRaisesRegex(ValueError, 'rebuild required'):
                        Provenance.main()
                    values[key] = old

    def test_source_movement_during_build(self):
        with tempfile.TemporaryDirectory() as folder:
            inputs = {"closure": "before"}
            argv = ['Provenance.py', 'prepare', folder, folder, folder]
            with mock.patch('sys.argv', argv), mock.patch.object(Provenance, 'inputs', return_value=inputs):
                Provenance.main()
                inputs['closure'] = 'after'
                argv[1] = 'seal'
                with self.assertRaisesRegex(ValueError, 'changed during build'):
                    Provenance.main()

    def test_missing_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'missing executable'):
                Provenance.artifacts(Path(folder))


if __name__ == '__main__':
    unittest.main()
