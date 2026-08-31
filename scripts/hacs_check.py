#!/usr/bin/env python3
"""The subset of the HACS repository checks that need no GitHub API.

The full ``hacs/action`` talks to ``api.github.com`` for repo metadata
(description, topics, issues) and to ``home-assistant/brands`` — none of which
works from a Gitea runner. This script runs the parts that only look at the
files in the repo, so CI still catches the common HACS mistakes. The real
action runs on GitHub (see ``.github/workflows/validate.yml``).

    python3 scripts/hacs_check.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

HACS_JSON_KEYS = {
    "name",
    "content_in_root",
    "filename",
    "country",
    "homeassistant",
    "hacs",
    "persistent_directory",
    "zip_release",
    "hide_default_branch",
    "render_readme",
}
MANIFEST_REQUIRED = (
    "domain",
    "name",
    "version",
    "documentation",
    "issue_tracker",
    "codeowners",
)
HA_VERSION_RE = re.compile(r"^\d{4}\.\d{1,2}(\.\d+)?$")

errors: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def ok(msg: str) -> None:
    notes.append(msg)


def load_json(path: pathlib.Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        fail(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")
        return None


def check_hacs_json() -> None:
    path = ROOT / "hacs.json"
    if not path.is_file():
        fail("hacs.json is missing from the repository root")
        return
    data = load_json(path)
    if data is None:
        return
    if not data.get("name"):
        fail("hacs.json must set 'name'")
    for key in data:
        if key not in HACS_JSON_KEYS:
            fail(f"hacs.json has an unknown key: '{key}'")
    version = data.get("homeassistant")
    if version is not None and not HA_VERSION_RE.match(str(version)):
        fail(f"hacs.json 'homeassistant' is not a valid HA version: {version!r}")
    ok("hacs.json is valid")


def check_integration() -> None:
    root = ROOT / "custom_components"
    domains = (
        [p for p in root.iterdir() if (p / "manifest.json").is_file()]
        if root.is_dir()
        else []
    )
    if len(domains) != 1:
        fail(
            "expected exactly one integration under custom_components/, "
            f"found {len(domains)}"
        )
        return

    folder = domains[0]
    manifest = load_json(folder / "manifest.json")
    if manifest is None:
        return

    if manifest.get("domain") != folder.name:
        fail(
            f"manifest 'domain' ({manifest.get('domain')!r}) does not match the "
            f"folder name ({folder.name!r})"
        )
    for key in MANIFEST_REQUIRED:
        if not manifest.get(key):
            fail(f"{folder.name}/manifest.json is missing HACS-required key '{key}'")
    for key in ("documentation", "issue_tracker"):
        value = manifest.get(key, "")
        if value and not value.startswith(("http://", "https://")):
            fail(f"manifest.json '{key}' must be a URL, got {value!r}")
    owners = manifest.get("codeowners")
    if not (
        isinstance(owners, list)
        and owners
        and all(isinstance(o, str) and o.startswith("@") for o in owners)
    ):
        fail(
            "manifest.json 'codeowners' must be a non-empty list of @handles: "
            f"{owners!r}"
        )
    ok(f"custom_components/{folder.name}/manifest.json is valid for HACS")

    # HACS `brands` check: a local brand/icon.png, else the domain must be in
    # the home-assistant/brands repo (which we can't check offline).
    if (folder / "brand" / "icon.png").is_file():
        ok(f"custom_components/{folder.name}/brand/icon.png present")
    else:
        fail(
            f"custom_components/{folder.name}/brand/icon.png is missing "
            "(needed for the HACS 'brands' check unless the domain is in "
            "home-assistant/brands)"
        )


def check_readme() -> None:
    for name in ("README.md", "README.MD", "readme.md"):
        path = ROOT / name
        if path.is_file():
            if len(path.read_text().strip()) < 200:
                fail(f"{name} is very short — add real documentation")
            else:
                ok(f"{name} present")
            return
    fail("no README.md in the repository root")


def main() -> int:
    check_hacs_json()
    check_integration()
    check_readme()

    for note in notes:
        print(f"  ok   {note}")
    for error in errors:
        print(f"  FAIL {error}")
    print()
    if errors:
        print(f"HACS offline checks failed ({len(errors)} problem(s))")
        return 1
    print("HACS offline checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
