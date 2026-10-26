"""Explicit accumulated static-friction variant of the pinned tracked controller."""
import difflib
import hashlib
import platform
import shutil
from Run import BUILD, REFERENCE, build_oracle, checked, fail

SOURCE_SHA256 = "780ab68e1be031d6fbffa28ce1d1470b0959fd96c55642c3b1a26704c6743e43"
ORIGINAL_BOUNDS = """\t\t\t\t// Check which direction the brakes should be applied (we don't want to apply an impulse that would accelerate the vehicle)
\t\t\t\tif (relative_longitudinal_velocity >= 0.0f)
\t\t\t\t{
\t\t\t\t\tmin_longitudinal_impulse = -brake_impulse;
\t\t\t\t\tmax_longitudinal_impulse = 0.0f;
\t\t\t\t}
\t\t\t\telse
\t\t\t\t{
\t\t\t\t\tmin_longitudinal_impulse = 0.0f;
\t\t\t\t\tmax_longitudinal_impulse = brake_impulse;
\t\t\t\t}
"""
STABLE_BOUNDS = "\t\t\t\tmin_longitudinal_impulse = -brake_impulse;\n\t\t\t\tmax_longitudinal_impulse = brake_impulse;\n"


def adapted_controller(source):
    original = source / "Jolt/Physics/Vehicle/TrackedVehicleController.cpp"
    content = original.read_bytes()
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256:
        fail("tracked controller differs from the pinned original")
    text = content.decode()
    if text.count(ORIGINAL_BOUNDS) != 1:
        fail("locked-track bound substitution count differs")
    text = text.replace(ORIGINAL_BOUNDS, STABLE_BOUNDS)
    destination = BUILD / "tracked-stable-brakes/TrackedVehicleController.cpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)
    patch = destination.with_suffix(".patch")
    patch.write_text("".join(difflib.unified_diff(content.decode().splitlines(True), text.splitlines(True),
                                                fromfile=str(original), tofile=str(destination))))
    return destination, dict(variant="stable-brakes-symmetric-accumulated", oracle_revision=REFERENCE,
                            original_source_sha256=SOURCE_SHA256,
                            adapted_source_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                            substitutions=1, patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),
                            scope="One locked-track accumulated friction bound block; capacities, free tracks and original Jolt stay unchanged")


def build_tracked_oracle(source, mode, oracle_source, stem, *, stable=False):
    original = build_oracle(source, mode, oracle_source, stem)
    provenance = dict(variant="original", oracle_revision=REFERENCE,
                      original_binary_sha256=hashlib.sha256(original.read_bytes()).hexdigest())
    if not stable:
        return original, provenance
    controller, adaptation = adapted_controller(source)
    library = BUILD / f"jolt-{mode}/libJolt.a"
    library_digest = hashlib.sha256(library.read_bytes()).hexdigest()
    binary = BUILD / f"{stem}-stable-brakes-{mode.lower()}"
    definitions = ["-DJPH_OBJECT_STREAM", "-DJPH_USE_CPU_COMPUTE", "-DJPH_DEBUG_RENDERER", "-DJPH_PROFILE_ENABLED"]
    if mode == "Release":
        definitions.append("-DNDEBUG")
    deployment = (["-mmacosx-version-min=" + platform.mac_ver()[0]] if platform.system() == "Darwin" else [])
    command = [shutil.which("clang++") or fail("clang++ unavailable"), "-std=c++23", "-fno-rtti", "-fno-exceptions",
               *deployment, "-O0" if mode == "Debug" else "-O2", *definitions, "-I", str(source),
               str(oracle_source), str(controller), str(library), "-pthread", "-o", str(binary)]
    checked(command)
    if hashlib.sha256((source / "Jolt/Physics/Vehicle/TrackedVehicleController.cpp").read_bytes()).hexdigest() != SOURCE_SHA256 or hashlib.sha256(library.read_bytes()).hexdigest() != library_digest:
        fail("original tracked controller or library changed during build")
    adaptation.update(original_binary_sha256=provenance["original_binary_sha256"], original_library_sha256=library_digest,
                      adapted_binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), compile_command=command,
                      linkage="Adapted tracked object precedes intact pinned Jolt archive")
    return binary, adaptation
