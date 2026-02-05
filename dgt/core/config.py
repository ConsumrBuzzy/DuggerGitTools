"""Configuration management for DGT."""

from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, validator


class LoggingConfig(BaseModel):
    """Centralized logging configuration using Loguru."""

    level: str = Field(default="INFO", description="Logging level")
    format_string: str = Field(
        default="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        description="Log format string",
    )
    rotation: str = Field(default="10 MB", description="Log file rotation size")
    retention: str = Field(default="7 days", description="Log retention period")
    compression: str = Field(default="gz", description="Log compression format")

    def configure(self) -> None:
        """Configure Loguru with the specified settings."""
        logger.remove()
        logger.add(
            sink=lambda msg: print(msg, end=""),
            level=self.level,
            format=self.format_string,
            colorize=True,
        )
        logger.add(
            sink="logs/dgt.log",
            level=self.level,
            format=self.format_string,
            rotation=self.rotation,
            retention=self.retention,
            compression=self.compression,
            colorize=False,
        )


class ProviderConfig(BaseModel):
    """Configuration for individual language providers."""

    enabled: bool = Field(default=True, description="Whether this provider is enabled")
    pre_flight_checks: list[str] = Field(
        default_factory=list,
        description="Pre-flight checks to run",
    )
    post_flight_checks: list[str] = Field(
        default_factory=list,
        description="Post-flight checks to run",
    )
    custom_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific settings",
    )


class DGTConfig(BaseModel):
    """Main configuration for DuggerCore Git Tools."""

    project_root: Path = Field(description="Root directory of the project")
    auto_push: bool = Field(
        default=True,
        description="Automatically push after successful commit",
    )
    dry_run: bool = Field(
        default=False,
        description="Run in dry-run mode without making changes",
    )
    commit_message_template: str = Field(
        default="[{language}] {message}",
        description="Template for commit messages",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )
    providers: dict[str, ProviderConfig] = Field(
        default_factory=dict,
        description="Provider configurations",
    )
    provider_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Legacy provider configuration field",
    )

    @validator("project_root")
    def validate_project_root(cls, v: Path) -> Path:
        """Validate that project root exists and is a directory."""
        if not v.exists():
            raise ValueError(f"Project root does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Project root is not a directory: {v}")
        return v.resolve()

    @classmethod
    def from_project_root(cls, project_root: Path | None = None) -> "DGTConfig":
        """Create configuration from project root directory."""
        if project_root is None:
            project_root = Path.cwd()

        config_file = project_root / "dgt.toml"

        if config_file.exists():
            import tomllib

            with config_file.open("rb") as f:
                config_data = tomllib.load(f)
            return cls(**config_data)

        return cls(project_root=project_root)

    def get_provider_config(self, provider_name: str) -> ProviderConfig:
        """Get configuration for a specific provider."""
        return self.providers.get(provider_name, ProviderConfig())
