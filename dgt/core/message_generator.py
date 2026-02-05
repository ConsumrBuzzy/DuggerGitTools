"""Enhanced message generator with patterns from all analyzed projects."""

from pathlib import Path

from loguru import logger

from .config import DGTConfig


class MessageGenerator:
    """Advanced commit message generator with project-specific patterns."""

    def __init__(self, config: DGTConfig) -> None:
        """Initialize message generator with configuration."""
        self.config = config
        self.logger = logger.bind(message_generator=True)

        # Consolidated categories from all projects
        self.CATEGORIES = {
            # Python/Brownbook patterns
            "ui": ["ui/", "components", "dialogs", "styles"],
            "utils": ["utils/", "shared_utils"],
            "main": ["main.py", "cli_args"],
            "config": ["config.py", "presets", "styles.py"],
            "test": ["test_", "tests/"],
            "docs": [".md", "readme", "doc"],
            "pipeline": ["pipeline.py"],
            "convert": ["convert_excel"],
            "clean": ["file_cleaner"],
            "drop": ["column_dropper"],
            "rename": ["column_renamer"],
            "map": ["column_mapper"],
            "address": ["address_formatter", "address_parser"],
            "phone": ["phone_formatter", "phone_deduplicator"],
            "state": ["state_lookup"],
            "scrub": ["fuzzy_scrubber", "fuzzy_deduplicator"],
            "email": ["email_validator"],
            "batch": ["batch_splitter"],
            "gemini": ["gemini_sic_enricher"],

            # Chrome Extension patterns
            "content": ["content.js"],
            "popup": ["popup.html", "popup.js"],
            "manifest": ["manifest.json"],
            "storage": ["storage.js"],
            "styles": ["styles.css"],
            "background": ["background.js"],
            "scripts": ["scripts/", ".ps1", ".sh"],
            "release": ["release/"],

            # Game/GreenGap patterns
            "backend": ["backend/"],
            "game": ["run_game.py"],
            "engine": ["engine.py"],

            # General patterns
            "build": ["build_", "makefile", "dockerfile"],
            "deploy": ["deploy", ".yml", ".yaml"],
            "ci": ["github/", ".gitlab-ci.yml"],
            "deps": ["requirements.txt", "pyproject.toml", "package.json", "cargo.toml"],
        }

        self.PREFIXES = {
            "ui": "feat(ui): ",
            "utils": "feat(utils): ",
            "main": "feat(main): ",
            "config": "config: ",
            "test": "test: ",
            "docs": "docs: ",
            "pipeline": "feat(pipeline): ",
            "convert": "feat(convert): ",
            "clean": "feat(clean): ",
            "drop": "feat(drop): ",
            "rename": "feat(rename): ",
            "map": "feat(map): ",
            "address": "feat(address): ",
            "phone": "feat(phone): ",
            "state": "feat(state): ",
            "scrub": "feat(scrub): ",
            "email": "feat(email): ",
            "batch": "feat(batch): ",
            "gemini": "feat(gemini): ",
            "content": "feat(content): ",
            "popup": "feat(popup): ",
            "manifest": "chore(manifest): ",
            "storage": "feat(storage): ",
            "styles": "style: ",
            "background": "feat(background): ",
            "scripts": "chore(build): ",
            "release": "build: ",
            "backend": "feat(backend): ",
            "game": "feat(game): ",
            "engine": "feat(engine): ",
            "build": "build: ",
            "deploy": "deploy: ",
            "ci": "ci: ",
            "deps": "deps: ",
            "other": "chore: ",
        }

    def generate_smart_message(
        self,
        files: list[str],
        line_numbers: dict[str, str] | None = None,
        use_llm: bool = False,
    ) -> str:
        """Generate intelligent commit message based on changes."""
        if not files:
            return "No changes to commit"

        # Categorize files
        categorized = self._categorize_files(files)

        # Try LLM enhancement if enabled and available
        if use_llm:
            try:
                llm_message = self._generate_llm_message(files, categorized)
                if llm_message:
                    return llm_message
            except Exception as e:
                self.logger.warning(f"LLM message generation failed: {e}")

        # Fall back to rule-based generation
        return self._build_message(files, categorized, line_numbers or {})

    def _categorize_files(self, files: list[str]) -> dict[str, list[str]]:
        """Categorize files by type using consolidated patterns."""
        result = {cat: [] for cat in self.CATEGORIES}
        result["other"] = []

        for file in files:
            file_lower = file.lower()
            categorized = False

            for category, patterns in self.CATEGORIES.items():
                for pattern in patterns:
                    if pattern in file_lower:
                        result[category].append(file)
                        categorized = True
                        break
                if categorized:
                    break

            if not categorized:
                result["other"].append(file)

        return result

    def _build_message(
        self,
        files: list[str],
        categorized: dict[str, list[str]],
        line_numbers: dict[str, str],
    ) -> str:
        """Build commit message with line numbers and smart categorization."""
        # Determine primary category
        primary_category = self._get_primary_category(categorized)
        prefix = self.PREFIXES.get(primary_category, self.PREFIXES["other"])

        # Build title
        if len(files) == 1:
            title = f"{prefix}{Path(files[0]).name}"
        else:
            title = f"{prefix}{self._describe_changes(categorized)}"

        # Build body with file details and line numbers
        body_lines = []
        for file in files[:8]:  # Limit to 8 files for readability
            line_info = line_numbers.get(file, "")
            if line_info:
                body_lines.append(f"- {file} ({line_info})")
            else:
                body_lines.append(f"- {file}")

        if len(files) > 8:
            body_lines.append(f"- ... and {len(files) - 8} more files")

        body = "\n".join(body_lines)
        return f"{title}\n\n{body}" if body else title

    def _get_primary_category(self, categorized: dict[str, list[str]]) -> str:
        """Determine primary category with priority ordering."""
        # Priority order based on common development patterns
        priority = [
            "main", "ui", "utils", "backend", "engine", "game",
            "pipeline", "config", "test", "docs", "convert", "clean",
            "drop", "rename", "map", "address", "phone", "state",
            "scrub", "email", "batch", "gemini", "content", "popup",
            "manifest", "storage", "styles", "background", "scripts",
            "release", "build", "deploy", "ci", "deps",
        ]

        for cat in priority:
            if categorized.get(cat):
                return cat

        return "other"

    def _describe_changes(self, categorized: dict[str, list[str]]) -> str:
        """Generate description of changes."""
        non_empty = {k: v for k, v in categorized.items() if v}

        if len(non_empty) == 1:
            category = list(non_empty.keys())[0]
            count = len(non_empty[category])
            return f"{count} {category} file{'s' if count > 1 else ''}"

        total = sum(len(v) for v in non_empty.values())
        return f"{total} files across {len(non_empty)} areas"

    def _generate_llm_message(self, files: list[str], categorized: dict[str, list[str]]) -> str | None:
        """Generate LLM-enhanced commit message (LDLA pattern)."""
        try:
            import requests

            # Prepare context for LLM
            context = {
                "files": files,
                "categories": {k: v for k, v in categorized.items() if v},
                "project_type": self._detect_project_type(),
            }

            prompt = self._build_llm_prompt(context)

            # Try Ollama (LDLA pattern)
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
            self.logger.debug(f"LLM generation failed: {e}")

        return None

    def _build_llm_prompt(self, context: dict) -> str:
        """Build prompt for LLM message generation."""
        files_str = "\n".join(f"- {f}" for f in context["files"])
        categories_str = ", ".join(context["categories"].keys())

        return f"""Generate a concise, conventional commit message for these changes:

Project Type: {context['project_type']}
Categories: {categories_str}

Changed Files:
{files_str}

Requirements:
- Use conventional commit format (type: description)
- Be descriptive but concise
- Focus on the 'why' not the 'what'
- Maximum 50 characters for the title
- Include relevant category in type

Examples:
- feat(ui): Add responsive navigation
- fix(api): Resolve authentication timeout
- docs(readme): Update installation instructions
- test(utils): Add coverage for string helpers

Generate only the commit message, no explanation:"""

    def _detect_project_type(self) -> str:
        """Detect project type based on anchor files."""
        project_root = self.config.project_root

        if (project_root / "Cargo.toml").exists():
            return "Rust"
        if (project_root / "manifest.json").exists():
            return "Chrome Extension"
        if (project_root / "requirements.txt").exists() or (project_root / "pyproject.toml").exists():
            return "Python"
        if (project_root / "package.json").exists():
            return "Node.js"
        return "Unknown"
