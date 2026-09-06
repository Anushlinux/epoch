"""Separate verified-stage limits with one externally enforced repair ceiling."""

import time
from contextlib import contextmanager

from epoch_backend.operation_budget import BudgetExceeded, OperationBudget


class RepairBudget(OperationBudget):
    def __init__(self, max_turns, timeout_seconds, cancelled, on_turn, on_overall):
        super().__init__(max_turns, timeout_seconds, cancelled, on_turn)
        self.overall_deadline = time.monotonic() + 3 * timeout_seconds
        self.overall_max = 3 * max_turns
        self.overall_used = 0
        self.on_overall = on_overall
        self.paused_seconds = 0.0
        self.stage_seconds = timeout_seconds

    def overall_check(self):
        if self.cancelled.is_set():
            raise BudgetExceeded("cancelled", "Repair operation was cancelled.")
        if time.monotonic() >= self.overall_deadline:
            raise BudgetExceeded("repair_time_limit", "Overall repair wall-clock limit reached.")

    def reserve(self, actor):
        self.overall_check()
        if self.overall_used >= self.overall_max:
            raise BudgetExceeded("repair_turn_limit", "Overall repair model-request limit reached.")
        self.overall_used += 1
        self.on_overall(
            {
                "used": self.overall_used,
                "maximum": self.overall_max,
                "actor": actor,
                "paused_primary_seconds": round(self.paused_seconds, 3),
            }
        )

    def check(self):
        super().check()
        self.overall_check()

    def remaining_seconds(self):
        seconds = min(super().remaining_seconds(), int(self.overall_deadline - time.monotonic()))
        if seconds < 1:
            raise BudgetExceeded("repair_time_limit", "No overall repair time remains.")
        return seconds

    def consume(self, actor):
        self.check()
        if self.used >= self.max_turns:
            raise BudgetExceeded("turn_limit", "Primary agent request limit reached.")
        self.reserve(actor)
        super().consume(actor)

    @contextmanager
    def verification_stage(self, on_turn):
        self.check()
        started = time.monotonic()
        seconds = min(600, int(self.overall_deadline - started))
        if seconds < 1:
            raise BudgetExceeded("repair_time_limit", "No verification time remains.")

        def record(actor, used):
            self.reserve("verification_executor")
            on_turn(actor, used)

        try:
            yield OperationBudget(
                self.max_turns, min(seconds, self.stage_seconds), self.cancelled, record
            )
        finally:
            elapsed = time.monotonic() - started
            self.deadline += elapsed
            self.paused_seconds += elapsed
            self.overall_check()
