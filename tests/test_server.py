from __future__ import annotations

from pathlib import Path

import pytest

from filesystem import (
    answer_documentation_question,
    DocumentationError,
    append_to_document,
    create_document,
    create_project,
    delete_document,
    delete_project,
    get_documents,
    get_projects,
    import_document,
    read_project_document,
    resolve_safe_path,
    replace_document_content,
    search_all_documents,
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


def test_create_project_with_initial_document(tmp_path: Path) -> None:
    result = create_project(tmp_path, "nuevo", initial_document="ejemplo", content="hola")

    assert result == "Project 'nuevo' created with document 'ejemplo.md'."
    assert (tmp_path / "nuevo").is_dir()
    assert (tmp_path / "nuevo" / "ejemplo.md").read_text(encoding="utf-8") == "hola"


def test_create_document_appends_default_extension(tmp_path: Path) -> None:
    _create_project(tmp_path, "proj")

    result = create_document(tmp_path, "proj", "nota", content="contenido")

    assert result == "Document 'nota.md' created in project 'proj'."
    assert (tmp_path / "proj" / "nota.md").read_text(encoding="utf-8") == "contenido"


def test_edit_document_append_and_replace(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "nota.md").write_text("uno", encoding="utf-8")

    append_result = append_to_document(tmp_path, "proj", "nota", "dos")
    assert append_result == "Content appended to 'nota.md' in project 'proj'."
    assert (project / "nota.md").read_text(encoding="utf-8") == "uno\ndos"

    replace_result = replace_document_content(tmp_path, "proj", "nota", "tres")
    assert replace_result == "Document 'nota.md' updated in project 'proj'."
    assert (project / "nota.md").read_text(encoding="utf-8") == "tres"


def test_delete_document_and_project(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "nota.md").write_text("contenido", encoding="utf-8")

    delete_doc_result = delete_document(tmp_path, "proj", "nota")
    assert delete_doc_result == "Document 'nota.md' deleted from project 'proj'."
    assert not (project / "nota.md").exists()

    (project / "otra.txt").write_text("x", encoding="utf-8")
    delete_project_result = delete_project(tmp_path, "proj")
    assert delete_project_result == "Project 'proj' deleted."
    assert not project.exists()


def test_import_document_uses_source_name_by_default(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    _create_project(root, "proj")
    source = tmp_path / "adjunto.md"
    source.write_text("contenido importado", encoding="utf-8")

    result = import_document(root, "proj", str(source))

    assert result == "Document 'adjunto.md' imported into project 'proj'."
    assert (root / "proj" / "adjunto.md").read_text(encoding="utf-8") == "contenido importado"


def test_import_document_allows_custom_target_name(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    _create_project(root, "proj")
    source = tmp_path / "adjunto.txt"
    source.write_text("contenido importado", encoding="utf-8")

    result = import_document(root, "proj", str(source), document="carpeta/guia")

    assert result == "Document 'carpeta/guia.txt' imported into project 'proj'."
    assert (root / "proj" / "carpeta" / "guia.txt").read_text(encoding="utf-8") == "contenido importado"


def test_import_document_rejects_unsupported_source_type(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    _create_project(root, "proj")
    source = tmp_path / "adjunto.json"
    source.write_text("{}", encoding="utf-8")

    with pytest.raises(DocumentationError, match="Unsupported file type"):
        import_document(root, "proj", str(source))


def test_search_project_documents_understands_natural_language_query(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "devops-procedures.md").write_text(
        "# Secrets\n"
        "To change the value of an existing secret, update it in AWS Secrets Manager.\n"
        "Do not edit the tfvars value to rotate a secret.\n",
        encoding="utf-8",
    )

    results = search_project_documents(tmp_path, "proj", "como cambiar el valor de un secret ya creado")

    assert results
    assert results[0]["document"] == "devops-procedures.md"
    assert any("existing secret" in match["text"] for match in results[0]["matches"])
    assert results[0]["score"] > 0


def test_search_all_documents_ranks_across_projects(tmp_path: Path) -> None:
    project_a = _create_project(tmp_path, "onersiverschool")
    (project_a / "devops-procedures.md").write_text(
        "Grant QA database access through the QA bastion process.",
        encoding="utf-8",
    )
    project_b = _create_project(tmp_path, "other")
    (project_b / "notes.md").write_text("General notes without db access details.", encoding="utf-8")

    results = search_all_documents(tmp_path, "como darle acceso a la db a una persona en qa")

    assert results
    assert results[0]["project"] == "onersiverschool"
    assert results[0]["document"] == "devops-procedures.md"


def test_answer_documentation_question_returns_ranked_sources(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "proj")
    (project / "runbook.md").write_text(
        "# Secret Rotation\n"
        "Restart the API deployment after rotating a secret so new tasks load the new value.\n"
        "Do not update the tfvars value to rotate the secret.\n",
        encoding="utf-8",
    )

    answer = answer_documentation_question(tmp_path, "que hago despues de cambiar un secreto", project="proj")

    assert answer["question"] == "que hago despues de cambiar un secreto"
    assert answer["resolved_project"] == "proj"
    assert "Según la documentación del proyecto proj" in answer["answer"]
    assert "Restart the API deployment" in answer["answer"]
    assert answer["sources"]
    assert answer["sources"][0]["section_title"] == "Secret Rotation"
    assert answer["results"]
    assert answer["results"][0]["document"] == "runbook.md"


def test_answer_documentation_question_resolves_project_alias(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "onersiverschool")
    (project / "devops-procedures.md").write_text(
        "# Secrets\n"
        "To create a new secret, add it in AWS Secrets Manager for the right environment.\n"
        "Then redeploy the service if the application only loads secrets at startup.\n",
        encoding="utf-8",
    )

    answer = answer_documentation_question(
        tmp_path,
        "como crear un nuevo secret",
        project="oneriver",
    )

    assert answer["resolved_project"] == "onersiverschool"
    assert "AWS Secrets Manager" in answer["answer"]
    assert answer["sources"][0]["document"] == "devops-procedures.md"


def test_answer_documentation_question_infers_project_from_question(tmp_path: Path) -> None:
    project = _create_project(tmp_path, "onersiverschool")
    (project / "modules.md").write_text(
        "# New Module\n"
        "To create a new module, copy the module template, register it in the main router, and add its environment variables.\n"
        "Finally, run the project checks before opening the PR.\n",
        encoding="utf-8",
    )

    answer = answer_documentation_question(
        tmp_path,
        "como crear un nuevo modulo en el proyecto de oneriver",
    )

    assert answer["resolved_project"] == "onersiverschool"
    assert "copy the module template" in answer["answer"]
    assert answer["sources"][0]["section_title"] == "New Module"
