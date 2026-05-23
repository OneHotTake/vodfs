# Repository Map

Root
- plugin.json                 : Plugin manifest (name, version, fields, actions)
- plugin.py                   : Main Plugin class (run/stop hooks, child process mgmt)
- plugin/__init__.py          : Package init
- plugin/tree.py              : Virtual filesystem tree (FSNode, building logic)
- plugin/httpfs.py            : HTTP handlers (GET/HEAD, directory listings, redirects)
- plugin/integration.py       : Dispatcharr integration (models, tasks, hydration)
- CLAUDE.md                   : AI steering rules
- BACKLOG.md                  : Technical debt backlog + sprint assignments
- REPO_MAP.md                 : This file (ultra-lean repo map)
- TOKEN_BUDGET.md             : Monthly token budget tracker
- TODO.md                     : Open items

.ai/
- CURRENT_TASK.md             : Active task (read first each session)
- SESSION_SUMMARY.md          : Token ledger
- SPRINT_TEMPLATE.md          : Sprint template

architecture/
- OVERVIEW.md                 : System overview
- HTTPFS.md                   : HTTP filesystem design
- HYDRATION.md                : Hydration strategy

docs/
- README.md                   : Main documentation
- ARCHITECTURE.md             : Architecture docs
- CONTRIBUTING.md             : Contribution guide

tests/
- test_tree.py                : Tree tests
- test_httpfs.py              : HTTP handler tests
- test_integration.py         : Integration tests

scripts/
- start-dispatcharr.sh        : Start Dispatcharr for testing
- install-plugin.sh           : Install plugin into Dispatcharr