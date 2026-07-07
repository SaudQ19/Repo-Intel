"""Pull Request Review Agent — fetches PRs via GitHub MCP and generates AI reviews."""

import json

from langchain_core.messages import SystemMessage, HumanMessage
from mcp.types import TextContent

from app.core.config import settings
from app.core.logging import logger
from app.core.langgraph.tools import github_mcp
from app.services.llm import llm_service
from app.utils.graph import extract_text_content

PR_REVIEW_PROMPT = """You are a Principal Software Engineer reviewing a pull request.
Analyze the PR title, description, and diff. Provide a thorough technical review.

Return ONLY valid JSON with these keys:
{
  "summary": "2-3 sentence summary of the PR",
  "what_changed": "Clear explanation of what was modified",
  "architectural_impact": "How this affects the system architecture",
  "potential_risks": "Any risks or edge cases",
  "possible_bugs": "Potential bugs or issues spotted",
  "testing_recommendations": "What tests should be added or verified",
  "review_verdict": "APPROVE, REQUEST_CHANGES, or COMMENT with brief rationale"
}
"""

PR_LIST_REVIEW_PROMPT = """You are a Principal Software Engineer and PR reviewer.
Review the following Git diff. Identify logic errors, potential bugs, syntax issues, and security vulnerabilities.
Return ONLY valid JSON:
{
  "summary": "High-level summary of changes",
  "issues": [
    {
      "file": "file path",
      "line": 10,
      "severity": "critical | warning | suggestion",
      "description": "Explanation",
      "suggestion": "Fix recommendation"
    }
  ]
}
"""


async def _call_mcp_tool(tool_name: str, **kwargs) -> str:
    """Call a GitHub MCP tool by name."""
    if not github_mcp._mcp_session:
        await github_mcp.get_github_mcp_tools()

    if not github_mcp._mcp_session:
        raise RuntimeError("GitHub MCP session not available.")

    result = await github_mcp._mcp_session.call_tool(tool_name, arguments=kwargs)
    text_contents = [c.text for c in result.content if isinstance(c, TextContent)]
    return "\n".join(text_contents)


class PRReviewerAgent:
    """Agent that fetches PRs via GitHub MCP and generates structured reviews."""

    def __init__(self):
        """Initialize the PR reviewer agent."""
        self.llm = llm_service

    async def list_prs(self, owner: str, repo: str, state: str = "open") -> list[dict]:
        """List pull requests via GitHub MCP.

        Args:
            owner: Repository owner.
            repo: Repository name.
            state: PR state filter.

        Returns:
            List of PR summary dicts.
        """
        try:
            raw = await _call_mcp_tool("list_pull_requests", owner=owner, repo=repo, state=state, per_page=20)
            prs_data = json.loads(raw)

            if not isinstance(prs_data, list):
                logger.warning("prs_data_not_list", data=prs_data)
                return []

            items = []
            for pr in prs_data:
                if not pr or not isinstance(pr, dict):
                    continue

                user_data = pr.get("user")
                user_login = "unknown"
                if isinstance(user_data, dict):
                    user_login = user_data.get("login", "unknown")

                items.append({
                    "number": pr.get("number", 0),
                    "title": pr.get("title", ""),
                    "state": pr.get("state", "open"),
                    "user": user_login,
                    "created_at": pr.get("created_at", ""),
                    "body": (pr.get("body", "") or "")[:500],
                })
            return items
        except json.JSONDecodeError:
            logger.warning("pr_list_response_not_json", owner=owner, repo=repo)
            return []
        except Exception as e:
            logger.exception("list_prs_failed", owner=owner, repo=repo, error=str(e))
            raise

    async def review_pr(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch a PR and generate an AI review.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            Structured review dict.
        """
        try:
            logger.info("pr_review_started", owner=owner, repo=repo, pr_number=pr_number)

            # Fetch PR details
            raw_pr = await _call_mcp_tool("get_pull_request", owner=owner, repo=repo, pull_number=pr_number)
            pr_data = json.loads(raw_pr)

            title = pr_data.get("title", f"PR #{pr_number}")
            body = pr_data.get("body", "") or ""

            # Fetch PR diff
            diff = ""
            try:
                diff = await _call_mcp_tool("get_pull_request_diff", owner=owner, repo=repo, pull_number=pr_number)
            except Exception as e:
                logger.warning("pr_diff_fetch_failed", pr_number=pr_number, error=str(e))
                diff = "Diff not available."

            # Truncate diff for LLM context window
            diff_truncated = diff[:8000] if len(diff) > 8000 else diff

            # Generate AI review
            response = await self.llm.call(
                [
                    SystemMessage(content=PR_REVIEW_PROMPT),
                    HumanMessage(
                        content=(
                            f"PR #{pr_number}: {title}\n\n"
                            f"Description:\n{body[:2000]}\n\n"
                            f"Diff:\n{diff_truncated}"
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
            logger.info("pr_review_completed", pr_number=pr_number)

            return {
                "pr_number": pr_number,
                "title": title,
                **parsed,
            }
        except json.JSONDecodeError:
            logger.warning("pr_review_json_parse_failed", pr_number=pr_number)
            return {
                "pr_number": pr_number,
                "title": f"PR #{pr_number}",
                "summary": "Review generated but could not be parsed as structured JSON.",
                "what_changed": "See raw PR diff for details.",
                "architectural_impact": "Manual review recommended.",
                "potential_risks": "Unable to assess automatically.",
                "possible_bugs": "Unable to assess automatically.",
                "testing_recommendations": "Run existing test suite.",
                "review_verdict": "COMMENT — automated parsing failed, manual review needed.",
            }
        except Exception as e:
            logger.exception("pr_review_agent_failed", pr_number=pr_number, error=str(e))
            raise

    async def review(self, diff: str) -> dict:
        """Legacy method: analyze a raw diff string.

        Args:
            diff: Git diff payload.

        Returns:
            Structured review dict.
        """
        try:
            logger.info("pr_review_started")
            response = await self.llm.call(
                [
                    SystemMessage(content=PR_LIST_REVIEW_PROMPT),
                    HumanMessage(content=f"Review this diff:\n\n{diff[:8000]}"),
                ],
                model_name=settings.DEFAULT_LLM_MODEL,
            )

            content = extract_text_content(response.content).strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            parsed = json.loads(content.strip())
            logger.info("pr_review_completed")
            return parsed

        except Exception as e:
            logger.exception("pr_review_agent_failed", error=str(e))
            return {"summary": f"Failed to perform review: {str(e)}", "issues": []}
