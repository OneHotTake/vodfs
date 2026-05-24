# Contributing

VODFS is a small plugin. The contribution loop is small to match.

## Before You Start

- Read [`architecture/OVERVIEW.md`](architecture/OVERVIEW.md) and [`architecture/HTTPFS.md`](architecture/HTTPFS.md). The plugin's design is deliberately constrained — no manifest, no media proxying, no background workers — and PRs that reintroduce any of those will probably get pushed back.
- Open an issue first for anything larger than a bug fix or a small ergonomic change, so we can agree on the shape before you spend time on it.

## Development Loop

1. Fork, branch, code.
2. Install the plugin into your local Dispatcharr (`cp -r . /data/plugins/vodfs/`), enable it from the UI, and exercise the change end-to-end. The `curl` recipes in [`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md) cover the basics.
3. `python -m pytest tests/` should still pass. Add tests for anything non-trivial.
4. Update docs in the same PR if behavior changes.

## Commit Style

Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. Subject line under ~70 chars. Use the body for the why; the diff already covers the what.

## What I'll Look For in Review

- Does it stay within the design? Live ORM queries, `302` redirects out, no second source of truth.
- Are Django ORM calls being made from async code without going through the executor in `httpfs.py`? That's a deadlock waiting to happen.
- Are credentials being logged anywhere?
- Is the change small enough to actually review? Splitting a refactor and a feature into separate PRs is almost always the right call.

## Reporting Bugs

Include the Dispatcharr version, plugin version, the URL or rclone operation that misbehaved, the relevant lines from `/data/plugins/vodfs/server.log`, and `curl -I` output for the failing URL if applicable. The [troubleshooting guide](docs/TROUBLESHOOTING.md) covers the common cases first.

## License

By contributing you agree your changes are licensed under the project's MIT license.
