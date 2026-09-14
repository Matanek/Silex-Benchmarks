#!/usr/bin/env python3
import collections
import contextlib
import io
import json
from pathlib import Path
import subprocess
import shlex
import tempfile
import unittest
from unittest.mock import patch

import types

# Load the embedded implementation for focused checks; CLI tests execute the shell.
LAUNCHER = Path(__file__).with_name('RunComparison.sh')
Comparison = types.ModuleType('BoidsComparison')
Comparison.__file__ = str(LAUNCHER)
embedded = LAUNCHER.read_text().split("<<'BOIDS_PYTHON'\n", 1)[1].split('\nBOIDS_PYTHON\n', 1)[0]
exec(compile(embedded, str(LAUNCHER), 'exec'), Comparison.__dict__)

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
            output = Path(tmp) / 'capture.md'
            argv = ['RunComparison.sh', '--config', str(config_path), '--wait', '--output', str(output)]
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
            report = output.read_text()
            self.assertIn('Capture complète — séries stables.', report)
            self.assertEqual(report.count('| Mesure |'), 12)
            self.assertEqual(report.count('| Échauffement |'), 6)
            self.assertEqual(set(output.parent.iterdir()), {config_path, output})
            for label in Comparison.LABELS:
                self.assertIn(f'| {label} | 90.000 | 90.000 | 90.000 | 0.000 |', report)
            for field in ('window', 'pixels', 'scale', 'density', 'stdout'):
                self.assertNotIn(field, report)


    def test_nonstationary_capture_keeps_evidence_and_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / 'Configuration.json'
            config_path.write_text(json.dumps({'executables': [dict(label=label, path=str(i)) for i, label in enumerate(Comparison.LABELS)]}))
            output = Path(tmp) / 'capture.md'
            argv = ['RunComparison.sh', '--config', str(config_path), '--output', str(output)]
            def execute(args, **kwargs):
                return result(int(Path(args[0]).name))
            summary = dict(stationary=False, values=[90.0] * 12)
            with patch('sys.argv', argv), patch.object(Comparison, 'verify'), patch.object(Comparison.platform, 'platform', return_value='test-host'), patch.object(Comparison.subprocess, 'run', side_effect=execute), patch.object(Comparison, 'summarize', return_value=summary), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(Comparison.main(), 2)
            report = output.read_text()
            self.assertIn('séries instables', report)
            self.assertEqual(report.count('| Mesure |'), 12)
            self.assertEqual(report.count('| Échauffement |'), 6)

    def test_default_configuration_output_and_prepare_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / 'Silex-Benchmarks/Sources/Boids2D/RunComparison.sh'
            config_path = root / 'Evaluations/boids-comparison/Configuration.json'
            config_path.parent.mkdir(parents=True)
            config_path.write_text(json.dumps({'executables': [dict(label=label, path=str(i)) for i, label in enumerate(Comparison.LABELS)]}))
            def execute(args, **kwargs):
                self.assertEqual(kwargs['cwd'], root)
                return result(int(Path(args[0]).name))
            with patch.object(Comparison, '__file__', str(source)), patch.object(Comparison, 'verify'), patch.object(Comparison.platform, 'platform', return_value='test-host'), patch.object(Comparison.subprocess, 'run', side_effect=execute) as run, patch('builtins.input') as wait, contextlib.redirect_stdout(io.StringIO()):
                with patch('sys.argv', ['RunComparison.sh', '--prepare-only', '--wait']):
                    self.assertEqual(Comparison.main(), 0)
                    run.assert_not_called()
                    wait.assert_not_called()
                with patch('sys.argv', ['RunComparison.sh']):
                    self.assertEqual(Comparison.main(), 0)
                logs = list(source.parent.glob('Baselines/*.md'))
                self.assertEqual(len(logs), 1)
                self.assertEqual(list(logs[0].parent.iterdir()), logs)
                run.reset_mock()
                with patch('sys.argv', ['RunComparison.sh', '--output', str(logs[0])]):
                    with self.assertRaisesRegex(ValueError, 'overwrite'):
                        Comparison.main()
                    run.assert_not_called()

    def test_platform_name_identifies_os_and_architecture(self):
        for system, machine, expected in [('Darwin', 'arm64', 'macos-arm64'), ('Linux', 'aarch64', 'linux-arm64'), ('Windows', 'AMD64', 'windows-x64'), ('Darwin', 'x86_64', 'macos-x64')]:
            with self.subTest(system=system, machine=machine), patch.object(Comparison.platform, 'system', return_value=system), patch.object(Comparison.platform, 'machine', return_value=machine):
                self.assertEqual(Comparison.platform_name(), expected)

    def test_report_means_ranges_and_relative_differences(self):
        report = dict(date='test', warmups=0, runs=6, host='test-host',
                      config_sha256='test', configuration={'executables': []},
                      verdict='diagnostic-complete', events=[], series={})
        for label, values in zip(Comparison.LABELS, ([80, 100, 120], [120, 120, 120], [80, 80, 80])):
            report['series'][label] = {'values': values}
        rendered = Comparison.render_report(report)
        self.assertIn('| Silex/Natif | 100.000 | 80.000 | 120.000 | 16.330 |', rendered)
        self.assertIn('| Silex/LLVM | Silex/Natif | +20.000 | +20.00 % |', rendered)
        self.assertIn('| Silex/Natif | C++ architectural | +20.000 | +25.00 % |', rendered)
        self.assertIn('| Silex/LLVM | C++ architectural | +40.000 | +50.00 % |', rendered)

    def test_failed_capture_keeps_one_readable_file_without_comparison(self):
        for failure in (result(0, code=7), KeyboardInterrupt()):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                config_path = Path(tmp) / 'Configuration.json'
                config_path.write_text(json.dumps({'executables': [dict(label=label, path=str(i)) for i, label in enumerate(Comparison.LABELS)]}))
                output = Path(tmp) / 'capture.md'
                argv = ['RunComparison.sh', '--config', str(config_path), '--output', str(output)]
                with patch('sys.argv', argv), patch.object(Comparison, 'verify'), patch.object(Comparison.platform, 'platform', return_value='test-host'), patch.object(Comparison.subprocess, 'run', side_effect=[failure]), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises((ValueError, KeyboardInterrupt)):
                        Comparison.main()
                report = output.read_text()
                self.assertIn('aucune comparaison validée', report)
                self.assertNotIn('## Écarts entre variantes', report)
                self.assertNotIn('| FPS moyens |', report)
                self.assertEqual(set(output.parent.iterdir()), {config_path, output})

    def test_executable_shell_preserves_arguments_stdin_and_single_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'workspace with spaces'
            launcher = root / 'Silex-Benchmarks/Sources/Boids2D/RunComparison.sh'
            launcher.parent.mkdir(parents=True)
            launcher.write_bytes(LAUNCHER.read_bytes())
            launcher.chmod(0o755)
            config = dict(version='boids-threeway-diagnostic-v1', repositories={}, files={}, executables=[])
            for index, label in enumerate(Comparison.LABELS):
                binary = root / f'binary {index}'
                binary.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(Comparison.PREFIXES[index] + ' ' + SENTINEL.strip()) + '\n')
                binary.chmod(0o755)
                config['files'][binary.name] = Comparison.digest(binary)
                config['executables'].append(dict(label=label, path=binary.name, expected_exit=0))
            config_path = root / 'Evaluations/boids-comparison/Configuration.json'
            config_path.parent.mkdir(parents=True)
            config_path.write_text(json.dumps(config))
            command = [str(launcher), '--wait', '--warmups', '0', '--runs', '6']
            prepared = subprocess.run(command + ['--prepare-only'], input='', cwd=tmp, capture_output=True, text=True)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertFalse((launcher.parent / 'Baselines').exists())
            aborted = subprocess.run(command, input='', cwd=tmp, capture_output=True, text=True)
            self.assertNotEqual(aborted.returncode, 0)
            self.assertFalse((launcher.parent / 'Baselines').exists())
            completed = subprocess.run(command, input='\n', cwd=tmp, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            files = list((launcher.parent / 'Baselines').iterdir())
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].name.endswith('-' + Comparison.platform_name() + '.md'))
            self.assertNotIn('boids', files[0].name)
            self.assertEqual(files[0].read_text().count('| Mesure |'), 6)


if __name__ == '__main__':
    unittest.main()
