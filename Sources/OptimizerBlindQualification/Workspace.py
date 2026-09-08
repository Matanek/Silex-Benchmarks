#!/usr/bin/env python3
"""Materialize and link the exact sealed multi-repository workspace."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import Qualification


REPOSITORIES = {
    "Silex": "Matanek/Silex",
    "GFX": "Matanek/Silex-Lib-GFX",
    "STD": "Matanek/Silex-Lib-STD",
    "GFX.Assets": "Matanek/Silex-Lib-GFX.Assets",
    "JSON": "Matanek/Silex-Lib-JSON",
    "GFX.Canvas": "Matanek/Silex-Lib-GFX.Canvas",
    "GFX.Font": "Matanek/Silex-Lib-GFX.Font",
    "GFX.ECS": "Matanek/Silex-Lib-GFX.ECS",
    "GFX.GPU": "Matanek/Silex-Lib-GFX.GPU",
    "GFX.Physics": "Matanek/Silex-Lib-GFX.Physics",
    "GFX.Application": "Matanek/Silex-Lib-GFX.Application",
    "GFX.Scene2D": "Matanek/Silex-Lib-GFX.Scene2D",
    "GFX.Rendering": "Matanek/Silex-Lib-GFX.Rendering",
    "GFX.Scene3D": "Matanek/Silex-Lib-GFX.Scene3D",
    "GFX.Stats": "Matanek/Silex-Lib-GFX.Stats",
    "GFX.UI": "Matanek/Silex-Lib-GFX.UI",
    "GFX.UI.Terminal": "Matanek/Silex-Lib-GFX.UI.Terminal",
    "GFX.Viewer": "Matanek/Silex-Lib-GFX.Viewer",
    "GFX.WebView": "Matanek/Silex-Lib-GFX.WebView",
    "Sync": "Matanek/Silex-Lib-Sync",
}


def checkout(manifest: dict, candidate: dict, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for repository in manifest["repositories"]:
        name = repository["name"]
        if name == manifest["owner_repository"]:
            continue
        revision = (
            candidate["qualified_candidate_revision"]
            if name == manifest["candidate"]["repository"]
            else repository["revision"]
        )
        destination = workspace / repository["path"]
        if destination.exists():
            actual = Qualification.run_checked(["git", "rev-parse", "HEAD"], destination).stdout.strip()
            if actual != revision:
                raise Qualification.QualificationError(
                    f"refusing existing {destination}: {actual} != {revision}"
                )
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        slug = REPOSITORIES.get(name)
        if slug is None:
            raise Qualification.QualificationError(f"no checkout mapping for {name}")
        Qualification.run_checked(
            ["git", "clone", "--filter=blob:none", "--no-checkout", f"https://github.com/{slug}.git", str(destination)],
            workspace,
            timeout=600,
        )
        Qualification.run_checked(["git", "config", "core.autocrlf", "false"], destination)
        Qualification.run_checked(["git", "config", "core.longpaths", "true"], destination)
        if name == manifest["candidate"]["repository"]:
            Qualification.run_checked(
                ["git", "fetch", "origin", revision, repository["revision"], "--depth=2"],
                destination,
                timeout=600,
            )
        else:
            Qualification.run_checked(["git", "fetch", "origin", revision, "--depth=1"], destination, timeout=600)
        Qualification.run_checked(["git", "checkout", "--detach", revision], destination, timeout=120)


def checkout_baseline(manifest: dict, workspace: Path) -> None:
    destination = workspace / "_baseline" / "Silex"
    revision = manifest["compiler_baseline"]["revision"]
    if destination.exists():
        actual = Qualification.run_checked(["git", "rev-parse", "HEAD"], destination).stdout.strip()
        if actual != revision:
            raise Qualification.QualificationError(f"baseline checkout mismatch: {actual} != {revision}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    Qualification.run_checked(
        ["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/Matanek/Silex.git", str(destination)],
        workspace,
        timeout=600,
    )
    Qualification.run_checked(["git", "config", "core.autocrlf", "false"], destination)
    Qualification.run_checked(["git", "config", "core.longpaths", "true"], destination)
    Qualification.run_checked(["git", "fetch", "origin", revision, "--depth=1"], destination, timeout=600)
    Qualification.run_checked(["git", "checkout", "--detach", revision], destination, timeout=120)


def link(
    manifest: dict,
    manifest_path: Path,
    candidate: dict,
    candidate_path: Path,
    fixture: dict,
    fixture_path: Path,
    workspace: Path,
    silex: Path,
    target: str | None,
) -> None:
    workspace = workspace.resolve()
    for repository in manifest["repositories"]:
        if not repository["path"].startswith("Packages/"):
            continue
        command = [str(silex.resolve()), "link", repository["path"], "--workspace", str(workspace)]
        if target:
            command.extend(["--target", target])
        Qualification.run_checked(command, workspace, timeout=600)
    Qualification.audit_workspace(
        manifest,
        manifest_path,
        candidate,
        candidate_path,
        fixture,
        fixture_path,
        workspace,
        silex,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("Manifest.json"))
    parser.add_argument("--candidate-descriptor", type=Path, default=Path(__file__).with_name("Candidate.json"))
    parser.add_argument("--fixture-correction", type=Path, default=Path(__file__).with_name("FixtureCorrection.json"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    checkout_parser = subparsers.add_parser("checkout")
    checkout_parser.add_argument("--workspace", required=True, type=Path)
    checkout_parser.add_argument("--baseline", action="store_true")
    link_parser = subparsers.add_parser("link")
    link_parser.add_argument("--workspace", required=True, type=Path)
    link_parser.add_argument("--silex", required=True, type=Path)
    link_parser.add_argument("--target")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    candidate_path = args.candidate_descriptor.resolve()
    fixture_path = args.fixture_correction.resolve()
    manifest = Qualification.read_json(manifest_path)
    Qualification.audit_manifest_shape(manifest)
    candidate = Qualification.read_json(candidate_path)
    Qualification.audit_candidate(candidate, candidate_path, manifest, manifest_path)
    fixture = Qualification.read_json(fixture_path)
    Qualification.audit_fixture(fixture, fixture_path, manifest, manifest_path)
    if args.command == "checkout":
        checkout(manifest, candidate, args.workspace.resolve())
        if args.baseline:
            checkout_baseline(manifest, args.workspace.resolve())
        print("sealed workspace checkout: PASS")
    else:
        link(
            manifest,
            manifest_path,
            candidate,
            candidate_path,
            fixture,
            fixture_path,
            args.workspace.resolve(),
            args.silex.resolve(),
            args.target,
        )
        print("sealed workspace links: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("workspace preparation: interrupted; active process group terminated", file=sys.stderr)
        sys.exit(130)
    except Qualification.QualificationError as error:
        print(f"workspace preparation: FAIL: {error}", file=sys.stderr)
        sys.exit(1)
