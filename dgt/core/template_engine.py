"""Template engine for DuggerCore project initialization."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .config import DGTConfig
from .schema import DuggerSchema, ProjectType


class TemplateEngine:
    """Template engine for DuggerCore project initialization."""
    
    def __init__(self, config: DGTConfig) -> None:
        """Initialize template engine."""
        self.config = config
        self.logger = logger.bind(template_engine=True)
        self.templates_dir = config.project_root / "templates"
        
        # Ensure templates directory exists
        self.templates_dir.mkdir(parents=True, exist_ok=True)
    
    def init_project(
        self, 
        project_name: str, 
        project_path: Path,
        project_type: Optional[ProjectType] = None,
        template_name: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Initialize a new DuggerCore project."""
        try:
            self.logger.info(f"Initializing DuggerCore project: {project_name}")
            
            # Determine project type if not specified
            if project_type is None:
                project_type = self._detect_project_type(project_path)
            
            # Select template
            template = self._select_template(project_type, template_name)
            if not template:
                self.logger.error(f"No template found for project type: {project_type}")
                return False
            
            # Create project directory
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Copy template files
            self._copy_template_files(template, project_path, project_name)
            
            # Generate configuration
            self._generate_dugger_config(project_path, project_type, project_name, custom_config)
            
            # Generate project structure
            self._generate_project_structure(project_path, project_type, project_name)
            
            # Initialize Git repository
            self._initialize_git_repo(project_path)
            
            # Create initial commit
            self._create_initial_commit(project_path, project_name)
            
            self.logger.info(f"Successfully initialized DuggerCore project: {project_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize project: {e}")
            return False
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        templates = []
        
        for template_dir in self.templates_dir.iterdir():
            if not template_dir.is_dir():
                continue
            
            template_info = self._load_template_info(template_dir)
            if template_info:
                templates.append(template_info)
        
        return sorted(templates, key=lambda t: t["name"])
    
    def create_custom_template(
        self, 
        template_name: str, 
        project_type: ProjectType,
        description: str,
        source_dir: Optional[Path] = None
    ) -> bool:
        """Create a custom template from existing project."""
        try:
            template_dir = self.templates_dir / template_name
            
            if template_dir.exists():
                self.logger.error(f"Template already exists: {template_name}")
                return False
            
            template_dir.mkdir(parents=True, exist_ok=True)
            
            # Create template metadata
            template_info = {
                "name": template_name,
                "project_type": project_type.value,
                "description": description,
                "version": "1.0.0",
                "created_at": self._get_timestamp(),
            }
            
            (template_dir / "template.json").write_text(
                json.dumps(template_info, indent=2), 
                encoding="utf-8"
            )
            
            # Copy source files if provided
            if source_dir and source_dir.exists():
                self._copy_template_files_from_source(source_dir, template_dir)
            
            self.logger.info(f"Created custom template: {template_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create template: {e}")
            return False
    
    def _detect_project_type(self, project_path: Path) -> ProjectType:
        """Detect project type from existing files."""
        # Check for anchor files
        anchor_files = {
            ProjectType.RUST: ["Cargo.toml", "src/main.rs", "src/lib.rs"],
            ProjectType.PYTHON: ["pyproject.toml", "requirements.txt", "setup.py"],
            ProjectType.CHROME_EXTENSION: ["manifest.json"],
            ProjectType.NODEJS: ["package.json"],
            ProjectType.SOLANA: ["Anchor.toml", "programs/"],
            ProjectType.GAME_MAKER: ["project.gmx"],
        }
        
        for project_type, files in anchor_files.items():
            for file_pattern in files:
                if (project_path / file_pattern).exists():
                    return project_type
        
        return ProjectType.UNKNOWN
    
    def _select_template(self, project_type: ProjectType, template_name: Optional[str]) -> Optional[Path]:
        """Select template for project type."""
        if template_name:
            template_path = self.templates_dir / template_name
            if template_path.exists():
                return template_path
            return None
        
        # Use built-in template for project type
        template_path = self.templates_dir / project_type.value
        if template_path.exists():
            return template_path
        
        # Fall back to generic template
        generic_path = self.templates_dir / "generic"
        if generic_path.exists():
            return generic_path
        
        return None
    
    def _copy_template_files(self, template_dir: Path, project_path: Path, project_name: str) -> None:
        """Copy template files to project directory."""
        for item in template_dir.iterdir():
            if item.name == "template.json":
                continue
            
            dest_path = project_path / item.name
            
            if item.is_file():
                # Process file content
                content = item.read_text(encoding="utf-8")
                processed_content = self._process_template_content(content, project_name)
                dest_path.write_text(processed_content, encoding="utf-8")
            elif item.is_dir():
                # Copy directory
                shutil.copytree(item, dest_path, dirs_exist_ok=True)
    
    def _process_template_content(self, content: str, project_name: str) -> str:
        """Process template content with variable substitution."""
        replacements = {
            "{{PROJECT_NAME}}": project_name,
            "{{PROJECT_NAME_UPPER}}": project_name.upper(),
            "{{PROJECT_NAME_LOWER}}": project_name.lower(),
            "{{PROJECT_NAME_SNAKE}}": self._to_snake_case(project_name),
            "{{PROJECT_NAME_KEBAB}}": self._to_kebab_case(project_name),
            "{{TIMESTAMP}}": self._get_timestamp(),
        }
        
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        
        return content
    
    def _generate_dugger_config(
        self, 
        project_path: Path, 
        project_type: ProjectType, 
        project_name: str,
        custom_config: Optional[Dict[str, Any]]
    ) -> None:
        """Generate dugger.yaml configuration."""
        # Base configuration
        config = {
            "project_type": project_type.value,
            "auto_bump": True,
            "bump_type": "patch",
            "auto_fix": True,
            "message_style": "conventional",
            "llm_enabled": False,
        }
        
        # Add project-specific configurations
        if project_type == ProjectType.RUST:
            config.update({
                "anchor_files": [
                    {"path": "Cargo.toml", "weight": 20, "provider": "rust"},
                    {"path": "src/", "weight": 10, "provider": "rust"},
                ],
                "version_formats": [
                    {
                        "file_path": "Cargo.toml",
                        "pattern": 'version\\s*=\\s*"([^"]+)"',
                        "replacement": 'version = "{new_version}"'
                    }
                ],
                "tools": [
                    {
                        "name": "cargo-fmt",
                        "check": {"command": ["cargo", "fmt", "--version"], "expected_exit": 0, "timeout": 5},
                        "fix_command": ["cargo", "fmt", "--all"],
                        "priority": 10,
                        "description": "Rust code formatter"
                    },
                    {
                        "name": "cargo-clippy",
                        "check": {"command": ["cargo", "clippy", "--version"], "expected_exit": 0, "timeout": 5},
                        "fix_command": ["cargo", "clippy", "--all", "--fix", "--allow-dirty"],
                        "priority": 20,
                        "description": "Rust linter and auto-fixer"
                    }
                ]
            })
        
        elif project_type == ProjectType.PYTHON:
            config.update({
                "anchor_files": [
                    {"path": "pyproject.toml", "weight": 20, "provider": "python"},
                    {"path": "requirements.txt", "weight": 15, "provider": "python"},
                ],
                "version_formats": [
                    {
                        "file_path": "pyproject.toml",
                        "pattern": 'version\\s*=\\s*"([^"]+)"',
                        "replacement": 'version = "{new_version}"'
                    }
                ],
                "tools": [
                    {
                        "name": "ruff",
                        "check": {"command": ["ruff", "--version"], "expected_exit": 0, "timeout": 5},
                        "fix_command": ["ruff", "check", "--fix", "."],
                        "file_patterns": ["*.py"],
                        "priority": 10,
                        "description": "Python linter and formatter"
                    },
                    {
                        "name": "black",
                        "check": {"command": ["black", "--version"], "expected_exit": 0, "timeout": 5},
                        "fix_command": ["black", "."],
                        "file_patterns": ["*.py"],
                        "priority": 20,
                        "description": "Python code formatter"
                    }
                ]
            })
        
        elif project_type == ProjectType.CHROME_EXTENSION:
            config.update({
                "anchor_files": [
                    {"path": "manifest.json", "weight": 25, "provider": "chrome"},
                    {"path": "popup.html", "weight": 10, "provider": "chrome"},
                ],
                "version_formats": [
                    {
                        "file_path": "manifest.json",
                        "pattern": '"version"\\s*:\\s*"([^"]+)"',
                        "replacement": '"version": "{new_version}"'
                    }
                ],
                "tools": [
                    {
                        "name": "eslint",
                        "check": {"command": ["npx", "eslint", "--version"], "expected_exit": 0, "timeout": 5},
                        "fix_command": ["npx", "eslint", "--fix", "."],
                        "file_patterns": ["*.js", "*.mjs"],
                        "priority": 10,
                        "description": "JavaScript linter"
                    }
                ]
            })
        
        # Apply custom configuration
        if custom_config:
            config.update(custom_config)
        
        # Write configuration file
        import yaml
        config_file = project_path / "dugger.yaml"
        with config_file.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
    
    def _generate_project_structure(self, project_path: Path, project_type: ProjectType, project_name: str) -> None:
        """Generate project-specific directory structure."""
        if project_type == ProjectType.RUST:
            (project_path / "src").mkdir(exist_ok=True)
            (project_path / "tests").mkdir(exist_ok=True)
            (project_path / "benches").mkdir(exist_ok=True)
            
            # Create basic Cargo.toml if not exists
            cargo_toml = project_path / "Cargo.toml"
            if not cargo_toml.exists():
                cargo_content = f'''[package]
name = "{self._to_kebab_case(project_name)}"
version = "0.1.0"
edition = "2021"
description = "A new Rust project"

[dependencies]
'''
                cargo_toml.write_text(cargo_content, encoding="utf-8")
        
        elif project_type == ProjectType.PYTHON:
            (project_path / "src").mkdir(exist_ok=True)
            (project_path / "tests").mkdir(exist_ok=True)
            (project_path / "docs").mkdir(exist_ok=True)
            
            # Create basic pyproject.toml if not exists
            pyproject_toml = project_path / "pyproject.toml"
            if not pyproject_toml.exists():
                pyproject_content = f'''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{self._to_kebab_case(project_name)}"
version = "0.1.0"
description = "A new Python project"
authors = [
    {{name = "Developer", email = "dev@example.com"}},
]
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
    "black>=23.0.0",
]

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.black]
line-length = 88
target-version = ['py311']
'''
                pyproject_toml.write_text(pyproject_content, encoding="utf-8")
        
        elif project_type == ProjectType.CHROME_EXTENSION:
            (project_path / "popup").mkdir(exist_ok=True)
            (project_path / "content").mkdir(exist_ok=True)
            (project_path / "background").mkdir(exist_ok=True)
            (project_path / "icons").mkdir(exist_ok=True)
            
            # Create basic manifest.json if not exists
            manifest_json = project_path / "manifest.json"
            if not manifest_json.exists():
                manifest_content = f'''{{
  "manifest_version": 3,
  "name": "{project_name}",
  "version": "0.1.0",
  "description": "A new Chrome extension",
  "action": {{
    "default_popup": "popup/popup.html"
  }},
  "permissions": [
    "activeTab"
  ]
}}
'''
                manifest_json.write_text(manifest_content, encoding="utf-8")
    
    def _initialize_git_repo(self, project_path: Path) -> None:
        """Initialize Git repository."""
        try:
            import subprocess
            
            # Initialize git repo
            subprocess.run(
                ["git", "init"],
                cwd=project_path,
                check=True,
                capture_output=True
            )
            
            # Set up basic gitignore
            gitignore_content = self._generate_gitignore_content(project_path)
            (project_path / ".gitignore").write_text(gitignore_content, encoding="utf-8")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize Git repo: {e}")
    
    def _create_initial_commit(self, project_path: Path, project_name: str) -> None:
        """Create initial commit."""
        try:
            import subprocess
            
            # Add all files
            subprocess.run(
                ["git", "add", "."],
                cwd=project_path,
                check=True,
                capture_output=True
            )
            
            # Create initial commit
            subprocess.run(
                ["git", "commit", "-m", f"feat: Initialize {project_name} with DuggerCore"],
                cwd=project_path,
                check=True,
                capture_output=True
            )
            
            self.logger.info("Created initial commit")
            
        except Exception as e:
            self.logger.warning(f"Failed to create initial commit: {e}")
    
    def _generate_gitignore_content(self, project_path: Path) -> str:
        """Generate appropriate .gitignore content."""
        # Check project type and generate appropriate gitignore
        pyproject_toml = project_path / "pyproject.toml"
        cargo_toml = project_path / "Cargo.toml"
        package_json = project_path / "package.json"
        
        if pyproject_toml.exists():
            return '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
venv/
env/
ENV/
.venv/
.env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# DuggerCore
.dgt/
'''
        
        elif cargo_toml.exists():
            return '''# Rust
/target/
**/*.rs.bk
Cargo.lock

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# DuggerCore
.dgt/
'''
        
        elif package_json.exists():
            return '''# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm
.eslintcache

# Build outputs
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# DuggerCore
.dgt/
'''
        
        else:
            return '''# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# DuggerCore
.dgt/
'''
    
    def _load_template_info(self, template_dir: Path) -> Optional[Dict[str, Any]]:
        """Load template information."""
        template_json = template_dir / "template.json"
        
        if not template_json.exists():
            return None
        
        try:
            with template_json.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    
    def _copy_template_files_from_source(self, source_dir: Path, template_dir: Path) -> None:
        """Copy files from source directory to template."""
        # Copy all files except .git, node_modules, target, etc.
        exclude_patterns = [
            ".git",
            "node_modules",
            "target",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
        ]
        
        for item in source_dir.iterdir():
            if any(pattern in item.name for pattern in exclude_patterns):
                continue
            
            dest_path = template_dir / item.name
            
            if item.is_file():
                shutil.copy2(item, dest_path)
            elif item.is_dir():
                shutil.copytree(item, dest_path, dirs_exist_ok=True)
    
    def _to_snake_case(self, name: str) -> str:
        """Convert name to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def _to_kebab_case(self, name: str) -> str:
        """Convert name to kebab-case."""
        return self._to_snake_case(name).replace('_', '-')
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
