"""Task Extractor - Pure regex-based TODO/FIXME/NOTE scanner.

NO AI. NO LLM. Just deterministic grep-style logic.
Extracts developer annotations and generates TODO_REPORT.md.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass
class TaskAnnotation:
    """A single task annotation found in code."""

    file_path: Path
    line_number: int
    tag_type: str  # TODO, FIXME, NOTE, etc.
    message: str
    context_line: str  # Full line of code


class TaskExtractor:
    """Pure regex-based task annotation scanner.
    
    Scans source files for developer annotations:
    - TODO: Something to implement later
    - FIXME: Something broken that needs fixing
    - NOTE: Important information
    - HACK: Temporary workaround
    - XXX: Warning or important notice
    
    Output: TODO_REPORT.md with file:line references
    """

    # Regex patterns for different annotation styles
    PATTERNS = [
        # Python/Rust: # TODO: message
        re.compile(r"#\s*(TODO|FIXME|NOTE|HACK|XXX):\s*(.+)$", re.IGNORECASE),
        # JavaScript: // TODO: message
        re.compile(r"//\s*(TODO|FIXME|NOTE|HACK|XXX):\s*(.+)$", re.IGNORECASE),
        # Multi-line comments: /* TODO: message */
        re.compile(r"/\*\s*(TODO|FIXME|NOTE|HACK|XXX):\s*(.+?)\s*\*/", re.IGNORECASE),
    ]

    SUPPORTED_EXTENSIONS = [".py", ".rs", ".js", ".ts", ".jsx", ".tsx", ".toml", ".yaml", ".yml"]

    def __init__(self, project_root: Path):
        """Initialize TaskExtractor.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.logger = logger.bind(component="TaskExtractor")

    def scan_project(self) -> list[TaskAnnotation]:
        """Scan entire project for task annotations.
        
        Returns:
            List of TaskAnnotation objects
        """
        annotations = []

        # Find all source files
        for ext in self.SUPPORTED_EXTENSIONS:
            for file_path in self.project_root.rglob(f"*{ext}"):
                # Skip common ignore patterns
                if self._should_skip(file_path):
                    continue

                # Scan file
                file_annotations = self._scan_file(file_path)
                annotations.extend(file_annotations)

        self.logger.info(f"Found {len(annotations)} task annotations across project")
        return annotations

    def _should_skip(self, file_path: Path) -> bool:
        """Check if file should be skipped.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if should skip, False otherwise
        """
        # Skip patterns
        skip_patterns = [
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            "dist",
            "build",
            "target",  # Rust
            ".pytest_cache",
            ".mypy_cache",
        ]

        # Check if any parent directory matches skip pattern
        for part in file_path.parts:
            if part in skip_patterns:
                return True

        return False

    def _scan_file(self, file_path: Path) -> list[TaskAnnotation]:
        """Scan a single file for task annotations.
        
        Args:
            file_path: Path to file
            
        Returns:
            List of TaskAnnotation objects found in file
        """
        annotations = []

        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, start=1):
                    # Try each pattern
                    for pattern in self.PATTERNS:
                        match = pattern.search(line)
                        if match:
                            tag_type = match.group(1).upper()
                            message = match.group(2).strip()

                            annotations.append(TaskAnnotation(
                                file_path=file_path,
                                line_number=line_num,
                                tag_type=tag_type,
                                message=message,
                                context_line=line.strip(),
                            ))
                            break  # Only count first match per line

        except Exception as e:
            self.logger.warning(f"Failed to scan {file_path}: {e}")

        return annotations

    def generate_report(self, annotations: list[TaskAnnotation]) -> str:
        """Generate markdown report from annotations.
        
        Args:
            annotations: List of TaskAnnotation objects
            
        Returns:
            Markdown-formatted report
        """
        if not annotations:
            return "# TODO Report\n\nNo task annotations found.\n"

        # Group by tag type
        by_tag: dict[str, list[TaskAnnotation]] = {}
        for ann in annotations:
            if ann.tag_type not in by_tag:
                by_tag[ann.tag_type] = []
            by_tag[ann.tag_type].append(ann)

        # Build report
        lines = ["# TODO Report", ""]
        lines.append(f"**Total Annotations**: {len(annotations)}")
        lines.append("")

        # Summary by type
        lines.append("## Summary")
        lines.append("")
        for tag_type in sorted(by_tag.keys()):
            count = len(by_tag[tag_type])
            lines.append(f"- **{tag_type}**: {count}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Detailed listings by type
        tag_priority = ["FIXME", "TODO", "HACK", "NOTE", "XXX"]
        for tag_type in tag_priority:
            if tag_type not in by_tag:
                continue

            items = by_tag[tag_type]
            lines.append(f"## {tag_type} ({len(items)})")
            lines.append("")

            for ann in items:
                rel_path = ann.file_path.relative_to(self.project_root)
                # Create clickable file link with line number
                file_link = f"[{rel_path}](file:///{ann.file_path}#L{ann.line_number})"
                lines.append(f"- {file_link}:{ann.line_number}")
                lines.append("  ```")
                lines.append(f"  {ann.message}")
                lines.append("  ```")
                lines.append("")

        return "\n".join(lines)

    def generate_report_file(self, output_path: Path = None) -> Path:
        """Scan project and generate TODO_REPORT.md.
        
        Args:
            output_path: Optional custom output path
            
        Returns:
            Path to generated report
        """
        if output_path is None:
            output_path = self.project_root / "TODO_REPORT.md"

        # Scan project
        annotations = self.scan_project()

        # Generate report
        report = self.generate_report(annotations)

        # Write to file
        with output_path.open("w", encoding="utf-8") as f:
            f.write(report)

        self.logger.info(f"Generated TODO report: {output_path}")
        return output_path

    def get_annotations_by_file(self, file_path: Path) -> list[TaskAnnotation]:
        """Get all annotations for a specific file.
        
        Args:
            file_path: Path to file
            
        Returns:
            List of TaskAnnotation objects
        """
        return self._scan_file(file_path)
