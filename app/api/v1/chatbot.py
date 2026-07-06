"""Chatbot API endpoints for handling chat interactions.

This module provides endpoints for chat interactions, including regular chat,
streaming chat, message history management, and chat history clearing.
"""

import json

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.langgraph.graph import LangGraphAgent
from app.core.logging import logger
from app.core.metrics import llm_stream_duration_seconds
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    StreamResponse,
)
from app.services.database import database_service
from app.services.session_naming import maybe_name_session

router = APIRouter()
agent = LangGraphAgent()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    chat_request: ChatRequest,
):
    """Process a chat request using LangGraph.

    Args:
        request: The FastAPI request object.
        chat_request: The chat request containing messages and session_id.

    Returns:
        ChatResponse: The processed chat response.

    Raises:
        HTTPException: If there's an error processing the request.
    """
    session_id = chat_request.session_id
    try:
        logger.info(
            "chat_request_received",
            session_id=session_id,
            message_count=len(chat_request.messages),
        )

        db_session = await database_service.get_session(session_id)
        if not db_session:
            db_session = await database_service.create_session(session_id, name="New Chat")

        if settings.SESSION_NAMING_ENABLED:
            maybe_name_session(session_id, db_session.name, chat_request.messages)

        result = await agent.get_response(
            chat_request.messages,
            session_id,
            repository_id=chat_request.repository_id,
            user_id="default_user",
            username=db_session.username,
        )

        logger.info("chat_request_processed", session_id=session_id)

        return ChatResponse(messages=result)
    except Exception as e:
        logger.exception("chat_request_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
):
    """Process a chat request using LangGraph with streaming response.

    Args:
        request: The FastAPI request object.
        chat_request: The chat request containing messages and session_id.

    Returns:
        StreamingResponse: A streaming response of the chat completion.

    Raises:
        HTTPException: If there's an error processing the request.
    """
    session_id = chat_request.session_id
    try:
        logger.info(
            "stream_chat_request_received",
            session_id=session_id,
            message_count=len(chat_request.messages),
        )

        db_session = await database_service.get_session(session_id)
        if not db_session:
            db_session = await database_service.create_session(session_id, name="New Chat")

        if settings.SESSION_NAMING_ENABLED:
            maybe_name_session(session_id, db_session.name, chat_request.messages)

        async def event_generator():
            """Generate streaming events.

            Yields:
                str: Server-sent events in JSON format.

            Raises:
                Exception: If there's an error during streaming.
            """
            try:
                with llm_stream_duration_seconds.labels(model=agent.llm_service.get_llm().get_name()).time():
                    async for chunk in agent.get_stream_response(
                        chat_request.messages,
                        session_id,
                        repository_id=chat_request.repository_id,
                        user_id="default_user",
                        username=db_session.username,
                    ):
                        response = StreamResponse(content=chunk, done=False)
                        yield f"data: {json.dumps(response.model_dump(mode='json'))}\n\n"

                # Send final message indicating completion
                final_response = StreamResponse(content="", done=True)
                yield f"data: {json.dumps(final_response.model_dump(mode='json'))}\n\n"

            except Exception as e:
                logger.exception(
                    "stream_chat_request_failed",
                    session_id=session_id,
                    error=str(e),
                )
                error_response = StreamResponse(content=str(e), done=True)
                yield f"data: {json.dumps(error_response.model_dump(mode='json'))}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.exception(
            "stream_chat_request_failed",
            session_id=session_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages", response_model=ChatResponse)
async def get_session_messages(
    request: Request,
    session_id: str = "default_session",
):
    """Get all messages for a session.

    Args:
        request: The FastAPI request object.
        session_id: The ID of the session.

    Returns:
        ChatResponse: All messages in the session.

    Raises:
        HTTPException: If there's an error retrieving the messages.
    """
    try:
        messages = await agent.get_chat_history(session_id)
        return ChatResponse(messages=messages)
    except Exception as e:
        logger.exception("get_messages_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages")
async def clear_chat_history(
    request: Request,
    session_id: str = "default_session",
):
    """Clear all messages for a session.

    Args:
        request: The FastAPI request object.
        session_id: The ID of the session.

    Returns:
        dict: A message indicating the chat history was cleared.
    """
    try:
        await agent.clear_chat_history(session_id)
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        logger.exception("clear_chat_history_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
