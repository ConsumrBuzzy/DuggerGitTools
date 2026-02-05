"""Universal auto-fixer with capability-based tool sensing."""

import subprocess
import time
from pathlib import Path

from loguru import logger

from .config import DGTConfig
from .schema import CapabilityCheck, DuggerSchema, ToolConfig


class UniversalAutoFixer:
    """Language-agnostic auto-fixer using capability-based tool detection."""

    def __init__(self, config: DGTConfig, schema: DuggerSchema) -> None:
        """Initialize universal auto-fixer."""
        self.config = config
        self.schema = schema
        self.logger = logger.bind(auto_fixer=True)
        self.repo_path = config.project_root
        self.fixes_applied = False

    def run_all_fixes(self, staged_files: list[Path] | None = None) -> bool:
        """Run all available auto-fixes based on capability detection."""
        if not self.schema.auto_fix:
            self.logger.info("Auto-fix disabled in configuration")
            return False

        self.logger.info("Running universal auto-fixes...")
        self.fixes_applied = False

        # Get initial status
        initial_status = self._get_git_status()

        # Detect available tools and run fixes
        available_tools = self._detect_available_tools()

        if not available_tools:
            self.logger.warning("No auto-fix tools available")
            return False

        # Sort tools by priority
        available_tools.sort(key=lambda t: t.priority)

        # Run fixes in priority order
        for tool_config in available_tools:
            if self._should_run_tool(tool_config, staged_files):
                success = self._run_tool_fix(tool_config)
                if success:
                    self.fixes_applied = True

        # Check if files changed
        final_status = self._get_git_status()
        if initial_status != final_status:
            self.logger.info("Files changed during fixes - will re-stage")
            self.fixes_applied = True

        self.logger.info(f"{'Fixes applied' if self.fixes_applied else 'No fixes needed'}")
        return self.fixes_applied

    def _detect_available_tools(self) -> list[ToolConfig]:
        """Detect which tools are available on the system."""
        available_tools = []

        for tool_config in self.schema.tools:
            if self._check_tool_availability(tool_config.check):
                self.logger.info(f"Tool available: {tool_config.name}")
                available_tools.append(tool_config)
            else:
                self.logger.debug(f"Tool not available: {tool_config.name}")

        return available_tools

    def _check_tool_availability(self, capability_check: CapabilityCheck) -> bool:
        """Check if a tool is available using the capability check."""
        try:
            result = subprocess.run(
                capability_check.command,
                check=False, capture_output=True,
                text=True,
                timeout=capability_check.timeout,
                cwd=self.repo_path,
            )

            success = result.returncode == capability_check.expected_exit

            if success:
                self.logger.debug(f"Tool check passed: {' '.join(capability_check.command)}")
            else:
                self.logger.debug(f"Tool check failed: {' '.join(capability_check.command)} (exit: {result.returncode})")

            return success

        except subprocess.TimeoutExpired:
            self.logger.debug(f"Tool check timed out: {' '.join(capability_check.command)}")
            return False
        except FileNotFoundError:
            self.logger.debug(f"Tool not found: {capability_check.command[0]}")
            return False
        except Exception as e:
            self.logger.debug(f"Tool check error: {e}")
            return False

    def _should_run_tool(self, tool_config: ToolConfig, staged_files: list[Path] | None) -> bool:
        """Determine if a tool should run based on file patterns."""
        if not tool_config.file_patterns:
            # Tool runs on all files
            return True

        if not staged_files:
            # No staged files, check all files in repo
            return True

        # Check if any staged files match the tool's patterns
        for staged_file in staged_files:
            for pattern in tool_config.file_patterns:
                if self._matches_pattern(staged_file.name, pattern):
                    return True

        return False

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches a pattern."""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)

    def _run_tool_fix(self, tool_config: ToolConfig) -> bool:
        """Run a tool's fix command."""
        self.logger.info(f"Running {tool_config.name}...")

        try:
            start_time = time.time()
            result = subprocess.run(
                tool_config.fix_command,
                check=False, capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=self.repo_path,
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                self.logger.info(f"✅ {tool_config.name} completed successfully ({execution_time:.2f}s)")

                # Check if tool actually made changes
                if self._tool_made_changes(result.stdout):
                    self.logger.info(f"   {tool_config.name} applied fixes")
                    return True
                self.logger.info(f"   {tool_config.name} no fixes needed")
                return False
            self.logger.warning(f"⚠️  {tool_config.name} failed (exit: {result.returncode})")
            if result.stderr:
                self.logger.debug(f"   Error: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            self.logger.warning(f"⚠️  {tool_config.name} timed out")
            return False
        except Exception as e:
            self.logger.warning(f"⚠️  {tool_config.name} error: {e}")
            return False

    def _tool_made_changes(self, output: str) -> bool:
        """Check if tool output indicates changes were made."""
        # Common indicators that changes were made
        change_indicators = [
            "fixed",
            "reformatted",
            "changed",
            "modified",
            "applied",
            "updated",
        ]

        output_lower = output.lower()
        return any(indicator in output_lower for indicator in change_indicators)

    def _get_git_status(self) -> str:
        """Get current git status."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                check=False, capture_output=True,
                text=True,
                cwd=self.repo_path,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def get_tool_status(self) -> dict[str, dict]:
        """Get status of all configured tools."""
        tool_status = {}

        for tool_config in self.schema.tools:
            is_available = self._check_tool_availability(tool_config.check)

            tool_status[tool_config.name] = {
                "available": is_available,
                "description": tool_config.description,
                "priority": tool_config.priority,
                "file_patterns": tool_config.file_patterns,
                "check_command": " ".join(tool_config.check.command),
                "fix_command": " ".join(tool_config.fix_command),
            }

        return tool_status

    def run_specific_tool(self, tool_name: str) -> bool:
        """Run a specific tool by name."""
        tool_config = next((t for t in self.schema.tools if t.name == tool_name), None)

        if not tool_config:
            self.logger.error(f"Tool not found: {tool_name}")
            return False

        if not self._check_tool_availability(tool_config.check):
            self.logger.error(f"Tool not available: {tool_name}")
            return False

        return self._run_tool_fix(tool_config)

    def add_custom_tool(self, tool_config: ToolConfig) -> None:
        """Add a custom tool configuration."""
        self.schema.tools.append(tool_config)
        self.logger.info(f"Added custom tool: {tool_config.name}")

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool configuration."""
        original_count = len(self.schema.tools)
        self.schema.tools = [t for t in self.schema.tools if t.name != tool_name]

        if len(self.schema.tools) < original_count:
            self.logger.info(f"Removed tool: {tool_name}")
            return True
        self.logger.warning(f"Tool not found for removal: {tool_name}")
        return False


class MultiProviderAutoFixer:
    """Auto-fixer for multi-provider projects."""

    def __init__(self, config: DGTConfig, schema: DuggerSchema) -> None:
        """Initialize multi-provider auto-fixer."""
        self.config = config
        self.schema = schema
        self.logger = logger.bind(multi_auto_fixer=True)

        if not schema.multi_provider:
            raise ValueError("Multi-provider configuration not found")

    def run_all_fixes(self, staged_files: list[Path] | None = None) -> bool:
        """Run fixes across all providers."""
        fixes_applied = False

        execution_order = self.schema.multi_provider.execution_order or self.schema.multi_provider.enabled_providers

        for provider_name in execution_order:
            if provider_name not in self.schema.multi_provider.enabled_providers:
                continue

            try:
                self.logger.info(f"Running fixes for provider: {provider_name}")
                provider_fixes = self._run_provider_fixes(provider_name, staged_files)

                if provider_fixes:
                    fixes_applied = True
                    self.logger.info(f"✅ {provider_name} fixes applied")
                else:
                    self.logger.info(f"ℹ️  {provider_name} no fixes needed")

            except Exception as e:
                self.logger.error(f"❌ {provider_name} fixes failed: {e}")

                if self.schema.multi_provider.fail_fast:
                    self.logger.error("Fail-fast enabled, stopping remaining providers")
                    break

        return fixes_applied

    def _run_provider_fixes(self, provider_name: str, staged_files: list[Path] | None) -> bool:
        """Run fixes for a specific provider."""
        # This would integrate with individual provider auto-fixers
        # For now, simulate the process
        self.logger.info(f"Would run {provider_name} auto-fixer")
        return False
