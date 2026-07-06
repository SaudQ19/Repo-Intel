"""Agent run model definition."""

from typing import Optional
from sqlmodel import Field, Column, JSON
from app.models.base import BaseModel


class AgentRun(BaseModel, table=True):
    """AgentRun model representing executed background agent jobs.

    Attributes:
        id: Unique identifier for the agent run job.
        agent_type: The type of agent (pr_review, documentation, issue_resolver).
        status: Progress state (pending, running, completed, failed).
        payload: Inputs for the execution (e.g., repository_id, diffs, issue details).
        result: Outputs from the agent run (JSON format).
        error: Traceback or error details if execution failed.
    """

    id: str = Field(primary_key=True)
    agent_type: str = Field(nullable=False, index=True)
    status: str = Field(default="pending", index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    error: Optional[str] = Field(default=None)
