#!/usr/bin/env bash
# Build the distributable plugin package: dist/plugin-vodfs-v<version>.zip
#
# The zip contains ONLY what an end user needs, under a top-level vodfs/ dir, so it
# unzips straight into Dispatcharr's plugins/ directory. It is built from `git archive`,
# so anything gitignored is excluded automatically — notably config.json (unrelated dev
# tooling that wrongly shipped in v0.42.0), CLAUDE.md, REPO_MAP.md, TODO.md, BACKLOG.md,
# TOKEN_BUDGET.md, .ai/, and docs/DEPLOYMENT-*.md (host-specific). We additionally drop
# the dev-only tests/ and scripts/ dirs and the repo .gitignore.
#
# Usage:  scripts/build-package.sh        (packages the committed HEAD)
# Output: dist/plugin-vodfs-v<version>.zip   (dist/ is gitignored)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

VERSION=$(python3 -c "import json;print(json.load(open('plugin.json'))['version'])")
OUT="$ROOT/dist"; mkdir -p "$OUT"
ZIP="$OUT/plugin-vodfs-v$VERSION.zip"; rm -f "$ZIP"
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT

# tracked files only (auto-excludes everything gitignored)
git archive HEAD --prefix=vodfs/ | tar -x -C "$STAGE"
# drop dev-only bits from the distributable
rm -rf "$STAGE/vodfs/tests" "$STAGE/vodfs/scripts" "$STAGE/vodfs/.gitignore"
find "$STAGE/vodfs" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
find "$STAGE/vodfs" \( -name '*.pyc' -o -name 'server.log' -o -name 'server.pid' \) -delete 2>/dev/null || true

if command -v zip >/dev/null 2>&1; then
  ( cd "$STAGE" && zip -rq "$ZIP" vodfs )
else
  # no zip binary (e.g. this host) — build with Python's zipfile
  python3 - "$STAGE" "$ZIP" <<'PY'
import sys, os, zipfile
stage, zippath = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zippath, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(os.path.join(stage, "vodfs")):
        for f in sorted(files):
            full = os.path.join(root, f)
            z.write(full, os.path.relpath(full, stage))
PY
fi

# verify the built package is sane before anyone ships it
V="$(mktemp -d)"; trap 'rm -rf "$STAGE" "$V"' EXIT
python3 - "$ZIP" "$V" <<'PY'
import sys, zipfile, json, os, py_compile
zippath, dest = sys.argv[1], sys.argv[2]
zipfile.ZipFile(zippath).extractall(dest)
root = os.path.join(dest, "vodfs")
json.load(open(os.path.join(root, "plugin.json")))            # valid manifest
for dp, _, fs in os.walk(root):
    for f in fs:
        if f.endswith(".py"):
            py_compile.compile(os.path.join(dp, f), doraise=True)  # all .py compile
assert os.path.exists(os.path.join(root, "logo.png"))
for leaked in ("config.json", "CLAUDE.md", "REPO_MAP.md", ".gitignore"):
    assert not os.path.exists(os.path.join(root, leaked)), f"leaked {leaked}"
print("package verified OK")
PY

echo "Built $ZIP"
