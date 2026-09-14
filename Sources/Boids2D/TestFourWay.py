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

import FourWay

SENTINEL = (
    'count=4000 frames=480 fixed_delta=0.016666668 state_step=4 '
    'initial_px=35257.16 initial_py=876.71454 initial_vx=2641.7227 initial_vy=-3634.7185 '
    'initial_p2=460425120.0 initial_v2=26166672.0 state_px=33454.7 state_py=7233.885 '
    'state_vx=2280.807 state_vy=-3732.7944 state_p2=460473920.0 state_v2=25559316.0 '
    'present=immediate fps=90.0 window=960.0x640.0 pixels=1920.0x1280.0 scale=2.0 density=2.0\n'
)


def result(index, code=None, tail=SENTINEL):
    return subprocess.CompletedProcess([], 0 if code is None else code,
                                       FourWay.PREFIXES[index] + ' ' + tail, '')


class FourWayTests(unittest.TestCase):
    def test_order_balances_positions_and_directed_transitions(self):
        positions = collections.Counter((position, item) for row in FourWay.ORDERS for position, item in enumerate(row))
        transitions = collections.Counter(pair for row in FourWay.ORDERS for pair in zip(row, row[1:]))
        self.assertEqual(len(positions), 16)
        self.assertEqual(set(positions.values()), {1})
        self.assertEqual(len(transitions), 12)
        self.assertEqual(set(transitions.values()), {1})

    def test_expected_llvm_guard_does_not_admit_other_failures(self):
        FourWay.observe(1, result(1))
        for index, code in [(0, 2), (1, 2), (1, 1), (1, -11), (2, 2), (3, 2)]:
            with self.assertRaises(ValueError):
                FourWay.observe(index, result(index, code))

    def test_invalid_state_and_fps_are_rejected(self):
        for tail in [SENTINEL.replace('fps=90.0', 'fps=nan'), SENTINEL.replace('frames=480', 'frames=479'), SENTINEL.rstrip() + ' count=4000\n']:
            with self.assertRaises((ValueError, KeyError)):
                FourWay.observe(0, result(0, tail=tail))
        reference = FourWay.observe(0, result(0))[1]
        changed = FourWay.observe(0, result(0, tail=SENTINEL.replace('state_px=33454.7', 'state_px=100')))[1]
        with self.assertRaises(ValueError):
            FourWay.match(reference, changed)

    def test_changed_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'binary'
            binary.write_text('sealed')
            config = {'version': 'boids-fourway-diagnostic-v2', 'files': {'binary': FourWay.digest(binary)},
                      'repositories': {}, 'executables': [dict(label=label, path='binary', expected_exit=0) for i, label in enumerate(FourWay.LABELS)]}
            FourWay.verify(config, root)
            binary.write_text('changed')
            with self.assertRaises(ValueError):
                FourWay.verify(config, root)

    def test_wait_prevents_launch_and_complete_run_keeps_four_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'Configuration.json'
            config_path.write_text(json.dumps({'executables': [dict(label=label, path=str(i)) for i, label in enumerate(FourWay.LABELS)]}))
            output = Path(tmp) / 'capture.log'
            argv = ['FourWay.py', '--config', str(config_path), '--wait', '--output', str(output)]
            with patch('sys.argv', argv), patch.object(FourWay, 'verify'), patch.object(FourWay.platform, 'platform', return_value='test-host'), patch('builtins.input', side_effect=EOFError), patch.object(FourWay.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(EOFError):
                    FourWay.main()
                run.assert_not_called()
                self.assertFalse(output.exists())
            def execute(args, **kwargs):
                return result(int(Path(args[0]).name))
            with patch('sys.argv', argv), patch.object(FourWay, 'verify'), patch.object(FourWay.platform, 'platform', return_value='test-host'), patch('builtins.input', return_value=''), patch.object(FourWay.subprocess, 'run', side_effect=execute) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(FourWay.main(), 0)
                self.assertEqual(run.call_count, 64)
            report = json.loads(Path(str(output) + '.json').read_text())
            self.assertEqual(report['verdict'], 'diagnostic-complete')
            self.assertEqual(set(report['series']), set(FourWay.LABELS))
            for series in report['series'].values():
                self.assertEqual(len(series['values']), 12)
            self.assertEqual([e['returncode'] for e in report['events'] if e['label'] == 'Silex/LLVM'], [0] * 16)


    def test_nonstationary_capture_keeps_evidence_and_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'Configuration.json'
            config_path.write_text(json.dumps({'executables': [dict(label=label, path=str(i)) for i, label in enumerate(FourWay.LABELS)]}))
            output = Path(tmp) / 'capture.log'
            argv = ['FourWay.py', '--config', str(config_path), '--output', str(output)]
            def execute(args, **kwargs):
                return result(int(Path(args[0]).name))
            summary = dict(stationary=False, median=90.0, mad=0.0, drift_fraction=0.02, failures=['drift'])
            with patch('sys.argv', argv), patch.object(FourWay, 'verify'), patch.object(FourWay.subprocess, 'run', side_effect=execute), patch.object(FourWay.Protocol, 'summarize', return_value=summary), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(FourWay.main(), 2)
            report = json.loads(Path(str(output) + '.json').read_text())
            self.assertEqual(report['verdict'], 'diagnostic-nonstationary')
            self.assertEqual(len(report['events']), 64)


if __name__ == '__main__':
    unittest.main()
