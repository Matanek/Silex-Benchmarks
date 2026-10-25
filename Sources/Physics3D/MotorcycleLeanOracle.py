"""Explicit small-angle variant of the pinned Jolt motorcycle controller."""
import difflib
import hashlib
import platform
import shutil
from Run import BUILD, REFERENCE, build_oracle, checked, fail

SOURCE_SHA256 = "7e284b19b668284a64aab7add0e30e67fa09adc192a561120b8562c7ac1aa9b0"
SUBSTITUTIONS = (
    ("ACos(mTargetLean.Dot(adjusted_world_up))",
     "ATan2(mTargetLean.Cross(adjusted_world_up).Length(), mTargetLean.Dot(adjusted_world_up))", 1),
    ("ACos(mTargetLean.Dot(up))",
     "ATan2(mTargetLean.Cross(up).Length(), mTargetLean.Dot(up))", 2),
)


def adapted_controller(source):
    original = source / "Jolt/Physics/Vehicle/MotorcycleController.cpp"
    content = original.read_bytes()
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256:
        fail("motorcycle controller differs from the pinned original")
    text = content.decode()
    for old, new, count in SUBSTITUTIONS:
        if text.count(old) != count:
            fail("motorcycle lean substitution count differs")
        text = text.replace(old, new)
    destination = BUILD / "motorcycle-stable-lean/MotorcycleController.cpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)
    delta = "".join(difflib.unified_diff(content.decode().splitlines(True), text.splitlines(True),
                                      fromfile=str(original), tofile=str(destination)))
    patch = destination.with_suffix(".patch")
    patch.write_text(delta)
    return destination, dict(
        variant="stable-lean-atan2", oracle_revision=REFERENCE,
        original_source_sha256=SOURCE_SHA256,
        adapted_source_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        substitutions=3, patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),
        scope="Three signed lean-angle magnitudes only; original library and sources unchanged",
    )


def build_motorcycle_oracle(source, mode, oracle_source, stem, *, stable=False):
    original = build_oracle(source, mode, oracle_source, stem)
    provenance = dict(variant="original", oracle_revision=REFERENCE,
                      original_binary_sha256=hashlib.sha256(original.read_bytes()).hexdigest())
    if not stable:
        return original, provenance
    controller, adaptation = adapted_controller(source)
    binary = BUILD / f"{stem}-stable-lean-{mode.lower()}"
    definitions = ["-DJPH_OBJECT_STREAM", "-DJPH_USE_CPU_COMPUTE",
                   "-DJPH_DEBUG_RENDERER", "-DJPH_PROFILE_ENABLED"]
    if mode == "Release":
        definitions.append("-DNDEBUG")
    deployment = (["-mmacosx-version-min=" + platform.mac_ver()[0]]
                  if platform.system() == "Darwin" else [])
    command = [shutil.which("clang++") or fail("clang++ unavailable"),
               "-std=c++23", "-fno-rtti", "-fno-exceptions", *deployment,
               "-O0" if mode == "Debug" else "-O2", *definitions,
               "-I", str(source), str(oracle_source), str(controller),
               str(BUILD / f"jolt-{mode}/libJolt.a"), "-pthread", "-o", str(binary)]
    checked(command)
    if hashlib.sha256((source / "Jolt/Physics/Vehicle/MotorcycleController.cpp").read_bytes()).hexdigest() != SOURCE_SHA256:
        fail("original motorcycle controller changed during build")
    adaptation.update(original_binary_sha256=provenance["original_binary_sha256"],
                      adapted_binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                      compile_command=command, linkage="Adapted controller object precedes intact pinned Jolt archive")
    return binary, adaptation
