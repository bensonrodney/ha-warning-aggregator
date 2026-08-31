#!/usr/bin/env bash
# Cut a release: bump the version, commit, tag `vX.Y.Z`, push to every remote.
# CI (ci.yml `release` job) then builds the zip and publishes the release.
#
#   scripts/release.sh [patch|minor|major]     (default: patch)
#   scripts/release.sh --set 1.4.0
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

arg="${1:-patch}"

if [ -n "$(git status --porcelain)" ]; then
    echo "working tree is not clean — commit or stash first" >&2
    exit 1
fi
if [ "$(git branch --show-current)" != "main" ]; then
    echo "not on main" >&2
    exit 1
fi
git fetch --quiet --tags --all || true

case "$arg" in
    --set) new="$(python3 scripts/bump_version.py --set "${2:?version required}" --write)" ;;
    patch | minor | major) new="$(python3 scripts/bump_version.py "$arg" --write)" ;;
    *) echo "usage: release.sh [patch|minor|major] | --set X.Y.Z" >&2; exit 1 ;;
esac

tag="v${new}"
echo ">> releasing ${tag}"

git commit -aqm "Release ${tag}"
git tag -a "${tag}" -m "${tag}"

for remote in $(git remote); do
    echo ">> push ${remote}"
    git push --quiet "${remote}" main --follow-tags
done

echo ">> done — watch CI build the release for ${tag}"
