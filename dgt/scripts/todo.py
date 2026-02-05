"""Quick TODO brain-dump script.

Usage:
  python -m dgt.scripts.todo DEVOPS "Fix venv creation bug"
  python -m dgt.scripts.todo "Remember to test this"
  
Appends to TODO.md in format TaskExtractor can parse.
"""

import datetime
import sys
from pathlib import Path


def quick_todo():
    """Log a quick TODO to TODO.md.
    
    Usage:
        python -m dgt.scripts.todo [PHASE] "Note text"
        
    Examples:
        python -m dgt.scripts.todo DEVOPS "Fix the venv bug"
        python -m dgt.scripts.todo "Review authorization logic"
    """
    args = sys.argv[1:]

    if not args:
        print('Usage: python -m dgt.scripts.todo [PHASE] "Note text"')
        print('Example: python -m dgt.scripts.todo DEVOPS "Fix venv creation"')
        return

    # Determine phase and note
    if len(args) > 1:
        phase = args[0].upper()
        note = args[1]
    else:
        phase = "GENERAL"
        note = args[0]

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Format in TaskExtractor-compatible format
    entry = f"\n# TODO: [{phase}] {note} (Logged: {timestamp})\n"

    # Find project root (look for dugger.yaml)
    current = Path.cwd()
    project_root = None

    for parent in [current] + list(current.parents):
        if (parent / "dugger.yaml").exists():
            project_root = parent
            break

    if project_root is None:
        project_root = current

    todo_file = project_root / "TODO.md"

    # Append to TODO.md
    with todo_file.open("a", encoding="utf-8") as f:
        f.write(entry)

    print(f"✅ Logged to {todo_file}")
    print(f"   [{phase}] {note}")


if __name__ == "__main__":
    quick_todo()
