"""Documentation Service - SRP-compliant wrapper for DocParser and ArchitectureMapper.

Moves documentation logic OUT of MultiProviderOrchestrator.
The Orchestrator triggers; the Service executes.
"""

from pathlib import Path

from loguru import logger

from ..core.architecture_mapper import ArchitectureMapper
from ..core.doc_parser import DocParser


class DocumentationService:
    """Service layer for documentation management.
    
    Responsibilities:
    - Coordinate DocParser and ArchitectureMapper
    - Manage PROJECT_MAP.json and ARCHITECTURE.md updates
    - Provide high-level sync_all() interface for orchestrator
    """

    def __init__(self, project_root: Path):
        """Initialize DocumentationService.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.logger = logger.bind(component="DocumentationService")

        # Initialize core components
        self.doc_parser = DocParser(project_root)
        self.arch_mapper = ArchitectureMapper(project_root)

    def sync_all(self, changed_files: list[Path]) -> list[Path]:
        """Sync all documentation artifacts.
        
        This is the primary interface for the orchestrator.
        Updates PROJECT_MAP.json and ARCHITECTURE.md based on changed files.
        
        Args:
            changed_files: List of files that changed
            
        Returns:
            List of documentation files that were updated
        """
        updated_files = []

        # Update PROJECT_MAP.json
        if self._update_project_map(changed_files):
            map_file = self.project_root / "PROJECT_MAP.json"
            if map_file.exists():
                updated_files.append(map_file)

        # Update ARCHITECTURE.md
        if self._update_architecture_map():
            arch_file = self.project_root / "ARCHITECTURE.md"
            if arch_file.exists():
                updated_files.append(arch_file)

        if updated_files:
            self.logger.info(f"✅ Synced {len(updated_files)} documentation files")

        return updated_files

    def _update_project_map(self, changed_files: list[Path]) -> bool:
        """Update PROJECT_MAP.json incrementally.
        
        Args:
            changed_files: List of files that changed
            
        Returns:
            True if update succeeded, False otherwise
        """
        try:
            self.doc_parser.update_project_map_incremental(changed_files)
            return True
        except Exception as e:
            self.logger.warning(f"Failed to update PROJECT_MAP.json: {e}")
            return False

    def _update_architecture_map(self) -> bool:
        """Update ARCHITECTURE.md with dependency graph.
        
        Returns:
            True if update succeeded, False otherwise
        """
        try:
            self.arch_mapper.update_architecture_doc()
            return True
        except Exception as e:
            self.logger.warning(f"Failed to update ARCHITECTURE.md: {e}")
            return False

    def generate_full_project_map(self) -> bool:
        """Generate complete PROJECT_MAP.json from scratch.
        
        Returns:
            True if generation succeeded, False otherwise
        """
        try:
            project_map = self.doc_parser.generate_project_map()

            import json
            map_file = self.project_root / "PROJECT_MAP.json"
            with map_file.open("w", encoding="utf-8") as f:
                json.dump(project_map.model_dump(), f, indent=2)

            self.logger.info("✅ Generated full PROJECT_MAP.json")
            return True
        except Exception as e:
            self.logger.error(f"Failed to generate PROJECT_MAP.json: {e}")
            return False

    def get_project_stats(self) -> dict:
        """Get project documentation statistics.
        
        Returns:
            Dict with stats (symbol count, file count, etc.)
        """
        map_file = self.project_root / "PROJECT_MAP.json"
        if not map_file.exists():
            return {"status": "not_generated"}

        try:
            import json
            with map_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            return {
                "status": "available",
                "symbol_count": len(data.get("symbols", [])),
                "file_count": data.get("file_count", 0),
                "total_lines": data.get("total_lines", 0),
                "languages": data.get("languages", []),
                "last_updated": data.get("generated_at", "unknown"),
            }
        except Exception as e:
            self.logger.warning(f"Failed to read PROJECT_MAP.json stats: {e}")
            return {"status": "error", "error": str(e)}
