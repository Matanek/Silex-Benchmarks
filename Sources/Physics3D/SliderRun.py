#!/usr/bin/env python3
"""Qualify a free or rigidly limited rotating slider against pinned Jolt and mechanics."""
import argparse, hashlib, json, math, platform, sys
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
FIELDS = ('position', 'speed', 'x', 'y', 'first_angular_speed', 'second_angular_speed', 'anchor_error', 'angular_error', 'force_x', 'force_y', 'limit_force')
CASES = {(case, step) for case in range(6) for step in range(10, 241, 10)}
# Bounds declared before the first execution; no bound was widened.
BOUNDS = dict(
    position=0.003,
    speed=0.003,
    x=0.003,
    y=0.003,
    first_angular_speed=0.003,
    second_angular_speed=0.003,
    anchor_error=0.001,
    angular_error=0.001,
    force_x=0.1,
    force_y=0.1,
    limit_force=0.05,
)

def parse_rows(output):
    rows = {}
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 14 or tokens[0] != 'slider':
            fail(f'invalid slider row: {line}')
        values = list(map(float, tokens[1:]))
        key = tuple(values[:2])
        if not all(map(math.isfinite, values)) or key not in CASES or key in rows:
            fail('non-finite, duplicate or unknown slider sample')
        rows[tuple(map(int, key))] = dict(zip(FIELDS, values[2:]))
    if set(rows) != CASES:
        fail('missing slider samples')
    return rows

def qualify(rows):
    for (case, step), r in rows.items():
        if not 0 <= r['anchor_error'] < 0.001 or not 0 <= r['angular_error'] < 0.001:
            fail('slider lost transverse or angular alignment')
        t = step / 120
        if case in (0, 4):
            initial = -0.5 if case == 0 else 0
            expected = initial * t + 0.3 * (step * (step + 1) / 2) / (120 * 120)
            if abs(r['position'] - expected) > 0.0003 or abs(r['speed'] - (initial + 0.3 * t)) > 0.0003:
                fail('independent free slider trajectory differs')
            if abs(r['force_x']) > 0.001 or abs(r['force_y'] - 19.62) > 0.05 or abs(r['limit_force']) > 0.001:
                fail('slider constrained its free axis or lost support')
        if case == 1:
            target, force = (0.5, -4.0) if step <= 120 else (-0.5, 4.0)
            if abs(r['position'] - target) > 0.001 or abs(r['speed']) > 0.001 or abs(r['limit_force'] - force) > 0.01:
                fail('slider signed rigid-stop reaction differs')
        if case == 2:
            expected = 0.2 / 7.4
            if abs(r['first_angular_speed'] - r['second_angular_speed']) > 0.0001 or abs(r['first_angular_speed'] - expected) > 0.0003:
                fail('rotating rail projection differs')
            if r['position'] < 1.999 or abs(r['limit_force']) > 0.0001:
                fail('free slider rail was locked or moved backwards')
        if case == 3:
            if abs(r['position'] - 2 * math.cosh(0.2 * t)) > 0.003 or abs(r['speed'] - 0.4 * math.sinh(0.2 * t)) > 0.003:
                fail('rotating slider differs from centrifugal motion')
        if case == 5:
            if abs(r['position']) > 0.001 or abs(r['speed']) > 0.001 or abs(r['limit_force'] + 0.6) > 0.01 or (abs(r['force_y'] - 19.62) > 0.05):
                fail('equal slider limits do not hold the six degrees')

def compare(actual, reference):
    errors = dict.fromkeys(FIELDS, 0.0)
    for key in sorted(CASES):
        for name in FIELDS:
            error = abs(actual[key][name] - reference[key][name])
            errors[name] = max(errors[name], error)
            if error > BOUNDS[name]:
                fail(f'slider {key} {name}: error {error}, bound {BOUNDS[name]}')
    return errors

def self_test():
    rows = {key: dict.fromkeys(FIELDS, 0.0) for key in CASES}
    output = '\n'.join(('slider ' + ' '.join(map(str, (case, step, *(r[n] for n in FIELDS)))) for (case, step), r in sorted(rows.items())))
    compare(parse_rows(output), rows)
    for corrupt in (output + '\n' + output.splitlines()[0], '\n'.join(output.splitlines()[1:]), output.replace('slider 0 10 0.0', 'slider 0 10 nan', 1), output.replace('slider 0 10', 'slider 6 10', 1)):
        try:
            parse_rows(corrupt)
        except ValueError:
            continue
        fail('slider guard accepted corrupt evidence')
    altered = {key: r.copy() for key, r in rows.items()}
    altered[0, 10]['position'] = 0.1
    try:
        compare(altered, rows)
    except ValueError:
        pass
    else:
        fail('slider comparator accepted a perturbed position')
    try:
        qualify(rows)
    except ValueError:
        pass
    else:
        fail('slider independent guard accepted motionless or unloaded fixtures')
    print('physics3d slider guard self-test: ok')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path)
    p.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    p.add_argument('--self-test', action='store_true')
    o = p.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    self_test()
    if o.self_test:
        return
    source, digest = verified_source(o.archive)
    record = dict(
        schema=1,
        fixture='slider-six-cases-240-steps',
        oracle_revision=REFERENCE,
        archive_sha256=digest,
        host=platform.platform(),
        architecture=platform.machine(),
        bounds=BOUNDS,
        sources_sha256={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in ('Slider.sx', 'SliderOracle.cpp', 'SliderRun.py', 'Run.py')},
        scope='120 Hz, two seconds, free axial acceleration, signed static rigid stops with explicit pose reset, two unequal free bodies, rotating kinematic rail, offset anchor, equal limits compared to a FixedConstraint because pinned Jolt rejects equal rigid slider bounds; impacts, mutation, COM and contacts qualified by package tests',
        iterations=dict(jolt_velocity=12, jolt_position=8, silex_preparation=12, silex_velocity=12, silex_position=4),
        modes={},
    )
    for mode in ('Debug', 'Release') if o.mode == 'both' else (o.mode,):
        oracle = build_oracle(source, mode, HERE / 'SliderOracle.cpp', 'slider-oracle')
        silex = build_silex(mode, 'Slider.sx', 'slider-silex', physics=True)
        outputs = dict(jolt=checked([str(oracle)]), silex=checked([str(silex)]))
        for name, out in outputs.items():
            (BUILD / f'slider-{name}-{mode.lower()}.txt').write_text(out)
        reference, actual = (parse_rows(outputs['jolt']), parse_rows(outputs['silex']))
        qualify(reference)
        qualify(actual)
        record['modes'][mode] = dict(samples=144, maximum_absolute_errors=compare(actual, reference))
        print(f'physics3d slider {mode}: 144 samples qualified against Jolt and independent mechanics')
    (BUILD / 'slider-qualification.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        print(f'physics3d slider: {e}', file=sys.stderr)
        sys.exit(1)
