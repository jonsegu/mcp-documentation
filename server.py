from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from config import DOCUMENTATION_ROOT
from filesystem import (
    answer_documentation_question as fs_answer_documentation_question,
    DocumentationError,
    append_to_document as fs_append_to_document,
    create_document as fs_create_document,
    create_project as fs_create_project,
    delete_document as fs_delete_document,
    delete_project as fs_delete_project,
    get_documents,
    get_projects,
    import_document as fs_import_document,
    read_project_document,
    replace_document_content as fs_replace_document_content,
    search_all_documents as fs_search_all_documents,
    search_project_documents,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("documentation-mcp")

mcp = MCPServer("documentation-mcp")

logger.info("Starting documentation-mcp server")
logger.info("Documentation root: %s", DOCUMENTATION_ROOT)


@mcp.tool()
def list_projects() -> list[str]:
    """Return all available project directories inside DOCUMENTATION_ROOT."""
    logger.info("Tool called: list_projects")
    try:
        return get_projects(DOCUMENTATION_ROOT)
    except DocumentationError as exc:
        logger.error("list_projects failed: %s", exc)
        raise ValueError(str(exc)) from None


@mcp.tool()
def list_documents(project: str) -> list[str]:
    """Return all supported documents in a project."""
    logger.info("Tool called: list_documents project=%s", project)
    try:
        return get_documents(DOCUMENTATION_ROOT, project)
    except DocumentationError as exc:
        logger.error("list_documents failed for project=%s: %s", project, exc)
        raise ValueError(str(exc)) from None


@mcp.tool()
def read_document(project: str, document: str) -> str:
    """Read and return full content of a project document."""
    logger.info("Tool called: read_document project=%s document=%s", project, document)
    try:
        return read_project_document(DOCUMENTATION_ROOT, project, document)
    except DocumentationError as exc:
        logger.error(
            "read_document failed for project=%s document=%s: %s",
            project,
            document,
            exc,
        )
        raise ValueError(str(exc)) from None


@mcp.tool()
def search_documentation(project: str, query: str) -> list[dict]:
    """Search one project using literal and natural-language term matching."""
    logger.info("Tool called: search_documentation project=%s", project)
    try:
        return search_project_documents(DOCUMENTATION_ROOT, project, query)
    except DocumentationError as exc:
        logger.error("search_documentation failed for project=%s: %s", project, exc)
        raise ValueError(str(exc)) from None


@mcp.tool()
def search_all_documentation(query: str) -> list[dict]:
    """Search all projects for a question or query and return ranked relevant excerpts."""
    logger.info("Tool called: search_all_documentation query=%s", query)
    try:
        return fs_search_all_documents(DOCUMENTATION_ROOT, query)
    except DocumentationError as exc:
        logger.error("search_all_documentation failed: %s", exc)
        raise ValueError(str(exc)) from None


@mcp.tool()
def ask_documentation(question: str, project: str | None = None) -> dict:
    """Use this for natural-language questions; it resolves the project, reads the best section, and returns a final answer."""
    logger.info("Tool called: ask_documentation project=%s question=%s", project, question)
    try:
        return fs_answer_documentation_question(DOCUMENTATION_ROOT, question, project=project)
    except DocumentationError as exc:
        logger.error("ask_documentation failed for project=%s: %s", project, exc)
        raise ValueError(str(exc)) from None


@mcp.tool()
def create_project(project: str, initial_document: str | None = None, content: str = "", overwrite_document: bool = False) -> str:
    """Create a project and optionally seed it with an initial document."""
    logger.info(
        "Tool called: create_project project=%s initial_document=%s overwrite_document=%s",
        project,
        initial_document,
        overwrite_document,
    )
    try:
        return fs_create_project(
            DOCUMENTATION_ROOT,
            project,
            initial_document=initial_document,
            content=content,
            overwrite_document=overwrite_document,
        )
    except DocumentationError as exc:
        logger.error("create_project_tool failed for project=%s: %s", project, exc)
        raise ValueError(str(exc)) from None


@mcp.tool()
def create_document(project: str, document: str, content: str = "", overwrite: bool = False) -> str:
    """Create a new document inside an existing project."""
    logger.info(
        "Tool called: create_document project=%s document=%s overwrite=%s",
        project,
        document,
        overwrite,
    )
    try:
        return fs_create_document(DOCUMENTATION_ROOT, project, document, content=content, overwrite=overwrite)
    except DocumentationError as exc:
        logger.error(
            "create_document_tool failed for project=%s document=%s: %s",
            project,
            document,
            exc,
        )
        raise ValueError(str(exc)) from None


@mcp.tool()
def import_document(project: str, source_path: str, document: str | None = None, overwrite: bool = False) -> str:
    """Import an attached local .md or .txt file into an existing project."""
    logger.info(
        "Tool called: import_document project=%s source_path=%s document=%s overwrite=%s",
        project,
        source_path,
        document,
        overwrite,
    )
    try:
        return fs_import_document(
            DOCUMENTATION_ROOT,
            project,
            source_path,
            document=document,
            overwrite=overwrite,
        )
    except DocumentationError as exc:
        logger.error(
            "import_document failed for project=%s source_path=%s document=%s: %s",
            project,
            source_path,
            document,
            exc,
        )
        raise ValueError(str(exc)) from None


@mcp.tool()
def edit_document(project: str, document: str, content: str, mode: str = "append") -> str:
    """Edit a document by appending to it or replacing its full content."""
    logger.info(
        "Tool called: edit_document project=%s document=%s mode=%s",
        project,
        document,
        mode,
    )
    try:
        if mode == "replace":
            return fs_replace_document_content(DOCUMENTATION_ROOT, project, document, content)
        if mode == "append":
            return fs_append_to_document(DOCUMENTATION_ROOT, project, document, content)
        raise ValueError("Unsupported mode. Use 'append' or 'replace'.")
    except (DocumentationError, ValueError) as exc:
        logger.error(
            "edit_document_tool failed for project=%s document=%s: %s",
            project,
            document,
            exc,
        )
        raise ValueError(str(exc)) from None


@mcp.tool()
def delete_document(project: str, document: str) -> str:
    """Delete a document from a project."""
    logger.info("Tool called: delete_document project=%s document=%s", project, document)
    try:
        return fs_delete_document(DOCUMENTATION_ROOT, project, document)
    except DocumentationError as exc:
        logger.error(
            "delete_document_tool failed for project=%s document=%s: %s",
            project,
            document,
            exc,
        )
        raise ValueError(str(exc)) from None


@mcp.tool()
def delete_project(project: str) -> str:
    """Delete a project and all of its documents."""
    logger.info("Tool called: delete_project project=%s", project)
    try:
        return fs_delete_project(DOCUMENTATION_ROOT, project)
    except DocumentationError as exc:
        logger.error("delete_project_tool failed for project=%s: %s", project, exc)
        raise ValueError(str(exc)) from None


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000,
        stateless_http=True,
        json_response=True,
    )
