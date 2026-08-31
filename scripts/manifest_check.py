#!/usr/bin/env python3
"""hassfest-style manifest checks that need no Home Assistant source tree.

The real hassfest (``home-assistant/actions/hassfest``) is a Docker action that
mounts ``${{ github.workspace }}`` — a path that exists only on a VM runner, not
inside a Gitea container job — so it just reports "No integrations found!" here.
This covers the manifest / config-flow / translations rules that matter for a
custom integration. The real hassfest still runs on GitHub
(``.github/workflows/validate.yml``).
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "warning_aggregator"
MANIFEST = COMPONENT / "manifest.json"

IOT_CLASSES = {
    "assumed_state",
    "calculated",
    "cloud_polling",
    "cloud_push",
    "local_polling",
    "local_push",
}
INTEGRATION_TYPES = {
    "device",
    "entity",
    "hardware",
    "helper",
    "hub",
    "service",
    "system",
    "virtual",
}
LIST_OF_STR_KEYS = (
    "codeowners",
    "dependencies",
    "after_dependencies",
    "requirements",
    "loggers",
)

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def _sort_key(key: str) -> str:
    # hassfest: 'domain' then 'name' first, then the rest alphabetically.
    return {"domain": ".domain", "name": ".name"}.get(key, key)


def check() -> None:
    if not MANIFEST.is_file():
        err(f"{MANIFEST.relative_to(ROOT)} is missing")
        return
    try:
        manifest = json.loads(MANIFEST.read_text())
    except json.JSONDecodeError as exc:
        err(f"manifest.json is not valid JSON: {exc}")
        return

    for key in ("domain", "name", "codeowners", "version", "documentation"):
        if not manifest.get(key):
            err(f"manifest.json is missing the required key '{key}'")

    if manifest.get("domain") != COMPONENT.name:
        err(
            f"manifest 'domain' ({manifest.get('domain')!r}) must match the folder "
            f"name ({COMPONENT.name!r})"
        )

    keys = list(manifest)
    if sorted(keys, key=_sort_key) != keys:
        want = ", ".join(sorted(keys, key=_sort_key))
        err(f"manifest.json keys are not sorted (expected: {want})")

    doc = manifest.get("documentation", "")
    if doc and not doc.startswith("https://"):
        err(f"manifest 'documentation' must be an https URL: {doc!r}")
    tracker = manifest.get("issue_tracker", "")
    if tracker and not re.match(r"^https?://", tracker):
        err(f"manifest 'issue_tracker' must be a URL: {tracker!r}")

    owners = manifest.get("codeowners")
    if owners is not None and not (
        isinstance(owners, list)
        and all(isinstance(o, str) and o.startswith("@") for o in owners)
    ):
        err(f"manifest 'codeowners' must be a list of @handles: {owners!r}")

    iot_class = manifest.get("iot_class")
    if iot_class is None:
        err("manifest is missing 'iot_class'")
    elif iot_class not in IOT_CLASSES:
        err(f"manifest 'iot_class' is not one of {sorted(IOT_CLASSES)}: {iot_class!r}")

    itype = manifest.get("integration_type")
    if itype is not None and itype not in INTEGRATION_TYPES:
        err(f"manifest 'integration_type' is not valid: {itype!r}")

    for key in LIST_OF_STR_KEYS:
        value = manifest.get(key)
        if value is not None and not (
            isinstance(value, list) and all(isinstance(x, str) for x in value)
        ):
            err(f"manifest '{key}' must be a list of strings: {value!r}")

    version = manifest.get("version")
    if version is not None and not re.match(r"^\d[\w.+-]*$", str(version)):
        err(f"manifest 'version' is not a valid version: {version!r}")

    if manifest.get("config_flow"):
        if not (COMPONENT / "config_flow.py").is_file():
            err("manifest sets config_flow: true but config_flow.py is missing")
        strings = COMPONENT / "strings.json"
        if not strings.is_file():
            err("config_flow: true but strings.json is missing")
        else:
            try:
                if "config" not in json.loads(strings.read_text()):
                    err("strings.json has no 'config' section for the config flow")
            except json.JSONDecodeError as exc:
                err(f"strings.json is not valid JSON: {exc}")

    strings = COMPONENT / "strings.json"
    english = COMPONENT / "translations" / "en.json"
    if strings.is_file() and english.is_file():
        try:
            if json.loads(strings.read_text()) != json.loads(english.read_text()):
                err("translations/en.json is out of sync with strings.json")
        except json.JSONDecodeError:
            pass  # bad JSON is reported below

    for path in sorted(COMPONENT.rglob("*.json")):
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            err(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")


def main() -> int:
    check()
    for problem in errors:
        print(f"  FAIL {problem}")
    if errors:
        print(f"\nmanifest checks failed ({len(errors)} problem(s))")
        return 1
    print("manifest checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
