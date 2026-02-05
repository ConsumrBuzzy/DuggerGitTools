"""Core DGT functionality - Language-Agnostic DevOps Orchestration."""

from .auto_fixer import AutoFixer
from .capability_cache import CachedCapabilityChecker, CapabilityCache
from .config import DGTConfig, LoggingConfig, ProviderConfig
from .docs_merger import DocsMerger
from .git_operations import GitOperations
from .message_generator import MessageGenerator
from .multi_provider_orchestrator import MultiProviderOrchestrator

# Orchestrators
from .orchestrator import DGTOrchestrator
from .schema import DuggerSchema, ProjectType, SchemaLoader
from .universal_auto_fixer import MultiProviderAutoFixer, UniversalAutoFixer
from .universal_message_generator import UniversalMessageGenerator
from .universal_rollback import RollbackContext, RollbackManager

# Universal components
from .universal_versioning import MultiProviderVersionManager, UniversalVersionManager
from .versioning import VersionManager

__all__ = [
    # Configuration
    "DGTConfig",
    "LoggingConfig",
    "ProviderConfig",

    # Schema
    "DuggerSchema",
    "SchemaLoader",
    "ProjectType",

    # Core operations
    "GitOperations",
    "MessageGenerator",
    "AutoFixer",
    "VersionManager",

    # Universal components
    "UniversalVersionManager",
    "MultiProviderVersionManager",
    "UniversalAutoFixer",
    "MultiProviderAutoFixer",
    "UniversalMessageGenerator",
    "CapabilityCache",
    "CachedCapabilityChecker",
    "DocsMerger",
    "RollbackManager",
    "RollbackContext",

    # Orchestrators
    "DGTOrchestrator",
    "MultiProviderOrchestrator",
]
