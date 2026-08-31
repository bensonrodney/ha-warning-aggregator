#!/usr/bin/env python3
"""Read / bump / verify the integration version.

`custom_components/warning_aggregator/manifest.json` is the single source of
truth. The card's banner constant is kept in sync as a convenience.

    python3 scripts/bump_version.py --show
    python3 scripts/bump_version.py patch --write     # -> prints new version
    python3 scripts/bump_version.py --check v1.2.3     # exit 1 on mismatch
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "warning_aggregator"
MANIFEST = COMPONENT / "manifest.json"
CARD = COMPONENT / "frontend" / "warning-aggregator-card.js"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def current() -> str:
    match = re.search(r'"version"\s*:\s*"([^"]+)"', MANIFEST.read_text())
    if not match:
        sys.exit("no 'version' in manifest.json")
    return match.group(1)


def bumped(version: str, part: str) -> str:
    if not SEMVER.match(version):
        sys.exit(f"current version {version!r} is not X.Y.Z; use --set")
    major, minor, patch = (int(n) for n in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write(version: str) -> None:
    MANIFEST.write_text(
        re.sub(
            r'("version"\s*:\s*")[^"]+(")',
            rf"\g<1>{version}\g<2>",
            MANIFEST.read_text(),
            count=1,
        )
    )
    if CARD.is_file():
        CARD.write_text(
            re.sub(
                r'(const VERSION = ")[^"]+(")',
                rf"\g<1>{version}\g<2>",
                CARD.read_text(),
                count=1,
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("part", nargs="?", choices=("major", "minor", "patch"))
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--set", metavar="X.Y.Z")
    parser.add_argument("--check", metavar="TAG", help="verify a tag matches")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    now = current()

    if args.show:
        print(now)
        return

    if args.check is not None:
        want = args.check.removeprefix("v")
        if want != now:
            sys.exit(f"tag {args.check} does not match manifest version {now}")
        print(f"tag matches manifest ({now})")
        return

    new = args.set or bumped(now, args.part or "patch")
    if not SEMVER.match(new):
        sys.exit(f"target version {new!r} is not X.Y.Z")
    if args.write:
        write(new)
    print(new)


if __name__ == "__main__":
    main()
