#!/usr/bin/env python3
import collections
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import RunComparison as Comparison

SENTINEL = (
    'count=4000 frames=480 fixed_delta=0.016666668 state_step=4 '
    'initial_px=35257.16 initial_py=876.71454 initial_vx=2641.7227 initial_vy=-3634.7185 '
    'initial_p2=460425120.0 initial_v2=26166672.0 state_px=33454.7 state_py=7233.885 '
    'state_vx=2280.807 state_vy=-3732.7944 state_p2=460473920.0 state_v2=25559316.0 '
    'present=immediate fps=90.0 window=960.0x640.0 pixels=1920.0x1280.0 scale=2.0 density=2.0\n'
)


def result(index, code=None, tail=SENTINEL):
    return subprocess.CompletedProcess([], 0 if code is None else code,
                                       Comparison.PREFIXES[index] + ' ' + tail, '')


class ComparisonTests(unittest.TestCase):
    def test_order_balances_positions_and_directed_transitions(self):
        positions = collections.Counter((position, item) for row in Comparison.ORDERS for position, item in enumerate(row))
        transitions = collections.Counter(pair for row in Comparison.ORDERS for pair in zip(row, row[1:]))
        self.assertEqual(len(positions), 9)
        self.assertEqual(set(positions.values()), {2})
        self.assertEqual(len(transitions), 6)
        self.assertEqual(set(transitions.values()), {2})

    def test_expected_llvm_guard_does_not_admit_other_failures(self):
        Comparison.observe(1, result(1))
        for index, code in [(0, 2), (1, 2), (1, 1), (1, -11), (2, 2)]:
            with self.assertRaises(ValueError):
                Comparison.observe(index, result(index, code))

    def test_invalid_state_and_fps_are_rejected(self):
        for tail in [SENTINEL.replace('fps=90.0', 'fps=nan'), SENTINEL.replace('frames=480', 'frames=479'), SENTINEL.rstrip() + ' count=4000\n']:
            with self.assertRaises((ValueError, KeyError)):
                Comparison.observe(0, result(0, tail=tail))
        reference = Comparison.observe(0, result(0))[1]
        changed = Comparison.observe(0, result(0, tail=SENTINEL.replace('state_px=33454.7', 'state_px=100')))[1]
        with self.assertRaises(ValueError):
            Comparison.match(reference, changed)

    def test_changed_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            binary = root / 'binary'
            binary.write_text('sealed')
            config = {'version': 'boids-threeway-diagnostic-v1', 'files': {'binary': Comparison.digest(binary)},
                      'repositories': {}, 'executables': [dict(label=label, path='binary', expected_exit=0) for i, label in enumerate(Comparison.LABELS)]}
            Comparison.verify(config, root)
            binary.write_text('changed')
            with self.assertRaises(ValueError):
                Comparison.verify(config, root)

    def test_wait_prevents_launch_and_complete_run_keeps_three_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'Configuration.json'
            config_path.write_text(json.dumps({'executables': [dict(label=label, path=str(i)) for i, label in enumerate(Comparison.LABELS)]}))
            output = Path(tmp) / 'capture.log'
            argv = ['RunComparison.py', '--config', str(config_path), '--wait', '--output', str(output)]
            with patch('sys.argv', argv), patch.object(Comparison, 'verify'), patch.object(Comparison.platform, 'platform', return_value='test-host'), patch('builtins.input', side_effect=EOFError), patch.object(Comparison.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(EOFError):
                    Comparison.main()
                run.assert_not_called()
                self.assertFalse(output.exists())
            def execute(args, **kwargs):
                return result(int(Path(args[0]).name))
            with patch('sys.argv', argv), patch.object(Comparison, 'verify'), patch.object(Comparison.platform, 'platform', return_value='test-host'), patch('builtins.input', return_value=''), patch.object(Comparison.subprocess, 'run', side_effect=execute) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(Comparison.main(), 0)
                self.assertEqual(run.call_count, 54)
            report = json.loads(Path(str(output) + '.json').read_text())
            self.assertEqual(report['verdict'], 'diagnostic-complete')
            self.assertEqual(set(report['series']), set(Comparison.LABELS))
            for series in report['series'].values():
                self.assertEqual(len(series['values']), 12)
            self.assertEqual([e['returncode'] for e in report['events'] if e['label'] == 'Silex/LLVM'], [0] * 18)


    def test_nonstationary_capture_keeps_evidence_and_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'Configuration.json'
            config_path.write_text(json.dumps({'executables': [dict(label=label, path=str(i)) for i, label in enumerate(Comparison.LABELS)]}))
            output = Path(tmp) / 'capture.log'
            argv = ['RunComparison.py', '--config', str(config_path), '--output', str(output)]
            def execute(args, **kwargs):
                return result(int(Path(args[0]).name))
            summary = dict(stationary=False, median=90.0, mad=0.0, drift_fraction=0.02, failures=['drift'])
            with patch('sys.argv', argv), patch.object(Comparison, 'verify'), patch.object(Comparison.platform, 'platform', return_value='test-host'), patch.object(Comparison.subprocess, 'run', side_effect=execute), patch.object(Comparison.Protocol, 'summarize', return_value=summary), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(Comparison.main(), 2)
            report = json.loads(Path(str(output) + '.json').read_text())
            self.assertEqual(report['verdict'], 'diagnostic-nonstationary')
            self.assertEqual(len(report['events']), 54)

    def test_default_configuration_output_and_prepare_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / 'Silex-Benchmarks/Sources/Boids2D/RunComparison.py'
            config_path = root / 'Evaluations/boids-comparison/Configuration.json'
            config_path.parent.mkdir(parents=True)
            config_path.write_text(json.dumps({'executables': [dict(label=label, path=str(i)) for i, label in enumerate(Comparison.LABELS)]}))
            def execute(args, **kwargs):
                self.assertEqual(kwargs['cwd'], root)
                return result(int(Path(args[0]).name))
            with patch.object(Comparison, '__file__', str(source)), patch.object(Comparison, 'verify'), patch.object(Comparison.platform, 'platform', return_value='test-host'), patch.object(Comparison.subprocess, 'run', side_effect=execute) as run, patch('builtins.input') as wait, contextlib.redirect_stdout(io.StringIO()):
                with patch('sys.argv', ['RunComparison.py', '--prepare-only', '--wait']):
                    self.assertEqual(Comparison.main(), 0)
                    run.assert_not_called()
                    wait.assert_not_called()
                with patch('sys.argv', ['RunComparison.py']):
                    self.assertEqual(Comparison.main(), 0)
                logs = list(source.parent.glob('Baselines/*.log'))
                self.assertEqual(len(logs), 1)
                report = json.loads(Path(str(logs[0]) + '.json').read_text())
                self.assertEqual(report['policy'], Comparison.Protocol.POLICY)
                run.reset_mock()
                with patch('sys.argv', ['RunComparison.py', '--output', str(logs[0])]):
                    with self.assertRaisesRegex(ValueError, 'overwrite'):
                        Comparison.main()
                    run.assert_not_called()

    def test_imported_baseline_preserves_raw_evidence_and_selected_series(self):
        source = Path(__file__).resolve().parent
        manifest = json.loads((source / 'BaselineManifest.json').read_text())
        for relative, expected in manifest['files'].items():
            self.assertEqual(Comparison.digest(source / relative), expected)
        raw_path = next(source / p for p in manifest['files'] if p.endswith('.log.json'))
        report = json.loads(raw_path.read_text())
        self.assertEqual(len(report['events']), manifest['source_event_count'])
        self.assertEqual(manifest['retained_labels'], list(Comparison.LABELS))
        self.assertFalse(manifest['qualified'])
        for label in Comparison.LABELS:
            values = [e['fps'] for e in report['events'] if e['label'] == label and e['phase'] == 'sample']
            self.assertEqual(Comparison.Protocol.summarize(values), manifest['series'][label])
            self.assertEqual(report['series'][label], manifest['series'][label])


if __name__ == '__main__':
    unittest.main()
