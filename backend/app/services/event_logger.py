"""
app/services/event_logger.py

Best-effort event logging (Phase 0 — Instrumentation).

`log_event()` writes one row to `interaction_events`. It is deliberately
FIRE-AND-FORGET from the caller's perspective:

  • It MUST NEVER raise into the request path. Any failure (DB down, bad payload,
    session in a weird state) is caught, logged as a warning, and swallowed. A
    broken logger must not break a user's recommendations or application update.

  • It uses its OWN short-lived session (SessionLocal), independent of the
    request's `db`. This guarantees a logging failure can't poison the caller's
    transaction, and a caller rollback can't lose an already-recorded event.
    Because the table is append-only and each event stands alone, an independent
    commit is exactly the semantics we want.

Emit events AFTER the response payload is built, so instrumentation is never on
the critical path of producing the user's result.
"""
import logging
from typing import Any, Optional

from app.database import SessionLocal
from app.models.interaction_event import InteractionEvent

logger = logging.getLogger(__name__)

# Canonical event type names — import these instead of typing string literals so
# emit sites and the offline analytics agree on spelling.
EVENT_RECOMMENDATIONS_SERVED = "recommendations_served"
EVENT_MATCH_VIEWED = "match_viewed"
EVENT_WHATIF_SIMULATED = "whatif_simulated"
EVENT_APPLICATION_STATUS_CHANGED = "application_status_changed"


def log_event(
    event_type: str,
    *,
    user_id: Optional[int] = None,
    internship_id: Optional[int] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """
    Record a single interaction event. Never raises.

    Uses an independent session so it neither depends on nor disturbs the
    request's transaction. On any error it logs a warning and returns.
    """
    session = None
    try:
        session = SessionLocal()
        session.add(
            InteractionEvent(
                event_type=event_type,
                user_id=user_id,
                internship_id=internship_id,
                payload=payload,
            )
        )
        session.commit()
    except Exception:  # noqa: BLE001 — instrumentation must never break callers
        logger.warning("event_logger: failed to record %s", event_type, exc_info=True)
        if session is not None:
            try:
                session.rollback()
            except Exception:  # noqa: BLE001
                pass
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:  # noqa: BLE001
                pass
