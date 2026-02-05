"""Audit Manager - Proactive security and code health scanning.

The "Beast Mode" defense layer:
1. Secret Sentry - Hardcoded credentials detection
2. Rot-Detector - Dependency vulnerability scanning
3. Vulture - Dead code detection
"""

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger


@dataclass
class SecretFinding:
    """A potential hardcoded secret."""

    file_path: Path
    line_number: int
    secret_type: str
    snippet: str
    entropy: float = 0.0


@dataclass
class VulnerabilityFinding:
    """A dependency vulnerability."""

    package: str
    version: str
    vulnerability_id: str
    severity: str
    description: str


@dataclass
class DeadCodeFinding:
    """Dead/unreachable code."""

    file_path: Path
    line_number: int
    item_type: str  # function, class, variable
    item_name: str


@dataclass
class AuditReport:
    """Complete audit report."""

    project_name: str
    project_type: str
    timestamp: str

    # Findings
    secrets: list[SecretFinding]
    vulnerabilities: list[VulnerabilityFinding]
    dead_code: list[DeadCodeFinding]

    # Metadata
    has_tests: bool
    has_gitignore: bool
    has_secrets_exposed: bool

    # Risk score (0-100, higher = more risk)
    risk_score: int

    # Warnings
    warnings: list[str]
    errors: list[str]


class AuditManager:
    """Centralized codebase security and health auditor.
    
    The "Eyes of the Machine" - Triple-scan architecture:
    - Secret Sentry: Regex-based credential detection
    - Rot-Detector: Dependency vulnerability scanning
    - Vulture: Dead code detection
    """

    # Common API key patterns
    SECRET_PATTERNS = {
        "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "Generic API Key": re.compile(r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', re.IGNORECASE),
        "Generic Secret": re.compile(r'["\']?secret["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', re.IGNORECASE),
        "Password": re.compile(r'["\']?password["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-@!#$%^&*]{8,})["\']', re.IGNORECASE),
        "Bearer Token": re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
        "Private Key": re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
        "OpenAI Key": re.compile(r"sk-[a-zA-Z0-9]{48}"),
        "Stripe Key": re.compile(r"sk_live_[a-zA-Z0-9]{24,}"),
        "Generic Token": re.compile(r'["\']?token["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{32,})["\']', re.IGNORECASE),
    }

    # File patterns to skip
    SKIP_PATTERNS = [
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
        ".pytest_cache",
        ".mypy_cache",
        "TODO_REPORT.md",
        "AUDIT_REPORT.md",
    ]

    def __init__(self, project_root: Path):
        """Initialize AuditManager.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.logger = logger.bind(component="AuditManager")

        self.secrets: list[SecretFinding] = []
        self.vulnerabilities: list[VulnerabilityFinding] = []
        self.dead_code: list[DeadCodeFinding] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def _should_skip(self, file_path: Path) -> bool:
        """Check if file should be skipped.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if should skip
        """
        for part in file_path.parts:
            if part in self.SKIP_PATTERNS:
                return True
        return False

    def scan_secrets(self) -> list[SecretFinding]:
        """Scan for hardcoded secrets (Secret Sentry).
        
        Returns:
            List of secret findings
        """
        self.logger.info("Running Secret Sentry scan...")
        findings = []

        # Scan all text files
        for ext in [".py", ".js", ".ts", ".yaml", ".yml", ".json", ".toml", ".env", ".sh"]:
            for file_path in self.project_root.rglob(f"*{ext}"):
                if self._should_skip(file_path):
                    continue

                try:
                    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, start=1):
                            # Check each pattern
                            for secret_type, pattern in self.SECRET_PATTERNS.items():
                                if pattern.search(line):
                                    findings.append(SecretFinding(
                                        file_path=file_path,
                                        line_number=line_num,
                                        secret_type=secret_type,
                                        snippet=line.strip()[:100],  # First 100 chars
                                    ))
                except Exception as e:
                    self.logger.debug(f"Could not scan {file_path}: {e}")

        self.secrets = findings
        self.logger.info(f"Secret Sentry found {len(findings)} potential secrets")
        return findings

    def scan_dependencies(self, project_type: str) -> list[VulnerabilityFinding]:
        """Scan dependencies for vulnerabilities (Rot-Detector).
        
        Args:
            project_type: Project type (python, rust, nodejs)
            
        Returns:
            List of vulnerability findings
        """
        self.logger.info("Running Rot-Detector scan...")
        findings = []

        if project_type == "python":
            findings.extend(self._scan_python_deps())
        elif project_type == "rust":
            findings.extend(self._scan_rust_deps())
        elif project_type == "nodejs":
            findings.extend(self._scan_node_deps())

        self.vulnerabilities = findings
        self.logger.info(f"Rot-Detector found {len(findings)} vulnerabilities")
        return findings

    def _scan_python_deps(self) -> list[VulnerabilityFinding]:
        """Scan Python dependencies with pip-audit.
        
        Returns:
            List of vulnerabilities
        """
        findings = []

        # Check if pip-audit is installed
        try:
            subprocess.run(
                ["pip-audit", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.warnings.append("pip-audit not installed (install: pip install pip-audit)")
            return findings

        # Run pip-audit
        try:
            result = subprocess.run(
                ["pip-audit", "--format", "json"],
                check=False, cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)

                for vuln in data.get("vulnerabilities", []):
                    findings.append(VulnerabilityFinding(
                        package=vuln.get("name", "unknown"),
                        version=vuln.get("version", "unknown"),
                        vulnerability_id=vuln.get("id", "unknown"),
                        severity=vuln.get("severity", "unknown"),
                        description=vuln.get("description", "")[:200],
                    ))

        except subprocess.TimeoutExpired:
            self.warnings.append("pip-audit timed out (skipping)")
        except Exception as e:
            self.warnings.append(f"pip-audit failed: {e}")

        return findings

    def _scan_rust_deps(self) -> list[VulnerabilityFinding]:
        """Scan Rust dependencies with cargo audit.
        
        Returns:
            List of vulnerabilities
        """
        findings = []

        if not (self.project_root / "Cargo.toml").exists():
            return findings

        # Check if cargo-audit is installed
        try:
            subprocess.run(
                ["cargo", "audit", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.warnings.append("cargo-audit not installed (install: cargo install cargo-audit)")
            return findings

        # Run cargo audit
        try:
            result = subprocess.run(
                ["cargo", "audit", "--json"],
                check=False, cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)

                for vuln in data.get("vulnerabilities", {}).get("list", []):
                    advisory = vuln.get("advisory", {})
                    findings.append(VulnerabilityFinding(
                        package=vuln.get("package", {}).get("name", "unknown"),
                        version=vuln.get("package", {}).get("version", "unknown"),
                        vulnerability_id=advisory.get("id", "unknown"),
                        severity="high",  # cargo audit doesn't provide severity
                        description=advisory.get("title", "")[:200],
                    ))

        except subprocess.TimeoutExpired:
            self.warnings.append("cargo audit timed out (skipping)")
        except Exception as e:
            self.warnings.append(f"cargo audit failed: {e}")

        return findings

    def _scan_node_deps(self) -> list[VulnerabilityFinding]:
        """Scan Node.js dependencies with npm audit.
        
        Returns:
            List of vulnerabilities
        """
        findings = []

        if not (self.project_root / "package.json").exists():
            return findings

        # Run npm audit
        try:
            result = subprocess.run(
                ["npm", "audit", "--json"],
                check=False, cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            import json
            data = json.loads(result.stdout)

            for vuln_id, vuln_data in data.get("vulnerabilities", {}).items():
                findings.append(VulnerabilityFinding(
                    package=vuln_id,
                    version=vuln_data.get("version", "unknown"),
                    vulnerability_id=vuln_data.get("via", [{}])[0].get("url", "unknown"),
                    severity=vuln_data.get("severity", "unknown"),
                    description=vuln_data.get("via", [{}])[0].get("title", "")[:200],
                ))

        except subprocess.TimeoutExpired:
            self.warnings.append("npm audit timed out (skipping)")
        except Exception as e:
            self.warnings.append(f"npm audit failed: {e}")

        return findings

    def scan_dead_code(self) -> list[DeadCodeFinding]:
        """Scan for dead code with vulture.
        
        Returns:
            List of dead code findings
        """
        self.logger.info("Running Vulture scan...")
        findings = []

        # Check if vulture is installed
        try:
            subprocess.run(
                ["vulture", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.warnings.append("vulture not installed (install: pip install vulture)")
            return findings

        # Run vulture on Python files
        try:
            result = subprocess.run(
                ["vulture", ".", "--min-confidence", "80"],
                check=False, cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Parse output
            for line in result.stdout.splitlines():
                if ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 3:
                        file_path = self.project_root / parts[0].strip()
                        try:
                            line_num = int(parts[1].strip())
                            message = parts[2].strip()

                            # Extract item type and name
                            if "unused function" in message:
                                item_type = "function"
                                item_name = message.split("'")[1] if "'" in message else "unknown"
                            elif "unused class" in message:
                                item_type = "class"
                                item_name = message.split("'")[1] if "'" in message else "unknown"
                            elif "unused variable" in message:
                                item_type = "variable"
                                item_name = message.split("'")[1] if "'" in message else "unknown"
                            else:
                                continue

                            findings.append(DeadCodeFinding(
                                file_path=file_path,
                                line_number=line_num,
                                item_type=item_type,
                                item_name=item_name,
                            ))
                        except (ValueError, IndexError):
                            continue

        except subprocess.TimeoutExpired:
            self.warnings.append("vulture timed out (skipping)")
        except Exception as e:
            self.warnings.append(f"vulture failed: {e}")

        self.dead_code = findings
        self.logger.info(f"Vulture found {len(findings)} dead code items")
        return findings

    def calculate_risk_score(self) -> int:
        """Calculate risk score (0-100, higher = more risk).
        
        Returns:
            Risk score
        """
        score = 0

        # Secrets (critical)
        score += len(self.secrets) * 30

        # High-severity vulnerabilities
        high_vulns = [v for v in self.vulnerabilities if v.severity in ["high", "critical"]]
        score += len(high_vulns) * 20

        # Medium vulnerabilities
        med_vulns = [v for v in self.vulnerabilities if v.severity == "medium"]
        score += len(med_vulns) * 5

        # Dead code (lower priority)
        score += min(len(self.dead_code) // 10, 10)  # Cap at 10

        # No tests
        if not (self.project_root / "tests").exists() and not (self.project_root / "test").exists():
            score += 10

        # No .gitignore
        if not (self.project_root / ".gitignore").exists():
            score += 5

        return min(score, 100)  # Cap at 100

    def run_full_audit(self, project_type: str = "python") -> AuditReport:
        """Run complete audit (secrets + dependencies + dead code).
        
        Args:
            project_type: Project type
            
        Returns:
            AuditReport
        """
        self.logger.info(f"Starting full audit of {self.project_root}")

        # Run scans
        self.scan_secrets()
        self.scan_dependencies(project_type)
        self.scan_dead_code()

        # Calculate metadata
        has_tests = (self.project_root / "tests").exists() or (self.project_root / "test").exists()
        has_gitignore = (self.project_root / ".gitignore").exists()
        has_secrets_exposed = len(self.secrets) > 0

        # Generate report
        report = AuditReport(
            project_name=self.project_root.name,
            project_type=project_type,
            timestamp=datetime.now().isoformat(),
            secrets=self.secrets,
            vulnerabilities=self.vulnerabilities,
            dead_code=self.dead_code,
            has_tests=has_tests,
            has_gitignore=has_gitignore,
            has_secrets_exposed=has_secrets_exposed,
            risk_score=self.calculate_risk_score(),
            warnings=self.warnings,
            errors=self.errors,
        )

        self.logger.info(f"Audit complete. Risk score: {report.risk_score}/100")
        return report

    def generate_markdown_report(self, report: AuditReport) -> str:
        """Generate markdown audit report.
        
        Args:
            report: AuditReport object
            
        Returns:
            Markdown-formatted report
        """
        lines = [
            "# Security & Code Health Audit Report",
            "",
            f"**Project**: {report.project_name}",
            f"**Project Type**: {report.project_type}",
            f"**Timestamp**: {report.timestamp}",
            f"**Risk Score**: {report.risk_score}/100",
            "",
            "---",
            "",
        ]

        # Risk level indicator
        if report.risk_score >= 70:
            lines.append("🔴 **CRITICAL RISK** - Immediate action required")
        elif report.risk_score >= 30:
            lines.append("🟡 **MODERATE RISK** - Review and address issues")
        else:
            lines.append("🟢 **LOW RISK** - Project is relatively healthy")

        lines.extend(["", "---", ""])

        # Secrets
        if report.secrets:
            lines.append(f"## 🔐 Hardcoded Secrets ({len(report.secrets)})")
            lines.append("")
            lines.append("**⚠️ CRITICAL: Remove these immediately!**")
            lines.append("")

            for secret in report.secrets[:20]:  # Limit to 20
                rel_path = secret.file_path.relative_to(self.project_root)
                lines.append(f"- **{secret.secret_type}** in [{rel_path}](file:///{secret.file_path}#L{secret.line_number}):{secret.line_number}")
                lines.append("  ```")
                lines.append(f"  {secret.snippet}")
                lines.append("  ```")

            if len(report.secrets) > 20:
                lines.append(f"... and {len(report.secrets) - 20} more")

            lines.extend(["", "---", ""])

        # Vulnerabilities
        if report.vulnerabilities:
            lines.append(f"## 🛡️ Dependency Vulnerabilities ({len(report.vulnerabilities)})")
            lines.append("")

            # Group by severity
            high = [v for v in report.vulnerabilities if v.severity in ["high", "critical"]]
            medium = [v for v in report.vulnerabilities if v.severity == "medium"]
            low = [v for v in report.vulnerabilities if v.severity == "low"]

            if high:
                lines.append(f"### 🔴 High/Critical ({len(high)})")
                lines.append("")
                for v in high[:10]:
                    lines.append(f"- **{v.package}** ({v.version})")
                    lines.append(f"  - ID: {v.vulnerability_id}")
                    lines.append(f"  - {v.description}")
                lines.append("")

            if medium:
                lines.append(f"### 🟡 Medium ({len(medium)})")
                lines.append("")
                for v in medium[:10]:
                    lines.append(f"- **{v.package}** ({v.version}) - {v.vulnerability_id}")
                lines.append("")

            lines.extend(["---", ""])

        # Dead code
        if report.dead_code:
            lines.append(f"## 🧹 Dead Code ({len(report.dead_code)})")
            lines.append("")
            lines.append("_Potentially unused code that can be safely removed:_")
            lines.append("")

            for item in report.dead_code[:20]:
                rel_path = item.file_path.relative_to(self.project_root)
                lines.append(f"- {item.item_type} `{item.item_name}` in [{rel_path}](file:///{item.file_path}#L{item.line_number}):{item.line_number}")

            if len(report.dead_code) > 20:
                lines.append(f"... and {len(report.dead_code) - 20} more")

            lines.extend(["", "---", ""])

        # Metadata
        lines.append("## 📊 Project Metadata")
        lines.append("")
        lines.append(f"- **Has Tests**: {'✅' if report.has_tests else '❌'}")
        lines.append(f"- **Has .gitignore**: {'✅' if report.has_gitignore else '❌'}")
        lines.append(f"- **Secrets Exposed**: {'🔴 YES' if report.has_secrets_exposed else '🟢 NO'}")

        # Warnings
        if report.warnings:
            lines.extend(["", "## ⚠️ Scan Warnings", ""])
            for warning in report.warnings:
                lines.append(f"- {warning}")

        # Recommendations
        lines.extend(["", "---", "", "## 💡 Recommendations", ""])

        if report.secrets:
            lines.append("1. **URGENT**: Move all secrets to environment variables or secret management")
        if report.vulnerabilities:
            lines.append("2. Update vulnerable dependencies immediately")
        if report.dead_code:
            lines.append("3. Review and remove dead code to reduce maintenance burden")
        if not report.has_tests:
            lines.append("4. Add test suite for better code quality")

        return "\n".join(lines)

    def save_report(self, report: AuditReport, output_path: Path | None = None) -> Path:
        """Save audit report to file.
        
        Args:
            report: AuditReport object
            output_path: Optional output path
            
        Returns:
            Path to saved report
        """
        if output_path is None:
            output_path = self.project_root / "AUDIT_REPORT.md"

        markdown = self.generate_markdown_report(report)

        with output_path.open("w", encoding="utf-8") as f:
            f.write(markdown)

        self.logger.info(f"Saved audit report to {output_path}")
        return output_path
