"""Tree-sitter AST parser implementation for Repository Intelligence Platform."""

import os
from typing import List, Dict, Any, Optional
from tree_sitter_languages import get_parser
from tree_sitter import Node, Parser


class ASTParser:
    """Wrapper around tree-sitter to parse source files and extract semantic symbol structures."""

    def __init__(self):
        self._parsers: Dict[str, Parser] = {}

    def _get_parser(self, extension: str) -> Optional[Parser]:
        """Load the correct parser based on file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".java": "java",
        }
        lang = ext_map.get(extension.lower())
        if not lang:
            return None

        if lang not in self._parsers:
            try:
                self._parsers[lang] = get_parser(lang)
            except Exception:
                return None
        return self._parsers.get(lang)

    def parse_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Parse source content and extract classes, functions, and symbols.

        Falls back to a structural line-based chunker if no parser is available.
        """
        _, ext = os.path.splitext(file_path)
        parser = self._get_parser(ext)
        
        if not parser:
            return self._fallback_chunking(file_path, content)

        try:
            tree = parser.parse(bytes(content, "utf8"))
            symbols: List[Dict[str, Any]] = []
            self._traverse_tree(tree.root_node, content, symbols)
            
            if not symbols:
                # If parsed but no specific symbols extracted, chunk it structurally
                return self._fallback_chunking(file_path, content)
                
            return symbols
        except Exception:
            return self._fallback_chunking(file_path, content)

    def _traverse_tree(self, node: Node, content: str, symbols: List[Dict[str, Any]]) -> None:
        """Recursively traverse AST to find function/class definition nodes."""
        node_type = node.type
        
        # Target Python, JS/TS, Go, etc. declarations
        is_symbol = False
        sym_type = None
        sym_name = None

        if node_type in ("class_definition", "class_declaration"):
            is_symbol = True
            sym_type = "class"
            # Attempt to extract name node
            name_node = node.child_by_field_name("name")
            if name_node:
                sym_name = content[name_node.start_byte:name_node.end_byte]
        elif node_type in ("function_definition", "function_declaration", "method_declaration", "method_definition"):
            is_symbol = True
            sym_type = "function"
            name_node = node.child_by_field_name("name")
            if name_node:
                sym_name = content[name_node.start_byte:name_node.end_byte]

        if is_symbol and sym_type:
            start_point = node.start_point[0] + 1  # 1-indexed
            end_point = node.end_point[0] + 1
            raw_text = content[node.start_byte:node.end_byte]
            
            symbols.append({
                "symbol_name": sym_name or "anonymous",
                "symbol_type": sym_type,
                "start_line": start_point,
                "end_line": end_point,
                "content": raw_text,
                "metadata": {
                    "node_type": node_type,
                    "child_count": node.child_count,
                }
            })

        # Recurse through children
        for child in node.children:
            self._traverse_tree(child, content, symbols)

    def _fallback_chunking(self, file_path: str, content: str, lines_per_chunk: int = 50) -> List[Dict[str, Any]]:
        """Fallback chunker for unparsed languages, dividing the file into linear line segments."""
        lines = content.splitlines()
        chunks = []
        
        for i in range(0, len(lines), lines_per_chunk):
            chunk_lines = lines[i:i + lines_per_chunk]
            start_line = i + 1
            end_line = min(i + lines_per_chunk, len(lines))
            chunk_content = "\n".join(chunk_lines)
            
            chunks.append({
                "symbol_name": os.path.basename(file_path),
                "symbol_type": "file_chunk",
                "start_line": start_line,
                "end_line": end_line,
                "content": chunk_content,
                "metadata": {
                    "is_fallback": True
                }
            })
            
        return chunks
