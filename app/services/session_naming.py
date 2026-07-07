"""Session auto-naming using a fast Groq model.

On the first message of a new session this module:
  1. Atomically claims the session in Postgres (prevents duplicate LLM calls).
  2. Writes a placeholder name from the user's message.
  3. Fires a background task to generate a proper title via LLM.
"""

import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage
from sqlmodel import (
    Session as DBSession,
    col,
    update,
)

from app.core.logging import logger
from app.core.metrics import session_names_generated_total
from app.core.prompts import SESSION_TITLE_PROMPT
from app.models.session import Session as ChatSession
from app.services.database import database_service
from app.services.llm import llm_service
from app.utils.graph import extract_text_content

_PLACEHOLDER_MAX = 40

_background_tasks: set[asyncio.Task] = set()


def _build_placeholder(user_message: str) -> str:
    cleaned = " ".join(user_message.split())
    return cleaned[:_PLACEHOLDER_MAX].rstrip() or "New chat"


def _claim_session(session_id: str, placeholder: str) -> bool:
    """Return True iff this caller wins the atomic Postgres claim."""
    with DBSession(database_service.engine) as db:
        stmt = (
            update(ChatSession)
            .where(col(ChatSession.id) == session_id, col(ChatSession.name) == "")
            .values(name=placeholder)
        )
        result = db.exec(stmt)
        db.commit()
        return (result.rowcount or 0) == 1


def _parse_title_from_response(content: str) -> str:
    """Extract a clean title string from LLM response, handling JSON or plain text."""
    content = content.strip().strip("\"'`")

    # Try JSON parsing first (structured output)
    if content.startswith("{"):
        try:
            parsed = json.loads(content)
            if "title" in parsed:
                return parsed["title"]
        except json.JSONDecodeError:
            pass

    # Clean up common formatting artifacts
    title = " ".join(content.split()).strip(" \"'`.,:;!?-")
    return title[:60] if title else "New chat"


async def _persist_session_name(session_id: str, user_message: str) -> None:
    try:
        response = await llm_service.call(
            [
                SystemMessage(content=SESSION_TITLE_PROMPT),
                HumanMessage(content=user_message[:500]),
            ],
            model_name="llama-3.1-8b-instant",
            max_tokens=32,
            temperature=0.3,
        )
        title = _parse_title_from_response(extract_text_content(response.content))
        await database_service.update_session_name(session_id, title)
        session_names_generated_total.labels(status="success").inc()
        logger.info("session_name_generated", session_id=session_id, name=title)
    except Exception:
        session_names_generated_total.labels(status="error").inc()
        logger.exception("session_name_generation_failed", session_id=session_id)


def maybe_name_session(session_id: str, session_name: str, messages: list) -> None:
    """Trigger session auto-naming if the session is still unnamed.

    Safe to call from any chat endpoint — concurrent callers for the same
    session are deduplicated by the Postgres claim.
    """
    if session_name:
        return
    first_user_msg = next((m.content for m in messages if m.role == "user"), None)
    if not first_user_msg:
        return
    if _claim_session(session_id, _build_placeholder(first_user_msg)):
        task = asyncio.create_task(_persist_session_name(session_id, first_user_msg))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
