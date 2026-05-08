"""AST-based chunker using tree-sitter.

Extracts function-level and class-level chunks from Python and TypeScript files,
enriched with symbols_defined and imports metadata.  Falls back to the naive
line-based chunker for unsupported languages or parse failures.
"""

from dataclasses import dataclass, field

import structlog
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Node, Parser

from repolens.config import get_settings
from repolens.ingestion.chunker import chunk_file

log = structlog.get_logger(__name__)

PY_LANGUAGE = Language(tspython.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())

_LANGUAGE_MAP: dict[str, Language] = {
    "python": PY_LANGUAGE,
    "typescript": TS_LANGUAGE,
}

# tree-sitter node types that represent top-level definitions
_PY_DEFINITION_TYPES = {"function_definition", "class_definition", "decorated_definition"}
_TS_DEFINITION_TYPES = {
    "function_declaration",
    "class_declaration",
    "interface_declaration",
    "type_alias_declaration",
    "export_statement",
    "lexical_declaration",
}

_PY_IMPORT_TYPES = {"import_statement", "import_from_statement"}
_TS_IMPORT_TYPES = {"import_statement"}


@dataclass(frozen=True, slots=True)
class ASTChunk:
    """A semantically-meaningful code chunk extracted from an AST."""

    content: str
    start_line: int
    end_line: int
    symbols_defined: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def ast_chunk_file(
    content: str,
    language: str | None,
) -> list[ASTChunk]:
    """Parse *content* with tree-sitter and extract semantic chunks.

    Returns enriched ``ASTChunk`` objects with symbols and imports.
    Falls back to naive chunking if the language is unsupported or parsing fails.
    """
    if language not in _LANGUAGE_MAP:
        return _fallback(content)

    try:
        return _parse_and_chunk(content, language)
    except Exception:
        log.warning("ast_chunker.parse_failed", language=language)
        return _fallback(content)


def _parse_and_chunk(content: str, language: str) -> list[ASTChunk]:
    lang = _LANGUAGE_MAP[language]
    parser = Parser(lang)
    tree = parser.parse(content.encode("utf-8"))
    root = tree.root_node

    # Extract file-level imports
    file_imports = _extract_imports(root, language)

    # Extract top-level definitions
    chunks: list[ASTChunk] = []
    settings = get_settings()
    max_chunk_lines = settings.chunk_size * 3  # allow larger AST chunks than naive

    definition_types = _PY_DEFINITION_TYPES if language == "python" else _TS_DEFINITION_TYPES
    definitions = [child for child in root.children if child.type in definition_types]

    if not definitions:
        # No extractable definitions — fall back to naive
        return _fallback(content)

    # If there's a preamble (imports, module docstring, etc.), include it as a chunk
    if definitions[0].start_point[0] > 0:
        preamble_end = definitions[0].start_point[0]
        lines = content.splitlines(keepends=True)
        preamble_text = "".join(lines[:preamble_end])
        if preamble_text.strip():
            preamble_imports = _extract_imports(root, language)
            chunks.append(
                ASTChunk(
                    content=preamble_text,
                    start_line=1,
                    end_line=preamble_end,
                    symbols_defined=[],
                    imports=preamble_imports,
                )
            )

    for node in definitions:
        text = _node_text(node, content)
        start = node.start_point[0] + 1  # 1-indexed
        end = node.end_point[0] + 1

        # If the chunk is too large, sub-chunk with naive fallback
        line_count = end - start + 1
        if line_count > max_chunk_lines:
            sub_chunks = chunk_file(text)
            for sc in sub_chunks:
                chunks.append(
                    ASTChunk(
                        content=sc.content,
                        start_line=start + sc.start_line - 1,
                        end_line=start + sc.end_line - 1,
                        symbols_defined=_extract_symbols(node, language),
                        imports=[],
                    )
                )
            continue

        symbols = _extract_symbols(node, language)
        local_imports = _extract_local_imports(node, language)

        chunks.append(
            ASTChunk(
                content=text,
                start_line=start,
                end_line=end,
                symbols_defined=symbols,
                imports=local_imports or file_imports,
            )
        )

    return chunks if chunks else _fallback(content)


def _extract_symbols(node: Node, language: str) -> list[str]:
    """Extract symbol names defined by a node."""
    symbols: list[str] = []

    if language == "python":
        if node.type == "decorated_definition":
            # unwrap decorator to get the actual definition
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    node = child
                    break

        if node.type in ("function_definition", "class_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append((name_node.text or b"").decode("utf-8"))

            # Extract method names from classes
            if node.type == "class_definition":
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        actual = child
                        if child.type == "decorated_definition":
                            for sub in child.children:
                                if sub.type == "function_definition":
                                    actual = sub
                                    break
                        if actual.type == "function_definition":
                            method_name = actual.child_by_field_name("name")
                            if method_name:
                                symbols.append((method_name.text or b"").decode("utf-8"))

    elif language == "typescript":
        if node.type == "export_statement":
            for child in node.children:
                if child.type in _TS_DEFINITION_TYPES:
                    symbols.extend(_extract_symbols(child, language))
                    return symbols

        name_node = node.child_by_field_name("name")
        if name_node:
            symbols.append((name_node.text or b"").decode("utf-8"))

    return symbols


def _extract_imports(root: Node, language: str) -> list[str]:
    """Extract all import statements from the file root."""
    import_types = _PY_IMPORT_TYPES if language == "python" else _TS_IMPORT_TYPES
    imports: list[str] = []
    for child in root.children:
        if child.type in import_types:
            imports.append((child.text or b"").decode("utf-8").strip())
    return imports


def _extract_local_imports(node: Node, language: str) -> list[str]:
    """Extract imports within a node (rare but possible in some languages)."""
    import_types = _PY_IMPORT_TYPES if language == "python" else _TS_IMPORT_TYPES
    imports: list[str] = []
    for child in _walk_tree(node):
        if child.type in import_types:
            imports.append((child.text or b"").decode("utf-8").strip())
    return imports


def _walk_tree(node: Node) -> list[Node]:
    """Recursively collect all descendant nodes."""
    nodes: list[Node] = []
    for child in node.children:
        nodes.append(child)
        nodes.extend(_walk_tree(child))
    return nodes


def _node_text(node: Node, source: str) -> str:
    """Extract the source text for a node."""
    return source.encode("utf-8")[node.start_byte : node.end_byte].decode("utf-8")


def _fallback(content: str) -> list[ASTChunk]:
    """Fall back to naive line-based chunking, wrapping as ASTChunk."""
    raw = chunk_file(content)
    return [
        ASTChunk(
            content=rc.content,
            start_line=rc.start_line,
            end_line=rc.end_line,
            symbols_defined=[],
            imports=[],
        )
        for rc in raw
    ]
