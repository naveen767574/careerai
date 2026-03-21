from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_state import AgentState


class StateManager:
    def __init__(self, db: Session):
        self.db = db

    def load(self, user_id: int) -> dict:
        state = self.db.execute(select(AgentState).where(AgentState.user_id == user_id)).scalar_one_or_none()
        if not state:
            state = AgentState(user_id=user_id, state_json={})
            self.db.add(state)
            self.db.commit()
            return {}
        return state.state_json or {}

    def save(self, user_id: int, state: dict) -> None:
        record = self.db.execute(select(AgentState).where(AgentState.user_id == user_id)).scalar_one_or_none()
        now = datetime.utcnow()
        if record:
            record.state_json = state
            record.last_run_at = now
            record.updated_at = now
            self.db.add(record)
        else:
            self.db.add(AgentState(user_id=user_id, state_json=state, last_run_at=now, updated_at=now))
        self.db.commit()

    def update(self, state: dict, action: str, result: dict) -> dict:
        state[f"{action}_output"] = result
        state["last_action"] = action
        return state
