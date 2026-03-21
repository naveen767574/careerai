import json
from dataclasses import asdict
from datetime import datetime

from groq import Groq
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.agent_run import AgentRun
from app.orchestrator.dispatcher import Dispatcher
from app.orchestrator.state_manager import StateManager

ORCHESTRATOR_SYSTEM_PROMPT = """
You are an orchestration agent managing a career assistance system.
Given the current state and trigger, decide which sub-agent to invoke next.

Available agents: scout | analyst | coach | done

Rules:
- Trigger 'cron_6h' or 'manual': run scout ? analyst ? coach in sequence
- Trigger 'resume_upload' or 'resume_builder_complete': run analyst ? coach
- Trigger 'user_refresh': run scout ? analyst
- If the required agents have already run in this session: action = "done"
- Check state["completed_agents"] list to know what already ran

Respond ONLY with valid JSON: {"thought": "one sentence reasoning", "action": "agent_name_or_done"}
"""


class OrchestratorRunner:
    def __init__(self, db: Session):
        self.db = db
        self.state_manager = StateManager(db)
        self.dispatcher = Dispatcher(db)
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def run(self, user_id: int, trigger: str) -> dict:
        state = self.state_manager.load(user_id)
        state["trigger"] = trigger
        state["done"] = False
        if "completed_agents" not in state:
            state["completed_agents"] = []

        last_run_id = None
        for _ in range(10):
            decision = self._call_llm(state, trigger)
            action = decision.get("action", "done")
            if action == "done":
                break
            if action in state["completed_agents"]:
                break

            run = self._log_run(user_id, action, trigger, status="running", input_json={"state": state})
            last_run_id = run.id
            try:
                result = self.dispatcher.dispatch(action, state, user_id)
                self._log_run(
                    user_id,
                    action,
                    trigger,
                    status="success",
                    output_json=result,
                    run_id=run.id,
                )
                state = self.state_manager.update(state, action, result)
                state["completed_agents"].append(action)
                self.state_manager.save(user_id, state)
            except Exception as exc:
                self._log_run(
                    user_id,
                    action,
                    trigger,
                    status="failed",
                    error_message=str(exc),
                    run_id=run.id,
                )
                break

        return state

    def _log_run(
        self,
        user_id: int,
        agent_name: str,
        trigger: str,
        status: str,
        input_json: dict | None = None,
        output_json: dict | None = None,
        error_message: str | None = None,
        run_id: int | None = None,
    ) -> AgentRun:
        now = datetime.utcnow()
        if run_id is None:
            run = AgentRun(
                user_id=user_id,
                agent_name=agent_name,
                trigger=trigger,
                status=status,
                input_json=input_json,
                output_json=output_json,
                error_message=error_message,
            )
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            return run

        run = self.db.execute(select(AgentRun).where(AgentRun.id == run_id)).scalar_one()
        run.status = status
        run.output_json = output_json
        run.error_message = error_message
        run.completed_at = now
        self.db.add(run)
        self.db.commit()
        return run

    def _call_llm(self, state: dict, trigger: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Trigger: {trigger}\nCurrent state: {json.dumps(state, default=str)}"},
                ],
                max_tokens=200,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return {"thought": data.get("thought", ""), "action": data.get("action", "done")}
        except Exception:
            return {"thought": "parse error", "action": "done"}

