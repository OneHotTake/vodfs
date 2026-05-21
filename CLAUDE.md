# VOD HTTP Filesystem Plugin - Project Steering

## Core Rules

- Max 3 files per subtask unless explicitly expanded
- Read only CURRENT_TASK.md + REPO_MAP.md at session start
- Never re-read files in same session
- Max 200 lines per file read (use grep/line-range)
- All state in .ai/, never trust chat history
- Stop after first working solution (unless user requests iteration)

## Model Policy Table

| Task Type | Model | Reason |
|-----------|-------|--------|
| Grep/navigation/search | Haiku | Fast, cheap, context-light |
| Code generation | Sonnet | Good balance of quality/speed |
| Architecture decisions | Opus | High-stakes, multiple perspectives |
| Code review | Opus | Deep analysis required |

**Special Rules:**
- Opus banned unless explicitly requested by human
- Force Haiku-only if monthly spend > 70%
- Always prefer Sonnet for plugin implementation

## Output Rules

- No preambles ("I'll help you with..." or "Let me explore...")
- Diffs only, no full file dumps
- One-sentence summary on completion
- Update SESSION_SUMMARY.md before finishing
- Log tokens saved at sprint end

## Scope Ceiling

Every subtask must include this header in CURRENT_TASK.md:
```
SCOPE_CEILING: Max 3 files | Deliverable: diff only | Stop after first working solution
```

## Sprint Planning

1. Copy SPRINT_TEMPLATE.md to .ai/sprint-XXX.md
2. Fill only: Why, Tasks, Verification
3. Commit empty sprint file before code work
4. Execute tasks within scope ceiling

## Sprint Completion Ritual

1. Update REPO_MAP.md (max 20 lines, ultra-lean)
2. Update BACKLOG.md (mark complete, prioritize next)
3. `git add .ai/ && git commit -m "chore: end-of-sprint XXX"`
4. Push immediately - no accumulated work
5. Log tokens saved in SESSION_SUMMARY.md (one line)

## High-Risk Files (Require Human Review)

- `plugin/plugin.py` - Main entry point, child process management
- `plugin/httpfs.py` - Request handlers, streaming redirects
- `plugin/tree.py` - Virtual filesystem structure

## Plugin-Specific Rules

- Never expose Dispatcharr credentials in logs
- Bind child process HTTP server to 127.0.0.1 only
- Implement graceful shutdown in `stop()` hook
- Use Celery for heavy work, never block in `run()`
- Store PIDs persistently in /data/plugins/vodfs/
- Validate all input from params/context

## Design Document Adherence

- Strictly follow sibling `All` + category filesystem structure
- `/Movies` and `/Series` as top-level directories
- `All` is a direct sibling to category directories
- Return HTTP 302 redirects to Dispatcharr proxy URLs
- No WebDAV implementation
- No deduplication across providers
- Trigger hydration on empty Series directories

## Success Criteria

- rclone can mount the filesystem
- Plex can scan both `/Movies/All` and category directories
- Multiple streams appear as separate files
- Series browsing triggers episode hydration
- Playback works via 302 redirect
- Large libraries remain responsive

## Token Budget Enforcement

Every session MUST read and update TOKEN_BUDGET.md. If spend > 70%, force Haiku-only for all tasks.