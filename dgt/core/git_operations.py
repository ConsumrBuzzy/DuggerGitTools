"""Enhanced Git operations with patterns from all analyzed projects."""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from .config import DGTConfig


class GitOperations:
    """Advanced Git operations wrapper with comprehensive functionality."""
    
    def __init__(self, config: DGTConfig) -> None:
        """Initialize Git operations with configuration."""
        self.config = config
        self.logger = logger.bind(git_ops=True)
        self.repo_path = config.project_root
    
    def get_status(self) -> str:
        """Get git status in porcelain format."""
        try:
            result = self._run_command(["status", "--porcelain"])
            return result.stdout.strip() if result.stdout.strip() else ""
        except Exception as e:
            self.logger.error(f"Failed to get git status: {e}")
            return ""
    
    def get_current_branch(self) -> str:
        """Get current branch name."""
        try:
            result = self._run_command(["rev-parse", "--abbrev-ref", "HEAD"])
            return result.stdout.strip()
        except Exception as e:
            self.logger.error(f"Failed to get current branch: {e}")
            return "unknown"
    
    def stage_all(self) -> bool:
        """Stage all changes in the repository."""
        try:
            result = self._run_command(["add", "."])
            success = result.returncode == 0
            if success:
                self.logger.info("All changes staged")
            else:
                self.logger.error("Failed to stage changes")
            return success
        except Exception as e:
            self.logger.error(f"Failed to stage changes: {e}")
            return False
    
    def stage_files(self, files: List[str]) -> bool:
        """Stage specific files."""
        try:
            result = self._run_command(["add"] + files)
            success = result.returncode == 0
            if success:
                self.logger.info(f"Staged {len(files)} files")
            else:
                self.logger.error("Failed to stage files")
            return success
        except Exception as e:
            self.logger.error(f"Failed to stage files: {e}")
            return False
    
    def commit(self, message: str, no_verify: bool = False, amend: bool = False) -> bool:
        """Create a commit with the given message."""
        try:
            cmd = ["commit"]
            if amend:
                cmd.extend(["--amend", "--no-edit"])
            else:
                cmd.extend(["-m", message])
            
            if no_verify:
                cmd.append("--no-verify")
            
            result = self._run_command(cmd)
            success = result.returncode == 0
            
            if success:
                self.logger.info(f"Commit created: {message[:50]}...")
            else:
                self.logger.error(f"Commit failed: {result.stderr}")
            
            return success
        except Exception as e:
            self.logger.error(f"Failed to create commit: {e}")
            return False
    
    def pull(self, branch: str, remote: str = "origin") -> bool:
        """Pull latest changes from remote."""
        try:
            result = self._run_command(["pull", remote, branch])
            success = result.returncode == 0
            
            if success:
                self.logger.info(f"Pulled from {remote}/{branch}")
            else:
                self.logger.warning(f"Pull from {remote}/{branch} had issues")
            
            return success
        except Exception as e:
            self.logger.error(f"Failed to pull from {remote}/{branch}: {e}")
            return False
    
    def push(self, branch: str, remote: str = "origin") -> bool:
        """Push changes to remote."""
        try:
            result = self._run_command(["push", remote, branch])
            success = result.returncode == 0
            
            if success:
                self.logger.info(f"Pushed to {remote}/{branch}")
            else:
                self.logger.error(f"Push to {remote}/{branch} failed")
            
            return success
        except Exception as e:
            self.logger.error(f"Failed to push to {remote}/{branch}: {e}")
            return False
    
    def get_changed_files(self, staged: bool = True) -> List[str]:
        """Get list of changed files."""
        try:
            if staged:
                result = self._run_command(["diff", "--cached", "--name-only"])
            else:
                result = self._run_command(["diff", "--name-only"])
            
            if result.stdout.strip():
                return [f.strip() for f in result.stdout.splitlines() if f.strip()]
            
            # Fallback to unstaged if no staged changes
            if staged:
                return self.get_changed_files(staged=False)
            
            return []
        except Exception as e:
            self.logger.error(f"Failed to get changed files: {e}")
            return []
    
    def get_diff_summary(self) -> str:
        """Get summary of changes for commit message generation."""
        try:
            result = self._run_command(["diff", "--cached", "--stat"])
            return result.stdout.strip()
        except Exception as e:
            self.logger.error(f"Failed to get diff summary: {e}")
            return ""
    
    def get_diff_stat(self) -> Dict[str, int]:
        """Get diff statistics (lines added/removed).
        
        Returns:
            Dict with 'lines_added' and 'lines_removed'
        """
        try:
            result = self._run_command(["diff", "--cached", "--numstat"])
            
            lines_added = 0
            lines_removed = 0
            
            for line in result.stdout.splitlines():
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            added = int(parts[0])
                            removed = int(parts[1])
                            lines_added += added
                            lines_removed += removed
                        except ValueError:
                            # Skip binary files (marked with '-')
                            continue
            
            return {
                "lines_added": lines_added,
                "lines_removed": lines_removed
            }
        except Exception as e:
            self.logger.error(f"Failed to get diff stat: {e}")
            return {"lines_added": 0, "lines_removed": 0}
    
    def get_changed_line_numbers(self) -> Dict[str, str]:
        """
        Extract line numbers for changed files from git diff.
        
        Returns:
            dict: Mapping of filename to line range string (e.g., "L10-15,L20-25")
        """
        try:
            # Try cached first (if already staged), then unstaged
            diff_result = self._run_command(["diff", "--cached", "--unified=0"], check=False)
            
            # If cached diff is empty, get unstaged diff
            if not diff_result.stdout.strip():
                diff_result = self._run_command(["diff", "--unified=0"], check=False)
            
            # If still empty, try HEAD diff (for new files)
            if not diff_result.stdout.strip():
                diff_result = self._run_command(["diff", "HEAD", "--unified=0"], check=False)
            
            line_ranges: Dict[str, List[str]] = {}
            current_file: Optional[str] = None
            
            for line in diff_result.stdout.split("\n"):
                # Match file headers: +++ b/path/to/file.py
                if line.startswith("+++ b/"):
                    current_file = line[6:]  # Remove "+++ b/"
                    line_ranges[current_file] = []
                
                # Match hunk headers: @@ -10,5 +10,7 @@
                elif line.startswith("@@") and current_file:
                    import re
                    match = re.search(r"\+(\d+)(?:,(\d+))?", line)
                    if match:
                        start_line = int(match.group(1))
                        line_count = int(match.group(2)) if match.group(2) else 1
                        
                        if line_count > 0:
                            if line_count == 1:
                                line_ranges[current_file].append(f"L{start_line}")
                            else:
                                end_line = start_line + line_count - 1
                                line_ranges[current_file].append(f"L{start_line}-{end_line}")
            
            # Format ranges as comma-separated strings
            formatted_ranges: Dict[str, str] = {}
            for file, ranges in line_ranges.items():
                if ranges:
                    formatted_ranges[file] = ",".join(ranges)
            
            return formatted_ranges
            
        except Exception as e:
            self.logger.error(f"Failed to get changed line numbers: {e}")
            return {}
    
    def get_commit_count(self) -> int:
        """Get total commit count (Convoso pattern)."""
        try:
            result = self._run_command(["rev-list", "HEAD", "--count"])
            return int(result.stdout.strip() or 0)
        except Exception as e:
            self.logger.error(f"Failed to get commit count: {e}")
            return 0
    
    def get_last_commit_hash(self) -> str:
        """Get the hash of the last commit."""
        try:
            result = self._run_command(["rev-parse", "HEAD"])
            return result.stdout.strip()
        except Exception as e:
            self.logger.error(f"Failed to get last commit hash: {e}")
            return ""
    
    def is_dirty(self, untracked_files: bool = True) -> bool:
        """Check if working directory is dirty."""
        try:
            cmd = ["status", "--porcelain"]
            if not untracked_files:
                cmd.append("--untracked-files=no")
            
            result = self._run_command(cmd)
            return bool(result.stdout.strip())
        except Exception as e:
            self.logger.error(f"Failed to check if dirty: {e}")
            return False
    
    def has_staged_changes(self) -> bool:
        """Check if there are staged changes."""
        try:
            result = self._run_command(["diff", "--cached", "--name-only"])
            return bool(result.stdout.strip())
        except Exception as e:
            self.logger.error(f"Failed to check staged changes: {e}")
            return False
    
    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """Get the URL of a remote repository."""
        try:
            result = self._run_command(["remote", "get-url", remote])
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception as e:
            self.logger.error(f"Failed to get remote URL: {e}")
            return None
    
    def create_branch(self, branch_name: str, checkout: bool = True) -> bool:
        """Create a new branch."""
        try:
            cmd = ["branch", branch_name]
            if checkout:
                cmd = ["checkout", "-b", branch_name]
            
            result = self._run_command(cmd)
            success = result.returncode == 0
            
            if success:
                self.logger.info(f"Branch '{branch_name}' created")
            else:
                self.logger.error(f"Failed to create branch '{branch_name}'")
            
            return success
        except Exception as e:
            self.logger.error(f"Failed to create branch: {e}")
            return False
    
    def merge_branch(self, branch_name: str, no_ff: bool = False) -> bool:
        """Merge a branch into the current branch."""
        try:
            cmd = ["merge", branch_name]
            if no_ff:
                cmd.append("--no-ff")
            
            result = self._run_command(cmd)
            success = result.returncode == 0
            
            if success:
                self.logger.info(f"Merged branch '{branch_name}'")
            else:
                self.logger.error(f"Failed to merge branch '{branch_name}'")
            
            return success
        except Exception as e:
            self.logger.error(f"Failed to merge branch: {e}")
            return False
    
    def _run_command(
        self,
        args: List[str],
        check: bool = False,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command in the repo directory."""
        return subprocess.run(
            ["git"] + args,
            cwd=self.repo_path,
            check=check,
            capture_output=capture_output,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
