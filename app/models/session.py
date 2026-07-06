"""This file contains the session model for the application."""

from typing import Optional
from sqlmodel import Field
from app.models.base import BaseModel


class Session(BaseModel, table=True):
    """Session model for storing chat sessions.

    Attributes:
        id: The primary key
        name: Name of the session (defaults to empty string)
        username: Display name for the session creator
        created_at: When the session was created
    """

    id: str = Field(primary_key=True)
    name: str = Field(default="")
    username: Optional[str] = Field(default="default_user")
