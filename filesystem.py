from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
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


STOPWORDS = {
    "a",
    "al",
    "and",
    "como",
    "con",
    "cual",
    "cuál",
    "de",
    "del",
    "el",
    "en",
    "es",
    "for",
    "how",
    "la",
    "las",
    "lo",
    "los",
    "para",
    "por",
    "que",
    "qué",
    "se",
    "si",
    "the",
    "to",
    "un",
    "una",
    "y",
}
MAX_ANSWER_SOURCES = 2
MAX_SECTION_LINES = 20
PROJECT_HINT_PATTERNS = [
    r"(?:proyecto|project)\s+de\s+([a-z0-9_-]+)",
    r"(?:proyecto|project)\s+([a-z0-9_-]+)",
]


def _project_root(root: Path) -> Path:
    return root.expanduser().resolve()


def _validate_project_name(root: Path, project: str) -> Path:
    if not project.strip():
        raise DocumentationError("Project name cannot be empty.")

    project_path = Path(project).expanduser()
    if project_path.is_absolute() or len(project_path.parts) != 1:
        raise DocumentationError("Project name must be a single directory name.")
    if any(part in {".", ".."} for part in project_path.parts):
        raise DocumentationError("Project name is invalid.")
    if project_path.name.startswith("."):
        raise DocumentationError("Hidden projects are not allowed.")

    return _project_root(root) / project_path.name


def resolve_safe_path(root: Path, requested_path: Path | str) -> Path:
    """Resolve a requested path and guarantee it stays inside the configured root."""
    base_root = _project_root(root)
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


def _ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _normalize_document_path(project_dir: Path, document: str, default_suffix: str = ".md") -> Path:
    path_input = Path(document).expanduser()
    candidate = path_input if path_input.is_absolute() else project_dir / path_input
    if candidate.suffix == "":
        candidate = candidate.with_suffix(default_suffix)
    return resolve_safe_path(project_dir, candidate)


def _write_text_file(path: Path, content: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise DocumentationError(f"Document '{path.name}' already exists.")

    _ensure_parent_directory(path)
    path.write_text(content, encoding="utf-8")


def _validate_text_document(path: Path) -> None:
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise DocumentationError("Unsupported file type.")
    if not path.exists() or not path.is_file():
        raise DocumentationError(f"Document '{path.name}' does not exist.")

    file_size = path.stat().st_size
    if file_size > MAX_DOCUMENT_BYTES:
        raise DocumentationError(
            f"Document exceeds size limit of {MAX_DOCUMENT_BYTES} bytes."
        )


def _read_text_document(path: Path) -> str:
    _validate_text_document(path)
    return path.read_text(encoding="utf-8")


def _append_text(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if existing.endswith("\n") or addition.startswith("\n"):
        return existing + addition
    return existing + "\n" + addition


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _tokenize(value: str) -> list[str]:
    normalized = _normalize_text(value)
    tokens = re.findall(r"[a-z0-9_-]+", normalized)
    return [token for token in tokens if len(token) > 1 and token not in STOPWORDS]


def _compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_text(value))


def _term_variants(token: str) -> set[str]:
    variants = {token}
    if token.endswith("s") and len(token) > 3:
        variants.add(token[:-1])
    if not token.endswith("s"):
        variants.add(f"{token}s")

    aliases = {
        "db": {"database", "base", "datos"},
        "database": {"db", "base", "datos"},
        "secret": {"secreto", "secrets", "secretos"},
        "secreto": {"secret", "secrets", "secretos"},
        "qa": {"quality", "assurance", "testing"},
    }
    variants.update(aliases.get(token, set()))
    return variants


def _project_aliases(project: str) -> set[str]:
    normalized_project = _normalize_text(project)
    compact_project = _compact_text(project)
    aliases = {normalized_project, compact_project}

    for token in _tokenize(project):
        aliases.add(token)
        if len(token) > 6:
            aliases.add(token[:-1])
        if token.endswith("school") and len(token) > len("school") + 3:
            aliases.add(token[: -len("school")])

    return {alias for alias in aliases if alias}


def _project_reference_score(reference: str, project: str) -> int:
    normalized_reference = _normalize_text(reference).strip()
    compact_reference = _compact_text(reference)
    if not normalized_reference and not compact_reference:
        return 0

    normalized_project = _normalize_text(project)
    compact_project = _compact_text(project)
    if normalized_reference == normalized_project or compact_reference == compact_project:
        return 100

    score = 0
    if normalized_reference and normalized_reference in normalized_project:
        score = max(score, 85)
    if compact_reference and compact_reference in compact_project:
        score = max(score, 82)

    project_aliases = _project_aliases(project)
    for token in _tokenize(reference):
        for alias in project_aliases:
            if token == alias:
                score = max(score, 75)
            elif token in alias or alias in token:
                score = max(score, 62)

    if compact_reference and compact_project:
        ratio = SequenceMatcher(None, compact_reference, compact_project).ratio()
        if ratio >= 0.55:
            score = max(score, int(ratio * 100))

    return score


def _extract_project_candidates(question: str) -> list[str]:
    normalized_question = _normalize_text(question)
    candidates: list[str] = []

    for pattern in PROJECT_HINT_PATTERNS:
        for match in re.finditer(pattern, normalized_question):
            candidate = match.group(1).strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)

    for token in _tokenize(question):
        if len(token) >= 6 and token not in candidates:
            candidates.append(token)

    return candidates


def resolve_project_reference(root: Path, project: str | None = None, question: str | None = None) -> str | None:
    projects = get_projects(root)
    if not projects:
        return None

    references: list[str] = []
    if project is not None and project.strip():
        references.append(project)
    if question is not None and question.strip():
        references.extend(_extract_project_candidates(question))

    best_match: str | None = None
    best_score = 0
    for reference in references:
        for candidate_project in projects:
            score = _project_reference_score(reference, candidate_project)
            if score > best_score:
                best_score = score
                best_match = candidate_project

    if best_score >= 60:
        return best_match
    return None


def _line_match_score(query_terms: list[str], line: str) -> int:
    normalized_line = _normalize_text(line)
    line_tokens = set(_tokenize(line))
    score = 0

    for term in query_terms:
        term_score = 0
        for variant in _term_variants(term):
            if variant in normalized_line:
                term_score = max(term_score, 3)
            if any(token.startswith(variant) or variant.startswith(token) for token in line_tokens):
                term_score = max(term_score, 2)
        score += term_score

    if normalized_line.startswith(("#", "##", "###")):
        score += 1

    return score


def _build_match(lines: list[str], index: int, score: int) -> dict:
    before_start = max(0, index - 1 - SEARCH_CONTEXT_LINES)
    after_end = min(len(lines), index + SEARCH_CONTEXT_LINES)
    return {
        "line": index,
        "text": lines[index - 1],
        "context_before": "\n".join(lines[before_start : index - 1]),
        "context_after": "\n".join(lines[index:after_end]),
        "score": score,
    }


def _extract_paragraph(lines: list[str], anchor_line: int) -> tuple[int, int, str | None, str]:
    start = anchor_line
    while start > 1 and lines[start - 2].strip():
        start -= 1

    end = anchor_line
    while end < len(lines) and lines[end].strip():
        end += 1

    excerpt_lines = lines[start - 1 : end]
    return start, end, None, "\n".join(excerpt_lines).strip()


def _extract_section(lines: list[str], anchor_line: int) -> tuple[int, int, str | None, str]:
    headings = [
        (index, line)
        for index, line in enumerate(lines, start=1)
        if re.match(r"^\s*#{1,6}\s+\S", line)
    ]
    if not headings:
        return _extract_paragraph(lines, anchor_line)

    section_start = 1
    section_title: str | None = None
    section_end = len(lines)
    for index, line in headings:
        if index <= anchor_line:
            section_start = index
            section_title = re.sub(r"^\s*#{1,6}\s+", "", line).strip()
        elif index > anchor_line:
            section_end = index - 1
            break

    if section_end - section_start + 1 > MAX_SECTION_LINES:
        excerpt_start = max(section_start, anchor_line - 8)
        excerpt_end = min(section_end, anchor_line + 8)
        excerpt_lines = lines[excerpt_start - 1 : excerpt_end]
        if section_title and excerpt_start > section_start:
            excerpt_lines = [lines[section_start - 1], ""] + excerpt_lines
        return excerpt_start, excerpt_end, section_title, "\n".join(excerpt_lines).strip()

    excerpt_lines = lines[section_start - 1 : section_end]
    return section_start, section_end, section_title, "\n".join(excerpt_lines).strip()


def _extract_relevant_excerpt(content: str, match_line: int) -> dict:
    lines = content.splitlines()
    if not lines:
        return {
            "section_title": None,
            "excerpt": "",
            "line_start": 0,
            "line_end": 0,
        }

    anchor_line = match_line if match_line > 0 else 1
    line_start, line_end, section_title, excerpt = _extract_section(lines, anchor_line)
    return {
        "section_title": section_title,
        "excerpt": excerpt,
        "line_start": line_start,
        "line_end": line_end,
    }


def _best_match_line(result: dict) -> int:
    content_matches = [match for match in result["matches"] if match["line"] > 0]
    if not content_matches:
        return 1
    best_match = max(content_matches, key=lambda match: (match["score"], -match["line"]))
    return int(best_match["line"])


def _build_answer_sources(root: Path, results: list[dict]) -> list[dict]:
    sources: list[dict] = []
    for result in results[:MAX_ANSWER_SOURCES]:
        content = read_project_document(root, result["project"], result["document"])
        excerpt = _extract_relevant_excerpt(content, _best_match_line(result))
        sources.append(
            {
                "project": result["project"],
                "document": result["document"],
                "score": result["score"],
                "section_title": excerpt["section_title"],
                "excerpt": excerpt["excerpt"],
                "line_start": excerpt["line_start"],
                "line_end": excerpt["line_end"],
            }
        )
    return sources


def _compose_final_answer(question: str, resolved_project: str | None, sources: list[dict]) -> str:
    if not sources:
        if resolved_project is not None:
            return f"No encontré información suficiente en la documentación del proyecto {resolved_project} para responder: {question}"
        return f"No encontré información suficiente en la documentación para responder: {question}"

    scope = (
        f"del proyecto {resolved_project}"
        if resolved_project is not None
        else "de la documentación disponible"
    )
    sections: list[str] = []
    for source in sources:
        label = source["document"]
        if source["section_title"]:
            label = f"{label} - {source['section_title']}"
        sections.append(f"Fuente: {label}\n{source['excerpt']}")

    return f"Según la documentación {scope}, esto es lo relevante para responder tu pregunta:\n\n" + "\n\n".join(sections)


def _search_documents(project_dir: Path, query: str) -> list[dict]:
    query_terms = _tokenize(query)
    normalized_query = _normalize_text(query).strip()
    if not normalized_query:
        return []

    results: list[dict] = []

    for document_path in _iter_documents(project_dir):
        relative_name = str(document_path.relative_to(project_dir).as_posix())
        normalized_name = _normalize_text(relative_name)
        document_score = 0
        matches: list[dict] = []

        if normalized_query in normalized_name:
            document_score += 6
            matches.append(
                {
                    "line": 0,
                    "text": relative_name,
                    "context_before": "",
                    "context_after": "",
                    "score": 6,
                }
            )
        else:
            name_term_score = _line_match_score(query_terms, relative_name)
            if name_term_score:
                document_score += name_term_score
                matches.append(
                    {
                        "line": 0,
                        "text": relative_name,
                        "context_before": "",
                        "context_after": "",
                        "score": name_term_score,
                    }
                )

        content = _read_text_document(document_path)
        lines = content.splitlines()
        ranked_matches: list[dict] = []

        for index, line in enumerate(lines, start=1):
            score = 0
            normalized_line = _normalize_text(line)
            if normalized_query and normalized_query in normalized_line:
                score += max(6, len(query_terms) * 2)
            score += _line_match_score(query_terms, line)
            if score <= 0:
                continue
            ranked_matches.append(_build_match(lines, index, score))

        ranked_matches.sort(key=lambda match: (-match["score"], match["line"]))
        top_matches = ranked_matches[:MAX_MATCHES_PER_DOCUMENT]
        if top_matches:
            document_score += sum(match["score"] for match in top_matches)
            matches.extend(top_matches)

        if matches:
            results.append(
                {
                    "document": relative_name,
                    "score": document_score,
                    "matches": matches,
                }
            )

    results.sort(key=lambda item: (-item["score"], item["document"]))
    return results[:MAX_SEARCH_RESULTS]


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


def create_project(root: Path, project: str, initial_document: str | None = None, content: str = "", overwrite_document: bool = False, default_suffix: str = ".md") -> str:
    """Create a project directory and optionally seed it with a first document."""
    project_dir = _validate_project_name(root, project)
    project_dir.mkdir(parents=True, exist_ok=True)

    if initial_document is not None:
        document_path = _normalize_document_path(project_dir, initial_document, default_suffix=default_suffix)
        _write_text_file(document_path, content, overwrite=overwrite_document)
        return f"Project '{project}' created with document '{document_path.relative_to(project_dir).as_posix()}'."

    return f"Project '{project}' created."


def create_document(root: Path, project: str, document: str, content: str = "", overwrite: bool = False, default_suffix: str = ".md") -> str:
    """Create a new document inside an existing project."""
    project_dir = _validate_project_dir(root, project)
    document_path = _normalize_document_path(project_dir, document, default_suffix=default_suffix)
    _write_text_file(document_path, content, overwrite=overwrite)
    return f"Document '{document_path.relative_to(project_dir).as_posix()}' created in project '{project}'."


def import_document(root: Path, project: str, source_path: str, document: str | None = None, overwrite: bool = False) -> str:
    """Import an existing local .md or .txt file into a project."""
    project_dir = _validate_project_dir(root, project)
    source = Path(source_path).expanduser().resolve()
    _validate_text_document(source)

    target_name = document if document is not None else source.name
    target_path = _normalize_document_path(project_dir, target_name, default_suffix=source.suffix.lower() or ".md")
    content = _read_text_document(source)
    _write_text_file(target_path, content, overwrite=overwrite)
    return f"Document '{target_path.relative_to(project_dir).as_posix()}' imported into project '{project}'."


def replace_document_content(root: Path, project: str, document: str, content: str, default_suffix: str = ".md") -> str:
    """Replace the full content of a document."""
    project_dir = _validate_project_dir(root, project)
    document_path = _normalize_document_path(project_dir, document, default_suffix=default_suffix)

    if not document_path.exists() or not document_path.is_file():
        raise DocumentationError(f"Document '{document}' does not exist in project '{project}'.")

    document_path.write_text(content, encoding="utf-8")
    return f"Document '{document_path.relative_to(project_dir).as_posix()}' updated in project '{project}'."


def append_to_document(root: Path, project: str, document: str, content: str, default_suffix: str = ".md") -> str:
    """Append text to the end of a document."""
    project_dir = _validate_project_dir(root, project)
    document_path = _normalize_document_path(project_dir, document, default_suffix=default_suffix)

    if not document_path.exists() or not document_path.is_file():
        raise DocumentationError(f"Document '{document}' does not exist in project '{project}'.")

    current_content = document_path.read_text(encoding="utf-8")
    document_path.write_text(_append_text(current_content, content), encoding="utf-8")
    return f"Content appended to '{document_path.relative_to(project_dir).as_posix()}' in project '{project}'."


def delete_document(root: Path, project: str, document: str, default_suffix: str = ".md") -> str:
    """Delete a document from a project."""
    project_dir = _validate_project_dir(root, project)
    document_path = _normalize_document_path(project_dir, document, default_suffix=default_suffix)

    if not document_path.exists() or not document_path.is_file():
        raise DocumentationError(f"Document '{document}' does not exist in project '{project}'.")

    document_path.unlink()
    return f"Document '{document_path.relative_to(project_dir).as_posix()}' deleted from project '{project}'."


def delete_project(root: Path, project: str) -> str:
    """Delete a project directory and all of its contents."""
    project_dir = _validate_project_dir(root, project)
    for child in sorted(project_dir.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    project_dir.rmdir()
    return f"Project '{project}' deleted."


def read_project_document(root: Path, project: str, document: str) -> str:
    """Read a document from a project after applying all safety checks."""
    project_dir = _validate_project_dir(root, project)
    target = resolve_safe_path(project_dir, document)
    try:
        return _read_text_document(target)
    except DocumentationError as exc:
        if not target.exists() or not target.is_file():
            raise DocumentationError(
                f"Document '{document}' does not exist in project '{project}'."
            ) from exc
        raise


def search_project_documents(root: Path, project: str, query: str) -> list[dict]:
    """Search project documents using literal and natural-language term matching."""
    project_dir = _validate_project_dir(root, project)
    return _search_documents(project_dir, query)


def search_all_documents(root: Path, query: str) -> list[dict]:
    """Search across all projects using ranked natural-language matching."""
    if not query.strip():
        return []

    results: list[dict] = []
    for project in get_projects(root):
        project_results = search_project_documents(root, project, query)
        for result in project_results:
            results.append(
                {
                    "project": project,
                    "document": result["document"],
                    "score": result["score"],
                    "matches": result["matches"],
                }
            )

    results.sort(key=lambda item: (-item["score"], item["project"], item["document"]))
    return results[:MAX_SEARCH_RESULTS]


def answer_documentation_question(root: Path, question: str, project: str | None = None) -> dict:
    """Return a final answer and the supporting excerpts for a natural-language documentation question."""
    if not question.strip():
        return {
            "question": question,
            "resolved_project": None,
            "answer": "",
            "sources": [],
            "results": [],
        }

    resolved_project = resolve_project_reference(root, project=project, question=question)

    if resolved_project is not None:
        results = search_project_documents(root, resolved_project, question)
        formatted_results = [
            {
                "project": resolved_project,
                "document": result["document"],
                "score": result["score"],
                "matches": result["matches"],
            }
            for result in results
        ]
    else:
        formatted_results = search_all_documents(root, question)

    sources = _build_answer_sources(root, formatted_results)
    return {
        "question": question,
        "resolved_project": resolved_project,
        "answer": _compose_final_answer(question, resolved_project, sources),
        "sources": sources,
        "results": formatted_results,
    }
