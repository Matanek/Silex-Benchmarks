"""Compose only the two already-qualified numerical Jolt controller variants."""
import hashlib
import platform
import shutil
from MotorcycleLeanOracle import adapted_controller as motorcycle_controller
from TrackedBrakeOracle import adapted_controller as tracked_controller
from Run import BUILD, REFERENCE, build_oracle, checked, fail


def build_composed_oracle(source,mode,oracle_source,stem):
    original=build_oracle(source,mode,oracle_source,stem)
    motorcycle,lean=motorcycle_controller(source)
    tracked,brakes=tracked_controller(source)
    library=BUILD/f'jolt-{mode}/libJolt.a'
    library_hash=hashlib.sha256(library.read_bytes()).hexdigest()
    binary=BUILD/f'{stem}-stable-controllers-{mode.lower()}'
    definitions=['-DJPH_OBJECT_STREAM','-DJPH_USE_CPU_COMPUTE','-DJPH_DEBUG_RENDERER','-DJPH_PROFILE_ENABLED']
    if mode=='Release':definitions.append('-DNDEBUG')
    deployment=['-mmacosx-version-min='+platform.mac_ver()[0]] if platform.system()=='Darwin' else []
    command=[shutil.which('clang++') or fail('clang++ unavailable'),'-std=c++23','-fno-rtti','-fno-exceptions',
        *deployment,'-O0' if mode=='Debug' else '-O2',*definitions,'-I',str(source),str(oracle_source),
        str(motorcycle),str(tracked),str(library),'-pthread','-o',str(binary)]
    checked(command)
    for filename,record in [('MotorcycleController.cpp',lean),('TrackedVehicleController.cpp',brakes)]:
        if hashlib.sha256((source/'Jolt/Physics/Vehicle'/filename).read_bytes()).hexdigest()!=record['original_source_sha256']:
            fail('original vehicle controller changed during reference composition')
    if hashlib.sha256(library.read_bytes()).hexdigest()!=library_hash:fail('original Jolt library changed')
    return binary,dict(oracle_revision=REFERENCE,variants=[lean,brakes],original_library_sha256=library_hash,
        original_binary_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
        adapted_binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),compile_command=command,
        scope='Exactly the accepted lean magnitudes and accumulated track brake bounds; no further adaptation')
