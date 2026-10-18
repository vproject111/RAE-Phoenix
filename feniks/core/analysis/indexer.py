# feniks/core/analysis/indexer.py
import ast
import os
import glob
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from pydantic import BaseModel
from feniks.infra.logging import get_logger

logger = get_logger("core.analysis.indexer")

class SymbolInfo(BaseModel):
    name: str
    type: str  # 'class', 'function', 'variable'
    file_path: str
    line: int
    dependencies: Set[str] = set()

class ProjectGraph(BaseModel):
    symbols: Dict[str, SymbolInfo] = {}
    file_map: Dict[str, List[str]] = {}

class SystemIndexer:
    """Advanced System-wide Indexer for Dependency and Impact Analysis."""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.graph = ProjectGraph()

    def scan_project(self):
        """Full project scan to build the dependency graph (Python, TS, PHP)."""
        logger.info(f"Building system graph for: {self.project_root}")
        
        # Supported extensions for Silicon Oracle v3.2
        extensions = ["*.py", "*.ts", "*.tsx", "*.php"]
        ignore_dirs = {
            "venv", ".venv", "node_modules", ".git", "dist", "build", 
            "__pycache__", ".pytest_cache", "rae-open-claw", "tmp_node1_sync",
            "work_dir", "runs", "experiments", "htmlcov", ".benchmarks", "output"
        }
        files = []
        for ext in extensions:
            for match in glob.glob(os.path.join(self.project_root, f"**/{ext}"), recursive=True):
                path_parts = set(Path(match).parts)
                if not (path_parts & ignore_dirs):
                    files.append(match)
            
        for f in files:
            try:
                # Dispatch indexing based on extension
                if f.endswith(".py"):
                    self._index_python_file(f)
                elif f.endswith((".ts", ".tsx")):
                    self._index_ts_file(f)
                elif f.endswith(".php"):
                    self._index_php_file(f)
            except Exception as e:
                logger.warning(f"Failed to index {f}: {e}")
        logger.info(f"System graph ready. Indexed {len(self.graph.symbols)} symbols across {len(self.graph.file_map)} files.")

    def _index_python_file(self, file_path: str):
        """Python-specific AST indexing."""
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
            # ... existing logic ... (implementing call tracking)
            self._generic_ast_visitor(tree, file_path)

    def _index_ts_file(self, file_path: str):
        """TS/TSX-specific indexing (DeepMind level: Regex-based symbol extraction for now)."""
        # Note: In a full prod version, this would use tree-sitter or LSP.
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Simple regex discovery for TS classes and functions
            import re
            matches = re.finditer(r'(?:export\s+)?(?:const|class|function)\s+([a-zA-Z0-9_]+)', content)
            file_symbols = []
            for m in matches:
                name = m.group(1)
                self.graph.symbols[name] = SymbolInfo(name=name, type="ts_symbol", file_path=file_path, line=0)
                file_symbols.append(name)
            self.graph.file_map[file_path] = file_symbols

    def _index_php_file(self, file_path: str):
        """PHP-specific indexing."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            import re
            matches = re.finditer(r'(?:class|function)\s+([a-zA-Z0-9_]+)', content)
            file_symbols = []
            for m in matches:
                name = m.group(1)
                self.graph.symbols[name] = SymbolInfo(name=name, type="php_symbol", file_path=file_path, line=0)
                file_symbols.append(name)
            self.graph.file_map[file_path] = file_symbols

    def _generic_ast_visitor(self, tree, file_path):
        # Implementation of previous Python visitor logic
        file_symbols = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                symbol_name = node.name
                symbol = SymbolInfo(
                    name=symbol_name,
                    type="class" if isinstance(node, ast.ClassDef) else "function",
                    file_path=file_path,
                    line=node.lineno
                )
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                        symbol.dependencies.add(child.func.id)
                self.graph.symbols[symbol_name] = symbol
                file_symbols.append(symbol_name)
        self.graph.file_map[file_path] = file_symbols

    def get_impact_zone(self, file_path: str) -> Dict[str, Any]:
        """Identifies which parts of the system are affected by changes in this file."""
        symbols_in_file = self.graph.file_map.get(file_path, [])
        impacted_symbols = {}
        
        for source_symbol in symbols_in_file:
            dependents = []
            for name, info in self.graph.symbols.items():
                if source_symbol in info.dependencies and info.file_path != file_path:
                    dependents.append({
                        "symbol": name,
                        "file": info.file_path,
                        "line": info.line
                    })
            if dependents:
                impacted_symbols[source_symbol] = dependents
                
        return {
            "file": file_path,
            "impacted_symbols": impacted_symbols,
            "total_dependents": sum(len(v) for v in impacted_symbols.values())
        }
