"""Dugger-Schema: Universal configuration and metadata system."""

import json
import re
import yaml
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pydantic import BaseModel, Field, validator

from .config import DGTConfig


class ProjectType(str, Enum):
    """Universal project types."""
    PYTHON = "python"
    RUST = "rust"
    CHROME_EXTENSION = "chrome-extension"
    NODEJS = "nodejs"
    GAME_MAKER = "game-maker"
    SOLANA = "solana"
    UNKNOWN = "unknown"


class VersionFormat(BaseModel):
    """Version format configuration."""
    file_path: str = Field(..., description="Path to version file")
    pattern: str = Field(..., description="Regex pattern to find version")
    replacement: Optional[str] = Field(None, description="Replacement template")
    encoding: str = Field("utf-8", description="File encoding")


class AnchorFile(BaseModel):
    """Anchor file fingerprint for project detection."""
    path: str = Field(..., description="File path pattern")
    weight: int = Field(10, description="Detection weight")
    provider: str = Field(..., description="Associated provider")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CapabilityCheck(BaseModel):
    """Tool capability check configuration."""
    command: List[str] = Field(..., description="Command to check availability")
    expected_exit: int = Field(0, description="Expected exit code")
    timeout: int = Field(5, description="Timeout in seconds")
    description: str = Field(..., description="Human-readable description")


class ToolConfig(BaseModel):
    """Tool configuration for auto-fixing."""
    name: str = Field(..., description="Tool name")
    check: CapabilityCheck = Field(..., description="Availability check")
    fix_command: List[str] = Field(..., description="Command to run fixes")
    file_patterns: List[str] = Field(default_factory=list, description="File patterns to process")
    priority: int = Field(50, description="Priority order")
    description: str = Field(..., description="Tool description")


class MultiProviderConfig(BaseModel):
    """Multi-provider configuration for hybrid projects."""
    enabled_providers: List[str] = Field(..., description="List of enabled providers")
    execution_order: List[str] = Field(default_factory=list, description="Execution order")
    fail_fast: bool = Field(True, description="Fail on first provider error")
    merge_strategies: Dict[str, str] = Field(default_factory=dict, description="Merge strategies")


class DuggerSchema(BaseModel):
    """Universal Dugger configuration schema."""
    
    # Project detection
    project_type: ProjectType = Field(ProjectType.UNKNOWN, description="Detected project type")
    anchor_files: List[AnchorFile] = Field(default_factory=list, description="Anchor file fingerprints")
    
    # Version management
    version_formats: List[VersionFormat] = Field(default_factory=list, description="Version format configurations")
    auto_bump: bool = Field(False, description="Auto-bump version on commit")
    bump_type: str = Field("patch", description="Bump type (major/minor/patch)")
    
    # Tool configuration
    tools: List[ToolConfig] = Field(default_factory=list, description="Available tools")
    auto_fix: bool = Field(True, description="Enable auto-fixing")
    
    # Multi-provider support
    multi_provider: Optional[MultiProviderConfig] = Field(None, description="Multi-provider configuration")
    
    # Message generation
    message_style: str = Field("conventional", description="Message style")
    llm_enabled: bool = Field(False, description="Enable LLM enhancement")
    llm_context: Dict[str, Any] = Field(default_factory=dict, description="LLM context")
    
    # Build and deployment
    build_commands: List[List[str]] = Field(default_factory=list, description="Build commands")
    pre_commit_hooks: List[List[str]] = Field(default_factory=list, description="Pre-commit hooks")
    post_commit_hooks: List[List[str]] = Field(default_factory=list, description="Post-commit hooks")
    
    @validator('anchor_files')
    def validate_anchor_files(cls, v):
        """Validate anchor file configuration."""
        if not v:
            raise ValueError("At least one anchor file must be defined")
        return v
    
    @validator('version_formats')
    def validate_version_formats(cls, v):
        """Validate version format configuration."""
        if not v:
            raise ValueError("At least one version format must be defined")
        for fmt in v:
            try:
                re.compile(fmt.pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern in version format: {e}")
        return v


class SchemaLoader:
    """Load and validate Dugger schema from various sources."""
    
    def __init__(self, config: DGTConfig) -> None:
        """Initialize schema loader."""
        self.config = config
        self.logger = logger.bind(schema_loader=True)
        self.repo_path = config.project_root
    
    def load_schema(self) -> DuggerSchema:
        """Load schema from project configuration files."""
        # Try different configuration sources in order of preference
        schema_sources = [
            self.repo_path / "dugger.yaml",
            self.repo_path / "dugger.yml", 
            self.repo_path / ".dgtrc",
            self.repo_path / ".dugger.json",
        ]
        
        for schema_file in schema_sources:
            if schema_file.exists():
                self.logger.info(f"Loading schema from {schema_file}")
                return self._load_from_file(schema_file)
        
        # Fallback to auto-detection
        self.logger.info("No schema file found, using auto-detection")
        return self._auto_detect_schema()
    
    def _load_from_file(self, schema_file: Path) -> DuggerSchema:
        """Load schema from a specific file."""
        try:
            content = schema_file.read_text(encoding="utf-8")
            
            if schema_file.suffix in [".yaml", ".yml"]:
                data = yaml.safe_load(content)
            elif schema_file.suffix == ".json":
                data = json.loads(content)
            else:
                raise ValueError(f"Unsupported schema file format: {schema_file.suffix}")
            
            return DuggerSchema(**data)
            
        except Exception as e:
            self.logger.error(f"Failed to load schema from {schema_file}: {e}")
            raise
    
    def _auto_detect_schema(self) -> DuggerSchema:
        """Auto-detect schema based on project files."""
        project_type = self._detect_project_type()
        anchor_files = self._generate_anchor_files(project_type)
        version_formats = self._generate_version_formats(project_type)
        tools = self._generate_tool_configs(project_type)
        
        return DuggerSchema(
            project_type=project_type,
            anchor_files=anchor_files,
            version_formats=version_formats,
            tools=tools,
            multi_provider=self._detect_multi_provider()
        )
    
    def _detect_project_type(self) -> ProjectType:
        """Detect project type using fingerprint scoring."""
        scores = {}
        
        # Check for anchor files and calculate scores
        fingerprints = {
            ProjectType.RUST: [
                ("Cargo.toml", 20),
                ("Cargo.lock", 10),
                ("src/main.rs", 5),
                ("src/lib.rs", 5),
            ],
            ProjectType.PYTHON: [
                ("pyproject.toml", 20),
                ("requirements.txt", 15),
                ("setup.py", 10),
                ("Pipfile", 10),
                ("poetry.lock", 5),
            ],
            ProjectType.CHROME_EXTENSION: [
                ("manifest.json", 25),
                ("popup.html", 10),
                ("content.js", 10),
                ("background.js", 5),
            ],
            ProjectType.NODEJS: [
                ("package.json", 20),
                ("package-lock.json", 10),
                ("node_modules", 5),
                (".nvmrc", 5),
            ],
            ProjectType.SOLANA: [
                ("Cargo.toml", 15),  # Rust-based
                ("Anchor.toml", 25),  # Anchor framework
                ("programs/", 10),
                ("tests/", 5),
            ],
            ProjectType.GAME_MAKER: [
                ("project.gmx", 25),
                ("*.yy", 15),
                ("objects/", 10),
                ("scripts/", 5),
            ],
        }
        
        for project_type, files in fingerprints.items():
            score = 0
            for file_pattern, weight in files:
                if self._file_exists_pattern(file_pattern):
                    score += weight
            scores[project_type] = score
        
        # Return the highest scoring project type
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] > 0:
                self.logger.info(f"Detected project type: {best_type.value} (score: {scores[best_type]})")
                return best_type
        
        return ProjectType.UNKNOWN
    
    def _file_exists_pattern(self, pattern: str) -> bool:
        """Check if a file pattern exists."""
        if "*" in pattern:
            # Glob pattern
            from glob import glob
            return len(glob(str(self.repo_path / pattern))) > 0
        else:
            # Direct file path
            return (self.repo_path / pattern).exists()
    
    def _generate_anchor_files(self, project_type: ProjectType) -> List[AnchorFile]:
        """Generate anchor files for detected project type."""
        anchor_configs = {
            ProjectType.RUST: [
                AnchorFile(path="Cargo.toml", weight=20, provider="rust"),
                AnchorFile(path="src/", weight=10, provider="rust"),
            ],
            ProjectType.PYTHON: [
                AnchorFile(path="pyproject.toml", weight=20, provider="python"),
                AnchorFile(path="requirements.txt", weight=15, provider="python"),
            ],
            ProjectType.CHROME_EXTENSION: [
                AnchorFile(path="manifest.json", weight=25, provider="chrome"),
                AnchorFile(path="popup.html", weight=10, provider="chrome"),
            ],
            ProjectType.NODEJS: [
                AnchorFile(path="package.json", weight=20, provider="nodejs"),
            ],
            ProjectType.SOLANA: [
                AnchorFile(path="Anchor.toml", weight=25, provider="solana"),
                AnchorFile(path="Cargo.toml", weight=15, provider="rust"),
            ],
        }
        
        return anchor_configs.get(project_type, [])
    
    def _generate_version_formats(self, project_type: ProjectType) -> List[VersionFormat]:
        """Generate version formats for detected project type."""
        version_configs = {
            ProjectType.RUST: [
                VersionFormat(
                    file_path="Cargo.toml",
                    pattern=r'version\s*=\s*"([^"]+)"',
                    replacement='version = "{new_version}"'
                ),
            ],
            ProjectType.PYTHON: [
                VersionFormat(
                    file_path="pyproject.toml",
                    pattern=r'version\s*=\s*"([^"]+)"',
                    replacement='version = "{new_version}"'
                ),
            ],
            ProjectType.CHROME_EXTENSION: [
                VersionFormat(
                    file_path="manifest.json",
                    pattern=r'"version"\s*:\s*"([^"]+)"',
                    replacement='"version": "{new_version}"'
                ),
            ],
            ProjectType.NODEJS: [
                VersionFormat(
                    file_path="package.json",
                    pattern=r'"version"\s*:\s*"([^"]+)"',
                    replacement='"version": "{new_version}"'
                ),
            ],
            ProjectType.SOLANA: [
                VersionFormat(
                    file_path="Anchor.toml",
                    pattern=r'version\s*=\s*"([^"]+)"',
                    replacement='version = "{new_version}"'
                ),
                VersionFormat(
                    file_path="Cargo.toml",
                    pattern=r'version\s*=\s*"([^"]+)"',
                    replacement='version = "{new_version}"'
                ),
            ],
        }
        
        return version_configs.get(project_type, [])
    
    def _generate_tool_configs(self, project_type: ProjectType) -> List[ToolConfig]:
        """Generate tool configurations for detected project type."""
        tool_configs = {
            ProjectType.RUST: [
                ToolConfig(
                    name="cargo-fmt",
                    check=CapabilityCheck(command=["cargo", "fmt", "--version"], description="Cargo formatter"),
                    fix_command=["cargo", "fmt", "--all"],
                    priority=10,
                    description="Rust code formatter"
                ),
                ToolConfig(
                    name="cargo-clippy",
                    check=CapabilityCheck(command=["cargo", "clippy", "--version"], description="Cargo linter"),
                    fix_command=["cargo", "clippy", "--all", "--fix", "--allow-dirty"],
                    priority=20,
                    description="Rust linter and auto-fixer"
                ),
            ],
            ProjectType.PYTHON: [
                ToolConfig(
                    name="ruff",
                    check=CapabilityCheck(command=["ruff", "--version"], description="Python linter"),
                    fix_command=["ruff", "check", "--fix", "."],
                    file_patterns=["*.py"],
                    priority=10,
                    description="Python linter and formatter"
                ),
                ToolConfig(
                    name="black",
                    check=CapabilityCheck(command=["black", "--version"], description="Python formatter"),
                    fix_command=["black", "."],
                    file_patterns=["*.py"],
                    priority=20,
                    description="Python code formatter"
                ),
            ],
            ProjectType.CHROME_EXTENSION: [
                ToolConfig(
                    name="eslint",
                    check=CapabilityCheck(command=["npx", "eslint", "--version"], description="JavaScript linter"),
                    fix_command=["npx", "eslint", "--fix", "."],
                    file_patterns=["*.js", "*.mjs"],
                    priority=10,
                    description="JavaScript linter"
                ),
            ],
        }
        
        return tool_configs.get(project_type, [])
    
    def _detect_multi_provider(self) -> Optional[MultiProviderConfig]:
        """Detect if multi-provider configuration is needed."""
        # Check for hybrid projects (e.g., Solana with both Rust and Python)
        rust_indicators = ["Cargo.toml", "src/"]
        python_indicators = ["pyproject.toml", "requirements.txt"]
        
        has_rust = any(self._file_exists_pattern(pattern) for pattern in rust_indicators)
        has_python = any(self._file_exists_pattern(pattern) for pattern in python_indicators)
        
        if has_rust and has_python:
            return MultiProviderConfig(
                enabled_providers=["rust", "python"],
                execution_order=["rust", "python"],
                fail_fast=False,
                merge_strategies={"version": "highest", "build": "sequential"}
            )
        
        return None
