"""AST extraction utilities."""

from __future__ import annotations

from dataclasses import dataclass
import re
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


def _extract_call_target(source_bytes: bytes, node: Any) -> str | None:
    snippet = _node_text(source_bytes, node).strip()
    if not snippet:
        return None
    match = re.match(r"([A-Za-z_][A-Za-z0-9_\.]*)\s*\(", snippet)
    if not match:
        return None
    target = match.group(1).split(".")[-1]
    if target in {"if", "for", "while", "return"}:
        return None
    return target


def _extract_inherits_from_class_snippet(class_snippet: str) -> list[str]:
    bases: list[str] = []
    py_match = re.search(r"class\s+[A-Za-z_][A-Za-z0-9_]*\s*\(([^)]*)\)", class_snippet)
    if py_match:
        for base in py_match.group(1).split(","):
            candidate = base.strip().split(".")[-1]
            if candidate:
                bases.append(candidate)
    js_match = re.search(r"extends\s+([A-Za-z_][A-Za-z0-9_\.]*)", class_snippet)
    if js_match:
        bases.append(js_match.group(1).split(".")[-1])
    return sorted(set(bases))


def _collect_symbols(language: str, source_text: str) -> dict[str, Any]:
    parser = _build_parser(language)
    source_bytes = source_text.encode("utf-8")
    fallback = {
        "functions": [],
        "classes": [],
        "imports": [],
        "calls": [],
        "inherits": [],
        "symbols": [],
        "parse_mode": "raw_text_fallback",
    }
    if parser is None:
        return fallback

    try:
        tree = parser.parse(source_bytes)
    except Exception:
        return fallback

    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    calls: list[dict[str, str]] = []
    inherits: list[dict[str, str]] = []
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
            fn_stack = [node]
            while fn_stack:
                fn_node = fn_stack.pop()
                if fn_node.type == "call_expression":
                    callee = _extract_call_target(source_bytes, fn_node)
                    if callee and callee != name:
                        calls.append({"caller": name, "callee": callee})
                fn_stack.extend(reversed(fn_node.children))
        elif ntype in class_nodes:
            name = _extract_name_from_decl(source_bytes, node)
            classes.append(name)
            symbols.append(Symbol(name=name, symbol_type="class", start_byte=node.start_byte, end_byte=node.end_byte))
            class_snippet = _node_text(source_bytes, node)
            for base in _extract_inherits_from_class_snippet(class_snippet):
                if base != name:
                    inherits.append({"class": name, "base": base})
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
        "calls": sorted(calls, key=lambda x: (x["caller"], x["callee"])),
        "inherits": sorted(inherits, key=lambda x: (x["class"], x["base"])),
        "symbols": [s.__dict__ for s in symbols],
        "parse_mode": "tree_sitter",
    }


def build_symbol_table(parsed_files: list[dict]) -> dict[str, dict]:
    """
    Build symbol table per file:
    {file: {functions: [], classes: [], imports: [], calls: [], inherits: [], symbols: []}}
    """
    table: dict[str, dict] = {}
    for file_doc in parsed_files:
        file_path = file_doc["filepath"]
        table[file_path] = _collect_symbols(file_doc["language"], file_doc["content"])
    return table
