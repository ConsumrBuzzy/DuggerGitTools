"""Plan ingestion script.

Usage:
  python -m dgt.scripts.phase "C:/Downloads/new_plan.md"
  
Copies planning documents into PLANNING/inbox/ for AI agent processing.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime


def drop_plan():
    """Drop a planning document into PLANNING/inbox/.
    
    Usage:
        python -m dgt.scripts.phase "path/to/plan.md"
    """
    if len(sys.argv) < 2:
        print("Usage: python -m dgt.scripts.phase \"path/to/plan.md\"")
        return
    
    source = Path(sys.argv[1])
    
    if not source.exists():
        print(f"❌ File not found: {source}")
        return
    
    # Find project root
    current = Path.cwd()
    project_root = None
    
    for parent in [current] + list(current.parents):
        if (parent / "dugger.yaml").exists():
            project_root = parent
            break
    
    if project_root is None:
        project_root = current
    
    # Create inbox directory
    inbox_dir = project_root / "PLANNING" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy file with timestamp prefix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_name = f"{timestamp}_{source.name}"
    dest = inbox_dir / dest_name
    
    shutil.copy2(source, dest)
    
    print(f"📂 Plan dropped into inbox:")
    print(f"   {dest}")
    print(f"\n💡 Agent will process this on next initialization")


if __name__ == "__main__":
    drop_plan()
