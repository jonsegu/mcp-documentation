from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from config import DOCUMENTATION_ROOT
from filesystem import (
    DocumentationError,
    get_documents,
    get_projects,
    read_project_document,
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
    """Search for text in file names and content within a project."""
    logger.info("Tool called: search_documentation project=%s", project)
    try:
        return search_project_documents(DOCUMENTATION_ROOT, project, query)
    except DocumentationError as exc:
        logger.error("search_documentation failed for project=%s: %s", project, exc)
        raise ValueError(str(exc)) from None


if __name__ == "__main__":
    mcp.run()
