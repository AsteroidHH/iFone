import threading
import time
from typing import Dict, Any


class MockHelpdeskService:
    """
    Mock external Helpdesk API (refund, email, ticket actions).
    Thread-safe and enforces the Tombstone rule:
    - If compensation is requested for an unknown/unseen idempotency key, record a TOMBSTONE and return 200.
    - If an execute request arrives with a tombstoned key, REJECT it with 409 Conflict.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.executed_actions: Dict[str, Dict[str, Any]] = {}
        self.tombstones: set[str] = set()

    def execute_action(self, idempotency_key: str, action_type: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        with self._lock:
            if idempotency_key in self.tombstones:
                return {
                    "status": 409,
                    "error": "CONFLICT",
                    "message": f"Action with idempotency key '{idempotency_key}' was tombstoned by a prior compensation request.",
                }

            # Idempotent replay of previously executed action
            if idempotency_key in self.executed_actions:
                return {
                    "status": 200,
                    "result": "success",
                    "replayed": True,
                    "data": self.executed_actions[idempotency_key],
                }

            data = {
                "idempotency_key": idempotency_key,
                "action_type": action_type,
                "payload": payload or {},
                "executed_at": int(time.time() * 1000),
            }
            self.executed_actions[idempotency_key] = data
            return {"status": 200, "result": "success", "replayed": False, "data": data}

    def compensate_action(self, idempotency_key: str, action_id: str, action_type: str) -> Dict[str, Any]:
        with self._lock:
            # If the original execution has not landed yet, lay down a TOMBSTONE!
            if idempotency_key not in self.executed_actions:
                self.tombstones.add(idempotency_key)
                return {
                    "status": 200,
                    "result": "tombstoned",
                    "message": f"Action '{action_id}' not yet seen; recorded tombstone for idempotency key '{idempotency_key}'.",
                }

            # Original action was executed, perform compensation
            return {
                "status": 200,
                "result": "compensated",
                "message": f"Action '{action_id}' ({action_type}) successfully reversed/reverted.",
            }

    def reset(self):
        with self._lock:
            self.executed_actions.clear()
            self.tombstones.clear()


helpdesk_service = MockHelpdeskService()
