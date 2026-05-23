# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and documentation
- Plugin manifest (plugin.json) with configuration UI
- Basic Plugin class skeleton with run/stop hooks
- Virtual filesystem tree implementation (tree.py)
- HTTP request handlers (httpfs.py)
- Dispatcharr integration layer (integration.py)
- Project management infrastructure (CLAUDE.md, BACKLOG.md, etc.)
- Architecture documentation (OVERVIEW.md, HTTPFS.md, HYDRATION.md)
- User documentation (README.md, DEV_GUIDE.md, CONTRIBUTING.md)

### Planned
- Child HTTP process implementation (FastAPI server)
- Tree building logic for Movies (All + categories)
- Tree building logic for Series (All + categories)
- Episode hydration implementation
- Testing suite
- rclone integration examples

## [0.1.0] - 2026-05-21

### Added
- Initial release
- Project setup and structure
- Documentation framework