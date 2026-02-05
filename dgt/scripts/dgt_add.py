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
    
    elif command == "assimilate":
        from dgt.core.assimilator import AssimilatorEngine
        
        # Get target directory (default to current)
        if len(sys.argv) > 2:
            target_dir = Path(sys.argv[2])
        else:
            target_dir = Path.cwd()
        
        if not target_dir.exists():
            print(f"❌ Directory not found: {target_dir}")
            return
        
        print(f"🔧 Assimilating project: {target_dir.name}")
        print("   [Non-destructive chassis graft in progress...]")
        
        # Run dry-run first if requested
        dry_run = "--dry-run" in sys.argv
        
        engine = AssimilatorEngine(target_dir, dry_run=dry_run)
        result = engine.assimilate()
        
        # Display results
        print(f"\n📊 Assimilation {'Simulation' if dry_run else 'Complete'}")
        print(f"   Project Type: {result.project_type}")
        print(f"   Success: {'✅' if result.success else '❌'}")
        
        if result.changes_made:
            print(f"\n✅ Changes Made ({len(result.changes_made)}):")
            for change in result.changes_made:
                print(f"   - {change}")
        
        if result.warnings:
            print(f"\n⚠️  Warnings ({len(result.warnings)}):")
            for warning in result.warnings:
                print(f"   - {warning}")
        
        if result.errors:
            print(f"\n❌ Errors ({len(result.errors)}):")
            for error in result.errors:
                print(f"   - {error}")
        
        if dry_run:
            print("\n💡 This was a dry-run. Re-run without --dry-run to apply changes.")
    
    elif command == "audit":
        from dgt.core.audit_manager import AuditManager
        from dgt.core.schema import SchemaLoader
        from dgt.core.config import DGTConfig
        
        # Get target directory (default to current)
        if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
            target_dir = Path(sys.argv[2])
        else:
            target_dir = Path.cwd()
        
        if not target_dir.exists():
            print(f"❌ Directory not found: {target_dir}")
            return
        
        print(f"🔍 Running Beast Mode Audit: {target_dir.name}")
        print("   [Secret Sentry + Rot-Detector + Vulture scanning...]")
        print()
        
        # Detect project type
        try:
            config = DGTConfig.from_project_root(target_dir)
            schema_loader = SchemaLoader(config)
            schema = schema_loader.load_schema()
            project_type = schema.project_type.value
        except:
            project_type = "python"  # Default
        
        # Run audit
        auditor = AuditManager(target_dir)
        report = auditor.run_full_audit(project_type)
        
        # Display summary
        print(f"📊 Audit Complete")
        print(f"   Project: {report.project_name}")
        print(f"   Risk Score: {report.risk_score}/100")
        print()
        
        # Risk level
        if report.risk_score >= 70:
            print("🔴 CRITICAL RISK - Immediate action required!")
        elif report.risk_score >= 30:
            print("🟡 MODERATE RISK - Review and address issues")
        else:
            print("🟢 LOW RISK - Project is relatively healthy")
        print()
        
        # Findings summary
        if report.secrets:
            print(f"🔐 Secrets Found: {len(report.secrets)} (CRITICAL!)")
        if report.vulnerabilities:
            high = [v for v in report.vulnerabilities if v.severity in ["high", "critical"]]
            print(f"🛡️  Vulnerabilities: {len(report.vulnerabilities)} ({len(high)} high/critical)")
        if report.dead_code:
            print(f"🧹 Dead Code: {len(report.dead_code)} items")
        
        print()
        
        # Save report
        report_path = auditor.save_report(report)
        print(f"✅ Full report saved: {report_path}")
        
        # Warnings
        if report.warnings:
            print(f"\n⚠️  Warnings ({len(report.warnings)}):")
            for warning in report.warnings:
                print(f"   - {warning}")
    
    elif command in ["help", "-h", "--help"]:
        print_help()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_help()


def print_help():
    """Print help message."""
    help_text = """
DGT Input Bridge - Zero-friction knowledge capture & project assimilation

Usage:
  dgt-add todo [PHASE] "Note text"     Log a quick TODO
  dgt-add plan "path/to/file.md"       Ingest a planning document
  dgt-add scan                         Run TODO extraction
  dgt-add assimilate [path]            Assimilate project into DGT chassis
  dgt-add audit [path]                 Run Beast Mode security audit

Examples:
  dgt-add todo DEVOPS "Fix venv creation bug"
  dgt-add todo "Remember to test authorization"
  dgt-add plan "C:/Downloads/ADR-004.md"
  dgt-add scan
  dgt-add assimilate                   # Assimilate current directory
  dgt-add assimilate C:/Projects/Legacy --dry-run
  dgt-add audit                        # Audit current directory
  dgt-add audit C:/Projects/Legacy     # Audit specific project

Notes:
  - TODOs are appended to TODO.md in TaskExtractor format
  - Plans are copied to PLANNING/inbox/ for AI agent processing
  - Scan generates TODO_REPORT.md from all code annotations
  - Assimilate injects DGT chassis (dugger.yaml, .gitignore, PLANNING/)
  - Audit runs Secret Sentry + Rot-Detector + Vulture (creates AUDIT_REPORT.md)
"""
    print(help_text)


if __name__ == "__main__":
    main()
