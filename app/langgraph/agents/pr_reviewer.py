"""Pull Request Review Agent implementation."""

from langchain_core.messages import SystemMessage, HumanMessage
from app.core.logging import logger
from app.services.llm import llm_service

PR_REVIEW_PROMPT = """You are a Principal Software Engineer and PR reviewer.
Review the following Git diff. Identify logic errors, potential bugs, syntax issues, styling deviations, and security vulnerabilities.
Format your response as a JSON structure:
{
  "summary": "High-level summary of changes and overall code quality",
  "issues": [
    {
      "file": "file path",
      "line": 10,
      "severity": "critical | warning | suggestion",
      "description": "Explanation of the issue",
      "suggestion": "How to fix it"
    }
  ]
}
Return ONLY valid JSON.
"""


class PRReviewerAgent:
    """Agent that analyzes Git diffs and generates structured pull request reviews."""

    def __init__(self):
        self.llm = llm_service

    async def review(self, diff: str) -> dict:
        """Analyze a diff and return structural comments."""
        try:
            logger.info("pr_review_started")
            from app.core.config import settings
            response = await self.llm.call(
                [
                    SystemMessage(content=PR_REVIEW_PROMPT),
                    HumanMessage(content=f"Review this diff:\n\n{diff}")
                ],
                model_name=settings.DEFAULT_LLM_MODEL
            )
            
            # Simple fallback parser for JSON responses
            content = response.content.strip()
            # Strip markdown fences if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            import json
            parsed = json.loads(content.strip())
            logger.info("pr_review_completed")
            return parsed
            
        except Exception as e:
            logger.exception("pr_review_agent_failed", error=str(e))
            return {
                "summary": f"Failed to perform review: {str(e)}",
                "issues": []
            }
