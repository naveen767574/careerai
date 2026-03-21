from dataclasses import asdict

from sqlalchemy.orm import Session

from app.agents.analyst_agent import AnalystAgent
from app.agents.coach_agent import CoachAgent
from app.agents.scout_agent import ScoutAgent


class Dispatcher:
    def __init__(self, db: Session):
        self.db = db

    def dispatch(self, action: str, state: dict, user_id: int) -> dict:
        if action == "scout":
            return asdict(ScoutAgent(self.db).run(user_id, state))
        if action == "analyst":
            return asdict(AnalystAgent(self.db).run(user_id, state))
        if action == "coach":
            return asdict(CoachAgent(self.db).run(user_id, state))
        if action == "writer":
            raise ValueError("Writer is triggered per listing, not by orchestrator loop")
        raise ValueError(f"Unknown action: {action}")
