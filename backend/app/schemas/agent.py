from pydantic import BaseModel
from datetime import datetime


class AgentTriggerRequest(BaseModel):
    trigger: str = "manual"


class AgentRunOut(BaseModel):
    id: int
    agent_name: str
    trigger: str
    status: str
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class AgentStatusResponse(BaseModel):
    last_run_at: datetime | None
    completed_agents: list[str]
    current_state_keys: list[str]
    recent_runs: list[AgentRunOut]


class AgentTriggerResponse(BaseModel):
    message: str
    trigger: str
    completed_agents: list[str]
