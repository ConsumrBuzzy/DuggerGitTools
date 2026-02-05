"""Templater - Static docstring template injection.

NO AI. Just AST-based detection and static string insertion.
Inserts empty Google-style docstring templates for functions without docs.
"""

import ast
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger


class DocstringTemplater:
    """Static docstring template injector.
    
    Uses AST to detect functions without docstrings and inserts
    empty Google-style templates. NO AI—just static templates.
    """
    
    GOOGLE_STYLE_TEMPLATE = '''"""
    Summary: 

    Args:
{args}
    Returns:

    """'''
    
    SIMPLE_TEMPLATE = '''"""
    Summary: 

    """'''
    
    def __init__(self, project_root: Path):
        """Initialize DocstringTemplater.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.logger = logger.bind(component="DocstringTemplater")
    
    def scan_file(self, file_path: Path) -> List[Tuple[int, str]]:
        """Scan file for functions without docstrings.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of (line_number, function_name) tuples
        """
        missing_docs = []
        
        try:
            with file_path.open('r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source, filename=str(file_path))
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check if has docstring
                    if not ast.get_docstring(node):
                        missing_docs.append((node.lineno, node.name))
        
        except SyntaxError as e:
            self.logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to scan {file_path}: {e}")
        
        return missing_docs
    
    def generate_template(self, function_node: ast.FunctionDef) -> str:
        """Generate Google-style docstring template for function.
        
        Args:
            function_node: AST FunctionDef node
            
        Returns:
            Docstring template string
        """
        # Extract argument names (skip self/cls)
        args = []
        for arg in function_node.args.args:
            arg_name = arg.arg
            if arg_name not in ['self', 'cls']:
                args.append(arg_name)
        
        # Build template
        if args:
            args_section = "\n".join(f"        {arg}: " for arg in args)
            template = self.GOOGLE_STYLE_TEMPLATE.format(args=args_section)
        else:
            template = self.SIMPLE_TEMPLATE
        
        return template
    
    def inject_template_in_file(self, file_path: Path, dry_run: bool = True) -> int:
        """Inject docstring templates into file.
        
        Args:
            file_path: Path to Python file
            dry_run: If True, only report what would be changed
            
        Returns:
            Number of templates injected
        """
        try:
            with file_path.open('r', encoding='utf-8') as f:
                lines = f.readlines()
                source = ''.join(lines)
            
            tree = ast.parse(source, filename=str(file_path))
            
            # Collect functions needing docstrings (reverse order for line number stability)
            functions_to_template = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not ast.get_docstring(node):
                        functions_to_template.append(node)
            
            if not functions_to_template:
                return 0
            
            # Sort by line number (descending) to insert from bottom up
            functions_to_template.sort(key=lambda n: n.lineno, reverse=True)
            
            # Insert templates
            for func_node in functions_to_template:
                template = self.generate_template(func_node)
                
                # Find indentation of function definition
                func_line_idx = func_node.lineno - 1
                func_line = lines[func_line_idx]
                indent = len(func_line) - len(func_line.lstrip())
                
                # Add 4 spaces for docstring indent
                template_lines = [' ' * (indent + 4) + line + '\n' 
                                 for line in template.split('\n')]
                
                # Insert after function definition line
                insert_idx = func_line_idx + 1
                lines[insert_idx:insert_idx] = template_lines
                
                self.logger.info(f"Injected template for {func_node.name} at line {func_node.lineno}")
            
            # Write back to file
            if not dry_run:
                with file_path.open('w', encoding='utf-8') as f:
                    f.writelines(lines)
                self.logger.info(f"Injected {len(functions_to_template)} templates into {file_path}")
            else:
                self.logger.info(f"DRY RUN: Would inject {len(functions_to_template)} templates into {file_path}")
            
            return len(functions_to_template)
        
        except Exception as e:
            self.logger.error(f"Failed to inject templates in {file_path}: {e}")
            return 0
    
    def scan_project(self) -> dict:
        """Scan entire project for functions without docstrings.
        
        Returns:
            Dict mapping file paths to list of (line_number, function_name) tuples
        """
        results = {}
        
        for py_file in self.project_root.rglob("*.py"):
            # Skip common ignore patterns
            if any(part in py_file.parts for part in ['.venv', 'venv', '__pycache__', 'dist', 'build']):
                continue
            
            missing = self.scan_file(py_file)
            if missing:
                results[py_file] = missing
        
        total = sum(len(funcs) for funcs in results.values())
        self.logger.info(f"Found {total} functions without docstrings across {len(results)} files")
        
        return results
    
    def generate_report(self, scan_results: dict) -> str:
        """Generate markdown report of functions without docstrings.
        
        Args:
            scan_results: Dict from scan_project()
            
        Returns:
            Markdown-formatted report
        """
        if not scan_results:
            return "# Docstring Report\n\nAll functions have docstrings! ✅\n"
        
        lines = ["# Docstring Report", ""]
        
        total = sum(len(funcs) for funcs in scan_results.values())
        lines.append(f"**Functions Missing Docstrings**: {total}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        for file_path, missing_funcs in sorted(scan_results.items()):
            rel_path = file_path.relative_to(self.project_root)
            lines.append(f"## [{rel_path}](file:///{file_path})")
            lines.append("")
            
            for line_num, func_name in missing_funcs:
                lines.append(f"- `{func_name}` (line {line_num})")
            
            lines.append("")
        
        return "\n".join(lines)
