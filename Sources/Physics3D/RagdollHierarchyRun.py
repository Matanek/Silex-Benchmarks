#!/usr/bin/env python3
"""Qualify ragdoll hierarchy poses and parent filtering against pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, verified_source
from LoadedSwingTwistRun import product, rotate

KEYS = {(instance, stage, part) for instance in (0, 1) for stage in (0, 1) for part in (0, 1, 2)}
TOLERANCE = 0.00002

def parse(raw):
    poses = {}
    filters = {}
    for line in raw.splitlines():
        fields = line.split()
        try:
            if len(fields) == 18 and fields[0] == 'pose':
                key = tuple(map(int, fields[1:4]))
                values = tuple(map(float, fields[4:]))
                if key not in KEYS or key in poses or not all(map(math.isfinite, values)):
                    fail('invalid ragdoll pose row')
                poses[key] = values
            elif len(fields) == 3 and fields[0] == 'filter':
                name = fields[1]
                if name not in ('own', 'cross') or name in filters:
                    fail('invalid ragdoll filter row')
                filters[name] = int(fields[2])
            else:
                fail('invalid ragdoll observation row')
        except (ValueError, OverflowError):
            fail('invalid ragdoll number')
    if set(poses) != KEYS or filters != dict(own=1, cross=9):
        fail('missing ragdoll poses or incorrect parent/instance filtering')
    return poses

def quaternion(axis, angle):
    return tuple(v * math.sin(angle / 2) for v in axis) + (math.cos(angle / 2),)

def rotation_error(first, second):
    return min(max(abs(a - b) for a, b in zip(first, second)),
               max(abs(a + b) for a, b in zip(first, second)))

def qualify(poses):
    worst = 0.0
    z = quaternion((0, 0, 1), math.pi / 2)
    x = quaternion((1, 0, 0), math.pi / 2)
    offsets = ((.2, 0, 0), (0, .3, 0), (0, 0, .4))
    rotations = (quaternion((1, 0, 0), .3), quaternion((0, 1, 0), .2), (0, 0, 0, 1))
    for (instance, stage, part), values in poses.items():
        jp, jq, bp, bq = values[:3], values[3:7], values[7:10], values[10:]
        root = (3 + 10 * instance, 4, 5) if stage == 0 else (-2 + 10 * instance, 3, 1)
        # Independent closed-form joint positions for this quarter-turn chain.
        displacement = ((0, 0, 0), (0, 0, -1), (0, 0, 1)) if stage == 0 else ((0, 0, 0), (1, 0, 0), (-1, 0, 0))
        expected_p = tuple(a + b for a, b in zip(root, displacement[part]))
        root_q = quaternion((0, 1, 0), math.pi / 2) if stage == 0 else quaternion((1, 0, 0), .8)
        expected_q = root_q if part == 0 else product(root_q, z if part == 1 else product(z, x))
        offset = rotate(expected_q, offsets[part])
        expected_bp = tuple(a + b for a, b in zip(expected_p, offset))
        errors = [max(abs(a - b) for a, b in zip(jp, expected_p)), rotation_error(jq, expected_q),
                  max(abs(a - b) for a, b in zip(bp, expected_bp)), rotation_error(bq, product(expected_q, rotations[part])),
                  abs(sum(v * v for v in jq) - 1), abs(sum(v * v for v in bq) - 1)]
        worst = max(worst, *errors)
        if max(errors) > TOLERANCE:
            fail(f'ragdoll hierarchy/body offset differs at {(instance, stage, part)}: {errors}')
    return worst

def rejected(action):
    try:
        action()
    except ValueError:
        return
    fail('ragdoll guard accepted a corrupt witness')

def self_test(raw, poses):
    lines = raw.splitlines()
    rejected(lambda: parse(raw + '\n' + lines[0]))
    rejected(lambda: parse('\n'.join(lines[1:])))
    rejected(lambda: parse(raw.replace('filter cross 9', 'filter cross 0')))
    rejected(lambda: parse(raw.replace('filter own 1', 'filter own 3')))
    rejected(lambda: parse(raw.replace('pose 0 0 0', 'pose 8 0 0')))
    changed_lines = lines.copy()
    fields = changed_lines[0].split(); fields[4] = 'nan'
    changed_lines[0] = ' '.join(fields)
    rejected(lambda: parse('\n'.join(changed_lines)))
    for component in range(14):
        changed = poses.copy()
        values = list(changed[0, 0, 0]); values[component] += .1
        changed[0, 0, 0] = tuple(values)
        rejected(lambda: qualify(changed))
    return 20

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    args = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from workspace or Spec group root: {GROUP}')
    source, digest = verified_source(args.archive)
    record = dict(schema=1, fixture='ragdoll-hierarchy-body-offset-v1', oracle_revision=REFERENCE,
                  archive_sha256=digest, tolerance=TOLERANCE,
                  scope='Jolt Ragdoll GetPose/SetPose uses body origins; known offsets recover joint poses. Silex overlapping sensor contacts are compared with Jolt allowed group-pair counts. No dynamic contact or motor parity claim.', modes={})
    for mode in ('Debug', 'Release') if args.mode == 'both' else (args.mode,):
        oracle = build_oracle(source, mode, HERE / 'RagdollHierarchyOracle.cpp', 'ragdoll-hierarchy-oracle')
        binary = build_silex(mode, 'RagdollHierarchy.sx', 'ragdoll-hierarchy-silex', True)
        evidence = {}
        for name, executable in (('silex', binary), ('jolt', oracle)):
            raw = checked([str(executable)])
            (BUILD / f'ragdoll-hierarchy-{name}-{mode.lower()}.txt').write_text(raw)
            poses = parse(raw)
            evidence[name] = dict(observations=14, worst_error=qualify(poses),
                                  corrupt_witnesses_rejected=self_test(raw, poses),
                                  output_sha256=hashlib.sha256(raw.encode()).hexdigest())
        record['modes'][mode] = evidence
        (BUILD / 'ragdoll-hierarchy-qualification.json').write_text(json.dumps(record, indent=2) + '\n')
        print(f'{mode}: hierarchy poses, body offsets and parent/instance filters green', flush=True)

if __name__ == '__main__':
    main()
