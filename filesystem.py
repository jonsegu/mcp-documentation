from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import (
    ALLOWED_EXTENSIONS,
    MAX_DOCUMENT_BYTES,
    MAX_MATCHES_PER_DOCUMENT,
    MAX_SEARCH_RESULTS,
    SEARCH_CONTEXT_LINES,
)


class DocumentationError(ValueError):
    """Raised when a documentation operation cannot be completed safely."""


@dataclass(frozen=True)
class SearchMatch:
    line: int
    text: str
    context_before: str
    context_after: str


@dataclass(frozen=True)
class SearchResult:
    document: str
    matches: list[SearchMatch]


def resolve_safe_path(root: Path, requested_path: Path | str) -> Path:
    """Resolve a requested path and guarantee it stays inside the configured root."""
    base_root = root.expanduser().resolve()
    path_input = Path(requested_path).expanduser()
    candidate = path_input if path_input.is_absolute() else base_root / path_input
    resolved = candidate.resolve()

    try:
        resolved.relative_to(base_root)
    except ValueError as exc:
        raise DocumentationError(
            "Access denied: requested path is outside DOCUMENTATION_ROOT."
        ) from exc

    return resolved


def _validate_project_dir(root: Path, project: str) -> Path:
    project_path = resolve_safe_path(root, project)
    if not project_path.exists() or not project_path.is_dir():
        raise DocumentationError(f"Project '{project}' does not exist.")
    return project_path


def _iter_documents(project_dir: Path) -> list[Path]:
    documents: list[Path] = []
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(project_dir).parts):
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        documents.append(path)
    return sorted(documents)


def get_projects(root: Path) -> list[str]:
    """Return direct project directories under root sorted alphabetically."""
    safe_root = root.expanduser().resolve()
    if not safe_root.exists() or not safe_root.is_dir():
        return []

    projects = [
        item.name
        for item in safe_root.iterdir()
        if item.is_dir() and not item.name.startswith(".")
    ]
    return sorted(projects)


def get_documents(root: Path, project: str) -> list[str]:
    """List supported documents inside a project (recursive)."""
    project_dir = _validate_project_dir(root, project)
    return [str(path.relative_to(project_dir).as_posix()) for path in _iter_documents(project_dir)]


def read_project_document(root: Path, project: str, document: str) -> str:
    """Read a document from a project after applying all safety checks."""
    project_dir = _validate_project_dir(root, project)
    target = resolve_safe_path(project_dir, document)

    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise DocumentationError("Unsupported file type.")
    if not target.exists() or not target.is_file():
        raise DocumentationError(
            f"Document '{document}' does not exist in project '{project}'."
        )

    file_size = target.stat().st_size
    if file_size > MAX_DOCUMENT_BYTES:
        raise DocumentationError(
            f"Document exceeds size limit of {MAX_DOCUMENT_BYTES} bytes."
        )

    return target.read_text(encoding="utf-8")


def search_project_documents(root: Path, project: str, query: str) -> list[dict]:
    """Search by file name and file content in project documents."""
    if not query.strip():
        return []

    project_dir = _validate_project_dir(root, project)
    query_lower = query.lower()
    results: list[dict] = []

    for document_path in _iter_documents(project_dir):
        if len(results) >= MAX_SEARCH_RESULTS:
            break

        relative_name = str(document_path.relative_to(project_dir).as_posix())
        matches: list[dict] = []

        if query_lower in relative_name.lower():
            matches.append(
                {
                    "line": 0,
                    "text": relative_name,
                    "context_before": "",
                    "context_after": "",
                }
            )

        content = document_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for index, line in enumerate(lines, start=1):
            if len(matches) >= MAX_MATCHES_PER_DOCUMENT:
                break
            if query_lower not in line.lower():
                continue

            before_start = max(0, index - 1 - SEARCH_CONTEXT_LINES)
            after_end = min(len(lines), index + SEARCH_CONTEXT_LINES)
            context_before = "\n".join(lines[before_start : index - 1])
            context_after = "\n".join(lines[index:after_end])
            matches.append(
                {
                    "line": index,
                    "text": line,
                    "context_before": context_before,
                    "context_after": context_after,
                }
            )

        if matches:
            results.append({"document": relative_name, "matches": matches})

    return results
