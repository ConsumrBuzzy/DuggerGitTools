# Agent Protocol: The Living Roadmap

This document defines how AI agents (like Claude via Antigravity) should interact with DGT's deterministic tools to maintain project context and momentum.

## Initialization Protocol

On every session start, the agent should:

1. **Run TODO Extraction**
   ```bash
   python -m dgt.core.task_extractor
   ```
   This generates `TODO_REPORT.md` from all code annotations.

2. **Read TODO_REPORT.md**
   This is the user's "Brain Dump" and current priority list. Use it as primary context for what needs attention.

3. **Check PLANNING/inbox/**
   Look for new ADRs, phase plans, or design documents. If found:
   - Review and integrate into `ROADMAP.md`
   - Move processed files to `PLANNING/archive/`
   - Create timestamped snapshots for reference

## Active Work Protocol

1. **Task Completion**
   When you complete a task that had a `# TODO:` comment:
   - Remove the comment from the source code
   - Next `dgt-add scan` will automatically update `TODO_REPORT.md`

2. **New Tasks Discovered**
   When you identify new work during implementation:
   - Add inline `# TODO:` comments in code
   - OR: Log to `TODO.md` via `dgt-add todo`

3. **Sprint Updates**
   After significant commits:
   - Run `PlanningSyncManager.update_current_sprint()`
   - This appends recent commits to `CURRENT_SPRINT.md`

## Quick Reference Commands

### User Brain-Dump
```bash
# Log a quick TODO
dgt-add todo DEVOPS "Fix venv detection on Windows"
dgt-add todo "Remember to test PyO3 bindings"

# Ingest a planning document
dgt-add plan "C:/Downloads/ADR-004.md"

# Scan for TODOs
dgt-add scan
```

### Agent Operations
```python
# Generate TODO report
from dgt.core.task_extractor import TaskExtractor
extractor = TaskExtractor(project_root)
extractor.generate_report_file()

# Update sprint log
from dgt.core.planning_sync import PlanningSyncManager
planner = PlanningSyncManager(project_root)
planner.update_current_sprint()

# Inject docstring templates
from dgt.core.templater import DocstringTemplater
templater = DocstringTemplater(project_root)
templater.inject_template_in_file(file_path, dry_run=False)
```

## File Organization

```
project_root/
  TODO.md                    # User brain-dumps (append-only)
  TODO_REPORT.md            # Auto-generated from code annotations
  ROADMAP.md                # High-level project plan
  
  PLANNING/
    inbox/                  # New plans awaiting processing
    archive/                # Processed plans
    CURRENT_SPRINT.md       # Auto-updated with commits
    sprint_snapshot_*.md    # Timestamped backups
  
  builds/
    v1.0.0/                # Version-stamped artifacts
    v1.0.1/
```

## Philosophy

- **Deterministic**: No AI inference—tools use regex, AST, git log
- **Fast**: All operations are instant
- **Offline**: No API keys required
- **Zero Friction**: Command-line shortcuts for instant capture
- **Self-Documenting**: Codebase is the single source of truth

## Best Practices

1. **Always scan on initialization** to get current TODO state
2. **Check inbox regularly** for new planning documents
3. **Clean completed TODOs** from code when tasks finish
4. **Update sprint log** after significant work
5. **Organize artifacts** by version (builds/v{version}/)

---

**Result**: The agent stays synchronized with the user's brain-dumps, the codebase's annotations, and the project's evolving plan—all through deterministic filesystem operations.
