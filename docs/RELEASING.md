# Releasing VODFS

How to cut a versioned release and publish the downloadable plugin package. This is
the exact process used for v0.42.1.

## TL;DR

```bash
# 1. bump version in plugin.json ("version": "X.Y.Z")
# 2. roll CHANGELOG.md: rename "## [Unreleased]" -> "## [X.Y.Z] — YYYY-MM-DD",
#    add a fresh empty "## [Unreleased]" above it
git add plugin.json CHANGELOG.md && git commit -m "chore(release): vX.Y.Z"
git tag -a vX.Y.Z -m "VODFS vX.Y.Z"
git push origin master && git push origin vX.Y.Z

scripts/build-package.sh                       # -> dist/plugin-vodfs-vX.Y.Z.zip (self-verifies)
gh release create vX.Y.Z dist/plugin-vodfs-vX.Y.Z.zip \
  --title "VODFS vX.Y.Z" --notes-file <notes.md>
```

## What goes in the package

`scripts/build-package.sh` builds `dist/plugin-vodfs-vX.Y.Z.zip` from `git archive HEAD`,
so the contents are exactly the **tracked** files, under a top-level `vodfs/` dir (unzips
straight into Dispatcharr's `plugins/`). The script additionally drops the dev-only
`tests/` and `scripts/` dirs and the repo `.gitignore`, then **self-verifies** (manifest
parses, every `.py` compiles, `logo.png` present, no leaked files).

Included: `plugin.json`, `plugin.py`, `logo.png`, `LICENSE`, `README.md`, `CHANGELOG.md`,
`CONTRIBUTING.md`, all of `plugin/*.py`, `docs/*.md` (+ `docs/assets/logo.svg`), and
`tools/`.

**Deliberately excluded** (all gitignored, so `git archive` skips them automatically):
- `config.json` — unrelated AI dev tooling. ⚠️ It wrongly shipped in **v0.42.0**; the
  git-archive approach is what keeps it out now. Never hand-add files to the zip.
- `CLAUDE.md`, `REPO_MAP.md`, `TODO.md`, `BACKLOG.md`, `TOKEN_BUDGET.md`, `.ai/` — local steering/scratch.
- `docs/DEPLOYMENT-*.md` — host-specific (IPs, paths, access). Never publish.

Note: this host has no `zip` binary, so the script falls back to Python's `zipfile`.

## Versioning

Semantic versioning. The version lives in `plugin.json` (`"version"`) and is the source of
truth — the package filename and the `plugin.json` inside the zip both derive from it.
Patch (`0.42.0 → 0.42.1`) for fixes/polish; minor for features; keep the git tag
(`vX.Y.Z`) and the manifest version in lockstep.

## Deploying a release to a live Dispatcharr box

Publishing the GitHub release does **not** update a running install. To deploy, copy the
plugin files into the box's plugins dir, clear `__pycache__`, reload, and re-enable —
`plugin.py` is cached in memory and only swaps on a fresh enable. Full procedure and the
prod specifics are in `docs/DEPLOYMENT-vault-home.md` (gitignored, on the box).

## Release-notes template

```markdown
Patch release on top of vA.B.C.

### Highlights
- ...

### Install
Download `plugin-vodfs-vX.Y.Z.zip` and install via Dispatcharr's plugin manager, or
unzip the `vodfs/` folder into your Dispatcharr `plugins/` directory. See `docs/INSTALL.md`.

Full changelog: `CHANGELOG.md` (section X.Y.Z).
```
