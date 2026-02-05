"""Documentation merger for multi-provider projects."""

import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from .config import DGTConfig
from .schema import DuggerSchema


class DocsMerger:
    """Merge documentation from multiple providers into unified docs."""

    def __init__(self, config: DGTConfig, schema: DuggerSchema) -> None:
        """Initialize documentation merger."""
        self.config = config
        self.schema = schema
        self.logger = logger.bind(docs_merger=True)
        self.repo_path = config.project_root

    def merge_all_documentation(self, output_file: str = "ARCH.md") -> bool:
        """Merge all documentation into unified architecture document."""
        try:
            self.logger.info("Starting documentation merge...")

            # Collect documentation from all sources
            doc_sections = self._collect_documentation_sections()

            if not doc_sections:
                self.logger.warning("No documentation sections found")
                return False

            # Generate merged document
            merged_content = self._generate_merged_document(doc_sections)

            # Write merged document
            output_path = self.repo_path / output_file
            output_path.write_text(merged_content, encoding="utf-8")

            self.logger.info(f"Documentation merged successfully: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Documentation merge failed: {e}")
            return False

    def _collect_documentation_sections(self) -> dict[str, dict[str, Any]]:
        """Collect documentation sections from all providers."""
        sections = {}

        # Python documentation
        python_docs = self._collect_python_docs()
        if python_docs:
            sections["python"] = python_docs

        # Rust documentation
        rust_docs = self._collect_rust_docs()
        if rust_docs:
            sections["rust"] = rust_docs

        # Chrome Extension documentation
        chrome_docs = self._collect_chrome_docs()
        if chrome_docs:
            sections["chrome"] = chrome_docs

        # API documentation
        api_docs = self._collect_api_docs()
        if api_docs:
            sections["api"] = api_docs

        # Architecture documentation
        arch_docs = self._collect_arch_docs()
        if arch_docs:
            sections["architecture"] = arch_docs

        # Project README
        readme_docs = self._collect_readme_docs()
        if readme_docs:
            sections["overview"] = readme_docs

        return sections

    def _collect_python_docs(self) -> dict[str, Any] | None:
        """Collect Python-specific documentation."""
        docs = {
            "title": "Python Components",
            "content": "",
            "subsections": {},
        }

        # API docs from docstrings
        api_doc = self.repo_path / "docs" / "API.md"
        if api_doc.exists():
            docs["subsections"]["api"] = {
                "title": "API Documentation",
                "content": api_doc.read_text(encoding="utf-8"),
            }

        # Module documentation
        pyproject_toml = self.repo_path / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                import tomllib
                with pyproject_toml.open("rb") as f:
                    data = tomllib.load(f)

                project_info = data.get("project", {})
                description = project_info.get("description", "")
                if description:
                    docs["subsections"]["description"] = {
                        "title": "Project Description",
                        "content": description,
                    }
            except Exception:
                pass

        # Collect Python module docs
        for py_file in self.repo_path.rglob("*.py"):
            if self._should_include_python_file(py_file):
                module_docs = self._extract_python_module_docs(py_file)
                if module_docs:
                    module_name = py_file.relative_to(self.repo_path).with_suffix("")
                    docs["subsections"][str(module_name)] = module_docs

        return docs if docs["subsections"] else None

    def _collect_rust_docs(self) -> dict[str, Any] | None:
        """Collect Rust-specific documentation."""
        docs = {
            "title": "Rust Components",
            "content": "",
            "subsections": {},
        }

        # Cargo documentation
        cargo_toml = self.repo_path / "Cargo.toml"
        if cargo_toml.exists():
            try:
                import tomllib
                with cargo_toml.open("rb") as f:
                    data = tomllib.load(f)

                package_info = data.get("package", {})
                description = package_info.get("description", "")
                if description:
                    docs["subsections"]["description"] = {
                        "title": "Package Description",
                        "content": description,
                    }

                # Dependencies
                dependencies = data.get("dependencies", {})
                if dependencies:
                    deps_content = "\n".join(f"- {name}: {version}" for name, version in dependencies.items())
                    docs["subsections"]["dependencies"] = {
                        "title": "Dependencies",
                        "content": deps_content,
                    }
            except Exception:
                pass

        # Rust documentation comments
        for rs_file in self.repo_path.rglob("*.rs"):
            if self._should_include_rust_file(rs_file):
                module_docs = self._extract_rust_module_docs(rs_file)
                if module_docs:
                    module_name = rs_file.relative_to(self.repo_path).with_suffix("")
                    docs["subsections"][str(module_name)] = module_docs

        return docs if docs["subsections"] else None

    def _collect_chrome_docs(self) -> dict[str, Any] | None:
        """Collect Chrome Extension documentation."""
        docs = {
            "title": "Chrome Extension",
            "content": "",
            "subsections": {},
        }

        # Manifest documentation
        manifest_json = self.repo_path / "manifest.json"
        if manifest_json.exists():
            try:
                manifest = json.loads(manifest_json.read_text(encoding="utf-8"))

                # Extension info
                name = manifest.get("name", "Unknown Extension")
                description = manifest.get("description", "")
                version = manifest.get("version", "0.0.0")

                docs["subsections"]["info"] = {
                    "title": "Extension Information",
                    "content": f"**Name:** {name}\n**Version:** {version}\n**Description:** {description}",
                }

                # Permissions
                permissions = manifest.get("permissions", [])
                if permissions:
                    perms_content = "\n".join(f"- {perm}" for perm in permissions)
                    docs["subsections"]["permissions"] = {
                        "title": "Permissions",
                        "content": perms_content,
                    }

                # Components
                components = []
                if "background" in manifest:
                    components.append("Background Service Worker")
                if "content_scripts" in manifest:
                    components.append("Content Scripts")
                if "action" in manifest:
                    components.append("Popup/Action")

                if components:
                    comps_content = "\n".join(f"- {comp}" for comp in components)
                    docs["subsections"]["components"] = {
                        "title": "Components",
                        "content": comps_content,
                    }

            except Exception:
                pass

        return docs if docs["subsections"] else None

    def _collect_api_docs(self) -> dict[str, Any] | None:
        """Collect API documentation."""
        docs = {
            "title": "API Documentation",
            "content": "",
            "subsections": {},
        }

        # Look for OpenAPI/Swagger specs
        for api_file in self.repo_path.rglob("*api*.json"):
            try:
                api_spec = json.loads(api_file.read_text(encoding="utf-8"))
                if "paths" in api_spec:
                    # Extract endpoints
                    endpoints = []
                    for path, methods in api_spec["paths"].items():
                        for method in methods.keys():
                            endpoints.append(f"{method.upper()} {path}")

                    if endpoints:
                        endpoints_content = "\n".join(f"- {ep}" for ep in endpoints)
                        docs["subsections"][api_file.stem] = {
                            "title": f"{api_file.stem.title()} Endpoints",
                            "content": endpoints_content,
                        }
            except Exception:
                pass

        # Look for API documentation files
        for doc_file in self.repo_path.rglob("*api*.md"):
            content = doc_file.read_text(encoding="utf-8")
            if content.strip():
                docs["subsections"][doc_file.stem] = {
                    "title": doc_file.stem.replace("-", " ").replace("_", " ").title(),
                    "content": content,
                }

        return docs if docs["subsections"] else None

    def _collect_arch_docs(self) -> dict[str, Any] | None:
        """Collect architecture documentation."""
        docs = {
            "title": "Architecture",
            "content": "",
            "subsections": {},
        }

        # Look for architecture files
        arch_patterns = ["*arch*.md", "*design*.md", "*architecture*.md"]

        for pattern in arch_patterns:
            for arch_file in self.repo_path.rglob(pattern):
                content = arch_file.read_text(encoding="utf-8")
                if content.strip():
                    docs["subsections"][arch_file.stem] = {
                        "title": arch_file.stem.replace("-", " ").replace("_", " ").title(),
                        "content": content,
                    }

        return docs if docs["subsections"] else None

    def _collect_readme_docs(self) -> dict[str, Any] | None:
        """Collect README documentation."""
        readme_files = [
            self.repo_path / "README.md",
            self.repo_path / "readme.md",
            self.repo_path / "README.rst",
        ]

        for readme_file in readme_files:
            if readme_file.exists():
                content = readme_file.read_text(encoding="utf-8")
                if content.strip():
                    return {
                        "title": "Project Overview",
                        "content": content,
                        "subsections": {},
                    }

        return None

    def _should_include_python_file(self, py_file: Path) -> bool:
        """Determine if Python file should be included in docs."""
        # Skip test files, __pycache__, etc.
        exclude_patterns = [
            "test_",
            "_test",
            "__pycache__",
            "venv",
            ".venv",
            "site-packages",
        ]

        file_path_str = str(py_file)
        return not any(pattern in file_path_str for pattern in exclude_patterns)

    def _should_include_rust_file(self, rs_file: Path) -> bool:
        """Determine if Rust file should be included in docs."""
        # Skip test files, target directory, etc.
        exclude_patterns = [
            "test",
            "tests",
            "target",
            "Cargo.lock",
        ]

        file_path_str = str(rs_file)
        return not any(pattern in file_path_str for pattern in exclude_patterns)

    def _extract_python_module_docs(self, py_file: Path) -> dict[str, Any] | None:
        """Extract documentation from Python module."""
        try:
            content = py_file.read_text(encoding="utf-8")

            # Extract module docstring
            module_docstring = self._extract_module_docstring(content)
            if not module_docstring:
                return None

            # Extract class and function docstrings
            classes = self._extract_python_classes(content)
            functions = self._extract_python_functions(content)

            doc_content = module_docstring

            if classes:
                doc_content += "\n\n## Classes\n\n"
                for class_name, class_doc in classes.items():
                    doc_content += f"### {class_name}\n\n{class_doc}\n\n"

            if functions:
                doc_content += "\n## Functions\n\n"
                for func_name, func_doc in functions.items():
                    doc_content += f"### {func_name}\n\n{func_doc}\n\n"

            return {
                "title": py_file.stem.replace("_", " ").replace("-", " ").title(),
                "content": doc_content.strip(),
            }

        except Exception:
            return None

    def _extract_rust_module_docs(self, rs_file: Path) -> dict[str, Any] | None:
        """Extract documentation from Rust module."""
        try:
            content = rs_file.read_text(encoding="utf-8")

            # Extract Rust documentation comments
            doc_comments = self._extract_rust_doc_comments(content)

            if not doc_comments:
                return None

            return {
                "title": rs_file.stem.replace("_", " ").replace("-", " ").title(),
                "content": doc_comments,
            }

        except Exception:
            return None

    def _extract_module_docstring(self, content: str) -> str | None:
        """Extract module docstring from Python content."""
        # Look for triple quotes at the beginning
        match = re.search(r'^\s*"""(.*?)"""', content, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()

        # Look for single quotes
        match = re.search(r"^\s*'''(.*?)'''", content, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()

        return None

    def _extract_python_classes(self, content: str) -> dict[str, str]:
        """Extract class documentation from Python content."""
        classes = {}

        # Find class definitions with docstrings
        class_pattern = r'^\s*class\s+(\w+).*?:\s*(?:.*?"""(.*?)""")?'
        matches = re.findall(class_pattern, content, re.MULTILINE | re.DOTALL)

        for class_name, docstring in matches:
            if docstring:
                classes[class_name] = docstring.strip()

        return classes

    def _extract_python_functions(self, content: str) -> dict[str, str]:
        """Extract function documentation from Python content."""
        functions = {}

        # Find function definitions with docstrings
        func_pattern = r'^\s*def\s+(\w+).*?:\s*(?:.*?"""(.*?)""")?'
        matches = re.findall(func_pattern, content, re.MULTILINE | re.DOTALL)

        for func_name, docstring in matches:
            if docstring:
                functions[func_name] = docstring.strip()

        return functions

    def _extract_rust_doc_comments(self, content: str) -> str | None:
        """Extract documentation comments from Rust content."""
        # Look for /// comments and /*! ... */ blocks
        doc_lines = []
        in_doc_block = False

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("///"):
                doc_lines.append(line[3:].strip())
            elif line.startswith("/*!"):
                in_doc_block = True
            elif line.startswith("*/") and in_doc_block:
                in_doc_block = False
            elif in_doc_block and not line.startswith("/*"):
                doc_lines.append(line)

        return "\n".join(doc_lines) if doc_lines else None

    def _generate_merged_document(self, sections: dict[str, dict[str, Any]]) -> str:
        """Generate merged documentation document."""
        # Document header
        header = f"""# {self.schema.project_type.value.title()} Architecture Documentation

*Auto-generated by DuggerCore-Universal*
*Generated on {self._get_current_timestamp()}*

## Table of Contents

"""

        # Generate table of contents
        toc_items = []
        for section_key, section_data in sections.items():
            toc_items.append(f"- [{section_data['title']}](#{section_key.lower()})")

            for sub_key in section_data.get("subsections", {}):
                sub_title = section_data["subsections"][sub_key]["title"]
                toc_items.append(f"  - [{sub_title}](#{sub_key.lower()})")

        header += "\n".join(toc_items) + "\n\n---\n\n"

        # Generate sections
        content = header

        for section_key, section_data in sections.items():
            content += f"## {section_data['title']}\n\n"

            if section_data.get("content"):
                content += section_data["content"] + "\n\n"

            # Add subsections
            subsections = section_data.get("subsections", {})
            for sub_key, sub_data in subsections.items():
                content += f"### {sub_data['title']}\n\n"
                content += sub_data["content"] + "\n\n"

            content += "---\n\n"

        # Add footer
        content += f"""
## Generation Information

- **Project Type:** {self.schema.project_type.value}
- **Providers:** {', '.join(self.schema.multi_provider.enabled_providers) if self.schema.multi_provider else 'Single'}
- **Sections Merged:** {len(sections)}
- **Generated by:** DuggerCore-Universal
- **Timestamp:** {self._get_current_timestamp()}

---

*This document is automatically generated. Do not edit manually.*
"""

        return content

    def _get_current_timestamp(self) -> str:
        """Get current timestamp for documentation."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
