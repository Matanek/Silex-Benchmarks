#!/usr/bin/env python3
"""Qualify a free three-part ragdoll impulse and symmetric floor impact."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from SpatialHingesRun import add, sub, mul, norm, cross

KEYS = {(case, rate, side, step, part)
        for case in (0, 1) for rate in (60, 120) for side in (-1, 1)
        for step in range((rate // 2 if case == 0 else rate * 2) + 1) for part in range(3)}
BOUNDS = dict(anchor=.01, linear=.0001, angular=.1, rest_speed=.05)

def parse(raw):
    result = {}
    for line in raw.splitlines():
        fields = line.split()
        try:
            if len(fields) != 16 or fields[0] != 'dynamic':
                fail('invalid ragdoll dynamics row')
            key = tuple(map(int, fields[1:6]))
            values = tuple(map(float, fields[6:]))
            if key not in KEYS or key in result or not all(map(math.isfinite, values)):
                fail('invalid, duplicate or nonfinite ragdoll dynamics row')
            result[key] = values
        except (ValueError, OverflowError):
            fail('invalid ragdoll dynamics number')
    if set(result) != KEYS:
        fail('missing ragdoll dynamics observations')
    return result

def qualify(rows):
    worst = dict.fromkeys(BOUNDS, 0.0)
    for case in (0, 1):
        for rate in (60, 120):
            for side in (-1, 1):
                steps = rate // 2 if case == 0 else rate * 2
                for step in range(steps + 1):
                    members = [rows[case, rate, side, step, part] for part in range(3)]
                    for part, row in enumerate(members):
                        p, v, w, anchor = row[:3], row[3:6], row[6:9], row[9]
                        if not 0 <= anchor < BOUNDS['anchor']:
                            fail('ragdoll anchor detached')
                        worst['anchor'] = max(worst['anchor'], anchor)
                        if step == 0:
                            expected_v = (0, 0, 1.5 * side) if case == 0 and part == 2 else (0, 0, 0)
                            expected_w = (1.5 * side, 0, 0) if case == 0 and part == 2 else (0, 0, 0)
                            if max(norm(sub(p, (part, 3, 0))), norm(sub(v, expected_v)), norm(sub(w, expected_w))) > .00001:
                                fail('initial impulse or rest geometry differs')
                        if case == 1:
                            if step <= rate * 3 // 5:
                                expected_y = 3 - 9.81 * step * (step + 1) / (2 * rate * rate)
                                if max(abs(p[1] - expected_y), abs(v[1] + 9.81 * step / rate)) > .0001:
                                    fail('pre-impact analytical free fall differs')
                            # Discrete impact can cross the plane before the next
                            # contact solve. Bound one step of impact travel plus
                            # Jolt's default 2 cm penetration slop; rest is stricter.
                            impact_floor = .25 - .02 - 7.5 / rate
                            if p[1] < impact_floor or norm(w) > .001 or abs(p[0] - part) > .001 or abs(p[2]) > .001:
                                fail('symmetric floor motion or penetration differs')
                            if step == steps:
                                if not .22 <= p[1] <= .28 or norm(v) >= BOUNDS['rest_speed']:
                                    fail('ragdoll did not reach bounded floor rest')
                                worst['rest_speed'] = max(worst['rest_speed'], norm(v))
                    if case == 0:
                        linear = (0, 0, 0); angular = (0, 0, 0)
                        for row in members:
                            linear = add(linear, mul(row[3:6], 2))
                            angular = add(angular, add(cross(row[:3], mul(row[3:6], 2)), mul(row[6:9], .2)))
                        errors = dict(linear=norm(sub(linear, (0, 0, 3 * side))),
                                      angular=norm(sub(angular, (9.3 * side, -6 * side, 0))))
                        for name, value in errors.items():
                            worst[name] = max(worst[name], value)
                            if value >= BOUNDS[name]:
                                fail(f'ragdoll {name} balance exceeds bound: {value}')
                    if step == steps and case == 0 and norm(members[0][3:6]) < .01:
                        fail('impulse did not transmit to parent')
    return worst

def rejected(action):
    try:
        action()
    except ValueError:
        return
    fail('ragdoll dynamics guard accepted corrupt evidence')

def self_test(raw, rows):
    lines = raw.splitlines()
    rejected(lambda: parse(raw + '\n' + lines[0]))
    rejected(lambda: parse('\n'.join(lines[1:])))
    rejected(lambda: parse(raw.replace('dynamic 0 60 -1 0 0', 'dynamic 8 60 -1 0 0')))
    changed_lines = lines.copy(); fields = changed_lines[0].split(); fields[6] = 'nan'
    changed_lines[0] = ' '.join(fields)
    rejected(lambda: parse('\n'.join(changed_lines)))
    for case in (0, 1):
        for component in range(10):
            changed = rows.copy(); key = (case, 60, -1, 30 if case == 0 else 120, 2)
            values = list(changed[key]); values[component] += 2
            changed[key] = tuple(values)
            rejected(lambda: qualify(changed))
    return 24

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    args = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    source, digest = verified_source(args.archive)
    record = dict(schema=1, fixture='ragdoll-impulse-symmetric-floor-v1', oracle_revision=REFERENCE,
                  archive_sha256=digest, bounds=BOUNDS,
                  scope='Free three-sphere chain, off-center impulse without gravity; separate symmetric sphere-floor fall. Physical invariants compared independently in each engine, no general contact trajectory or motor parity claim.', modes={})
    for mode in ('Debug', 'Release') if args.mode == 'both' else (args.mode,):
        oracle = build_oracle(source, mode, HERE / 'RagdollDynamicsOracle.cpp', 'ragdoll-dynamics-oracle')
        binary = build_silex(mode, 'RagdollDynamics.sx', 'ragdoll-dynamics-silex', True)
        evidence = {}
        for name, executable in (('silex', binary), ('jolt', oracle)):
            raw = checked([str(executable)])
            (BUILD / f'ragdoll-dynamics-{name}-{mode.lower()}.txt').write_text(raw)
            rows = parse(raw)
            evidence[name] = dict(observations=len(rows), worst=qualify(rows),
                                  corrupt_witnesses_rejected=self_test(raw, rows),
                                  output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        record['modes'][mode] = evidence
        (BUILD / 'ragdoll-dynamics-qualification.json').write_text(json.dumps(record, indent=2) + '\n')
        print(f'{mode}: ragdoll impulse balance, transmission, anchors and symmetric floor rest green', flush=True)

if __name__ == '__main__':
    main()
