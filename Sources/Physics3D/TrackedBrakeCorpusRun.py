#!/usr/bin/env python3
"""Requalify previous tracked contact fixtures with the explicit stable-brakes oracle."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
from Run import BUILD, GROUP, HERE, REFERENCE, build_silex, checked, fail, verified_source
from TrackedBrakeOracle import build_tracked_oracle

FIXTURES = ("TrackedGround", "TrackedRamp", "TrackedAutomatic", "TrackedAutomaticRamp",
            "TrackedPlatform", "TrackedDynamicPlatform", "TrackedRotatingPlatform")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--mode', choices=('Debug', 'Release', 'both'), default='both')
    parser.add_argument('--stable-brakes', action='store_true', required=True)
    args = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f'run from group root {GROUP}')
    source, digest = verified_source(args.archive)
    report = dict(schema=1, oracle_revision=REFERENCE, archive_sha256=digest,
                  scope='Previous seven tracked contact fixtures; unchanged programs, profiles, qualifiers, mirrors, guards and parity budgets',
                  fixtures={})
    for fixture in FIXTURES:
        module = importlib.import_module(fixture + 'Run')
        stem = 'tracked-brake-corpus-' + fixture.removeprefix('Tracked').lower()
        outputs = {}
        entry = dict(velocity_iterations=48 if fixture == 'TrackedDynamicPlatform' else 12,
                     position_iterations=4, modes={})
        for mode in ('Debug', 'Release') if args.mode == 'both' else (args.mode,):
            oracle, adapter = build_tracked_oracle(source, mode, HERE / (fixture + 'Oracle.cpp'),
                                                   stem + '-oracle', stable=True)
            silex = build_silex(mode, fixture + '.sx', stem + '-silex', True)
            parsed = {}
            evidence = dict(oracle_adapter=adapter)
            for engine, binary in (('jolt', oracle), ('silex', silex)):
                raw = checked([str(binary)])
                (BUILD / f'{stem}-stable-brakes-{engine}-{mode.lower()}.txt').write_text(raw)
                rows = module.parse(raw)
                result = dict(states=len(rows), qualification=module.qualify(rows, engine),
                              guards=module.self_test(raw, rows, engine), sha256=hashlib.sha256(raw.encode()).hexdigest())
                if fixture == 'TrackedGround':
                    result['mirror'] = module.compare(rows, module.mirror_curves(rows), conditioned_velocity=True)
                evidence[engine] = result
                parsed[engine] = rows
                outputs[mode, engine] = raw
            evidence['parity'] = module.compare(parsed['silex'], parsed['jolt'])
            if fixture == 'TrackedGround':
                raw = checked([str(oracle), '--perturb'])
                (BUILD / f'{stem}-stable-brakes-jolt-perturbed-{mode.lower()}.txt').write_text(raw)
                rows = module.parse(raw)
                evidence['height_perturbation'] = dict(qualification=module.qualify(rows, 'jolt'),
                                                     parity=module.compare(parsed['jolt'], rows),
                                                     sha256=hashlib.sha256(raw.encode()).hexdigest())
            entry['modes'][mode] = evidence
            print(f'{fixture} {mode}: both engines, guards, invariants and parity green', flush=True)
        if args.mode == 'both':
            for engine in ('jolt', 'silex'):
                if outputs['Debug', engine] != outputs['Release', engine]:
                    fail(f'{fixture} {engine} Debug/Release differ')
            entry['debug_release_identical'] = True
        report['fixtures'][fixture] = entry
        (BUILD / 'tracked-brake-corpus-stable-brakes-qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Stable-brakes tracked corpus green', flush=True)


if __name__ == '__main__':
    main()
