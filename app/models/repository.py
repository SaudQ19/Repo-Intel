"""Repository model definition."""

from typing import Optional
from sqlmodel import Field
from app.models.base import BaseModel


class Repository(BaseModel, table=True):
    """Repository model representing indexed codebases.

    Attributes:
        id: Unique identifier for the repository (UUID string).
        name: Naming identifier for display.
        clone_url: Git clone URL or local directory path.
        branch: Target Git branch (defaults to 'main').
        status: Progress state (pending, indexing, active, failed).
        last_indexed_at: Timestamp of the most recent indexing completion.
    """

    id: str = Field(primary_key=True)
    name: str = Field(nullable=False)
    clone_url: str = Field(nullable=False)
    branch: str = Field(default="main")
    status: str = Field(default="pending")
    last_indexed_at: Optional[str] = Field(default=None)
