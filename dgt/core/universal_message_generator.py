"""Universal message generator with LLM integration and project context."""

from pathlib import Path
from typing import Any

from loguru import logger

from .config import DGTConfig
from .git_operations import GitOperations
from .schema import DuggerSchema, ProjectType


class UniversalMessageGenerator:
    """Language-agnostic message generator with LLM enhancement."""

    def __init__(self, config: DGTConfig, schema: DuggerSchema) -> None:
        """Initialize universal message generator."""
        self.config = config
        self.schema = schema
        self.logger = logger.bind(message_generator=True)
        self.git_ops = GitOperations(config)
        self.repo_path = config.project_root

    def generate_smart_message(
        self,
        files: list[str],
        line_numbers: dict[str, str] | None = None,
        use_llm: bool | None = None,
    ) -> str:
        """Generate intelligent commit message based on changes."""
        if not files:
            return "No changes to commit"

        # Determine if LLM should be used
        should_use_llm = use_llm if use_llm is not None else self.schema.llm_enabled

        # Try LLM enhancement first if enabled
        if should_use_llm:
            try:
                llm_message = self._generate_llm_message(files, line_numbers)
                if llm_message:
                    return llm_message
            except Exception as e:
                self.logger.warning(f"LLM message generation failed: {e}")

        # Fall back to rule-based generation
        return self._generate_rule_based_message(files, line_numbers or {})

    def _generate_llm_message(
        self,
        files: list[str],
        line_numbers: dict[str, str] | None = None,
    ) -> str | None:
        """Generate LLM-enhanced commit message."""
        try:
            # Prepare context for LLM
            context = self._build_llm_context(files, line_numbers or {})
            prompt = self._build_llm_prompt(context)

            # Try different LLM providers
            llm_providers = ["ollama", "openai", "claude"]

            for provider in llm_providers:
                try:
                    response = self._call_llm_provider(provider, prompt)
                    if response:
                        return self._process_llm_response(response)
                except Exception as e:
                    self.logger.debug(f"LLM provider {provider} failed: {e}")
                    continue

            return None

        except Exception as e:
            self.logger.debug(f"LLM generation failed: {e}")
            return None

    def _build_llm_context(self, files: list[str], line_numbers: dict[str, str]) -> dict[str, Any]:
        """Build comprehensive context for LLM."""
        # Get git diff summary
        diff_summary = self.git_ops.get_diff_summary()

        # Categorize files
        categorized_files = self._categorize_files(files)

        # Detect change types
        change_types = self._detect_change_types(files)

        # Get project-specific context
        project_context = self._get_project_context()

        return {
            "files": files,
            "line_numbers": line_numbers,
            "diff_summary": diff_summary,
            "categorized_files": categorized_files,
            "change_types": change_types,
            "project_context": project_context,
            "message_style": self.schema.message_style,
            "project_type": self.schema.project_type.value,
        }

    def _build_llm_prompt(self, context: dict[str, Any]) -> str:
        """Build LLM prompt with project context."""
        project_type = context["project_type"]
        message_style = context["message_style"]

        # Build file context
        files_context = ""
        for file in context["files"][:10]:  # Limit to 10 files
            line_info = context["line_numbers"].get(file, "")
            files_context += f"- {file} {line_info}\n"

        if len(context["files"]) > 10:
            files_context += f"- ... and {len(context['files']) - 10} more files\n"

        # Build change types context
        change_types = ", ".join(context["change_types"])

        # Build project-specific context
        project_context = ""
        if context["project_context"]:
            project_context = f"\nProject Context: {context['project_context']}"

        base_prompt = f"""Generate a commit message for these changes:

Project Type: {project_type}
Message Style: {message_style}
Change Types: {change_types}{project_context}

Changed Files:
{files_context}

Requirements:
- Use {message_style} commit format
- Be descriptive but concise (max 50 characters for title)
- Focus on the 'why' not the 'what'
- Include relevant project context
- Use appropriate scope/type based on project type"""

        # Add style-specific instructions
        if message_style == "conventional":
            base_prompt += """
- Use conventional commit format: type(scope): description
- Types: feat, fix, docs, style, refactor, test, chore, perf, ci, build
- Scope should be relevant to project type"""

        elif message_style == "semantic":
            base_prompt += """
- Use semantic versioning impact: major, minor, patch
- Include breaking change indicators if applicable"""

        # Add project-specific instructions
        if project_type == "solana":
            base_prompt += """
- For Solana: consider gas optimization, program updates, instruction changes
- Use scope like 'program', 'client', 'tests', 'anchor'"""

        elif project_type == "chrome-extension":
            base_prompt += """
- For Chrome Extensions: consider manifest changes, UI updates, background scripts
- Use scope like 'manifest', 'popup', 'content', 'background'"""

        elif project_type == "rust":
            base_prompt += """
- For Rust: consider API changes, performance improvements, dependency updates
- Use scope like 'api', 'perf', 'deps', 'cargo'"""

        base_prompt += """

Generate only the commit message, no explanation:"""

        return base_prompt

    def _call_llm_provider(self, provider: str, prompt: str) -> str | None:
        """Call specific LLM provider."""
        if provider == "ollama":
            return self._call_ollama(prompt)
        if provider == "openai":
            return self._call_openai(prompt)
        if provider == "claude":
            return self._call_claude(prompt)
        raise ValueError(f"Unknown LLM provider: {provider}")

    def _call_ollama(self, prompt: str) -> str | None:
        """Call Ollama LLM provider."""
        try:
            import requests

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama2",
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()

        except Exception as e:
            self.logger.debug(f"Ollama call failed: {e}")

        return None

    def _call_openai(self, prompt: str) -> str | None:
        """Call OpenAI API."""
        try:
            import openai

            # Check for API key
            if not hasattr(openai, "api_key") or not openai.api_key:
                return None

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.7,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.debug(f"OpenAI call failed: {e}")

        return None

    def _call_claude(self, prompt: str) -> str | None:
        """Call Claude API."""
        # Placeholder for Claude integration
        return None

    def _process_llm_response(self, response: str) -> str:
        """Process and clean LLM response."""
        # Remove common LLM artifacts
        cleaned = response.strip()

        # Remove quotes if entire response is quoted
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]

        # Remove common prefixes
        prefixes_to_remove = ["Commit message:", "Message:", "Here's the commit message:"]
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()

        return cleaned

    def _generate_rule_based_message(self, files: list[str], line_numbers: dict[str, str]) -> str:
        """Generate rule-based commit message."""
        # Categorize files
        categorized = self._categorize_files(files)

        # Determine primary category
        primary_category = self._get_primary_category(categorized)

        # Get prefix based on style and project type
        prefix = self._get_message_prefix(primary_category)

        # Build title
        if len(files) == 1:
            title = f"{prefix}{Path(files[0]).name}"
        else:
            title = f"{prefix}{self._describe_changes(categorized)}"

        # Build body with file details
        body_lines = []
        for file in files[:8]:  # Limit to 8 files
            line_info = line_numbers.get(file, "")
            if line_info:
                body_lines.append(f"- {file} ({line_info})")
            else:
                body_lines.append(f"- {file}")

        if len(files) > 8:
            body_lines.append(f"- ... and {len(files) - 8} more files")

        body = "\n".join(body_lines)
        return f"{title}\n\n{body}" if body else title

    def _categorize_files(self, files: list[str]) -> dict[str, list[str]]:
        """Categorize files using universal patterns."""
        categories = {
            "src": ["src/", "lib/", "programs/", "contracts/"],
            "tests": ["test/", "tests/", "spec/", "__tests__/"],
            "docs": ["docs/", ".md", "readme", "doc/"],
            "config": [".toml", ".yaml", ".yml", ".json", "config/", ".env"],
            "build": ["build/", "dist/", "target/", "node_modules/"],
            "scripts": ["scripts/", "bin/", "tools/", ".sh", ".ps1", ".bat"],
            "assets": ["assets/", "static/", "public/", "images/", "icons/"],
            "deps": ["vendor/", "third_party/", "external/"],
        }

        # Add project-specific categories
        if self.schema.project_type == ProjectType.SOLANA:
            categories.update({
                "programs": ["programs/", "src/"],
                "anchor": ["Anchor.toml"],
                "client": ["client/", "sdk/"],
            })
        elif self.schema.project_type == ProjectType.CHROME_EXTENSION:
            categories.update({
                "manifest": ["manifest.json"],
                "popup": ["popup.html", "popup.js"],
                "content": ["content.js"],
                "background": ["background.js"],
            })

        categorized = {cat: [] for cat in categories}
        categorized["other"] = []

        for file in files:
            file_lower = file.lower()
            placed = False

            for category, patterns in categories.items():
                for pattern in patterns:
                    if pattern in file_lower:
                        categorized[category].append(file)
                        placed = True
                        break
                if placed:
                    break

            if not placed:
                categorized["other"].append(file)

        return categorized

    def _get_primary_category(self, categorized: dict[str, list[str]]) -> str:
        """Determine primary category with priority ordering."""
        # Priority order based on common development patterns
        priority = [
            "programs", "src", "lib",  # Source code
            "manifest", "popup", "content", "background",  # Chrome extension
            "anchor", "client",  # Solana specific
            "tests",  # Tests
            "config",  # Configuration
            "build", "scripts",  # Build and scripts
            "docs", "assets", "deps",  # Documentation and assets
            "other",
        ]

        for category in priority:
            if categorized.get(category):
                return category

        return "other"

    def _get_message_prefix(self, category: str) -> str:
        """Get message prefix based on style and category."""
        if self.schema.message_style == "conventional":
            conventional_prefixes = {
                "src": "feat(src): ",
                "programs": "feat(programs): ",
                "tests": "test: ",
                "docs": "docs: ",
                "config": "config: ",
                "build": "build: ",
                "scripts": "chore: ",
                "manifest": "chore(manifest): ",
                "popup": "feat(popup): ",
                "content": "feat(content): ",
                "background": "feat(background): ",
                "anchor": "feat(anchor): ",
                "client": "feat(client): ",
                "other": "chore: ",
            }
            return conventional_prefixes.get(category, "chore: ")

        # Default style
        return f"{category}: " if category != "other" else ""

    def _describe_changes(self, categorized: dict[str, list[str]]) -> str:
        """Generate description of changes."""
        non_empty = {k: v for k, v in categorized.items() if v}

        if len(non_empty) == 1:
            category = list(non_empty.keys())[0]
            count = len(non_empty[category])
            return f"{count} {category} file{'s' if count > 1 else ''}"

        total = sum(len(v) for v in non_empty.values())
        return f"{total} files across {len(non_empty)} areas"

    def _detect_change_types(self, files: list[str]) -> list[str]:
        """Detect types of changes based on file patterns."""
        change_types = []

        # Look for common change patterns
        for file in files:
            if "test" in file.lower():
                change_types.append("tests")
            elif file.endswith(".md"):
                change_types.append("documentation")
            elif any(pattern in file for pattern in ["requirements.txt", "package.json", "Cargo.toml", "pyproject.toml"]):
                change_types.append("dependencies")
            elif file.lower().startswith("readme"):
                change_types.append("documentation")
            elif "config" in file.lower() or file.endswith((".yaml", ".yml", ".toml", ".json")):
                change_types.append("configuration")

        return list(set(change_types)) or ["code"]

    def _get_project_context(self) -> str:
        """Get project-specific context from LLM configuration."""
        return self.schema.llm_context.get("description", "")
