"""Abstract base class for all language providers."""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel

from ..core.config import DGTConfig, ProviderConfig


class CheckResult(BaseModel):
    """Result of a pre-flight or post-flight check."""
    
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None


class ProviderType(Enum):
    """Supported provider types."""
    PYTHON = "python"
    RUST = "rust"
    CHROME_EXTENSION = "chrome_extension"
    UNKNOWN = "unknown"


class BaseProvider(ABC):
    """Abstract base class for language-specific providers."""
    
    def __init__(self, config: DGTConfig, provider_config: ProviderConfig) -> None:
        """Initialize provider with configuration."""
        self.config = config
        self.provider_config = provider_config
        self.logger = logger.bind(provider=self.provider_type.value)
    
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        pass
    
    @property
    @abstractmethod
    def anchor_files(self) -> List[str]:
        """Return list of anchor files that identify this provider's projects."""
        pass
    
    @abstractmethod
    def detect_project(self, project_root: Path) -> bool:
        """Detect if this provider should handle the given project."""
        pass
    
    @abstractmethod
    def run_pre_flight_checks(self, staged_files: List[Path]) -> List[CheckResult]:
        """Run pre-flight checks before committing."""
        pass
    
    @abstractmethod
    def run_post_flight_checks(self, commit_hash: str) -> List[CheckResult]:
        """Run post-flight checks after committing."""
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Get provider-specific metadata for commit messages."""
        pass
    
    def format_commit_message(self, base_message: str) -> str:
        """Format commit message with provider-specific context."""
        metadata = self.get_metadata()
        language_tag = self.provider_type.value.upper()
        
        template = self.config.commit_message_template
        formatted = template.format(
            language=language_tag,
            message=base_message,
            **metadata
        )
        
        return formatted
    
    def validate_environment(self) -> CheckResult:
        """Validate that the required environment is available."""
        try:
            self._validate_environment_impl()
            return CheckResult(
                success=True,
                message=f"{self.provider_type.value} environment validated successfully"
            )
        except Exception as e:
            return CheckResult(
                success=False,
                message=f"{self.provider_type.value} environment validation failed: {e}"
            )
    
    @abstractmethod
    def _validate_environment_impl(self) -> None:
        """Implementation-specific environment validation."""
        pass
    
    def __str__(self) -> str:
        """String representation of the provider."""
        return f"{self.__class__.__name__}(type={self.provider_type.value})"
