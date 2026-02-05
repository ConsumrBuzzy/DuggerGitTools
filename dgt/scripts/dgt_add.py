"""Unified CLI tool for DGT Input Bridge.

Usage:
  dgt-add todo DEVOPS "Fix the venv bug"
  dgt-add todo "Remember to test this"
  dgt-add plan "C:/Downloads/new_adr.md"
  dgt-add scan  # Run TODO extraction
  
Provides zero-friction knowledge capture from command line.
"""

import sys
from pathlib import Path


def main():
    """Main entry point for dgt-add CLI."""
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "todo":
        from dgt.scripts.todo import quick_todo
        # Remove 'todo' from args
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        quick_todo()
    
    elif command == "plan":
        from dgt.scripts.phase import drop_plan
        # Remove 'plan' from args
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        drop_plan()
    
    elif command == "scan":
        from dgt.core.task_extractor import TaskExtractor
        
        # Find project root
        current = Path.cwd()
        project_root = None
        
        for parent in [current] + list(current.parents):
            if (parent / "dugger.yaml").exists():
                project_root = parent
                break
        
        if project_root is None:
            project_root = current
        
        print("🔍 Scanning project for TODO/FIXME/NOTE annotations...")
        extractor = TaskExtractor(project_root)
        report_path = extractor.generate_report_file()
        print(f"✅ Generated: {report_path}")
    
    elif command in ["help", "-h", "--help"]:
        print_help()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_help()


def print_help():
    """Print help message."""
    help_text = """
DGT Input Bridge - Zero-friction knowledge capture

Usage:
  dgt-add todo [PHASE] "Note text"     Log a quick TODO
  dgt-add plan "path/to/file.md"       Ingest a planning document
  dgt-add scan                         Run TODO extraction

Examples:
  dgt-add todo DEVOPS "Fix venv creation bug"
  dgt-add todo "Remember to test authorization"
  dgt-add plan "C:/Downloads/ADR-004.md"
  dgt-add scan

Notes:
  - TODOs are appended to TODO.md in TaskExtractor format
  - Plans are copied to PLANNING/inbox/ for AI agent processing
  - Scan generates TODO_REPORT.md from all code annotations
"""
    print(help_text)


if __name__ == "__main__":
    main()
