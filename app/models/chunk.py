"""Code chunk model definition."""

from typing import Optional
from sqlmodel import Field, Column, JSON
from app.models.base import BaseModel
from pgvector.sqlalchemy import Vector


class CodeChunk(BaseModel, table=True):
    """CodeChunk model representing parsed code blocks and symbols.

    Attributes:
        id: Unique identifier for the chunk.
        repository_id: Associated Repository ID.
        file_path: Absolute or relative file path in the workspace.
        symbol_name: Name of the function, class, or method (if any).
        symbol_type: Type of the symbol (function, class, method, route, config, doc).
        start_line: Start line of the snippet (1-indexed).
        end_line: End line of the snippet (1-indexed).
        content: The raw text/code of the chunk.
        embedding: Dense vector representation (1536 float list).
        metadata: JSON dictionary of parsed data (imports, parameters, etc.).
    """

    id: str = Field(primary_key=True)
    repository_id: str = Field(foreign_key="repository.id", index=True)
    file_path: str = Field(nullable=False)
    symbol_name: Optional[str] = Field(default=None)
    symbol_type: Optional[str] = Field(default=None, index=True)
    start_line: int = Field(nullable=False)
    end_line: int = Field(nullable=False)
    content: str = Field(nullable=False)
    embedding: list[float] = Field(sa_column=Column(Vector(384)))
    chunk_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))
