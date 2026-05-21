# Sprint 100 — Project Setup

**Status:** Active | **Risk:** LOW | **Depends:** none | **Target:** v0.1.0

## Why
Establish the project foundation with proper structure, documentation, and configuration. This sprint creates all necessary files and directories for development to begin.

## Non-Goals
- No implementation of core functionality
- No testing with Dispatcharr
- No GitHub repository creation (separate task)

## Tasks

### SETUP-01: Create GitHub repository
**Files:** N/A (external)
**Effort:** S
**What:** Create `OneHotTake/dispatcharr-vodfs` repository with MIT license and .gitignore

### SETUP-02: Create project directory structure
**Files:** .ai/, architecture/, docs/, tests/, scripts/, plugin/ (create)
**Effort:** S
**What:** Create all directories following InfiniteDrive patterns

### SETUP-03: Create project management files
**Files:** CLAUDE.md, BACKLOG.md, REPO_MAP.md, TOKEN_BUDGET.md, TODO.md (create)
**Effort:** M
**What:** Create steering documents with guardrails and task catalog

### SETUP-04: Create .ai directory templates
**Files:** .ai/CURRENT_TASK.md, .ai/SESSION_SUMMARY.md, .ai/SPRINT_TEMPLATE.md (create)
**Effort:** S
**What:** Create templates for task tracking and session management

### SETUP-05: Create plugin manifest
**Files:** plugin.json (create)
**Effort:** S
**What:** Create manifest with name, version, fields, and actions

### SETUP-06: Create basic plugin skeleton
**Files:** plugin.py, plugin/__init__.py (create)
**Effort:** M
**What:** Implement Plugin class with run/stop hooks and PID management

### SETUP-07: Create architecture documentation
**Files:** architecture/OVERVIEW.md, architecture/HTTPFS.md, architecture/HYDRATION.md (create)
**Effort:** M
**What:** Document system architecture, HTTP protocol, and hydration strategy

### SETUP-08: Create core implementation modules
**Files:** plugin/tree.py, plugin/httpfs.py, plugin/integration.py (create)
**Effort:** M
**What:** Implement virtual tree, HTTP handlers, and Dispatcharr integration

### SETUP-09: Create user documentation
**Files:** README.md, LICENSE, CHANGELOG.md (create)
**Effort:** S
**What:** Create user-facing documentation and license

### SETUP-10: Create development documentation
**Files:** docs/DEV_GUIDE.md, CONTRIBUTING.md, scripts/README.md (create)
**Effort:** S
**What:** Create development and contribution guides

### SETUP-11: Create test suite
**Files:** tests/__init__.py, tests/test_tree.py, tests/test_httpfs.py, tests/test_integration.py (create)
**Effort:** M
**What:** Create unit and integration tests

### SETUP-12: Commit and verify structure
**Files:** N/A
**Effort:** S
**What:** Commit initial structure, verify all files present

## Verification (run these or it fails)

- [ ] All 37 files created (verify with `find . -type f | wc -l`)
- [ ] `tree.py` has no syntax errors (`python -m py_compile plugin/tree.py`)
- [ ] `httpfs.py` has no syntax errors (`python -m py_compile plugin/httpfs.py`)
- [ ] `integration.py` has no syntax errors (`python -m py_compile plugin/integration.py`)
- [ ] `plugin.json` is valid JSON (`python -m json.tool plugin.json`)
- [ ] All project management files exist (CLAUDE.md, BACKLOG.md, etc.)
- [ ] Architecture docs complete (3 files)
- [ ] User docs complete (README.md, LICENSE)
- [ ] Tests can be imported (`python -m pytest tests/ --collect-only`)
- [ ] BACKLOG.md updated (Sprint 100 marked active)
- [ ] REPO_MAP.md updated
- [ ] Git commit created: `git init && git add . && git commit -m "chore: initial project structure"`

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated
- [ ] REPO_MAP.md updated
- [ ] Git commit created
- [ ] SESSION_SUMMARY.md updated