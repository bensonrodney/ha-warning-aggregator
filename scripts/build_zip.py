#!/usr/bin/env python3
"""Build the HACS release zip: the integration's files at the archive root.

Referenced by ``hacs.json`` (``zip_release`` / ``filename``); HACS unpacks it
into ``custom_components/warning_aggregator/``.
"""

from __future__ import annotations

import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "custom_components" / "warning_aggregator"
OUT = ROOT / "warning_aggregator.zip"


def main() -> None:
    OUT.unlink(missing_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SRC.rglob("*")):
            if (
                path.is_file()
                and path.suffix != ".pyc"
                and "__pycache__" not in path.parts
            ):
                archive.write(path, path.relative_to(SRC))
    print(f"wrote {OUT.name} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
