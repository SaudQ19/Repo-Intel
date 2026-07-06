"""Filesystem exploration tools for LangGraph."""

import os
from typing import Optional
from langchain_core.tools import tool
from langchain_core.runnables.config import RunnableConfig
from sqlmodel import Session

from app.core.logging import logger
from app.models.repository import Repository
from app.services.database import database_service


def _get_workspace_path(config: RunnableConfig) -> Optional[str]:
    """Helper to resolve local directory path from active repository_id in context."""
    repository_id = config.get("metadata", {}).get("repository_id")
    if not repository_id:
        return None
    with Session(database_service.engine) as session:
        repo = session.get(Repository, repository_id)
        if repo:
            url = repo.clone_url.strip()
            is_git = (
                url.startswith("http://")
                or url.startswith("https://")
                or url.startswith("git@")
                or url.startswith("git://")
                or (url.endswith(".git") and ":" in url)
            )
            if is_git:
                local_path = os.path.join(os.getcwd(), "data", "cloned_repos", repo.id)
                if os.path.exists(local_path):
                    return local_path
            elif os.path.exists(repo.clone_url):
                return repo.clone_url
    return None


@tool
def list_directory_tool(config: RunnableConfig) -> str:
    """List the tree of contents in the active repository workspace.

    Args:
        config: RunnableConfig parameter passed implicitly.

    Returns:
        str: A tree of files and folders.
    """
    workspace_path = _get_workspace_path(config)
    if not workspace_path:
        return "Error: No active workspace found. Verify that the repository is registered and indexed."

    repository_id = config.get("metadata", {}).get("repository_id")
    repo_name = "workspace"
    if repository_id:
        with Session(database_service.engine) as session:
            repo = session.get(Repository, repository_id)
            if repo:
                repo_name = repo.name

    try:
        output = [f"{repo_name}/"]
        max_depth = 4

        # Directories to ignore
        ignore_dirs = {
            "__pycache__", "node_modules", ".git", ".venv", "venv",
            ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode"
        }

        def walk(path: str, prefix: str = "", depth: int = 1):
            if depth > max_depth:
                return
            try:
                items = sorted(os.listdir(path))
            except Exception:
                return

            items = [i for i in items if not i.startswith(".") and i not in ignore_dirs]

            # separate directories and files
            dirs = [i for i in items if os.path.isdir(os.path.join(path, i))]
            files = [i for i in items if os.path.isfile(os.path.join(path, i))]

            sorted_items = dirs + files

            for idx, item in enumerate(sorted_items):
                is_last = (idx == len(sorted_items) - 1)
                connector = "└── " if is_last else "├── "
                item_path = os.path.join(path, item)

                if os.path.isdir(item_path):
                    output.append(f"{prefix}{connector}{item}/")
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    walk(item_path, new_prefix, depth + 1)
                else:
                    output.append(f"{prefix}{connector}{item}")

        walk(workspace_path)
        return "\n".join(output)
    except Exception as e:
        logger.exception("list_directory_tool_failed", path=workspace_path, error=str(e))
        return f"Error listing directory: {str(e)}"


@tool
def view_file_content_tool(relative_file_path: str, config: RunnableConfig, start_line: int = 1, end_line: int = 200) -> str:
    """Read the content of a specific file in the active repository workspace.

    Args:
        relative_file_path: Relative path to the file from the workspace root.
        config: RunnableConfig parameter passed implicitly.
        start_line: 1-indexed start line to read (inclusive).
        end_line: 1-indexed end line to read (inclusive).

    Returns:
        str: The raw content of the file segment.
    """
    workspace_path = _get_workspace_path(config)
    if not workspace_path:
        return "Error: No active workspace context."

    try:
        full_path = os.path.join(workspace_path, relative_file_path)
        if not os.path.exists(full_path):
            return f"Error: File '{relative_file_path}' does not exist in workspace."

        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        total_lines = len(lines)
        start_idx = max(0, start_line - 1)
        end_idx = min(total_lines, end_line)

        segment = lines[start_idx:end_idx]
        formatted_segment = "".join(segment)

        return (
            f"### File: {relative_file_path} (Lines {start_line}-{end_line} of {total_lines})\n"
            f"```\n{formatted_segment}\n```"
        )
    except Exception as e:
        logger.exception("view_file_content_tool_failed", file=relative_file_path, error=str(e))
        return f"Error viewing file: {str(e)}"
