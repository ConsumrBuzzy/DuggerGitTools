"""Architecture Mapper - Visualize cross-language dependencies.

Generates dependency graphs for Python ↔ Rust bindings (PyO3/Maturin projects).
Creates Mermaid diagrams for ARCHITECTURE.md.
"""

import re
from pathlib import Path
from typing import List, Dict, Set, Optional

from loguru import logger
from pydantic import BaseModel


class Dependency(BaseModel):
    """Represents a dependency relationship."""
    
    source: str  # module/file that depends
    target: str  # module/file being depended on
    dep_type: str  # import, pyo3_binding, cargo_dep


class ArchitectureGraph(BaseModel):
    """Architecture dependency graph."""
    
    project_root: str
    python_modules: List[str]
    rust_crates: List[str]
    pyo3_bindings: List[str]
    dependencies: List[Dependency]
    

class ArchitectureMapper:
    """Maps cross-language architecture and generates dependency graphs.
    
    Key Features:
    - Detects PyO3 bindings between Python and Rust
    - Maps Python imports
    - Maps Rust cargo dependencies
    - Generates Mermaid diagrams for visualization
    """
    
    def __init__(self, project_root: Path):
        """Initialize ArchitectureMapper.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.logger = logger.bind(component="ArchitectureMapper")
    
    def detect_pyo3_modules(self) -> List[str]:
        """Detect PyO3 modules in Rust crates.
        
        Returns:
            List of PyO3 module names
        """
        pyo3_modules = []
        
        # Search for Cargo.toml files
        for cargo_toml in self.project_root.glob("**/Cargo.toml"):
            try:
                import tomllib
                with cargo_toml.open("rb") as f:
                    data = tomllib.load(f)
                
                # Check for pyo3 dependency
                deps = data.get("dependencies", {})
                if "pyo3" in deps:
                    # Get crate name
                    package = data.get("package", {})
                    crate_name = package.get("name", "")
                    
                    # Check for cdylib (Python extension)
                    lib = data.get("lib", {})
                    crate_type = lib.get("crate-type", [])
                    if isinstance(crate_type, str):
                        crate_type = [crate_type]
                    
                    if "cdylib" in crate_type:
                        pyo3_modules.append(crate_name)
                        self.logger.info(f"Found PyO3 module: {crate_name}")
            
            except Exception as e:
                self.logger.warning(f"Failed to parse {cargo_toml}: {e}")
        
        return pyo3_modules
    
    def map_python_imports(self, file_path: Path) -> List[str]:
        """Extract imports from Python file.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of imported module names
        """
        imports = []
        
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    # import foo
                    match = re.match(r'^\s*import\s+([\w.]+)', line)
                    if match:
                        imports.append(match.group(1).split(".")[0])
                    
                    # from foo import bar
                    match = re.match(r'^\s*from\s+([\w.]+)\s+import', line)
                    if match:
                        imports.append(match.group(1).split(".")[0])
        
        except Exception as e:
            self.logger.warning(f"Failed to parse imports from {file_path}: {e}")
        
        return list(set(imports))
    
    def map_cargo_dependencies(self, cargo_toml: Path) -> List[str]:
        """Extract dependencies from Cargo.toml.
        
        Args:
            cargo_toml: Path to Cargo.toml
            
        Returns:
            List of dependency crate names
        """
        deps = []
        
        try:
            import tomllib
            with cargo_toml.open("rb") as f:
                data = tomllib.load(f)
            
            # Regular dependencies
            for dep in data.get("dependencies", {}).keys():
                deps.append(dep)
            
            # Dev dependencies
            for dep in data.get("dev-dependencies", {}).keys():
                deps.append(dep)
        
        except Exception as e:
            self.logger.warning(f"Failed to parse {cargo_toml}: {e}")
        
        return deps
    
    def map_python_rust_bindings(self) -> ArchitectureGraph:
        """Map Python ↔ Rust bindings and dependencies.
        
        Returns:
            ArchitectureGraph with cross-language relationships
        """
        python_modules = []
        rust_crates = []
        pyo3_bindings = self.detect_pyo3_modules()
        dependencies = []
        
        # Find Python modules
        for py_file in self.project_root.glob("**/*.py"):
            if any(part in py_file.parts for part in [".venv", "venv", "__pycache__", "tests"]):
                continue
            
            rel_path = py_file.relative_to(self.project_root)
            module_name = str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")
            python_modules.append(module_name)
            
            # Extract imports
            imports = self.map_python_imports(py_file)
            for imp in imports:
                # Check if import is a PyO3 binding
                if imp in pyo3_bindings:
                    dependencies.append(Dependency(
                        source=module_name,
                        target=imp,
                        dep_type="pyo3_binding"
                    ))
                else:
                    dependencies.append(Dependency(
                        source=module_name,
                        target=imp,
                        dep_type="import"
                    ))
        
        # Find Rust crates
        for cargo_toml in self.project_root.glob("**/Cargo.toml"):
            if "target" in cargo_toml.parts:
                continue
            
            try:
                import tomllib
                with cargo_toml.open("rb") as f:
                    data = tomllib.load(f)
                
                package = data.get("package", {})
                crate_name = package.get("name", "")
                if crate_name:
                    rust_crates.append(crate_name)
                    
                    # Map cargo deps
                    cargo_deps = self.map_cargo_dependencies(cargo_toml)
                    for dep in cargo_deps:
                        dependencies.append(Dependency(
                            source=crate_name,
                            target=dep,
                            dep_type="cargo_dep"
                        ))
            
            except Exception as e:
                self.logger.warning(f"Failed to parse {cargo_toml}: {e}")
        
        return ArchitectureGraph(
            project_root=str(self.project_root),
            python_modules=python_modules,
            rust_crates=rust_crates,
            pyo3_bindings=pyo3_bindings,
            dependencies=dependencies
        )
    
    def generate_mermaid_diagram(self, graph: ArchitectureGraph) -> str:
        """Generate Mermaid diagram from architecture graph.
        
        Args:
            graph: ArchitectureGraph to visualize
            
        Returns:
            Mermaid diagram string
        """
        lines = ["graph TD"]
        
        # Define node styles
        lines.append("    classDef python fill:#3776ab,color:#fff")
        lines.append("    classDef rust fill:#ce412b,color:#fff")
        lines.append("    classDef pyo3 fill:#ffd43b,color:#000")
        
        # Add Python modules
        for module in graph.python_modules[:10]:  # Limit to 10 for readability
            safe_id = module.replace(".", "_")
            lines.append(f"    {safe_id}[{module}]:::python")
        
        # Add Rust crates
        for crate in graph.rust_crates:
            safe_id = crate.replace("-", "_")
            lines.append(f"    {safe_id}[{crate}]:::rust")
        
        # Add PyO3 bindings with special styling
        for binding in graph.pyo3_bindings:
            safe_id = binding.replace("-", "_")
            lines.append(f"    {safe_id}[{binding}<br/>PyO3]:::pyo3")
        
        # Add dependencies (PyO3 bindings only, to keep clean)
        pyo3_deps = [d for d in graph.dependencies if d.dep_type == "pyo3_binding"]
        for dep in pyo3_deps:
            source_id = dep.source.replace(".", "_").replace("-", "_")
            target_id = dep.target.replace(".", "_").replace("-", "_")
            lines.append(f"    {source_id} --> {target_id}")
        
        return "\n".join(lines)
    
    def generate_architecture_doc(self) -> str:
        """Generate complete ARCHITECTURE.md content.
        
        Returns:
            Markdown content for ARCHITECTURE.md
        """
        graph = self.map_python_rust_bindings()
        mermaid = self.generate_mermaid_diagram(graph)
        
        doc = f"""# Architecture Map

**Generated**: {graph.project_root}  
**Last Updated**: Auto-generated on commit

## Overview

This project uses the following languages:
- Python modules: {len(graph.python_modules)}
- Rust crates: {len(graph.rust_crates)}
- PyO3 bindings: {len(graph.pyo3_bindings)}

## Dependency Graph

```mermaid
{mermaid}
```

## Python Modules

{chr(10).join(f"- `{m}`" for m in graph.python_modules[:20])}

## Rust Crates

{chr(10).join(f"- `{c}`" for c in graph.rust_crates)}

## PyO3 Bindings

{chr(10).join(f"- `{b}` - Python extension module written in Rust" for b in graph.pyo3_bindings)}

---

*This file is auto-generated by DGT on each commit. Do not edit manually.*
"""
        
        return doc
    
    def update_architecture_doc(self) -> None:
        """Update ARCHITECTURE.md file."""
        arch_file = self.project_root / "ARCHITECTURE.md"
        
        content = self.generate_architecture_doc()
        
        with arch_file.open("w", encoding="utf-8") as f:
            f.write(content)
        
        self.logger.info(f"✅ Updated ARCHITECTURE.md")
