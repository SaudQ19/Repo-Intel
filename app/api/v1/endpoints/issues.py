"""Issue tracking endpoints powered by GitHub MCP + LLM analysis."""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger
from app.core.langgraph.tools import github_mcp
from app.services.llm import llm_service
from app.utils.graph import extract_text_content
from langchain_core.messages import SystemMessage, HumanMessage


router = APIRouter()


class IssueItem(BaseModel):
    """Summary of a GitHub issue."""

    number: int
    title: str
    state: str
    user: str
    created_at: str
    labels: list[str] = []
    body: str = ""


class IssueAnalysis(BaseModel):
    """AI-generated issue analysis."""

    number: int
    title: str
    root_cause: str
    affected_components: list[str]
    severity: str
    suggested_fix: str
    related_files: list[str]


ISSUE_ANALYSIS_PROMPT = """You are a Senior Debugging Specialist analyzing a GitHub issue.
Given the issue title, body, and labels, provide:
1. Root cause analysis
2. Affected components/modules
3. Severity assessment (critical, high, medium, low)
4. Suggested fix approach
5. Related files that likely need changes

Return ONLY valid JSON with keys: root_cause, affected_components (list), severity, suggested_fix, related_files (list).
"""


async def _call_mcp_tool(tool_name: str, **kwargs) -> str:
    """Call a GitHub MCP tool by name."""
    from mcp.types import TextContent

    if not github_mcp._mcp_session:
        await github_mcp.get_github_mcp_tools()

    if not github_mcp._mcp_session:
        raise RuntimeError("GitHub MCP session not available. Check GITHUB_PERSONAL_ACCESS_TOKEN.")

    result = await github_mcp._mcp_session.call_tool(tool_name, arguments=kwargs)
    text_contents = [c.text for c in result.content if isinstance(c, TextContent)]
    return "\n".join(text_contents)


@router.get("/{owner}/{repo}", response_model=list[IssueItem])
async def list_issues(owner: str, repo: str, state: str = "open"):
    """List issues for a repository via GitHub MCP.

    Args:
        owner: Repository owner.
        repo: Repository name.
        state: Issue state filter (open, closed, all).

    Returns:
        List of issue summaries.
    """
    try:
        raw = await _call_mcp_tool("list_issues", owner=owner, repo=repo, state=state, per_page=30)
        issues_data = json.loads(raw)

        if not isinstance(issues_data, list):
            logger.warning("issues_data_not_list", data=issues_data)
            return []

        items = []
        for issue in issues_data:
            if not issue or not isinstance(issue, dict):
                continue
            # Skip pull requests (GitHub API returns them as issues too)
            if "pull_request" in issue:
                continue

            user_data = issue.get("user")
            user_login = "unknown"
            if isinstance(user_data, dict):
                user_login = user_data.get("login", "unknown")

            labels_list = issue.get("labels") or []
            labels = []
            if isinstance(labels_list, list):
                for label in labels_list:
                    if isinstance(label, dict):
                        labels.append(label.get("name", ""))
                    elif isinstance(label, str):
                        labels.append(label)

            items.append(
                IssueItem(
                    number=issue.get("number", 0),
                    title=issue.get("title", ""),
                    state=issue.get("state", "open"),
                    user=user_login,
                    created_at=issue.get("created_at", ""),
                    labels=labels,
                    body=(issue.get("body", "") or "")[:500],
                )
            )
        return items
    except json.JSONDecodeError:
        # MCP may return formatted text instead of JSON
        logger.warning("issues_response_not_json", owner=owner, repo=repo)
        return []
    except Exception as e:
        logger.exception("list_issues_failed", owner=owner, repo=repo, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch issues: {str(e)}")


@router.get("/{owner}/{repo}/{issue_number}/analyze", response_model=IssueAnalysis)
async def analyze_issue(owner: str, repo: str, issue_number: int):
    """Fetch an issue via GitHub MCP and generate AI analysis.

    Args:
        owner: Repository owner.
        repo: Repository name.
        issue_number: Issue number.

    Returns:
        AI-generated issue analysis with root cause and fix suggestions.
    """
    try:
        raw = await _call_mcp_tool("get_issue", owner=owner, repo=repo, issue_number=issue_number)
        issue_data = json.loads(raw)

        title = issue_data.get("title", "")
        body = issue_data.get("body", "") or ""
        labels = [label.get("name", "") for label in issue_data.get("labels", [])]

        # LLM analysis
        response = await llm_service.call(
            [
                SystemMessage(content=ISSUE_ANALYSIS_PROMPT),
                HumanMessage(
                    content=(
                        f"Issue #{issue_number}: {title}\n"
                        f"Labels: {', '.join(labels)}\n"
                        f"Body:\n{body[:2000]}"
                    )
                ),
            ],
            model_name=settings.DEFAULT_LLM_MODEL,
        )

        content = extract_text_content(response.content).strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        parsed = json.loads(content.strip())

        return IssueAnalysis(
            number=issue_number,
            title=title,
            root_cause=parsed.get("root_cause", "Unable to determine"),
            affected_components=parsed.get("affected_components", []),
            severity=parsed.get("severity", "medium"),
            suggested_fix=parsed.get("suggested_fix", "No suggestion"),
            related_files=parsed.get("related_files", []),
        )
    except json.JSONDecodeError:
        logger.warning("issue_analysis_json_parse_failed", issue_number=issue_number)
        return IssueAnalysis(
            number=issue_number,
            title=f"Issue #{issue_number}",
            root_cause="Analysis unavailable — could not parse response",
            affected_components=[],
            severity="unknown",
            suggested_fix="Manual review recommended",
            related_files=[],
        )
    except Exception as e:
        logger.exception("analyze_issue_failed", owner=owner, repo=repo, issue_number=issue_number, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to analyze issue #{issue_number}: {str(e)}")
