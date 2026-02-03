"""Core DGT functionality - Language-Agnostic DevOps Orchestration."""

from .config import DGTConfig, LoggingConfig, ProviderConfig
from .schema import DuggerSchema, SchemaLoader, ProjectType
from .git_operations import GitOperations
from .message_generator import MessageGenerator
from .auto_fixer import AutoFixer
from .versioning import VersionManager

# Universal components
from .universal_versioning import UniversalVersionManager, MultiProviderVersionManager
from .universal_auto_fixer import UniversalAutoFixer, MultiProviderAutoFixer
from .universal_message_generator import UniversalMessageGenerator
from .capability_cache import CapabilityCache, CachedCapabilityChecker
from .docs_merger import DocsMerger
from .universal_rollback import RollbackManager, RollbackContext

# Orchestrators
from .orchestrator import DGTOrchestrator
from .multi_provider_orchestrator import MultiProviderOrchestrator

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
