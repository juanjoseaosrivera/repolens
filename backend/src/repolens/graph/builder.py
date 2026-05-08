"""Graph builder — populates Neo4j from AST analysis during ingestion.

Creates :File, :Function, :Class nodes and :IMPORTS, :CALLS, :DEFINES
relationships from the AST metadata extracted during chunking.
"""

from typing import Any

import structlog
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Node, Parser

from repolens.graph.client import GraphClient
from repolens.graph.schema import CLEANUP_QUERY, SETUP_QUERIES

log = structlog.get_logger(__name__)

PY_LANGUAGE = Language(tspython.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())

_LANGUAGE_MAP: dict[str, Language] = {
    "python": PY_LANGUAGE,
    "typescript": TS_LANGUAGE,
}


async def setup_graph_schema(client: GraphClient) -> None:
    """Create constraints and indexes (idempotent)."""
    for query in SETUP_QUERIES:
        await client.write(query)
    log.info("graph.schema_ready")


async def build_graph(
    client: GraphClient,
    repo_id: str,
    files: list[dict[str, Any]],
) -> None:
    """Build the dependency graph for a repository.

    Args:
        client: Neo4j client.
        repo_id: Repository UUID string.
        files: List of dicts with keys: path, language, content.
    """
    # Clean previous graph data for this repo
    await client.write(CLEANUP_QUERY, repo_id=repo_id)

    file_count = 0
    func_count = 0
    class_count = 0

    for file_info in files:
        path = file_info["path"]
        language = file_info.get("language")
        content = file_info["content"]

        # Create :File node
        await client.write(
            "MERGE (f:File {repo_id: $repo_id, path: $path}) SET f.language = $language",
            repo_id=repo_id,
            path=path,
            language=language,
        )
        file_count += 1

        if language not in _LANGUAGE_MAP:
            continue

        lang = _LANGUAGE_MAP[language]
        parser = Parser(lang)
        tree = parser.parse(content.encode("utf-8"))
        root = tree.root_node

        # Extract and create definitions
        definitions = _extract_definitions(root, language, path)
        for defn in definitions:
            if defn["kind"] == "function":
                await client.write(
                    "MERGE (fn:Function {repo_id: $repo_id, qualified_name: $qname}) "
                    "SET fn.name = $name, fn.file_path = $path, "
                    "fn.start_line = $start, fn.end_line = $end",
                    repo_id=repo_id,
                    qname=f"{path}::{defn['name']}",
                    name=defn["name"],
                    path=path,
                    start=defn["start_line"],
                    end=defn["end_line"],
                )
                # :File -[:DEFINES]-> :Function
                await client.write(
                    "MATCH (f:File {repo_id: $repo_id, path: $path}) "
                    "MATCH (fn:Function {repo_id: $repo_id, qualified_name: $qname}) "
                    "MERGE (f)-[:DEFINES]->(fn)",
                    repo_id=repo_id,
                    path=path,
                    qname=f"{path}::{defn['name']}",
                )
                func_count += 1

            elif defn["kind"] == "class":
                await client.write(
                    "MERGE (c:Class {repo_id: $repo_id, qualified_name: $qname}) "
                    "SET c.name = $name, c.file_path = $path, "
                    "c.start_line = $start, c.end_line = $end",
                    repo_id=repo_id,
                    qname=f"{path}::{defn['name']}",
                    name=defn["name"],
                    path=path,
                    start=defn["start_line"],
                    end=defn["end_line"],
                )
                await client.write(
                    "MATCH (f:File {repo_id: $repo_id, path: $path}) "
                    "MATCH (c:Class {repo_id: $repo_id, qualified_name: $qname}) "
                    "MERGE (f)-[:DEFINES]->(c)",
                    repo_id=repo_id,
                    path=path,
                    qname=f"{path}::{defn['name']}",
                )
                class_count += 1

                # Class methods → :Class -[:DEFINES]-> :Function
                for method in defn.get("methods", []):
                    method_qname = f"{path}::{defn['name']}.{method}"
                    await client.write(
                        "MERGE (fn:Function {repo_id: $repo_id, qualified_name: $qname}) "
                        "SET fn.name = $name, fn.file_path = $path",
                        repo_id=repo_id,
                        qname=method_qname,
                        name=method,
                        path=path,
                    )
                    await client.write(
                        "MATCH (c:Class {repo_id: $repo_id, qualified_name: $cqname}) "
                        "MATCH (fn:Function {repo_id: $repo_id, qualified_name: $fqname}) "
                        "MERGE (c)-[:DEFINES]->(fn)",
                        repo_id=repo_id,
                        cqname=f"{path}::{defn['name']}",
                        fqname=method_qname,
                    )

        # Extract and create import relationships
        imports = _extract_import_targets(root, language)
        for imp in imports:
            # Create or match the target file and link
            await client.write(
                "MERGE (target:File {repo_id: $repo_id, path: $target_path}) "
                "WITH target "
                "MATCH (source:File {repo_id: $repo_id, path: $source_path}) "
                "MERGE (source)-[:IMPORTS]->(target)",
                repo_id=repo_id,
                source_path=path,
                target_path=imp,
            )

        # Extract function calls
        calls = _extract_calls(root, language, path)
        for caller_qname, callee_name in calls:
            # Best-effort: link to any function with that name in the repo
            await client.write(
                "MATCH (caller:Function {repo_id: $repo_id, qualified_name: $caller}) "
                "MATCH (callee:Function {repo_id: $repo_id}) "
                "WHERE callee.name = $callee_name "
                "MERGE (caller)-[:CALLS]->(callee)",
                repo_id=repo_id,
                caller=caller_qname,
                callee_name=callee_name,
            )

    log.info(
        "graph.built",
        repo_id=repo_id,
        files=file_count,
        functions=func_count,
        classes=class_count,
    )


def _extract_definitions(root: Node, language: str, file_path: str) -> list[dict[str, Any]]:
    """Extract function and class definitions from the AST root."""
    definitions: list[dict[str, Any]] = []

    if language == "python":
        for child in root.children:
            node = child
            if child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in ("function_definition", "class_definition"):
                        node = sub
                        break

            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    definitions.append(
                        {
                            "kind": "function",
                            "name": (name_node.text or b"").decode(),
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                        }
                    )
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    methods = _extract_class_methods(node)
                    definitions.append(
                        {
                            "kind": "class",
                            "name": (name_node.text or b"").decode(),
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                            "methods": methods,
                        }
                    )

    elif language == "typescript":
        for child in root.children:
            actual = child
            if child.type == "export_statement":
                for sub in child.children:
                    if sub.type in ("function_declaration", "class_declaration"):
                        actual = sub
                        break

            if actual.type == "function_declaration":
                name_node = actual.child_by_field_name("name")
                if name_node:
                    definitions.append(
                        {
                            "kind": "function",
                            "name": (name_node.text or b"").decode(),
                            "start_line": actual.start_point[0] + 1,
                            "end_line": actual.end_point[0] + 1,
                        }
                    )
            elif actual.type == "class_declaration":
                name_node = actual.child_by_field_name("name")
                if name_node:
                    definitions.append(
                        {
                            "kind": "class",
                            "name": (name_node.text or b"").decode(),
                            "start_line": actual.start_point[0] + 1,
                            "end_line": actual.end_point[0] + 1,
                            "methods": [],
                        }
                    )

    return definitions


def _extract_class_methods(class_node: Node) -> list[str]:
    """Extract method names from a Python class body."""
    methods: list[str] = []
    body = class_node.child_by_field_name("body")
    if not body:
        return methods
    for child in body.children:
        actual = child
        if child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "function_definition":
                    actual = sub
                    break
        if actual.type == "function_definition":
            name = actual.child_by_field_name("name")
            if name:
                methods.append((name.text or b"").decode())
    return methods


def _extract_import_targets(root: Node, language: str) -> list[str]:
    """Extract import target module paths (best-effort file path mapping)."""
    targets: list[str] = []
    if language == "python":
        for child in root.children:
            if child.type == "import_from_statement":
                module = child.child_by_field_name("module_name")
                if module:
                    mod_path = (module.text or b"").decode().replace(".", "/") + ".py"
                    targets.append(mod_path)
    elif language == "typescript":
        for child in root.children:
            if child.type == "import_statement":
                source = child.child_by_field_name("source")
                if source:
                    raw = (source.text or b"").decode().strip("'\"")
                    if raw.startswith("."):
                        path = raw + ".ts" if not raw.endswith(".ts") else raw
                        targets.append(path)
    return targets


def _extract_calls(root: Node, language: str, file_path: str) -> list[tuple[str, str]]:
    """Extract (caller_qualified_name, callee_name) pairs."""
    calls: list[tuple[str, str]] = []
    if language != "python":
        return calls

    for child in root.children:
        node = child
        if child.type == "decorated_definition":
            for sub in child.children:
                if sub.type == "function_definition":
                    node = sub
                    break

        if node.type == "function_definition":
            func_name = node.child_by_field_name("name")
            if not func_name:
                continue
            caller = f"{file_path}::{(func_name.text or b'').decode()}"
            body = node.child_by_field_name("body")
            if body:
                for call_node in _find_calls(body):
                    calls.append((caller, call_node))
    return calls


def _find_calls(node: Node) -> list[str]:
    """Recursively find function call names within a node."""
    names: list[str] = []
    if node.type == "call":
        func = node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                names.append((func.text or b"").decode())
            elif func.type == "attribute":
                attr = func.child_by_field_name("attribute")
                if attr:
                    names.append((attr.text or b"").decode())
    for child in node.children:
        names.extend(_find_calls(child))
    return names
