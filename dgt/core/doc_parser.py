"""Documentation Parser - Auto-generate documentation from source code.

Extracts Python docstrings and Rust doc comments to maintain live PROJECT_MAP.json.
Implements the "Living Doc" protocol from ADR-001.
"""

import ast
import re
from datetime import datetime
from pathlib import Path

from loguru import logger
from pydantic import BaseModel


class CodeSymbol(BaseModel):
    """Represents a documented symbol in source code."""

    name: str
    symbol_type: str  # class, function, method, module
    file_path: str
    line_start: int
    line_end: int
    docstring: str | None = None
    signature: str | None = None
    parent: str | None = None  # Parent class/module


class ProjectMap(BaseModel):
    """Project architecture snapshot."""

    generated_at: str
    project_root: str
    languages: list[str]
    symbols: list[CodeSymbol]
    file_count: int
    total_lines: int


class DocParser:
    """Parses source code to extract documentation and generate architecture maps.
    
    Key Features:
    - Python docstring extraction via AST parsing
    - Rust doc comment extraction via regex
    - Incremental PROJECT_MAP.json updates
    - Tracks class/function signatures and line ranges
    """

    def __init__(self, project_root: Path):
        """Initialize DocParser.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.logger = logger.bind(component="DocParser")

    def extract_python_docstrings(self, file_path: Path) -> list[CodeSymbol]:
        """Extract docstrings from Python file.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of CodeSymbol objects
        """
        symbols = []

        try:
            with file_path.open("r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(file_path))

            # Module docstring
            module_doc = ast.get_docstring(tree)
            if module_doc:
                symbols.append(CodeSymbol(
                    name=file_path.stem,
                    symbol_type="module",
                    file_path=str(file_path.relative_to(self.project_root)),
                    line_start=1,
                    line_end=len(source.splitlines()),
                    docstring=module_doc.strip(),
                    signature=None,
                    parent=None,
                ))

            # Classes and functions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    symbols.append(self._parse_class(node, file_path))
                    # Methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            symbols.append(self._parse_function(item, file_path, parent=node.name))

                elif isinstance(node, ast.FunctionDef):
                    # Top-level functions (not methods)
                    if not any(isinstance(p, ast.ClassDef) for p in ast.walk(tree)
                              if hasattr(p, "body") and node in getattr(p, "body", [])):
                        symbols.append(self._parse_function(node, file_path))

        except SyntaxError as e:
            self.logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to parse {file_path}: {e}")

        return symbols

    def _parse_class(self, node: ast.ClassDef, file_path: Path) -> CodeSymbol:
        """Parse AST ClassDef node.
        
        Args:
            node: AST ClassDef node
            file_path: Source file path
            
        Returns:
            CodeSymbol for class
        """
        docstring = ast.get_docstring(node)

        # Build signature
        bases = [self._get_name(base) for base in node.bases]
        signature = f"class {node.name}"
        if bases:
            signature += f"({', '.join(bases)})"

        return CodeSymbol(
            name=node.name,
            symbol_type="class",
            file_path=str(file_path.relative_to(self.project_root)),
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring.strip() if docstring else None,
            signature=signature,
            parent=None,
        )

    def _parse_function(
        self,
        node: ast.FunctionDef,
        file_path: Path,
        parent: str | None = None,
    ) -> CodeSymbol:
        """Parse AST FunctionDef node.
        
        Args:
            node: AST FunctionDef node
            file_path: Source file path
            parent: Parent class name if method
            
        Returns:
            CodeSymbol for function/method
        """
        docstring = ast.get_docstring(node)

        # Build signature
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_annotation(arg.annotation)}"
            args.append(arg_str)

        return_annotation = ""
        if node.returns:
            return_annotation = f" -> {self._get_annotation(node.returns)}"

        signature = f"def {node.name}({', '.join(args)}){return_annotation}"

        return CodeSymbol(
            name=node.name,
            symbol_type="method" if parent else "function",
            file_path=str(file_path.relative_to(self.project_root)),
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring.strip() if docstring else None,
            signature=signature,
            parent=parent,
        )

    def _get_name(self, node: ast.expr) -> str:
        """Get name from AST expression."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return "..."

    def _get_annotation(self, node: ast.expr) -> str:
        """Get type annotation string from AST."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Subscript):
            return f"{self._get_annotation(node.value)}[{self._get_annotation(node.slice)}]"
        if isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return "..."

    def extract_rust_doc_comments(self, file_path: Path) -> list[CodeSymbol]:
        """Extract doc comments from Rust file.
        
        Args:
            file_path: Path to Rust file
            
        Returns:
            List of CodeSymbol objects
        """
        symbols = []

        try:
            with file_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()

            # Pattern: /// doc comment followed by fn/struct/impl/mod
            current_doc = []

            for i, line in enumerate(lines, start=1):
                stripped = line.strip()

                # Collect doc comments
                if stripped.startswith("///"):
                    doc_text = stripped[3:].strip()
                    current_doc.append(doc_text)

                # Match function definition
                elif stripped.startswith("pub fn") or stripped.startswith("fn"):
                    match = re.match(r"(?:pub\s+)?fn\s+(\w+)", stripped)
                    if match:
                        fn_name = match.group(1)
                        symbols.append(CodeSymbol(
                            name=fn_name,
                            symbol_type="function",
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_start=i,
                            line_end=i,  # Approximation
                            docstring="\n".join(current_doc) if current_doc else None,
                            signature=stripped,
                            parent=None,
                        ))
                    current_doc = []

                # Match struct definition
                elif stripped.startswith("pub struct") or stripped.startswith("struct"):
                    match = re.match(r"(?:pub\s+)?struct\s+(\w+)", stripped)
                    if match:
                        struct_name = match.group(1)
                        symbols.append(CodeSymbol(
                            name=struct_name,
                            symbol_type="class",  # Rust struct → class equivalent
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_start=i,
                            line_end=i,
                            docstring="\n".join(current_doc) if current_doc else None,
                            signature=stripped,
                            parent=None,
                        ))
                    current_doc = []

                # Reset doc comments if not a definition
                elif not stripped.startswith("///") and current_doc:
                    current_doc = []

        except Exception as e:
            self.logger.warning(f"Failed to parse Rust file {file_path}: {e}")

        return symbols

    def generate_project_map(self, file_patterns: list[str] | None = None) -> ProjectMap:
        """Generate complete project architecture map.
        
        Args:
            file_patterns: Glob patterns to include (default: *.py, *.rs)
            
        Returns:
            ProjectMap with all symbols
        """
        if file_patterns is None:
            file_patterns = ["**/*.py", "**/*.rs"]

        all_symbols = []
        languages = set()
        file_count = 0
        total_lines = 0

        for pattern in file_patterns:
            for file_path in self.project_root.glob(pattern):
                # Skip venvs, build dirs, tests
                if any(part in file_path.parts for part in [".venv", "venv", "target", "node_modules", "__pycache__"]):
                    continue

                file_count += 1

                # Count lines
                try:
                    with file_path.open("r", encoding="utf-8") as f:
                        total_lines += len(f.readlines())
                except Exception:
                    pass

                # Extract symbols
                if file_path.suffix == ".py":
                    languages.add("python")
                    symbols = self.extract_python_docstrings(file_path)
                    all_symbols.extend(symbols)

                elif file_path.suffix == ".rs":
                    languages.add("rust")
                    symbols = self.extract_rust_doc_comments(file_path)
                    all_symbols.extend(symbols)

        return ProjectMap(
            generated_at=datetime.now().isoformat(),
            project_root=str(self.project_root),
            languages=sorted(languages),
            symbols=all_symbols,
            file_count=file_count,
            total_lines=total_lines,
        )

    def update_project_map_incremental(self, changed_files: list[Path]) -> None:
        """Update PROJECT_MAP.json with only changed files.
        
        Args:
            changed_files: List of files that changed
        """
        map_file = self.project_root / "PROJECT_MAP.json"

        # Load existing map if present
        existing_map = None
        if map_file.exists():
            try:
                import json
                with map_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                existing_map = ProjectMap(**data)
            except Exception as e:
                self.logger.warning(f"Failed to load existing PROJECT_MAP.json: {e}")

        # If no existing map, generate full map
        if not existing_map:
            project_map = self.generate_project_map()
        else:
            # Remove symbols from changed files
            changed_file_strs = [str(f.relative_to(self.project_root)) for f in changed_files]
            kept_symbols = [
                s for s in existing_map.symbols
                if s.file_path not in changed_file_strs
            ]

            # Re-extract symbols from changed files
            new_symbols = []
            for file_path in changed_files:
                if file_path.suffix == ".py":
                    new_symbols.extend(self.extract_python_docstrings(file_path))
                elif file_path.suffix == ".rs":
                    new_symbols.extend(self.extract_rust_doc_comments(file_path))

            # Merge
            all_symbols = kept_symbols + new_symbols

            project_map = ProjectMap(
                generated_at=datetime.now().isoformat(),
                project_root=existing_map.project_root,
                languages=existing_map.languages,
                symbols=all_symbols,
                file_count=existing_map.file_count,
                total_lines=existing_map.total_lines,
            )

        # Write PROJECT_MAP.json
        import json
        with map_file.open("w", encoding="utf-8") as f:
            json.dump(project_map.model_dump(), f, indent=2)

        self.logger.info(f"✅ Updated PROJECT_MAP.json ({len(project_map.symbols)} symbols)")
