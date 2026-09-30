from __future__ import annotations

from pathlib import Path

import pytest

from filesystem import (
    DocumentationError,
    get_documents,
    get_projects,
    read_project_document,
    resolve_safe_path,
    search_project_documents,
)


def _create_project(base: Path, name: str) -> Path:
    project = base / name
    project.mkdir(parents=True, exist_ok=True)
    return project


def test_list_projects_only_directories_sorted_and_non_hidden(tmp_path: Path) -> None:
    _create_project(tmp_path, "zeta")
    _create_project(tmp_path, "alpha")
    _create_project(tmp_path, ".hidden")
    (tmp_path / "top-file.md").write_text("ignore", encoding="utf-8")

    assert get_projects(tmp_path) == ["alpha", "zeta"]


def test_list_documents_md_txt_and_subdirectories(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "README.md").write_text("readme", encoding="utf-8")
    (project / "notes.txt").write_text("notes", encoding="utf-8")
    (project / "ignore.json").write_text("{}", encoding="utf-8")
    (project / ".secret.md").write_text("secret", encoding="utf-8")
    (project / "incidents").mkdir()
    (project / "incidents" / "postgres.md").write_text("incident", encoding="utf-8")

    documents = get_documents(tmp_path, "proj")
    assert documents == ["README.md", "incidents/postgres.md", "notes.txt"]


def test_read_document_success(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "architecture.md").write_text("service topology", encoding="utf-8")

    content = read_project_document(tmp_path, "proj", "architecture.md")
    assert content == "service topology"


def test_read_document_missing_file_fails(tmp_path: Path) -> None:
    _create_project(tmp_path, "proj")

    with pytest.raises(DocumentationError, match="does not exist"):
        read_project_document(tmp_path, "proj", "missing.md")


def test_read_document_blocks_traversal(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "safe.md").write_text("ok", encoding="utf-8")

    with pytest.raises(DocumentationError, match="outside DOCUMENTATION_ROOT"):
        read_project_document(tmp_path, "proj", "../safe.md")


def test_resolve_safe_path_blocks_absolute_external(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "doc.md").write_text("ok", encoding="utf-8")

    external = Path.home() / ".ssh"
    with pytest.raises(DocumentationError, match="outside DOCUMENTATION_ROOT"):
        resolve_safe_path(tmp_path, external)


def test_search_case_insensitive_and_content_name_and_line(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "postgres-notes.md").write_text(
        "Infra status\nPostgreSQL reached max connections\nResolved",
        encoding="utf-8",
    )
    (project / "other.md").write_text("nothing here", encoding="utf-8")

    results = search_project_documents(tmp_path, "proj", "postgres")
    assert len(results) >= 1
    assert results[0]["document"] == "postgres-notes.md"
    assert any(match["line"] == 2 for match in results[0]["matches"])


def test_search_respects_result_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from filesystem import MAX_SEARCH_RESULTS

    project = _create_project(tmp_path, "proj")
    for index in range(5):
        (project / f"doc-{index}.md").write_text("postgres", encoding="utf-8")

    monkeypatch.setattr("filesystem.MAX_SEARCH_RESULTS", 2)
    results = search_project_documents(tmp_path, "proj", "postgres")
    assert len(results) == 2

    monkeypatch.setattr("filesystem.MAX_SEARCH_RESULTS", MAX_SEARCH_RESULTS)
