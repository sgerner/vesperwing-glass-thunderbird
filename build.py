#!/usr/bin/env python3
"""Build the adaptive and fixed-palette Vesperwing Glass Thunderbird themes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent
VARIANTS = {
    "adaptive": (ROOT / "manifest.json", ROOT / "dist" / "vesperwing-glass.xpi"),
    "light": (ROOT / "manifests" / "light.json", ROOT / "dist" / "vesperwing-glass-light.xpi"),
    "dark": (ROOT / "manifests" / "dark.json", ROOT / "dist" / "vesperwing-glass-dark.xpi"),
}


def read_manifest(path: Path, variant: str) -> bytes:
    raw = path.read_bytes()
    manifest = json.loads(raw)

    if manifest.get("manifest_version") != 3:
        raise ValueError(f"{path.relative_to(ROOT)} must use Manifest Version 3")
    if not manifest.get("theme"):
        raise ValueError(f"{path.relative_to(ROOT)} must define theme")
    if "theme_experiment" in manifest or "experiment_apis" in manifest:
        raise ValueError("release-compatible packages must not use experiments")
    gecko = manifest.get("browser_specific_settings", {}).get("gecko", {})
    if not gecko.get("id"):
        raise ValueError(f"{path.relative_to(ROOT)} must define a unique Gecko ID")
    if manifest.get("version") != "1.0.1":
        raise ValueError(f"{path.relative_to(ROOT)} must be version 1.0.1")

    if variant == "adaptive" and not manifest.get("dark_theme"):
        raise ValueError("adaptive manifest must define both theme and dark_theme")
    if variant != "adaptive" and manifest.get("dark_theme"):
        raise ValueError(f"fixed {variant} manifest must not define dark_theme")
    return raw


def write_xpi(output_path: Path, manifest_bytes: bytes) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(fd)
    temporary_path = Path(temp_name)

    try:
        info = ZipInfo("manifest.json", date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        with ZipFile(temporary_path, "w") as archive:
            archive.writestr(info, manifest_bytes)
        temporary_path.chmod(0o644)
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return output_path


def build(variant: str, output: Path | None = None) -> Path:
    manifest_path, default_output = VARIANTS[variant]
    raw = read_manifest(manifest_path, variant)
    return write_xpi(output or default_output, raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=("all", *VARIANTS),
        default="all",
        help="package one palette or all three (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="custom XPI path; valid only with --variant adaptive, light, or dark",
    )
    args = parser.parse_args()
    if args.output and args.variant == "all":
        parser.error("--output requires one specific --variant")

    variants = VARIANTS if args.variant == "all" else {args.variant: VARIANTS[args.variant]}
    try:
        if args.variant == "all":
            ids = []
            for name, (manifest_path, _output) in VARIANTS.items():
                raw = read_manifest(manifest_path, name)
                manifest = json.loads(raw)
                ids.append(manifest["browser_specific_settings"]["gecko"]["id"])
            if len(set(ids)) != len(ids):
                raise ValueError("each palette XPI must use a distinct Gecko ID")
        outputs = [build(name, args.output) for name in variants]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
