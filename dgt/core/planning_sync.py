"""Planning Sync - Filesystem-based sprint tracking.

NO AI. Just git log + file appending.
Auto-updates CURRENT_SPRINT.md with last 5 commits for "Living History".
"""

import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from loguru import logger


class PlanningSyncManager:
    """Filesystem-based planning synchronization.
    
    Maintains PLANNING/ directory with CURRENT_SPRINT.md auto-updates.
    Uses git log to create "Living History" of progress.
    """
    
    def __init__(self, project_root: Path):
        """Initialize PlanningSyncManager.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.planning_dir = project_root / "PLANNING"
        self.sprint_file = self.planning_dir / "CURRENT_SPRINT.md"
        self.logger = logger.bind(component="PlanningSyncManager")
    
    def ensure_planning_directory(self) -> bool:
        """Ensure PLANNING/ directory exists.
        
        Returns:
            True if directory exists or was created, False on error
        """
        try:
            self.planning_dir.mkdir(exist_ok=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to create PLANNING directory: {e}")
            return False
    
    def get_last_n_commits(self, n: int = 5) -> List[str]:
        """Get last N commit messages from git log.
        
        Args:
            n: Number of commits to retrieve
            
        Returns:
            List of commit messages
        """
        try:
            result = subprocess.run(
                ["git", "log", f"-{n}", "--pretty=format:%h - %s (%ar)"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            commits = result.stdout.strip().splitlines()
            return commits
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Failed to get git log: {e}")
            return []
    
    def update_current_sprint(self, commits: Optional[List[str]] = None) -> bool:
        """Update CURRENT_SPRINT.md with recent commits.
        
        Args:
            commits: Optional list of commit messages (uses git log if not provided)
            
        Returns:
            True if update succeeded, False otherwise
        """
        if not self.ensure_planning_directory():
            return False
        
        # Get commits if not provided
        if commits is None:
            commits = self.get_last_n_commits(5)
        
        if not commits:
            self.logger.info("No commits to append to sprint log")
            return True
        
        try:
            # Create or append to sprint file
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Read existing content if file exists
            existing_content = ""
            if self.sprint_file.exists():
                with self.sprint_file.open('r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # Build update section
            update_lines = [
                "",
                "---",
                "",
                f"## Update: {timestamp}",
                "",
                "### Recent Commits",
                ""
            ]
            for commit in commits:
                update_lines.append(f"- {commit}")
            update_lines.append("")
            
            update_section = "\n".join(update_lines)
            
            # Append to file
            with self.sprint_file.open('w', encoding='utf-8') as f:
                f.write(existing_content)
                f.write(update_section)
            
            self.logger.info(f"Updated {self.sprint_file} with {len(commits)} commits")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to update CURRENT_SPRINT.md: {e}")
            return False
    
    def create_snapshot(self) -> Optional[Path]:
        """Create timestamped snapshot of current sprint file.
        
        Returns:
            Path to snapshot file if created, None otherwise
        """
        if not self.sprint_file.exists():
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_path = self.planning_dir / f"sprint_snapshot_{timestamp}.md"
            
            # Copy current sprint to snapshot
            with self.sprint_file.open('r', encoding='utf-8') as src:
                content = src.read()
            
            with snapshot_path.open('w', encoding='utf-8') as dst:
                dst.write(content)
            
            self.logger.info(f"Created sprint snapshot: {snapshot_path}")
            return snapshot_path
        
        except Exception as e:
            self.logger.error(f"Failed to create snapshot: {e}")
            return None
