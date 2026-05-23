"""AST extraction utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tree_sitter import Language, Parser
from tree_sitter_javascript import language as js_language
from tree_sitter_python import language as py_language
from tree_sitter_typescript import language_typescript


@dataclass(frozen=True)
class Symbol:
    name: str
    symbol_type: str
    start_byte: int
    end_byte: int


def _build_parser(language_name: str) -> Parser | None:
    parser = Parser()
    if language_name == "python":
        parser.language = Language(py_language())
        return parser
    if language_name == "javascript":
        parser.language = Language(js_language())
        return parser
    if language_name == "typescript":
        parser.language = Language(language_typescript())
        return parser
    return None


def _node_text(source_bytes: bytes, node: Any) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _extract_name_from_decl(source_bytes: bytes, node: Any) -> str:
    for child in node.children:
        if child.type in {"identifier", "property_identifier", "type_identifier"}:
            return _node_text(source_bytes, child).strip()
    return "<anonymous>"


def _collect_symbols(language: str, source_text: str) -> dict[str, Any]:
    parser = _build_parser(language)
    source_bytes = source_text.encode("utf-8")
    fallback = {"functions": [], "classes": [], "imports": [], "symbols": [], "parse_mode": "raw_text_fallback"}
    if parser is None:
        return fallback

    try:
        tree = parser.parse(source_bytes)
    except Exception:
        return fallback

    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    symbols: list[Symbol] = []

    function_nodes = {
        "function_definition",
        "function_declaration",
        "method_definition",
        "arrow_function",
        "function",
    }
    class_nodes = {"class_definition", "class_declaration"}
    import_nodes = {"import_statement", "import_from_statement", "import_declaration", "call_expression"}

    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        ntype = node.type

        if ntype in function_nodes:
            name = _extract_name_from_decl(source_bytes, node)
            functions.append(name)
            symbols.append(Symbol(name=name, symbol_type="function", start_byte=node.start_byte, end_byte=node.end_byte))
        elif ntype in class_nodes:
            name = _extract_name_from_decl(source_bytes, node)
            classes.append(name)
            symbols.append(Symbol(name=name, symbol_type="class", start_byte=node.start_byte, end_byte=node.end_byte))
        elif ntype in import_nodes:
            snippet = _node_text(source_bytes, node).strip()
            if ntype == "call_expression":
                if "require(" not in snippet:
                    snippet = ""
            if snippet:
                imports.append(snippet.splitlines()[0][:200])

        stack.extend(reversed(node.children))

    return {
        "functions": sorted(set(functions)),
        "classes": sorted(set(classes)),
        "imports": sorted(set(imports)),
        "symbols": [s.__dict__ for s in symbols],
        "parse_mode": "tree_sitter",
    }


def build_symbol_table(parsed_files: list[dict]) -> dict[str, dict]:
    """
    Build symbol table per file:
    {file: {functions: [], classes: [], imports: [], symbols: []}}
    """
    table: dict[str, dict] = {}
    for file_doc in parsed_files:
        file_path = file_doc["filepath"]
        table[file_path] = _collect_symbols(file_doc["language"], file_doc["content"])
    return table
