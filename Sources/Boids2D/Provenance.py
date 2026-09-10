#!/usr/bin/env python3
"""Bind fixed executable artifacts to their compiler, source closure and shaders."""
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys


def run(*args):
    return subprocess.check_output([str(a) for a in args], text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(path, files):
    return {str(f.relative_to(path)): digest(f) for f in sorted(files) if f.is_file()}


def inputs(source, compiler):
    workspace = source.parents[2]
    repository = Path(run('git', '-C', compiler.parent, 'rev-parse', '--show-toplevel'))
    packages = []
    for line in run(compiler, 'packages', 'resolve', source / 'Silex.sx').splitlines():
        name, version, origin, raw_path = line.split(maxsplit=3)
        path = Path(raw_path)
        if origin not in ('workspace-link', 'user-link'):
            raise ValueError(f'{name}: qualification requires a Git-owned package closure')
        if 'Worktree' in workspace.parts and (origin != 'workspace-link' or not path.is_relative_to(workspace)):
            raise ValueError(f'{name}: package escapes the Spec workspace')
        if run('git', '-C', path, 'status', '--porcelain'):
            raise ValueError(f'{name}: dirty package cannot be sealed')
        target = {'Darwin': 'macos', 'Linux': 'linux', 'Windows': 'windows'}[platform.system()] + '-' + ('arm64' if platform.machine() in ('arm64', 'aarch64') else 'x64')
        declared = json.loads((path / 'Package.json').read_text()).get('artifacts', {}).get(target, {})
        native = {}
        for artifact, descriptor in declared.items():
            observed = digest(path / descriptor['path'])
            if observed != descriptor['sha256']:
                raise ValueError(f'{name}/{artifact}: artifact checksum mismatch')
            native[artifact] = descriptor
        packages.append({'name': name, 'version': version, 'origin': origin,
                         'path': str(path.relative_to(workspace)),
                         'commit': run('git', '-C', path, 'rev-parse', 'HEAD'), 'native_artifacts': native,
                         'dirty': bool(run('git', '-C', path, 'status', '--porcelain'))})
    if run('git', '-C', repository, 'status', '--porcelain'):
        raise ValueError('dirty compiler cannot be sealed')
    compiler_name = str(compiler.relative_to(workspace)) if compiler.is_relative_to(workspace) else compiler.name
    return {'compiler': compiler_name, 'compiler_sha256': digest(compiler),
            'compiler_commit': run('git', '-C', repository, 'rev-parse', 'HEAD'),
            'compiler_dirty': bool(run('git', '-C', repository, 'status', '--porcelain')),
            'packages': packages,
            'sources': tree(source, [source / 'Silex.sx', *source.joinpath('Cpp').rglob('*')]),
            'shader_sha256': digest(workspace / 'Packages/GFX.Scene2D/Shaders/Drawing.hlsl'),
            'cpp_compiler': run('c++', '--version').splitlines()[0],
            'sdl_version': run('pkg-config', '--modversion', 'sdl3'),
            'shadercross_sha256': digest(Path(run('which', 'shadercross')))}


def artifacts(build):
    cpp = build / 'cpp'
    binaries = [build / 'gfx-boids-silex']
    for name in ('BoidsCppArchitectural', 'BoidsCppDirect'):
        path = cpp / name
        binaries.append(path if path.exists() else cpp / 'Release' / name)
    for binary in binaries:
        if not binary.is_file():
            raise ValueError(f'missing executable: {binary.name}')
    files = [*binaries, *cpp.joinpath('Shaders').rglob('*')]
    cache = cpp / 'CMakeCache.txt'
    configuration = [line for line in cache.read_text().splitlines() if line.startswith(('CMAKE_BUILD_TYPE:', 'CMAKE_CXX_FLAGS', 'CMAKE_CXX_COMPILER:', 'EnTT_DIR:', 'SDL3_DIR:'))]
    entt = cpp / '_deps/entt-src'
    entt_revision = run('git', '-C', entt, 'rev-parse', 'HEAD') if entt.exists() else 'system-package'
    # Dynamic SDL is an input to the timed processes even when binary hashes match.
    libdir = Path(run('pkg-config', '--variable=libdir', 'sdl3'))
    sdl = {p.name: digest(p) for p in sorted(libdir.glob('*SDL3*')) if p.is_file()}
    return {'files': tree(build, files), 'sdl_libraries': sdl, 'configuration': configuration, 'entt_revision': entt_revision}


def main():
    command, raw_source, raw_compiler, raw_build = sys.argv[1:]
    source, compiler, build = map(lambda p: Path(p).resolve(), (raw_source, raw_compiler, raw_build))
    current = inputs(source, compiler)
    prepare = build / 'BuildInputs.json'
    seal = build / 'ArtifactSeal.json'
    if command == 'prepare':
        prepare.write_text(json.dumps(current, indent=2, sort_keys=True) + '\n')
    elif command == 'seal':
        if current != json.loads(prepare.read_text()):
            raise ValueError('source closure changed during build')
        seal.write_text(json.dumps({'inputs': current, 'artifacts': artifacts(build)}, indent=2, sort_keys=True) + '\n')
    elif command == 'verify':
        expected = json.loads(seal.read_text())
        if current != expected['inputs'] or artifacts(build) != expected['artifacts']:
            raise ValueError('artifact/compiler/closure changed; rebuild required')
    else:
        raise ValueError('unknown provenance operation')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f'provenance: {error}')
