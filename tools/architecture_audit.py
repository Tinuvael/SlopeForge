#!/usr/bin/env python3
"""Deterministic, dependency-free report of SlopeForge's internal imports.

This is deliberately a small AST inventory, not an import resolver.  Run it from
any directory; paths and output are stable so reports can be compared in reviews.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("app", "database", "repositories", "services", "reports", "prototype_2d", "ui", "widgets", "tools")
IGNORED_PARTS = {".git", ".venv", "venv", "env", "build", "dist", "__pycache__", ".pytest_cache", ".mypy_cache"}


def python_files(include_tests: bool = False) -> list[Path]:
    roots = [ROOT / name for name in SOURCE_ROOTS]
    roots.append(ROOT / "main.py")
    if include_tests:
        roots.append(ROOT / "tests")
    files: list[Path] = []
    for root in roots:
        candidates = [root] if root.is_file() else root.rglob("*.py")
        files.extend(path for path in candidates if not IGNORED_PARTS.intersection(path.parts))
    return sorted(set(files))


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or "<root>"


def imported_names(path: Path, known_modules: set[str] | None = None) -> set[str]:
    """Return imported modules, resolving ``from package import module``.

    Without the alias check, ``from database import assessment_models`` was
    reported only as ``database``.  That loses the exact module edge and can also
    hide a cycle.  Imported classes/functions still correctly point at their
    containing module.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    current = module_name(path).split(".")
    if path.name != "__init__.py":
        current = current[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = current[: max(0, len(current) - node.level + 1)]
                prefix = ".".join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module or ""
            if prefix:
                module_aliases = {
                    f"{prefix}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                    and known_modules is not None
                    and f"{prefix}.{alias.name}" in known_modules
                }
                result.update(module_aliases or {prefix})
    return result


def inventory(include_tests: bool = False) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    files = python_files(include_tests)
    modules = {module_name(path): path for path in files}
    graph: dict[str, set[str]] = {}
    externals: dict[str, set[str]] = {}
    for module, path in sorted(modules.items()):
        internal, external = set(), set()
        for imported in imported_names(path, set(modules)):
            matches = [candidate for candidate in modules if candidate == imported or candidate.startswith(imported + ".")]
            if matches:
                internal.add(imported)
            elif imported.split(".")[0] in {name.split(".")[0] for name in modules}:
                internal.add(imported)
            else:
                external.add(imported)
        graph[module] = internal
        externals[module] = external
    return graph, externals


def strongly_connected(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Return internal cycles using Tarjan's algorithm."""
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    cycles: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for neighbour in sorted(graph.get(node, ())):
            if neighbour not in graph:
                continue
            if neighbour not in indices:
                visit(neighbour)
                low[node] = min(low[node], low[neighbour])
            elif neighbour in on_stack:
                low[node] = min(low[node], indices[neighbour])
        if low[node] == indices[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1 or node in graph.get(node, ()):
                cycles.append(tuple(sorted(component)))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(cycles)


def layer(module: str) -> str:
    return module.split(".", 1)[0]


def report(include_tests: bool = False) -> str:
    graph, externals = inventory(include_tests)
    lines = ["# SlopeForge internal dependency audit", "", "## Module imports"]
    for module, dependencies in sorted(graph.items()):
        lines.append(f"{module}: {', '.join(sorted(dependencies)) or '-'}")
    layer_edges: dict[str, set[str]] = defaultdict(set)
    for source, dependencies in graph.items():
        for dependency in dependencies:
            if layer(source) != layer(dependency):
                layer_edges[layer(source)].add(layer(dependency))
    lines += ["", "## Layer dependencies"]
    for source in sorted(layer_edges):
        lines.append(f"{source}: {', '.join(sorted(layer_edges[source]))}")

    def section(title: str, predicate) -> None:
        lines.extend(["", f"## {title}"])
        matches = [(source, dep) for source, deps in graph.items() for dep in deps if predicate(source, dep)]
        lines.extend(f"{source} -> {dep}" for source, dep in sorted(matches))
        if not matches:
            lines.append("-")

    section("prototype_2d imports", lambda _s, d: d == "prototype_2d" or d.startswith("prototype_2d."))
    section("ui.prototype_2d imports", lambda s, d: s.startswith("ui.prototype_2d") or d.startswith("ui.prototype_2d"))
    section("assessment workspace imports", lambda s, d: "assessment_workspace" in s or "assessment_workspace" in d)
    section("UI direct persistence/service imports", lambda s, d: s.startswith("ui.") and layer(d) in {"database", "repositories", "services"})

    domain_like = {m for m in graph if m.startswith("prototype_2d.") and m not in {"prototype_2d.blast_event_storage"}}
    lines += ["", "## Domain-like external framework imports"]
    framework_hits = []
    for source in sorted(domain_like):
        for dependency in sorted(externals[source]):
            if dependency.startswith(("PySide6", "sqlalchemy", "database")):
                framework_hits.append(f"{source} -> {dependency}")
    lines.extend(framework_hits or ["-"])
    cycles = strongly_connected(graph)
    lines += ["", "## Circular internal dependencies"]
    lines.extend(" <-> ".join(cycle) for cycle in cycles)
    if not cycles:
        lines.append("-")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-tests", action="store_true", help="include tests in the module inventory")
    parser.add_argument("--output", type=Path, help="write report to this path instead of stdout")
    args = parser.parse_args()
    output = report(args.include_tests)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
