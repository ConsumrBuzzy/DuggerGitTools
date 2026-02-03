"""Enhanced auto-fixer with patterns from all analyzed projects."""

import subprocess
import time
from pathlib import Path
from typing import List, Optional

from loguru import logger

from .config import DGTConfig


class AutoFixer:
    """Advanced auto-fixer orchestrator with multi-language support."""
    
    def __init__(self, config: DGTConfig) -> None:
        """Initialize auto-fixer with configuration."""
        self.config = config
        self.logger = logger.bind(auto_fixer=True)
        self.repo_path = config.project_root
        self.fixes_applied = False
    
    def run_all_fixes(self, staged_files: Optional[List[Path]] = None) -> bool:
        """Run all applicable auto-fixes based on project type and files."""
        self.logger.info("Running auto-fixes...")
        self.fixes_applied = False
        
        # Get initial status
        initial_status = self._get_git_status()
        
        # Detect project type and run appropriate fixes
        project_type = self._detect_project_type()
        
        if project_type == "Python":
            self._run_python_fixes(staged_files)
        elif project_type == "Rust":
            self._run_rust_fixes()
        elif project_type == "Chrome Extension":
            self._run_chrome_fixes(staged_files)
        elif project_type == "Node.js":
            self._run_nodejs_fixes()
        
        # Run universal fixes
        self._run_universal_fixes()
        
        # Check if files changed
        final_status = self._get_git_status()
        if initial_status != final_status:
            self.logger.info("Files changed during fixes - will re-stage")
            self.fixes_applied = True
        
        self.logger.info(f"{'Fixes applied' if self.fixes_applied else 'No fixes needed'}")
        return self.fixes_applied
    
    def _detect_project_type(self) -> str:
        """Detect project type based on anchor files."""
        if (self.repo_path / "Cargo.toml").exists():
            return "Rust"
        elif (self.repo_path / "manifest.json").exists():
            return "Chrome Extension"
        elif (self.repo_path / "package.json").exists():
            return "Node.js"
        elif (self.repo_path / "requirements.txt").exists() or (self.repo_path / "pyproject.toml").exists():
            return "Python"
        else:
            return "Unknown"
    
    def _run_python_fixes(self, staged_files: Optional[List[Path]]) -> None:
        """Run Python-specific fixes (Brownbook/LDLA patterns)."""
        python_files = self._get_python_files(staged_files)
        
        if not python_files:
            return
        
        self.logger.info(f"Running Python fixes for {len(python_files)} files...")
        
        # 1. Ruff auto-fix (Brownbook pattern)
        if self._tool_available("ruff"):
            self.logger.info("  Running ruff auto-fix...")
            result = self._run_command(["ruff", "check", "--fix", "."])
            if result.returncode == 0 and "fixed" in result.stdout:
                self.logger.info("    ✅ Ruff fixes applied")
                self.fixes_applied = True
            else:
                self.logger.info("    ℹ️  No ruff fixes needed")
        
        # 2. Black formatting (Brownbook pattern)
        if self._tool_available("black"):
            self.logger.info("  Running black formatter...")
            try:
                result = self._run_command(
                    ["black", "--skip-string-normalization"] + python_files,
                    check=False
                )
                if result.returncode == 0 and "reformatted" in result.stdout:
                    self.logger.info("    ✅ Black formatting applied")
                    self.fixes_applied = True
                else:
                    self.logger.info("    ℹ️  No formatting needed")
            except Exception as e:
                self.logger.warning(f"    ⚠️  Black formatting error: {e}")
        
        # 3. isort (Brownbook pattern)
        if self._tool_available("isort"):
            self.logger.info("  Running isort...")
            try:
                result = self._run_command(
                    ["isort"] + python_files,
                    timeout=15,
                    check=False
                )
                if result.returncode == 0 and "Fixed" in result.stdout:
                    self.logger.info("    ✅ Import sorting applied")
                    self.fixes_applied = True
                else:
                    self.logger.info("    ℹ️  No import sorting needed")
            except Exception as e:
                self.logger.warning(f"    ⚠️  Import sorting error: {e}")
        
        # 4. mypy (if configured)
        if self._should_run_mypy():
            self._run_mypy_check()
    
    def _run_rust_fixes(self) -> None:
        """Run Rust-specific fixes."""
        self.logger.info("Running Rust fixes...")
        
        # 1. cargo fmt
        self.logger.info("  Running cargo fmt...")
        result = self._run_command(["cargo", "fmt", "--all"])
        if result.returncode == 0:
            self.logger.info("    ✅ Code formatted")
        else:
            self.logger.warning("    ⚠️  Cargo fmt failed")
        
        # 2. cargo clippy --fix
        self.logger.info("  Running cargo clippy --fix...")
        result = self._run_command(["cargo", "clippy", "--all", "--fix", "--allow-dirty", "--allow-staged"])
        if result.returncode == 0:
            self.logger.info("    ✅ Clippy fixes applied")
            self.fixes_applied = True
        else:
            self.logger.info("    ℹ️  No clippy fixes needed")
    
    def _run_chrome_fixes(self, staged_files: Optional[List[Path]]) -> None:
        """Run Chrome Extension-specific fixes."""
        self.logger.info("Running Chrome Extension fixes...")
        
        # 1. Validate manifest.json
        manifest_file = self.repo_path / "manifest.json"
        if manifest_file.exists():
            self._validate_manifest(manifest_file)
        
        # 2. JavaScript linting if available
        js_files = self._get_js_files(staged_files)
        if js_files and self._tool_available("eslint"):
            self.logger.info("  Running ESLint...")
            result = self._run_command(["npx", "eslint", "--fix"] + js_files, check=False)
            if result.returncode == 0:
                self.logger.info("    ✅ ESLint fixes applied")
                self.fixes_applied = True
    
    def _run_nodejs_fixes(self) -> None:
        """Run Node.js-specific fixes."""
        self.logger.info("Running Node.js fixes...")
        
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            # 1. npm install if package-lock.json changed
            package_lock = self.repo_path / "package-lock.json"
            if package_lock.exists():
                self.logger.info("  Running npm install...")
                result = self._run_command(["npm", "install"], check=False)
                if result.returncode == 0:
                    self.logger.info("    ✅ Dependencies installed")
            
            # 2. Run lint script if available
            self._run_npm_script("lint")
            self._run_npm_script("format")
    
    def _run_universal_fixes(self) -> None:
        """Run universal fixes applicable to all projects."""
        # 1. Pre-commit hooks (Brownbook pattern)
        if self._tool_available("pre-commit"):
            self.logger.info("  Running pre-commit hooks...")
            result = self._run_command(["pre-commit", "run", "--all-files"], check=False)
            if result.returncode != 0:
                self.logger.info("    ✅ Pre-commit hooks made additional fixes")
                self.fixes_applied = True
            else:
                self.logger.info("    ℹ️  Pre-commit hooks passed")
        
        # 2. Update documentation (GreenGap pattern)
        self._update_documentation()
        
        # 3. Build release (Convoso pattern)
        self._run_build_release()
    
    def _run_npm_script(self, script_name: str) -> None:
        """Run an npm script if it exists."""
        try:
            import json
            
            package_json = self.repo_path / "package.json"
            if package_json.exists():
                with package_json.open("r") as f:
                    package_data = json.load(f)
                
                scripts = package_data.get("scripts", {})
                if script_name in scripts:
                    self.logger.info(f"  Running npm run {script_name}...")
                    result = self._run_command(["npm", "run", script_name], check=False)
                    if result.returncode == 0:
                        self.logger.info(f"    ✅ {script_name} completed")
                        self.fixes_applied = True
        except Exception as e:
            self.logger.warning(f"    ⚠️  npm run {script_name} failed: {e}")
    
    def _validate_manifest(self, manifest_file: Path) -> None:
        """Validate Chrome Extension manifest.json."""
        try:
            import json
            
            with manifest_file.open("r") as f:
                manifest = json.load(f)
            
            # Basic validation
            required_fields = ["manifest_version", "name", "version"]
            missing = [field for field in required_fields if field not in manifest]
            
            if missing:
                self.logger.warning(f"    ⚠️  Missing manifest fields: {missing}")
            else:
                self.logger.info("    ✅ Manifest validation passed")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"    ❌ Invalid JSON in manifest.json: {e}")
    
    def _update_documentation(self) -> None:
        """Update project documentation (GreenGap pattern)."""
        # Check if this is a documentation-heavy project
        if (self.repo_path / "backend").exists():
            self._generate_api_docs()
        
        # Check for architecture generator (Brownbook pattern)
        arch_generator = self.repo_path / "arch_generator.py"
        if arch_generator.exists():
            self.logger.info("  Updating architecture documentation...")
            result = self._run_command(
                ["python", "arch_generator.py", "--format", "docs"],
                check=False
            )
            if result.returncode == 0:
                self.logger.info("    ✅ Architecture documentation updated")
                self.fixes_applied = True
    
    def _generate_api_docs(self) -> None:
        """Generate API documentation (GreenGap pattern)."""
        docs_dir = self.repo_path / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        api_doc = docs_dir / "API.md"
        
        # Simple API doc generation
        content = f"""# API Documentation

*Auto-generated on {time.strftime('%Y-%m-%d %H:%M')}*

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/state` | GET | Get current state |
| `/tick` | POST | Advance simulation |
"""
        
        api_doc.write_text(content)
        self.logger.info("    ✅ API documentation generated")
        self.fixes_applied = True
    
    def _run_build_release(self) -> None:
        """Run release build (Convoso pattern)."""
        # Check for PowerShell build script
        build_script = self.repo_path / "scripts" / "build-release.ps1"
        if build_script.exists():
            self.logger.info("  Running release build...")
            
            # Detect PowerShell
            shell = "pwsh" if Path("C:/Program Files/PowerShell/7/pwsh.exe").exists() else "powershell"
            
            try:
                result = self._run_command(
                    [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(build_script)],
                    check=False
                )
                if result.returncode == 0:
                    self.logger.info("    ✅ Release build successful")
                    self.fixes_applied = True
                else:
                    self.logger.warning("    ⚠️  Release build failed")
            except Exception as e:
                self.logger.warning(f"    ⚠️  Release build error: {e}")
    
    def _run_mypy_check(self) -> None:
        """Run mypy type checking."""
        if not self._tool_available("mypy"):
            return
        
        self.logger.info("  Running mypy...")
        result = self._run_command(["mypy", "."], check=False)
        if result.returncode == 0:
            self.logger.info("    ✅ Type checking passed")
        else:
            self.logger.warning("    ⚠️  Type issues found (not auto-fixable)")
    
    def _get_python_files(self, staged_files: Optional[List[Path]]) -> List[str]:
        """Get list of Python files to process."""
        if staged_files:
            return [str(f) for f in staged_files if f.suffix == ".py"]
        
        # Get all Python files in repo
        try:
            result = self._run_command(["git", "diff", "--name-only", "--cached", "*.py"])
            if result.returncode == 0:
                files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
                return files
        except Exception:
            pass
        
        return []
    
    def _get_js_files(self, staged_files: Optional[List[Path]]) -> List[str]:
        """Get list of JavaScript files to process."""
        if staged_files:
            return [str(f) for f in staged_files if f.suffix in [".js", ".mjs"]]
        
        return []
    
    def _get_git_status(self) -> str:
        """Get current git status."""
        try:
            result = self._run_command(["git", "status", "--porcelain"])
            return result.stdout.strip()
        except Exception:
            return ""
    
    def _tool_available(self, tool: str) -> bool:
        """Check if a tool is available."""
        try:
            result = self._run_command([tool, "--version"], check=False)
            return result.returncode == 0
        except Exception:
            return False
    
    def _should_run_mypy(self) -> bool:
        """Check if mypy should be run."""
        pyproject_toml = self.repo_path / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                import tomllib
                with pyproject_toml.open("rb") as f:
                    data = tomllib.load(f)
                return "mypy" in data.get("tool", {})
            except Exception:
                pass
        return False
    
    def _run_command(
        self,
        cmd: List[str],
        check: bool = False,
        capture_output: bool = True,
        timeout: Optional[int] = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command in the repo directory."""
        try:
            return subprocess.run(
                cmd,
                cwd=self.repo_path,
                check=check,
                capture_output=capture_output,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Command timed out: {' '.join(cmd)}")
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="Command timed out"
            )
