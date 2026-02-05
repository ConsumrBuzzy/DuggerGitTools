"""Chronicle Manager - Polymorphic state persistence with rotating logs.

The "Project Heartbeat" - captures commit intent, telemetry, and TODO state.
Rotates by frequency (Day/Week/Month/Phase) and size to keep IDE context clean.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Literal
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class RotationFrequency(str, Enum):
    """Chronicle rotation frequency."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    PHASE = "phase"


@dataclass
class ProjectPulse:
    """Machine-readable project heartbeat snapshot."""
    
    project: str
    last_heartbeat: str
    current_phase: str
    metrics: Dict[str, any]
    ide_status: str


@dataclass
class ChronicleEntry:
    """Single chronicle entry."""
    
    timestamp: str
    commit_message: str
    files_changed: int
    lines_added: int
    lines_removed: int
    todo_count: int
    bug_count: int
    fixme_count: int


class ChronicleManager:
    """Polymorphic chronicle with rotating hot/cold storage.
    
    Hot Storage: CHRONICLE_LATEST.md (root, <50KB, AI-friendly)
    Cold Storage: PLANNING/archive/chronicle_YYYY_WNN.md (timestamped archives)
    
    Rotation triggers:
    - Time-based (Day/Week/Month/Phase boundaries)
    - Size-based (max_size_kb exceeded)
    
    Carry-over: Open TODOs migrate to new hot log on rotation.
    """
    
    def __init__(
        self,
        project_root: Path,
        frequency: RotationFrequency = RotationFrequency.WEEK,
        max_size_kb: int = 50,
        retention_limit: int = 10
    ):
        """Initialize ChronicleManager.
        
        Args:
            project_root: Project root directory
            frequency: Rotation frequency
            max_size_kb: Max size before forced rotation
            retention_limit: Max number of archives to keep
        """
        self.project_root = project_root
        self.frequency = frequency
        self.max_size_kb = max_size_kb
        self.retention_limit = retention_limit
        self.logger = logger.bind(component="ChronicleManager")
        
        self.hot_log = project_root / "CHRONICLE_LATEST.md"
        self.archive_dir = project_root / "PLANNING" / "archive"
        self.pulse_file = project_root / "PROJECT_PULSE.json"
        
        # Ensure archive directory exists
        self.archive_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_current_period_label(self) -> str:
        """Get current period label for archive naming.
        
        Returns:
            Period label (e.g., "2026_W06", "2026_02", "2026_035")
        """
        now = datetime.now()
        
        if self.frequency == RotationFrequency.DAY:
            return now.strftime("%Y_%j")  # Year + day of year
        elif self.frequency == RotationFrequency.WEEK:
            return now.strftime("%Y_W%U")  # Year + week number
        elif self.frequency == RotationFrequency.MONTH:
            return now.strftime("%Y_%m")  # Year + month
        else:  # PHASE
            # Phase rotations are manual via force_rotate()
            return now.strftime("%Y_%m_%d")
    
    def _should_rotate(self) -> bool:
        """Check if rotation is needed.
        
        Returns:
            True if rotation needed
        """
        if not self.hot_log.exists():
            return False
        
        # Size guard
        size_kb = self.hot_log.stat().st_size / 1024
        if size_kb > self.max_size_kb:
            self.logger.info(f"Size guard triggered: {size_kb:.1f}KB > {self.max_size_kb}KB")
            return True
        
        # Time-based rotation (check if period has changed)
        # Read last entry timestamp from hot log
        try:
            with self.hot_log.open('r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Find last entry timestamp
            last_timestamp = None
            for line in reversed(lines):
                if line.startswith("**Timestamp**:"):
                    timestamp_str = line.split("**Timestamp**:")[1].strip()
                    last_timestamp = datetime.fromisoformat(timestamp_str)
                    break
            
            if last_timestamp:
                current_period = self._get_current_period_label()
                last_period = self._format_period_label(last_timestamp)
                
                if current_period != last_period:
                    self.logger.info(f"Period boundary crossed: {last_period} -> {current_period}")
                    return True
        
        except Exception as e:
            self.logger.debug(f"Could not check rotation timing: {e}")
        
        return False
    
    def _format_period_label(self, dt: datetime) -> str:
        """Format datetime to period label.
        
        Args:
            dt: Datetime to format
            
        Returns:
            Period label
        """
        if self.frequency == RotationFrequency.DAY:
            return dt.strftime("%Y_%j")
        elif self.frequency == RotationFrequency.WEEK:
            return dt.strftime("%Y_W%U")
        elif self.frequency == RotationFrequency.MONTH:
            return dt.strftime("%Y_%m")
        else:
            return dt.strftime("%Y_%m_%d")
    
    def _extract_open_todos(self) -> List[str]:
        """Extract open TODOs from current hot log for carry-over.
        
        Returns:
            List of open TODO lines
        """
        if not self.hot_log.exists():
            return []
        
        todos = []
        
        try:
            with self.hot_log.open('r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract TODOs section
            if "## Open TODOs" in content:
                todos_section = content.split("## Open TODOs")[1].split("##")[0]
                
                for line in todos_section.splitlines():
                    line = line.strip()
                    if line.startswith("- [ ]"):
                        todos.append(line)
        
        except Exception as e:
            self.logger.debug(f"Could not extract TODOs: {e}")
        
        return todos
    
    def rotate(self, phase_label: Optional[str] = None) -> Optional[Path]:
        """Rotate hot log to cold storage.
        
        Args:
            phase_label: Optional phase label for manual rotation
            
        Returns:
            Path to archived file, or None if no rotation
        """
        if not self.hot_log.exists():
            return None
        
        # Determine archive name
        if phase_label:
            archive_name = f"chronicle_{phase_label}.md"
        else:
            period_label = self._get_current_period_label()
            archive_name = f"chronicle_{period_label}.md"
        
        archive_path = self.archive_dir / archive_name
        
        # Extract open TODOs for carry-over
        open_todos = self._extract_open_todos()
        
        # Move hot log to archive
        self.hot_log.rename(archive_path)
        self.logger.info(f"Rotated chronicle to {archive_path}")
        
        # Create new hot log with carry-over TODOs
        if open_todos:
            header = f"""# Project Chronicle

**Project**: {self.project_root.name}  
**Chronicle Started**: {datetime.now().isoformat()}

## Open TODOs (Carried Over)

{chr(10).join(open_todos)}

---

## Entries

"""
            with self.hot_log.open('w', encoding='utf-8') as f:
                f.write(header)
        
        # Prune old archives
        self._prune_archives()
        
        return archive_path
    
    def _prune_archives(self) -> None:
        """Prune old archives beyond retention limit."""
        archives = sorted(
            self.archive_dir.glob("chronicle_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if len(archives) > self.retention_limit:
            for archive in archives[self.retention_limit:]:
                self.logger.info(f"Pruning old archive: {archive.name}")
                archive.unlink()
    
    def add_entry(
        self,
        commit_message: str,
        files_changed: int = 0,
        lines_added: int = 0,
        lines_removed: int = 0,
        todo_count: int = 0,
        bug_count: int = 0,
        fixme_count: int = 0
    ) -> None:
        """Add entry to chronicle.
        
        Args:
            commit_message: Semantic commit message
            files_changed: Number of files changed
            lines_added: Lines added
            lines_removed: Lines removed
            todo_count: Current TODO count
            bug_count: Current bug count
            fixme_count: Current FIXME count
        """
        # Check rotation
        if self._should_rotate():
            self.rotate()
        
        # Create hot log if not exists
        if not self.hot_log.exists():
            header = f"""# Project Chronicle

**Project**: {self.project_root.name}  
**Chronicle Started**: {datetime.now().isoformat()}

---

## Entries

"""
            with self.hot_log.open('w', encoding='utf-8') as f:
                f.write(header)
        
        # Format entry
        timestamp = datetime.now().isoformat()
        
        entry = f"""
### {commit_message}

**Timestamp**: {timestamp}  
**Files Changed**: {files_changed}  
**Delta**: +{lines_added}/-{lines_removed} lines  
**State**: {todo_count} TODOs, {bug_count} bugs, {fixme_count} FIXMEs

---

"""
        
        # Append entry
        with self.hot_log.open('a', encoding='utf-8') as f:
            f.write(entry)
        
        self.logger.info(f"Added chronicle entry: {commit_message[:50]}...")
    
    def update_pulse(
        self,
        current_phase: str,
        metrics: Dict[str, any],
        ide_status: str
    ) -> None:
        """Update PROJECT_PULSE.json.
        
        Args:
            current_phase: Current project phase
            metrics: Project metrics
            ide_status: IDE sync status
        """
        pulse = {
            "project": self.project_root.name,
            "last_heartbeat": datetime.now().isoformat(),
            "current_phase": current_phase,
            "metrics": metrics,
            "ide_status": ide_status
        }
        
        with self.pulse_file.open('w', encoding='utf-8') as f:
            json.dump(pulse, f, indent=2)
        
        self.logger.info("Updated PROJECT_PULSE.json")
    
    def force_rotate(self, phase_label: str) -> Path:
        """Force rotation with custom phase label.
        
        Args:
            phase_label: Phase label (e.g., "v1-alpha", "genesis")
            
        Returns:
            Path to archived file
        """
        self.logger.info(f"Forcing phase rotation: {phase_label}")
        return self.rotate(phase_label=phase_label)
    
    def get_recent_entries(self, limit: int = 10) -> List[str]:
        """Get recent chronicle entries.
        
        Args:
            limit: Max number of entries
            
        Returns:
            List of recent entry blocks
        """
        if not self.hot_log.exists():
            return []
        
        try:
            with self.hot_log.open('r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by entry markers
            entries = content.split("###")[1:]  # Skip header
            
            # Return most recent
            return entries[-limit:]
        
        except Exception as e:
            self.logger.error(f"Could not read entries: {e}")
            return []
