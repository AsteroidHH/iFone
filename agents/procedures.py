from typing import Dict, List, Optional
from pydantic import BaseModel


class Procedure(BaseModel):
    id: str
    task_type: str
    steps: List[str]
    uses: int = 0
    successes: int = 0
    failures: int = 0
    seeded: bool = False

    @property
    def rank_score(self) -> float:
        """Laplace-smoothed rank: (successes + 1) / (uses + 2)"""
        return round((self.successes + 1.0) / (self.uses + 2.0), 3)


class ProcedureRegistry:
    """
    Manages procedural memory with Laplace-smoothed ranking and adaptive selection.
    """
    def __init__(self):
        self._procedures: Dict[str, Procedure] = {
            "proc_refund_standard": Procedure(
                id="proc_refund_standard",
                task_type="refund",
                steps=["verify_policy", "check_order_receipt", "stage_refund", "execute_refund"],
                uses=42,
                successes=39,
                failures=3,
                seeded=True,
            ),
            "proc_refund_strict": Procedure(
                id="proc_refund_strict",
                task_type="refund",
                steps=["verify_policy_root_only", "check_receipt", "verify_gate", "stage_refund", "execute_refund"],
                uses=15,
                successes=14,
                failures=1,
                seeded=True,
            ),
            "proc_notify_customer": Procedure(
                id="proc_notify_customer",
                task_type="notify",
                steps=["draft_template", "verify_gate", "send_email"],
                uses=18,
                successes=17,
                failures=1,
                seeded=True,
            ),
        }

    def get_best_procedure(self, task_type: str) -> Optional[Procedure]:
        matching = [p for p in self._procedures.values() if p.task_type == task_type]
        if not matching:
            return None
        return max(matching, key=lambda p: p.rank_score)

    def record_outcome(self, procedure_id: str, success: bool):
        proc = self._procedures.get(procedure_id)
        if proc:
            proc.uses += 1
            if success:
                proc.successes += 1
            else:
                proc.failures += 1

    def distill_new_procedure(self, task_type: str, steps: List[str], procedure_id: Optional[str] = None) -> Procedure:
        pid = procedure_id or f"proc_{task_type}_{len(self._procedures) + 1}"
        proc = Procedure(
            id=pid,
            task_type=task_type,
            steps=steps,
            uses=1,
            successes=1,
            failures=0,
            seeded=False,
        )
        self._procedures[pid] = proc
        return proc

    def list_procedures(self) -> List[Procedure]:
        return sorted(self._procedures.values(), key=lambda p: p.rank_score, reverse=True)


procedure_registry = ProcedureRegistry()
