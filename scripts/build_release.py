"""Build the manual Home Assistant installation archive without runtime data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "solar_of_things_cloud"


def build(output: Path, tag: str | None = None) -> Path:
    """Package integration files and public setup documentation."""
    integration = ROOT / "custom_components" / DOMAIN
    manifest = json.loads((integration / "manifest.json").read_text())
    version = manifest["version"]
    if tag is not None and tag.removeprefix("v") != version:
        raise ValueError("Release tag does not match manifest.json")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{DOMAIN}-{version}.zip"
    files = [
        path
        for path in integration.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in {".py", ".json", ".png"}
    ]
    files.extend(
        ROOT / name
        for name in (
            "LICENSE",
            "README.md",
            "README.it.md",
            "docs/energy-dashboard.md",
            "examples/sot_cloud_energy.yaml",
        )
    )
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        for path in sorted(files):
            package.write(path, str(path.relative_to(ROOT)))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n")
    print(f"Created {archive.name}: {len(files)} public files")
    return archive


def main() -> None:
    """Parse output location and the optional published release tag."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--tag")
    args = parser.parse_args()
    build(args.output.resolve(), args.tag)


if __name__ == "__main__":
    main()
